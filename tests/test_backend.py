import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from backend import Client, Manager, UserError, atomic_json, trusted_url, unpack


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, contents in files.items():
            z.writestr(name, contents)
    return out.getvalue()


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wow = self.root / '_retail_'
        self.wow.mkdir()
        (self.wow / 'Wow.exe').touch()
        self.manager = Manager(self.root / 'settings')
        atomic_json(self.manager.settings_file, {'path': str(self.wow), 'flavor': 517, 'key': 'test'})
        self.addons = self.manager.root()
        self.data = archive({'Example/Example.toc': '## Interface: 120000', 'Example/core.lua': 'new'})
        self.file = {'id': 20, 'displayName': '2.0', 'downloadUrl': 'https://edge.forgecdn.net/example.zip',
                     'fileLength': len(self.data), 'hashes': [{'algo': 1, 'value': hashlib.sha1(self.data).hexdigest()}], 'dependencies': []}
        self.client = unittest.mock.Mock()
        self.client.api.return_value = {'id': 10, 'name': 'Example', 'gameId': 1}
        self.client.latest.return_value = self.file
        self.client.request.return_value = self.data
        patcher = patch.object(self.manager, 'client', return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_install_and_update_removes_obsolete_files(self):
        self.manager.install(10)
        (self.addons / 'Example' / 'obsolete.lua').touch()
        self.file['id'] = 21
        result = self.manager.install(10)
        self.assertFalse((self.addons / 'Example' / 'obsolete.lua').exists())
        self.assertEqual(result['addons'][0]['fileId'], 21)

    def test_unmanaged_folder_is_preserved(self):
        (self.addons / 'Example').mkdir()
        (self.addons / 'Example' / 'personal.lua').write_text('mine')
        with self.assertRaisesRegex(UserError, 'already exists'):
            self.manager.install(10)
        self.assertEqual((self.addons / 'Example' / 'personal.lua').read_text(), 'mine')

    def test_bad_checksum_changes_nothing(self):
        self.file['hashes'][0]['value'] = 'bad'
        with self.assertRaisesRegex(UserError, 'checksum'):
            self.manager.install(10)
        self.assertFalse((self.addons / 'Example').exists())

    def test_rollback_on_registry_failure(self):
        self.manager.install(10)
        (self.addons / 'Example' / 'core.lua').write_text('old')
        before = (self.addons / '.cursedeck.json').read_text()
        with patch('backend.atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.manager.install(10)
        self.assertEqual((self.addons / 'Example' / 'core.lua').read_text(), 'old')
        self.assertEqual((self.addons / '.cursedeck.json').read_text(), before)

    def test_traversal_and_symlink_rejected(self):
        for name in ('../escape', '/tmp/escape', 'Example/../../escape', 'Example\\evil', '.hidden/a.toc'):
            with self.subTest(name=name), self.assertRaises(UserError):
                unpack(archive({name: 'bad'}), self.root / 'stage')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            info = zipfile.ZipInfo('Example/link')
            info.external_attr = 0o120777 << 16
            z.writestr(info, '/tmp')
        with self.assertRaises(UserError):
            unpack(out.getvalue(), self.root / 'stage')

    def test_symlinked_addons_rejected(self):
        self.addons.rmdir()
        self.addons.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(UserError):
            self.manager.root()

    def test_no_key_exposed(self):
        self.assertNotIn('key', self.manager.status())
        self.assertEqual(self.manager.settings_file.stat().st_mode & 0o777, 0o600)

    def test_trusted_hosts(self):
        self.assertTrue(trusted_url('https://edge.forgecdn.net/a'))
        for url in ('http://edge.forgecdn.net/a', 'https://evil.net/a', 'https://forgecdn.net.evil.net/a', 'file:///tmp/a'):
            self.assertFalse(trusted_url(url))

    def test_required_dependency_is_installed(self):
        dep_data = archive({'Library/Library.toc': '## Title: Library'})
        dep_file = dict(self.file, id=30, dependencies=[], fileLength=len(dep_data),
                        hashes=[{'algo': 1, 'value': hashlib.sha1(dep_data).hexdigest()}], downloadUrl='https://edge.forgecdn.net/lib.zip')
        self.file['dependencies'] = [{'relationType': 3, 'modId': 11}]
        self.client.latest.side_effect = lambda project, flavor: self.file if project == 10 else dep_file
        self.client.request.side_effect = lambda url, limit: dep_data if 'lib.zip' in url else self.data
        self.manager.install(10)
        self.assertTrue((self.addons / 'Library' / 'Library.toc').exists())
        self.assertEqual(len(json.loads((self.addons / '.cursedeck.json').read_text())['addons']), 2)

    def test_flavor_mismatch_rejected(self):
        atomic_json(self.addons / '.cursedeck.json', {'flavor': 999, 'addons': {}})
        with self.assertRaises(UserError):
            self.manager.install(10)


    def test_latest_filters_edition_and_prerelease(self):
        client = Client('test')
        def release(identifier, flavor=517, kind=1):
            return {'id': identifier, 'fileDate': '2026-11-01', 'isAvailable': True,
                    'releaseType': kind, 'sortableGameVersions': [{'gameVersionTypeId': flavor}]}
        with patch.object(client, 'api', return_value=[release(1), release(2), release(3, 999), release(4, kind=2)]):
            self.assertEqual(client.latest(10, 517)['id'], 2)
        with patch.object(client, 'api', return_value=[release(3, 999)]):
            with self.assertRaises(UserError):
                client.latest(10, 517)

    def test_blocked_distribution_never_downloads(self):
        self.client.api.return_value['allowModDistribution'] = False
        with self.assertRaises(UserError):
            self.manager.install(10)
        self.client.request.assert_not_called()

    def test_no_silent_downgrade(self):
        self.manager.install(10)
        self.client.request.reset_mock()
        self.file['id'] = 19
        self.manager.install(10)
        self.client.request.assert_not_called()
        self.assertEqual(self.manager.installed()['addons'][0]['fileId'], 20)


if __name__ == '__main__':
    unittest.main()
