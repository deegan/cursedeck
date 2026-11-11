from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from discovery import discover_installations, library_paths


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.steam = self.home / '.local/share/Steam'
        self.steam.mkdir(parents=True)

    def wow(self, root, edition='_retail_', executable='Wow.exe'):
        folder = root / 'World of Warcraft' / edition
        folder.mkdir(parents=True)
        (folder / executable).touch()
        return folder

    def scan(self, **kwargs):
        return discover_installations(self.home, **kwargs)

    def test_common_and_arbitrary_proton_ids_and_multiple_editions(self):
        direct = self.wow(self.steam / 'steamapps/common')
        drive = self.steam / 'steamapps/compatdata/987654321/pfx/drive_c/Program Files (x86)'
        retail = self.wow(drive)
        classic = self.wow(drive, '_classic_era_', 'WowClassic.exe')
        results = self.scan()['installations']
        self.assertEqual({r['path'] for r in results}, {str(p) for p in (direct, retail, classic)})
        self.assertFalse((retail / 'Interface').exists())

    def test_sd_library_from_vdf_and_duplicate_steam_alias(self):
        sd = self.home / 'SD Card/SteamLibrary'
        game = self.wow(sd / 'steamapps/common')
        config = self.steam / 'steamapps/libraryfolders.vdf'
        config.parent.mkdir()
        config.write_text('"libraryfolders" { "0" { "path" "' + str(self.steam) + '" } "1" { "path" "' + str(sd) + '" } }')
        (self.home / '.steam').mkdir()
        (self.home / '.steam/steam').symlink_to(self.steam, target_is_directory=True)
        self.assertEqual([r['path'] for r in self.scan()['installations']], [str(game)])

    def test_flatpak_steam_and_legacy_library_list(self):
        flatpak = self.home / '.var/app/com.valvesoftware.Steam/data/Steam'
        extra = self.home / 'other-library'
        game = self.wow(extra / 'steamapps/compatdata/12/pfx/drive_c/Games')
        config = flatpak / 'config/libraryfolders.vdf'
        config.parent.mkdir(parents=True)
        config.write_text('"LibraryFolders" { "1" "' + str(extra) + '" }')
        self.assertEqual(self.scan()['installations'][0]['path'], str(game))

    def test_names_without_executables_are_not_installations(self):
        folder = self.steam / 'steamapps/common/World of Warcraft/_retail_'
        folder.mkdir(parents=True)
        (folder / 'Battle.net.exe').touch()
        self.assertEqual(self.scan()['installations'], [])

    def test_symlinked_wow_and_loops_are_deduplicated(self):
        game = self.wow(self.home / 'external')
        common = self.steam / 'steamapps/common'
        common.mkdir(parents=True)
        (common / 'World of Warcraft').symlink_to(game.parent, target_is_directory=True)
        (common / 'wow').symlink_to(common, target_is_directory=True)
        self.assertEqual([r['path'] for r in self.scan()['installations']], [str(game)])

    def test_generic_host_symlinks_not_followed(self):
        self.wow(self.home / 'outside')
        common = self.steam / 'steamapps/common'
        common.mkdir(parents=True)
        (common / 'host').symlink_to(self.home / 'outside', target_is_directory=True)
        self.assertEqual(self.scan()['installations'], [])

    def test_scan_limits_report_partial_results(self):
        self.wow(self.steam / 'steamapps/common')
        result = self.scan(max_dirs=1)
        self.assertTrue(result['limited'])
        self.assertTrue(result['warnings'])
        self.assertTrue(self.scan(timeout=0)['limited'])

    def test_unreadable_folder_does_not_hide_other_installations(self):
        import os
        game = self.wow(self.steam / 'steamapps/common')
        original = os.scandir
        def scan(path):
            if Path(path).name == 'compatdata':
                raise PermissionError('unreadable')
            return original(path)
        (self.steam / 'steamapps/compatdata').mkdir()
        with patch('discovery.os.scandir', side_effect=scan):
            result = self.scan()
        self.assertEqual(result['installations'][0]['path'], str(game))
        self.assertTrue(result['warnings'])

    def test_vdf_comments_and_escaped_paths(self):
        text = '// "path" "/fake"\n"path" "/mnt/Steam Library"\n"path" "/mnt/with\\\"quote"'
        self.assertEqual(list(library_paths(text)), [Path('/mnt/Steam Library'), Path('/mnt/with"quote')])
