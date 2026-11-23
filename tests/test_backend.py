import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import urllib.request

from backend import Client, Manager, SafeRedirect, UserError, atomic_json, download_page, logo_url, read_key_file, trusted_url, unpack


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
        self.manager = Manager(self.root / 'settings', downloads=self.root / 'Downloads')
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

    def test_folder_bundled_by_another_managed_project_is_taken_over(self):
        for folder in ('Example', 'Other'):
            (self.addons / folder).mkdir()
            (self.addons / folder / f'{folder}.toc').write_text('old')
        atomic_json(self.addons / '.cursedeck.json', {'flavor': 517, 'addons': {
            '99': {'id': 99, 'name': 'Bundle', 'fileId': 1, 'version': '1', 'folders': ['Example', 'Other']},
            '98': {'id': 98, 'name': 'Only', 'fileId': 1, 'version': '1', 'folders': ['Gone']}}})
        self.manager.install(10)
        registry = json.loads((self.addons / '.cursedeck.json').read_text())['addons']
        self.assertEqual(registry['10']['folders'], ['Example'])
        self.assertEqual(registry['99']['folders'], ['Other'])
        self.assertEqual((self.addons / 'Example' / 'core.lua').read_text(), 'new')
        self.assertEqual((self.addons / 'Other' / 'Other.toc').read_text(), 'old')

    def test_project_left_without_folders_is_dropped(self):
        (self.addons / 'Example').mkdir()
        atomic_json(self.addons / '.cursedeck.json', {'flavor': 517, 'addons': {
            '99': {'id': 99, 'name': 'Trace', 'fileId': 1, 'version': '1', 'folders': ['Example']}}})
        self.manager.install(10)
        self.assertEqual(list(json.loads((self.addons / '.cursedeck.json').read_text())['addons']), ['10'])

    repository = 'https://github.com/Author/WoWAddons'
    asset = repository + '/releases/download/v2/Example-2.0.zip'
    website = 'https://www.curseforge.com/wow/addons/example'

    def block_downloads(self, *ids, source=''):
        names = {10: 'Example', 11: 'Library'}
        def project(identifier):
            return {'id': identifier, 'name': names[identifier], 'gameId': 1,
                    'allowModDistribution': identifier not in ids,
                    'links': {'websiteUrl': self.website, 'sourceUrl': source}}

        def api(route):
            self.assertRegex(route, r'^mods/\d+$')  # Metadata only, never a restricted download URL.
            return project(int(route.split('/')[1]))

        self.client.api.side_effect = api
        self.client.post.side_effect = lambda route, payload: [project(i) for i in payload['modIds']]
        self.file['fileName'] = 'Example-2.0.zip'

    def downloaded(self, data):
        path = self.root / 'Downloads' / 'Example-2.0.zip'
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def test_blocked_addon_needs_a_downloaded_file(self):
        self.block_downloads(10)
        with self.assertRaisesRegex(UserError, 'ZIP'):
            self.manager.install(10)
        self.client.request.assert_not_called()

    def test_verified_download_installs_without_network_download(self):
        self.block_downloads(10, source=self.repository)
        with patch('addon_releases.find_release_asset') as find_asset:
            result = self.manager.install(10, self.downloaded(self.data))
            find_asset.assert_not_called()
        self.client.request.assert_not_called()
        self.assertEqual(result['addons'][0]['fileId'], 20)
        self.assertEqual((self.addons / 'Example' / 'core.lua').read_text(), 'new')

    def test_verified_zip_in_downloads_updates_without_github(self):
        self.manager.install(10)
        self.client.request.reset_mock()
        self.block_downloads(10, source=self.repository)
        self.file['id'] = 21
        zip_path = Path(self.downloaded(self.data))
        with patch('addon_releases.find_release_asset', side_effect=UserError('GitHub unavailable')) as find_asset, \
                patch('addon_releases.download_release_asset') as download:
            checked = self.manager.installed(check=True)['addons'][0]
            self.assertTrue(checked['download']['localRelease'])
            self.assertEqual(checked['fileId'], 20)
            self.assertIsNone(checked['error'])
            self.assertEqual(self.manager.install(10)['addons'][0]['fileId'], 21)
            find_asset.assert_not_called()
            download.assert_not_called()
        self.assertEqual(zip_path.read_bytes(), self.data)
        self.client.request.assert_not_called()

    def test_cached_zip_is_rechecked_before_install(self):
        self.manager.install(10)
        self.client.request.reset_mock()
        self.block_downloads(10, source=self.repository)
        with patch('addon_releases.find_release_asset') as find_asset, \
                patch('addon_releases.download_release_asset', return_value=self.data) as download:
            self.file['id'] = 21
            zip_path = Path(self.downloaded(self.data))
            self.assertTrue(self.manager.installed(check=True)['addons'][0]['download']['localRelease'])
            zip_path.unlink()
            find_asset.return_value = ''
            with self.assertRaises(UserError):
                self.manager.install(10)
            self.assertEqual(self.manager.installed()['addons'][0]['fileId'], 20)
            download.assert_not_called()

            zip_path.write_bytes(self.data)
            self.assertTrue(self.manager.installed(check=True)['addons'][0]['download']['localRelease'])
            zip_path.write_bytes(b'x' * len(self.data))
            find_asset.return_value = self.asset
            self.assertEqual(self.manager.install(10)['addons'][0]['fileId'], 21)
            download.assert_called_once_with(self.asset, len(self.data))
        self.client.request.assert_not_called()

    def test_restricted_update_tracks_release_and_uses_current_author_asset(self):
        self.manager.install(10)
        self.client.request.reset_mock()
        self.block_downloads(10, source=self.repository)
        self.file.update(id=21, displayName='2.1', fileName='Example-2.1.zip', downloadUrl=None)
        asset = self.repository + '/releases/download/v2.1/Example-2.1.zip'
        with patch('addon_releases.find_release_asset', return_value=asset) as find_asset, \
                patch('addon_releases.download_release_asset', return_value=self.data) as download:
            checked = self.manager.installed(check=True)['addons'][0]
            self.assertTrue(checked['blocked'])
            self.assertTrue(checked['download']['authorRelease'])
            self.assertEqual(checked['update'], '2.1')
            self.assertEqual(checked['fileId'], 20)
            find_asset.assert_called_once_with(self.repository, self.file)
            download.assert_not_called()

            self.file = dict(self.file, id=22, displayName='2.2', fileName='Example-2.2.zip')
            self.client.latest.return_value = self.file
            find_asset.reset_mock()
            find_asset.return_value = self.repository + '/releases/download/v2.2/Example-2.2.zip'
            installed = self.manager.install(10)['addons'][0]
            find_asset.assert_called_once_with(self.repository, self.file)
            download.assert_called_once_with(find_asset.return_value, self.file['fileLength'])
            self.assertEqual((installed['fileId'], installed['version']), (22, '2.2'))
            find_asset.reset_mock()
            self.assertIsNone(self.manager.installed(check=True)['addons'][0]['update'])
            find_asset.assert_not_called()
        self.client.request.assert_not_called()

    def test_install_observes_author_opt_out_after_update_check(self):
        self.manager.install(10)
        self.block_downloads()
        self.file['id'] = 21
        checked = self.manager.installed(check=True)['addons'][0]
        self.assertTrue(checked['update'])
        self.assertFalse(checked['blocked'])
        self.client.request.reset_mock()
        self.block_downloads(10)
        with self.assertRaises(UserError):
            self.manager.install(10)
        self.client.request.assert_not_called()
        self.assertEqual(self.manager.installed()['addons'][0]['fileId'], 20)

    def test_lookup_failure_keeps_tracked_update_and_download_page(self):
        self.manager.install(10)
        self.block_downloads(10, source=self.repository)
        self.file.update(id=21, displayName='2.1', fileName='Example-2.1.zip')
        for outcome in ('', UserError('GitHub is unavailable')):
            with self.subTest(outcome=outcome), patch('addon_releases.find_release_asset', side_effect=[outcome]):
                item = self.manager.installed(check=True)['addons'][0]
                self.assertTrue(item['blocked'])
                self.assertEqual(item['update'], '2.1')
                self.assertFalse(item['download'].get('authorRelease'))
                self.assertEqual(item['download']['page'], self.website + '/download/21')
                self.assertEqual(item['download']['fileName'], 'Example-2.1.zip')
                if isinstance(outcome, UserError):
                    self.assertIn(str(outcome), item['error'])

    def test_author_asset_must_match_size_and_every_supported_checksum(self):
        self.manager.install(10)
        self.client.request.reset_mock()
        self.block_downloads(10, source=self.repository)
        self.file['id'] = 21
        marker = self.addons / 'Example' / 'old.lua'
        marker.write_text('old')
        registry = self.addons / '.cursedeck.json'
        before = registry.read_bytes()
        with patch('addon_releases.find_release_asset', return_value=self.asset), \
                patch('addon_releases.download_release_asset', return_value=self.data):
            for metadata in ({'fileLength': len(self.data) + 1}, {'hashes': [
                    self.file['hashes'][0], {'algo': 2, 'value': '0' * 32}]}):
                with self.subTest(metadata=metadata), patch.dict(self.file, metadata), self.assertRaises(UserError):
                    self.manager.install(10)
                self.assertEqual(registry.read_bytes(), before)
                self.assertEqual(marker.read_text(), 'old')
        self.client.request.assert_not_called()

    def test_missing_restricted_dependency_uses_its_own_author_release(self):
        self.block_downloads(11, source=self.repository)
        self.file['dependencies'] = [{'modId': 11, 'relationType': 3}]
        library = archive({'Library/Library.toc': '## Title: Library'})
        dependency = dict(self.file, id=30, fileName='Library.zip', downloadUrl=None, dependencies=[],
                          fileLength=len(library), hashes=[{'algo': 1, 'value': hashlib.sha1(library).hexdigest()}])
        self.client.latest.side_effect = lambda project, flavor: dependency if project == 11 else self.file
        asset = self.repository + '/releases/download/v2/Library.zip'
        with patch('addon_releases.find_release_asset', return_value=asset) as find_asset, \
                patch('addon_releases.download_release_asset', return_value=library) as download:
            result = self.manager.install(10)
            find_asset.assert_called_once_with(self.repository, dependency)
            download.assert_called_once_with(asset, len(library))
        self.assertEqual(self.client.request.call_count, 1)
        self.assertEqual(self.client.request.call_args.args[0], self.file['downloadUrl'])
        self.assertEqual({a['id']: a['fileId'] for a in result['addons']}, {10: 20, 11: 30})
        self.assertTrue((self.addons / 'Library' / 'Library.toc').is_file())

    def test_wrong_download_is_refused_and_changes_nothing(self):
        self.block_downloads(10)
        other = archive({'Example/Example.toc': '## Interface: 120000', 'Example/core.lua': 'tampered'})
        for data in (other, self.data[:-1] + b'x'):
            with self.subTest(size=len(data)), self.assertRaisesRegex(UserError, 'not Example-2.0.zip'):
                self.manager.install(10, self.downloaded(data))
        self.assertFalse((self.addons / 'Example').exists())
        for bad in ('relative.zip', str(self.root / 'missing.zip'), str(self.root)):
            with self.subTest(path=bad), self.assertRaises(UserError):
                self.manager.install(10, bad)

    def test_blocked_dependency_must_already_be_installed(self):
        self.block_downloads(11)
        self.file['dependencies'] = [{'modId': 11, 'relationType': 3}]
        with self.assertRaisesRegex(UserError, 'Library is required'):
            self.manager.install(10)
        atomic_json(self.addons / '.cursedeck.json', {'flavor': 517, 'addons': {
            '11': {'id': 11, 'name': 'Library', 'fileId': 1, 'version': '1', 'folders': ['Library']}}})
        self.manager.install(10)
        self.assertEqual(self.client.request.call_count, 1)  # Only Example was downloaded.

    def test_logo_only_from_curseforge_cdn(self):
        good = 'https://media.forgecdn.net/avatars/thumbnails/1/2/64/64/a.png'
        self.assertEqual(logo_url({'logo': {'thumbnailUrl': good}}), good)
        for bad in ('http://media.forgecdn.net/a.png', 'https://evil.net/a.png', 'https://forgecdn.net.evil.net/a.png',
                    'https://user@media.forgecdn.net/a.png', 'javascript:alert(1)', None, 5):
            self.assertEqual(logo_url({'logo': {'thumbnailUrl': bad}}), '', bad)
        self.assertEqual(logo_url({'logo': None}), '')
        self.assertEqual(logo_url({}), '')

    def test_download_page_only_links_to_curseforge(self):
        self.assertEqual(download_page('https://www.curseforge.com/wow/addons/baganator', 9659116),
                         'https://www.curseforge.com/wow/addons/baganator/download/9659116')
        for site in ('http://www.curseforge.com/wow/addons/x', 'https://evil.com/wow/addons/x',
                     'https://www.curseforge.com/wow/addons/x?next=evil', 'https://www.curseforge.com/../x', None):
            self.assertEqual(download_page(site, 1), '')

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

    def test_hidden_files_inside_addon_are_extracted(self):
        folders = unpack(archive({'Example/Example.toc': '## Interface: 1', 'Example/.gitignore': '*.bak',
                                  'Example/.github/ci.yml': 'x'}), self.root / 'stage')
        self.assertEqual(folders, ['Example'])
        self.assertEqual((self.root / 'stage' / 'Example' / '.gitignore').read_text(), '*.bak')
        for name in ('.cursedeck-x/Example.toc', '.git/config'):
            with self.subTest(name=name), self.assertRaises(UserError):
                unpack(archive({name: 'bad', 'Example/Example.toc': ''}), self.root / 'stage2')

    def test_symlinked_addons_rejected(self):
        self.addons.rmdir()
        self.addons.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(UserError):
            self.manager.root()

    def test_no_key_exposed(self):
        self.assertNotIn('key', self.manager.status())
        self.assertEqual(self.manager.settings_file.stat().st_mode & 0o777, 0o600)

    def sent_headers(self, url):
        opener = unittest.mock.MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{}'
        with patch('urllib.request.build_opener', return_value=opener):
            Client('secret-key').request(url, 100)
        return {k.lower(): v for k, v in opener.open.call_args.args[0].header_items()}

    def test_key_sent_only_to_api_host(self):
        self.assertEqual(self.sent_headers('https://api.curseforge.com/v1/games')['x-api-key'], 'secret-key')
        self.assertNotIn('x-api-key', self.sent_headers('https://edge.forgecdn.net/example.zip'))

    def test_key_dropped_on_redirect_to_cdn(self):
        request = urllib.request.Request('https://api.curseforge.com/v1/x', headers={'x-api-key': 'secret-key'})
        handler = SafeRedirect()
        cdn = handler.redirect_request(request, None, 302, 'Found', {}, 'https://edge.forgecdn.net/example.zip')
        self.assertNotIn('x-api-key', [k.lower() for k, _ in cdn.header_items()])
        api = handler.redirect_request(request, None, 302, 'Found', {}, 'https://api.curseforge.com/v1/y')
        self.assertIn('x-api-key', [k.lower() for k, _ in api.header_items()])

    def test_key_file(self):
        good = self.root / 'key.txt'
        good.write_text('\ufeff$2a$10$abcdefghijklmnopqrstuvwxyz0123456789\r\n\n', encoding='utf-8')
        self.assertEqual(read_key_file(str(good)), '$2a$10$abcdefghijklmnopqrstuvwxyz0123456789')
        for name, contents in (('short.txt', b'abc'), ('two.txt', b'key: ' + b'a' * 40), ('bin.txt', b'\xff\xfe' * 30),
                               ('big.txt', b'a' * 5000)):
            (self.root / name).write_bytes(contents)
            with self.assertRaises(UserError):
                read_key_file(str(self.root / name))
        for path in (str(self.root), str(self.root / 'missing.txt'), 'key.txt'):
            with self.assertRaises(UserError):
                read_key_file(path)

    def test_tls_context_uses_certifi_then_system_bundle(self):
        import ssl, sys, types, backend
        fake = types.SimpleNamespace(where=lambda: '/bundle/cacert.pem')
        with patch.dict(sys.modules, {'certifi': fake}), patch('ssl.create_default_context') as create:
            backend.tls_context()
        create.assert_called_once_with(cafile='/bundle/cacert.pem')
        with patch.dict(sys.modules, {'certifi': None}), patch('os.path.isfile', lambda p: p == '/etc/ssl/cert.pem'), \
                patch('ssl.create_default_context') as create:
            backend.tls_context()
        create.assert_called_once_with(cafile='/etc/ssl/cert.pem')

    def test_certificate_failure_is_reported(self):
        import ssl, urllib.error
        opener = unittest.mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError('certificate verify failed'))
        with patch('urllib.request.build_opener', return_value=opener):
            with self.assertRaisesRegex(UserError, 'could not be verified'):
                Client('k').request('https://api.curseforge.com/v1/games', 100)

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


    def test_registry_traversal_rejected_before_read_or_install(self):
        self.manager.install(10)
        registry = self.addons / '.cursedeck.json'
        data = json.loads(registry.read_text())
        data['addons']['10']['folders'] = ['../../outside']
        atomic_json(registry, data)
        with self.assertRaisesRegex(UserError, 'registry is invalid'):
            self.manager.installed()
        with self.assertRaisesRegex(UserError, 'registry is invalid'):
            self.manager.install(10)

    def test_archive_parent_case_conflict_rejected(self):
        data = archive({'Example/Example.toc': '', 'Example/Lib/a.lua': '', 'Example/lib/b.lua': ''})
        with self.assertRaisesRegex(UserError, 'capitalization'):
            unpack(data, self.root / 'stage')
        self.assertFalse((self.root / 'stage').exists())

    def test_configure_rejects_symlink_before_persisting(self):
        before = self.manager.settings_file.read_bytes()
        self.addons.rmdir()
        self.addons.symlink_to(self.root, target_is_directory=True)
        self.manager.client_factory = lambda key: self.client
        self.client.api.return_value = [{'id': 517}]
        with self.assertRaisesRegex(UserError, 'Symlinked'):
            self.manager.configure(str(self.wow), 517, 'new-key')
        self.assertEqual(self.manager.settings_file.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
