import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from backend import UserError
from updates import BASE, RELEASE_API, ReleaseUpdater


def release(version='0.3.0'):
    base = BASE + 'v' + version + '/'
    return {'tag_name': 'v' + version, 'draft': False, 'prerelease': False,
            'assets': [{'name': name, 'browser_download_url': base + name}
                       for name in ('CurseDeck.zip', 'update.json')]}


def manifest(version='0.3.0'):
    return {'version': version, 'artifact': BASE + 'v' + version + '/CurseDeck.zip', 'sha256': 'a' * 64}


class ReleaseUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fetch = Mock(side_effect=lambda url: release() if url == RELEASE_API else manifest())
        self.updater = ReleaseUpdater(self.temp.name, '0.2.0', self.fetch)

    def test_update_uses_tag_pinned_url_and_checksum(self):
        update = self.updater.check()
        self.assertTrue(update['available'])
        self.assertEqual(update['artifact'], manifest()['artifact'])
        self.assertEqual(update['sha256'], 'a' * 64)
        self.assertEqual(self.fetch.call_count, 2)
        self.updater.check()
        self.assertEqual(self.fetch.call_count, 2)

    def test_automatic_checks_can_be_disabled_without_api_key(self):
        self.updater.set_automatic_checks(False)
        update = self.updater.check()
        self.fetch.assert_not_called()
        self.assertFalse(update['automaticChecks'])
        self.assertFalse(update['checked'])
        self.assertTrue(self.updater.check(force=True)['available'])
        self.assertFalse(ReleaseUpdater(self.temp.name, '0.2.0').preferences()['automaticChecks'])

    def test_older_current_and_prerelease_do_not_update(self):
        for data in (release('0.1.0'), release('0.2.0'), dict(release(), prerelease=True), dict(release(), draft=True), None):
            with self.subTest(data=data):
                self.fetch.side_effect = None
                self.fetch.return_value = data
                self.assertFalse(self.updater.check(force=True)['available'])

    def test_no_arbitrary_downloads_or_invalid_checksums(self):
        for data in (dict(manifest(), artifact='https://evil.invalid/plugin.zip'),
                     dict(manifest(), version='1.0.0'), dict(manifest(), sha256='bad'), None):
            with self.subTest(data=data):
                self.fetch.side_effect = lambda url: release() if url == RELEASE_API else data
                with self.assertRaises(UserError):
                    self.updater.check(force=True)

    def test_unexpected_asset_origin_rejected(self):
        data = release()
        data['assets'][0]['browser_download_url'] = 'https://evil.invalid/CurseDeck.zip'
        self.fetch.side_effect = None
        self.fetch.return_value = data
        with self.assertRaises(UserError):
            self.updater.check()
        self.assertEqual(self.fetch.call_count, 1)

    def test_unpublished_asset_and_malformed_release_are_clear_errors(self):
        for data in (dict(release(), assets=[]), dict(release(), tag_name='../bad'), []):
            self.fetch.side_effect = None
            self.fetch.return_value = data
            with self.assertRaises(UserError):
                self.updater.check(force=True)

    def test_preferences_are_separate_from_curseforge_credentials(self):
        settings = Path(self.temp.name) / 'settings.json'
        settings.write_text(json.dumps({'key':'private'}))
        self.updater.set_automatic_checks(False)
        self.assertEqual(json.loads(settings.read_text()), {'key':'private'})
