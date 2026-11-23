import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from addon_releases import ReleaseRedirect, download_release_asset, find_release_asset, github_repository, local_release_zip
from backend import MAX_DOWNLOAD, UserError, hashes_match, release_hashes


class AddonReleaseTests(unittest.TestCase):
    source = 'https://github.com/Author/Example'
    asset_url = source + '/releases/download/v2/Example-2.zip'

    def setUp(self):
        self.file = {'fileName': 'Example-2.zip', 'fileLength': 42, 'hashes': [{'algo': 1, 'value': 'a' * 40}]}
        self.asset = {'browser_download_url': self.asset_url, 'name': 'Example-2.zip', 'size': 42, 'state': 'uploaded'}
        self.release = {'draft': False, 'prerelease': False, 'assets': [self.asset]}

    def test_only_declared_public_repository(self):
        for suffix in ('', '/', '.git', '/tree/main'):
            self.assertEqual(github_repository(self.source + suffix), 'Author/Example')
        for source in (None, 'http://github.com/Author/Example', 'https://github.com.evil/Author/Example',
                       'https://user@github.com/Author/Example', 'https://github.com:bad/Author/Example',
                       self.source + '/../../other', 'https://github.com/Owner/..', self.source + '?token=secret'):
            self.assertEqual(github_repository(source), '')

    def test_lookup_validates_asset_in_a_published_release(self):
        invalid_assets = [dict(self.asset, size=41), dict(self.asset, name='example-2.zip'),
                          dict(self.asset, state='new'), dict(self.asset, browser_download_url=self.asset_url + '?secret'),
                          dict(self.asset, browser_download_url=self.asset_url.replace('Author', 'Other')),
                          dict(self.asset, browser_download_url=self.asset_url.replace('Example-2.zip', '%2e%2e'))]
        invalid = [dict(self.release, assets=invalid_assets), dict(self.release, draft=True),
                   dict(self.release, prerelease=True)]
        with patch('addon_releases._read', return_value=json.dumps(invalid)):
            self.assertEqual(find_release_asset(self.source, self.file), '')
        with patch('addon_releases._read', return_value=json.dumps(invalid + [self.release])) as read:
            self.assertEqual(find_release_asset(self.source, self.file), self.asset_url)
            self.assertEqual(read.call_count, 1)
            self.assertIn('/repos/Author/Example/releases?per_page=', read.call_args.args[0])

    def test_no_lookup_without_usable_metadata(self):
        with patch('addon_releases._read') as read:
            for changes in ({'hashes': None}, {'hashes': [{'algo': 1, 'value': 'bad'}]}, {'fileLength': 0},
                            {'hashes': self.file['hashes'] + [{'algo': 2}]},
                            {'hashes': [{'algo': 3, 'value': 'a' * 40}]}, {'fileName': ''}):
                self.assertEqual(find_release_asset(self.source, dict(self.file, **changes)), '')
            self.assertEqual(find_release_asset('https://elsewhere.invalid/code', self.file), '')
            read.assert_not_called()

    def test_distinguishes_absent_repository_from_lookup_failure(self):
        opener = MagicMock()
        with patch('addon_releases.urllib.request.build_opener', return_value=opener):
            for code in (404, 429, 500):
                opener.open.side_effect = urllib.error.HTTPError(self.source, code, 'failed', {}, None)
                if code == 404:
                    self.assertEqual(find_release_asset(self.source, self.file), '')
                else:
                    with self.assertRaisesRegex(UserError, 'GitHub'):
                        find_release_asset(self.source, self.file)
        with patch('addon_releases._read', return_value=b'not JSON'):
            with self.assertRaisesRegex(UserError, 'invalid release metadata'):
                find_release_asset(self.source, self.file)

    def test_asset_download_size_limit_and_headers(self):
        with patch('addon_releases.urllib.request.build_opener') as build:
            opener = build.return_value
            opener.open.side_effect = lambda *args, **kwargs: io.BytesIO(b'abcd')
            self.assertEqual(download_release_asset(self.asset_url, 4), b'abcd')
            request = opener.open.call_args.args[0]
            self.assertEqual({name.lower() for name, _ in request.header_items()}, {'accept', 'user-agent'})
            with self.assertRaisesRegex(UserError, 'size'):
                download_release_asset(self.asset_url, 3)
            with self.assertRaisesRegex(UserError, 'URL'):
                download_release_asset('https://github.com/Author/Example', 4)
            self.assertEqual(opener.open.call_count, 2)

    def test_redirects_remain_on_the_release_service(self):
        redirect = ReleaseRedirect()
        asset_req = urllib.request.Request(self.asset_url)
        cdn = 'https://release-assets.githubusercontent.com/github-production-release-asset/blob?sig=x'
        self.assertEqual(redirect.redirect_request(asset_req, None, 302, '', {}, cdn).full_url, cdn)
        metadata_req = urllib.request.Request('https://api.github.com/repos/Author/Example/releases')
        canonical = 'https://api.github.com/repositories/123/releases?per_page=10'
        self.assertEqual(redirect.redirect_request(metadata_req, None, 301, '', {}, canonical).full_url, canonical)
        for request, target in [(asset_req, 'https://github.com/Other/Else'), (asset_req, 'http://127.0.0.1/zip'),
                                (asset_req, 'https://token@objects.githubusercontent.com/zip'),
                                (metadata_req, cdn), (metadata_req, 'https://api.github.com/user')]:
            with self.subTest(target=target), self.assertRaises(UserError):
                redirect.redirect_request(request, None, 302, '', {}, target)


class LocalReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.downloads = Path(temp.name) / 'Downloads'
        self.downloads.mkdir()
        self.path = self.downloads / 'Example.zip'
        self.data = b'example'
        self.file = {'fileName': self.path.name, 'fileLength': len(self.data), 'hashes': [
            {'algo': 1, 'value': hashlib.sha1(self.data).hexdigest().upper()},
            {'algo': 2, 'value': hashlib.md5(self.data).hexdigest()}]}

    def test_returns_only_matching_bytes_from_exact_name(self):
        self.path.with_name('Example (1).zip').write_bytes(self.data)
        self.assertIsNone(local_release_zip(self.downloads, self.file))
        self.path.write_bytes(self.data)
        self.assertEqual(local_release_zip(self.downloads, self.file), self.data)
        self.file['hashes'][1]['value'] = '0' * 32
        self.assertIsNone(local_release_zip(self.downloads, self.file))

    def test_invalid_hash_metadata_fails_closed(self):
        for entry in (None, 'bad', {'algo': False}, {'algo': 2, 'value': 'not md5'}, {'algo': 1, 'value': None}):
            file = dict(self.file, hashes=self.file['hashes'] + [entry])
            with self.subTest(entry=entry):
                self.assertEqual(release_hashes(file), [])
                self.assertFalse(hashes_match(self.data, file))
        unknown = dict(self.file, hashes=self.file['hashes'] + [{'algo': 3, 'value': 'unknown'}])
        self.assertTrue(hashes_match(self.data, unknown))

    def test_rejects_unsafe_names_and_sizes_before_opening(self):
        with patch('addon_releases.os.open') as opened:
            for changes in ({'fileName': '../example.zip'}, {'fileName': '/tmp/example.zip'},
                            {'fileName': 'C:\\example.zip'}, {'fileName': 'broken\x00.zip'}, {'fileName': 'example.toc'},
                            {'fileLength': MAX_DOWNLOAD + 1}, {'fileLength': False}, {'hashes': []}):
                self.assertIsNone(local_release_zip(self.downloads, dict(self.file, **changes)))
            self.assertIsNone(local_release_zip(None, self.file))
            opened.assert_not_called()

    def test_skips_wrong_size_linked_or_nonregular_entries(self):
        other = self.downloads.parent / 'Other.zip'
        other.write_bytes(self.data)
        link = self.downloads.parent / 'LinkedDownloads'
        link.symlink_to(self.downloads, target_is_directory=True)
        self.path.write_bytes(self.data)
        self.assertIsNone(local_release_zip(link, self.file))
        with patch('builtins.open') as reader:
            self.assertIsNone(local_release_zip(self.downloads, dict(self.file, fileLength=1)))
            self.path.unlink()
            self.path.symlink_to(other)
            self.assertIsNone(local_release_zip(self.downloads, self.file))
            self.path.unlink()
            os.mkfifo(self.path)
            self.assertIsNone(local_release_zip(self.downloads, self.file))
            self.path.unlink()
            self.path.mkdir()
            self.assertIsNone(local_release_zip(self.downloads, self.file))
            reader.assert_not_called()

    def test_read_stays_on_checked_inode_after_filename_replaced(self):
        self.path.write_bytes(self.data)
        old = self.path.with_suffix('.old')
        real_open = open

        def after_check(path, mode):
            self.path.rename(old)
            self.path.write_bytes(b'changed')
            return real_open(path, mode)

        with patch('builtins.open', side_effect=after_check):
            self.assertEqual(local_release_zip(self.downloads, self.file), self.data)
        self.assertEqual(self.path.read_bytes(), b'changed')
