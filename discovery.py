"""Bounded, read-only discovery of WoW installations in Steam libraries."""
from collections import deque
import os
from pathlib import Path
import re
import time

STEAM_PATHS = ('.local/share/Steam', '.steam/steam', '.steam/root',
               '.var/app/com.valvesoftware.Steam/.local/share/Steam',
               '.var/app/com.valvesoftware.Steam/data/Steam')
EDITION_LABELS = {'_retail_': 'Retail', '_classic_': 'Classic',
                  '_classic_era_': 'Classic Era', '_ptr_': 'PTR', '_beta_': 'Beta'}
SKIP = {'windows', 'users', 'programdata', '$recycle.bin', 'system volume information',
        'data', 'cache', 'logs', 'interface', 'wtf', 'screenshots', 'node_modules'}


def library_paths(text):
    # Tokenize quoted VDF strings and comments so commented-out paths are ignored.
    tokens = re.findall(r'//[^\n]*|"((?:\\.|[^"\\])*)"', text)
    def unescape(value):
        return re.sub(r'\\([\\"])', r'\1', value)
    for index in range(len(tokens) - 1):
        if tokens[index].lower() == 'path' or tokens[index].isdigit():
            value = unescape(tokens[index + 1])
            if value.startswith('/'):
                yield Path(value)


def discover_installations(home=None, max_dirs=20000, timeout=8, clock=time.monotonic):
    home = Path(home) if home is not None else Path.home()
    deadline = clock() + timeout
    libraries, seen_libraries = [], set()
    warnings = set()
    count = 0
    limited = False

    def add_library(path):
        try:
            path = path.resolve()
            if path.is_dir() and path not in seen_libraries:
                seen_libraries.add(path)
                libraries.append(path)
        except (OSError, RuntimeError):
            warnings.add('Some Steam library paths could not be read.')

    for relative in STEAM_PATHS:
        add_library(home / relative)
    # A library's own VDF may list other libraries; deduplication bounds cycles.
    index = 0
    while index < len(libraries) and index < 64:
        library = libraries[index]
        index += 1
        for config in (library / 'steamapps/libraryfolders.vdf', library / 'config/libraryfolders.vdf'):
            try:
                if config.is_file():
                    with config.open() as stream:
                        text = stream.read(1024 * 1024 + 1)
                    if len(text) > 1024 * 1024:
                        warnings.add('A Steam library list was too large to scan.')
                        continue
                    for path in library_paths(text):
                        if len(libraries) >= 64:
                            limited = True
                            break
                        add_library(path)
            except OSError:
                warnings.add('Some Steam library paths could not be read.')

    queue = deque()
    for library in libraries:
        queue.append((library / 'steamapps/common', 0, 'Steam library', 7))
        # Scan just the prefix layout, not unrelated Steam shader/download data.
        queue.append((library / 'steamapps/compatdata', 0, 'Proton prefix', 10))
    seen = set()
    found = {}
    while queue:
        if count >= max_dirs or clock() >= deadline:
            limited = True
            break
        path, depth, source, max_depth = queue.popleft()
        try:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            count += 1
            if not resolved.is_dir():
                continue
            with os.scandir(resolved) as directory:
                entries = list(directory)
            names = {entry.name for entry in entries if entry.is_file(follow_symlinks=False)}
            if names & {'Wow.exe', 'WowClassic.exe'}:
                edition = EDITION_LABELS.get(resolved.name, resolved.name)
                found[str(resolved)] = {'path': str(resolved), 'label': f'World of Warcraft · {edition}', 'source': source}
                # Do not scan the large game data or addon tree after finding an edition.
                continue
            if depth >= max_depth:
                continue
            for entry in sorted(entries, key=lambda e: e.name):
                lower = entry.name.lower()
                if lower in SKIP or lower.startswith('.') or lower in {'dosdevices', 'drive_z'}:
                    continue
                # Follow named WoW links, but never generic prefix links into the host filesystem.
                if entry.is_symlink() and lower not in {'world of warcraft', 'wow', *EDITION_LABELS}:
                    continue
                if entry.is_dir():
                    # Within compatdata only enter numeric IDs, then pfx, then drive_c.
                    if source == 'Proton prefix':
                        if depth == 0 and not entry.name.isdigit():
                            continue
                        if depth == 1 and lower != 'pfx':
                            continue
                        if depth == 2 and lower != 'drive_c':
                            continue
                    queue.append((Path(entry.path), depth + 1, source, max_depth))
        except (OSError, RuntimeError):
            warnings.add('Some folders could not be read; other locations were still scanned.')
    if limited:
        warnings.add('The scan reached its limit. You can enter a missing installation path manually.')
    return {'installations': sorted(found.values(), key=lambda item: (item['label'], item['path'])),
            'warnings': sorted(warnings), 'limited': limited}
