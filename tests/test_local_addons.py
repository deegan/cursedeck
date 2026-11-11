import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import Manager, UserError, atomic_json


class LocalAddonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.wow = self.base / '_retail_'
        self.wow.mkdir()
        (self.wow / 'Wow.exe').touch()
        self.manager = Manager(self.base / 'settings')

    def addon(self, name='Example', toc=None):
        folder = self.wow / 'Interface/AddOns' / name
        folder.mkdir(parents=True)
        (folder / (name + '.toc')).write_text(toc or '## Title: Example addon\n## Version: 1.2.3\n## Notes: Local notes\n')
        return folder

    def test_save_and_list_existing_addons_without_key_or_network(self):
        folder = self.addon()
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network access')):
            status = self.manager.configure_local(str(self.wow))
            library = self.manager.installed()
        self.assertFalse(status['hasKey'])
        self.assertEqual(status['flavor'], 0)
        self.assertEqual(library['localAddons'][0]['name'], 'Example addon')
        self.assertEqual(library['localAddons'][0]['version'], '1.2.3')
        self.assertEqual(library['path'], str(folder.parent))
        self.assertEqual(library['addons'], [])
        self.assertFalse((folder.parent / '.cursedeck.json').exists())

    def test_empty_install_does_not_create_addon_directory(self):
        self.manager.configure_local(str(self.wow))
        self.assertEqual(self.manager.installed()['localAddons'], [])
        self.assertFalse((self.wow / 'Interface').exists())

    def test_case_insensitive_addon_directory(self):
        folder = self.wow / 'interface/addons/Example'
        folder.mkdir(parents=True)
        (folder / 'Example.toc').write_text('## Title: Found')
        self.manager.configure_local(str(self.wow))
        self.assertEqual(self.manager.installed()['localAddons'][0]['name'], 'Found')
        self.assertFalse((self.wow / 'Interface').exists())

    def test_refresh_sees_added_and_removed_addons(self):
        self.manager.configure_local(str(self.wow))
        self.assertEqual(len(self.manager.installed()['localAddons']), 0)
        folder = self.addon()
        self.assertEqual(len(self.manager.installed()['localAddons']), 1)
        (folder / 'Example.toc').unlink()
        folder.rmdir()
        self.assertEqual(len(self.manager.installed()['localAddons']), 0)

    def test_flavor_specific_toc_and_title_formatting(self):
        folder = self.addon()
        (folder / 'Example_Mainline.toc').write_text('\ufeff## Title: |cff00ff00Retail|r addon\n## Version: 2.0\n')
        self.manager.configure_local(str(self.wow))
        addon = self.manager.installed()['localAddons'][0]
        self.assertEqual((addon['name'], addon['version']), ('Retail addon', '2.0'))

    def test_local_save_preserves_credentials_and_managed_registry_flavor(self):
        folder = self.addon()
        atomic_json(self.manager.settings_file, {'path':'', 'flavor':0, 'key':'secret'})
        atomic_json(folder.parent / '.cursedeck.json', {'flavor':517,'addons':{}})
        self.manager.configure_local(str(self.wow))
        self.assertEqual(self.manager.settings()['key'], 'secret')
        self.assertEqual(self.manager.status()['flavor'], 517)
        self.assertEqual(len(self.manager.installed()['localAddons']), 1)

    def test_invalid_folder_does_not_replace_saved_settings(self):
        self.manager.configure_local(str(self.wow))
        before = self.manager.settings_file.read_bytes()
        with self.assertRaises(UserError):
            self.manager.configure_local(str(self.base))
        self.assertEqual(self.manager.settings_file.read_bytes(), before)

    def test_missing_metadata_still_lists_folder(self):
        folder = self.addon()
        (folder / 'Example.toc').unlink()
        self.manager.configure_local(str(self.wow))
        addon = self.manager.installed()['localAddons'][0]
        self.assertEqual(addon['name'], 'Example')
        self.assertIn('No addon manifest', addon['error'])

    def test_linked_manifest_is_not_read(self):
        folder = self.addon()
        (folder / 'Example.toc').unlink()
        secret = self.base / 'private'
        secret.write_text('## Title: Should not be read')
        (folder / 'Example.toc').symlink_to(secret)
        self.manager.configure_local(str(self.wow))
        self.assertEqual(self.manager.installed()['localAddons'][0]['name'], 'Example')
