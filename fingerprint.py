"""CurseForge folder fingerprints for matching installed WoW addons.

CurseForge identifies an addon folder by a MurmurHash2 of the files its .toc
loads. This follows the published behaviour of the CurseForge client as
reimplemented by WowUp (wowup-electron/app/curse-folder-scanner.ts):

* Start from the folder's own .toc files (``Folder.toc`` or a flavor variant
  such as ``Folder_Mainline.toc``) and a top-level ``Bindings.xml``.
* Follow .lua and .xml files listed in a .toc, and ``<Script>``/``<Include>``
  files referenced by an .xml, resolving names case-insensitively like Windows.
* Hash each file with whitespace removed, sort the hashes numerically, join
  them as decimal text, and hash that text.
"""
import os
import re
import sys
from pathlib import Path

TOC_NAME = re.compile(r'^([^/]+)/\1([-|_](mainline|bcc|tbc|classic|vanilla|wrath|wotlkc|cata|mists|forever|camelot))?\.toc$',
                      re.IGNORECASE)
BINDINGS = re.compile(r'^[^/]+/bindings\.xml$', re.IGNORECASE)
TOC_COMMENT = re.compile(r'\s*#.*$', re.MULTILINE)
TOC_INCLUDE = re.compile(r'^\s*((?:(?<!\.\.).)+\.(?:xml|lua))\s*$', re.IGNORECASE)
XML_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
XML_INCLUDE = re.compile(r'<(?:Include|Script)\s+file=["\']((?:(?<!\.\.).)+)["\']\s*/>', re.IGNORECASE | re.DOTALL)
INVALID_INCLUDE = set('|\0') | {chr(c) for c in range(1, 32)}
# JavaScript's trim() also removes a byte-order mark; Python's strip() does not.
TRIM = ' \t\n\r\v\f﻿   '
MAX_FILE = 64 * 1024 * 1024
MASK = 0xFFFFFFFF


def murmur2(data, seed=1):
    """32-bit MurmurHash2 of ``data`` after removing tab, newline, CR and space bytes."""
    data = data.translate(None, b'\t\n\r ')
    m = 0x5BD1E995
    length = len(data)
    h = (seed ^ length) & MASK
    body = length & ~3
    words = memoryview(data[:body]).cast('I') if sys.byteorder == 'little' else \
        [int.from_bytes(data[i:i + 4], 'little') for i in range(0, body, 4)]
    for k in words:
        k = (k * m) & MASK
        k ^= k >> 24
        h = ((h * m) & MASK) ^ ((k * m) & MASK)
    tail = data[body:]
    if tail:
        for index in range(len(tail) - 1, -1, -1):
            h ^= tail[index] << (8 * index)
        h = (h * m) & MASK
    h ^= h >> 13
    h = (h * m) & MASK
    return h ^ (h >> 15)


def _lines(text, pattern):
    """Match one include per line, as the CurseForge client does."""
    found = []
    for line in text.split('\n'):
        match = pattern.search(line.strip(TRIM))
        if match:
            found.append(match.group(1).strip(TRIM))
    return found


def folder_fingerprint(folder):
    """Return (fingerprint, file count) for an addon folder, or None if it has no matching .toc."""
    folder = Path(folder)
    parent = str(folder.parent) + os.sep
    files = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                files[full.lower()] = full
    matching = []
    roots = []
    for full in files.values():
        relative = full[len(parent):].replace(os.sep, '/')
        if TOC_NAME.match(relative):
            roots.append(full)
        elif BINDINGS.match(relative):
            matching.append(full)
    if not roots:
        return None

    def visit(path, depth=0):
        real = files.get(os.path.normpath(path).lower())
        if real is None or real in matching or depth > 64:
            return
        matching.append(real)
        extension = os.path.splitext(real)[1]
        if extension not in ('.toc', '.xml'):
            return
        try:
            text = Path(real).read_bytes()[:MAX_FILE].decode('utf-8', errors='replace')
        except OSError:
            return
        if extension == '.toc':
            includes = _lines(TOC_COMMENT.sub('', text), TOC_INCLUDE)
        else:
            includes = _lines(XML_COMMENT.sub('', text), XML_INCLUDE)
        for include in includes:
            if any(c in INVALID_INCLUDE for c in include):
                break
            visit(os.path.join(os.path.dirname(real), include.replace('\\', '/')), depth + 1)

    for root in roots:
        visit(root)
    hashes = []
    for path in matching:
        try:
            with open(path, 'rb') as stream:
                hashes.append(murmur2(stream.read(MAX_FILE)))
        except OSError:
            continue
    return murmur2(''.join(str(h) for h in sorted(hashes)).encode('ascii')), len(matching)
