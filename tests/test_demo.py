import asyncio
import importlib.util
import logging
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend import atomic_json
from demo import DemoSession


class DemoTests(unittest.TestCase):
    def test_full_lifecycle_without_network(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Unexpected network')):
            session = DemoSession()
            try:
                manager = session.manager
                root = manager.root()
                self.assertEqual(len(manager.installed()['addons']), 2)
                self.assertTrue(all(a['update'] for a in manager.installed(True)['addons']))
                manager.install(1001)
                self.assertFalse(any(a['update'] for a in manager.installed(True)['addons']))
                self.assertEqual([m['id'] for m in manager.search('raid')], [1002])
                manager.install(1002)
                self.assertTrue((root / 'DemoRaidNotes' / 'DemoRaidNotes.toc').is_file())
            finally:
                session.close()
            self.assertFalse(root.exists())


class PluginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        fake_decky = SimpleNamespace(DECKY_PLUGIN_SETTINGS_DIR=self.temp.name, logger=logging.getLogger('test'))
        spec = importlib.util.spec_from_file_location('cursedeck_plugin_test', Path(__file__).parents[1] / 'main.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, decky=fake_decky):
            spec.loader.exec_module(module)
        self.plugin = module.Plugin()
        await self.plugin._main()
        self.addAsyncCleanup(self.plugin._unload)

    async def test_demo_keeps_live_settings_and_returns_to_live_mode(self):
        settings_file = Path(self.temp.name) / 'settings.json'
        atomic_json(settings_file, {'path': '', 'flavor': 0, 'key': 'private-saved-key'})
        before = settings_file.read_bytes()
        reply = await self.plugin.set_demo(True)
        self.assertTrue(reply['data']['demo'])
        demo_root = Path(reply['data']['path'])
        self.assertNotIn('key', reply['data'])
        self.assertTrue((await self.plugin.install(1002))['ok'])
        self.assertEqual(settings_file.read_bytes(), before)
        reply = await self.plugin.set_demo(False)
        self.assertFalse(reply['data']['demo'])
        self.assertEqual(reply['data']['path'], '')
        self.assertFalse(demo_root.exists())
        self.assertEqual(settings_file.read_bytes(), before)

    async def test_configure_is_blocked_in_demo(self):
        await self.plugin.set_demo(True)
        reply = await self.plugin.configure('/arbitrary/real/path', 517, 'secret')
        self.assertFalse(reply['ok'])
        self.assertIn('Leave the offline demo', reply['error'])

    async def test_concurrent_mode_changes_are_serialized(self):
        replies = await asyncio.gather(*(self.plugin.set_demo(True) for _ in range(5)))
        self.assertEqual(len({r['data']['path'] for r in replies}), 1)
        self.assertTrue((await self.plugin.installed(False))['ok'])

    async def test_user_error_is_returned_without_traceback(self):
        reply = await self.plugin.search('test', 0)
        self.assertEqual(reply, {'ok': False, 'error': 'Complete Setup before searching.'})
