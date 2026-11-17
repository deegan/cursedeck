import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from backend import Manager, atomic_json
from fingerprint import folder_fingerprint, murmur2


def reference_murmur2(data, seed=1):
    """Byte-at-a-time MurmurHash2, written independently of the optimised version."""
    data = bytes(b for b in data if b not in (9, 10, 13, 32))
    m, h = 0x5BD1E995, (seed ^ len(data)) & 0xFFFFFFFF
    i = 0
    while len(data) - i >= 4:
        k = data[i] | data[i + 1] << 8 | data[i + 2] << 16 | data[i + 3] << 24
        k = (k * m) & 0xFFFFFFFF
        k ^= k >> 24
        k = (k * m) & 0xFFFFFFFF
        h = ((h * m) & 0xFFFFFFFF) ^ k
        i += 4
    rest = len(data) - i
    if rest == 3:
        h ^= data[i + 2] << 16
    if rest >= 2:
        h ^= data[i + 1] << 8
    if rest >= 1:
        h ^= data[i]
        h = (h * m) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    return h ^ (h >> 15)


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())


ADDON = {
    'MyAddon/MyAddon.toc': '﻿## Title: Mine\n## Version: 1\n# a comment\nlibs\\Embeds.xml\nCore.lua # trailing\n..\\Escape.lua\n',
    'MyAddon/MyAddon_Forever.toc': '## Title: Mine\ncore.lua\n',
    'MyAddon/Libs/embeds.xml': '<Ui><!-- <Script file="Commented.lua"/> -->\n<Script file="Lib.lua"/>\n<Include file="Sub\\Sub.xml"/></Ui>',
    'MyAddon/Libs/Lib.lua': 'return 1',
    'MyAddon/Libs/Commented.lua': 'never loaded',
    'MyAddon/Libs/Sub/Sub.xml': '<Ui/>',
    'MyAddon/Core.lua': 'print("core")\n',
    'MyAddon/Bindings.xml': '<Bindings/>',
    'MyAddon/README.md': 'docs',
    'MyAddon/Other.toc': 'Unrelated.lua',
    'MyAddon/Unrelated.lua': 'x',
    'Escape.lua': 'outside',
}


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_murmur2_matches_reference(self):
        for data in (b'', b'a', b'ab', b'abc', b'abcd', b'hello world\r\n\tx', bytes(range(256)) * 3):
            self.assertEqual(murmur2(data), reference_murmur2(data), data[:12])

    def test_follows_toc_and_xml_includes_case_insensitively(self):
        write(self.root, ADDON)
        fingerprint, count = folder_fingerprint(self.root / 'MyAddon')
        # Two tocs, embeds.xml, Lib.lua, Sub.xml, Core.lua, Bindings.xml.
        self.assertEqual(count, 7)
        expected = sorted(reference_murmur2((self.root / 'MyAddon' / name).read_bytes()) for name in (
            'MyAddon.toc', 'MyAddon_Forever.toc', 'Libs/embeds.xml', 'Libs/Lib.lua', 'Libs/Sub/Sub.xml', 'Core.lua', 'Bindings.xml'))
        self.assertEqual(fingerprint, reference_murmur2(''.join(map(str, expected)).encode()))

    def test_whitespace_and_unloaded_files_do_not_change_fingerprint(self):
        write(self.root, ADDON)
        before = folder_fingerprint(self.root / 'MyAddon')
        write(self.root, {'MyAddon/README.md': 'changed', 'MyAddon/Libs/Commented.lua': 'changed',
                          'MyAddon/Core.lua': 'print("core")\r\n\r\n  '})
        self.assertEqual(folder_fingerprint(self.root / 'MyAddon'), before)
        write(self.root, {'MyAddon/Core.lua': 'print("edited")'})
        self.assertNotEqual(folder_fingerprint(self.root / 'MyAddon')[0], before[0])

    def test_folder_without_own_toc_has_no_fingerprint(self):
        write(self.root, {'Loose/Other.toc': 'a.lua', 'Loose/a.lua': ''})
        self.assertIsNone(folder_fingerprint(self.root / 'Loose'))


class MatchExistingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        wow = root / '_forever_'
        (wow / 'Interface' / 'AddOns').mkdir(parents=True)
        (wow / 'Wow.exe').touch()
        self.addons = wow / 'Interface' / 'AddOns'
        write(self.addons, {
            'Pack/Pack.toc': 'a.lua', 'Pack/a.lua': '1',
            'Pack_Extra/Pack_Extra.toc': 'b.lua', 'Pack_Extra/b.lua': '2',
            'Edited/Edited.toc': 'c.lua', 'Edited/c.lua': 'mine',
            'Unknown/Unknown.toc': 'd.lua', 'Unknown/d.lua': '4',
        })
        self.prints = {name: folder_fingerprint(self.addons / name)[0] for name in ('Pack', 'Pack_Extra', 'Edited', 'Unknown')}
        self.manager = Manager(root / 'settings')
        atomic_json(self.manager.settings_file, {'path': str(wow), 'flavor': 88568, 'key': 'k'})
        self.client = Mock()
        self.sent = []

        def post(route, body):
            if route == 'fingerprints/1':
                self.assertLessEqual(set(body['fingerprints']), set(self.prints.values()))
                self.sent.append(sorted(body['fingerprints']))
                return {'exactMatches': [
                    {'id': 10, 'file': {'id': 500, 'displayName': '1.0', 'modules': [
                        {'name': 'Pack', 'fingerprint': self.prints['Pack']},
                        {'name': 'pack_extra', 'fingerprint': self.prints['Pack_Extra']},
                        {'name': 'Pack_Optional', 'fingerprint': 1}]}},
                    {'id': 20, 'file': {'id': 600, 'displayName': '2.0', 'modules': [
                        {'name': 'Edited', 'fingerprint': 12345}]}},
                    {'id': 30, 'file': {'id': 700, 'displayName': 'x', 'modules': [{'name': '../Evil', 'fingerprint': 1}]}},
                ]}
            if route == 'mods':
                return [{'id': 10, 'name': 'Pack Addon'}]
            raise AssertionError(route)
        self.client.post.side_effect = post
        self.client.latest.return_value = {'id': 501, 'displayName': '1.1'}
        self.manager.client = lambda: self.client

    def test_check_adopts_recognised_addons_without_touching_files(self):
        library = self.manager.installed(check=True)
        self.assertEqual(library['matching'], {'matched': 1, 'unmatched': ['Unknown'], 'modified': ['Edited']})
        [pack] = library['addons']
        self.assertEqual((pack['id'], pack['name'], pack['fileId'], pack['folders'], pack['update'], pack['adopted']),
                         (10, 'Pack Addon', 500, ['Pack', 'Pack_Extra'], '1.1', True))
        self.assertEqual(sorted(library['unmanaged']), ['Edited', 'Unknown'])
        self.assertEqual((self.addons / 'Pack' / 'a.lua').read_text(), '1')
        registry = json.loads((self.addons / '.cursedeck.json').read_text())
        self.assertEqual(list(registry['addons']), ['10'])

    def test_second_check_reuses_cache_and_skips_owned_folders(self):
        self.manager.installed(check=True)
        import fingerprint
        original = fingerprint.folder_fingerprint
        fingerprint.folder_fingerprint = Mock(side_effect=AssertionError('cache miss'))
        try:
            library = self.manager.installed(check=True)
        finally:
            fingerprint.folder_fingerprint = original
        self.assertEqual(library['matching']['matched'], 0)
        self.assertEqual(self.sent[0], sorted(self.prints.values()))
        self.assertEqual(self.sent[1], sorted([self.prints['Edited'], self.prints['Unknown']]))
        self.assertEqual(len(library['addons']), 1)

    def test_update_blocked_by_author_is_flagged(self):
        original = self.client.post.side_effect
        self.client.post.side_effect = lambda route, body: (
            [{'id': 10, 'name': 'Pack Addon', 'allowModDistribution': False}] if route == 'mods' else original(route, body))
        [pack] = self.manager.installed(check=True)['addons']
        self.assertEqual((pack['update'], pack['blocked']), ('1.1', True))

    def test_plain_listing_never_contacts_curseforge(self):
        library = self.manager.installed(check=False)
        self.client.post.assert_not_called()
        self.assertNotIn('matching', library)
