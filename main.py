import asyncio
import threading
import json
import decky
import sys
from pathlib import Path

# Decky loads main.py dynamically; make bundled modules importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import Manager, UserError
from demo import DemoSession
from updates import ReleaseUpdater


class Plugin:
    async def _main(self):
        self.manager = Manager(decky.DECKY_PLUGIN_SETTINGS_DIR)
        version = json.loads((Path(__file__).parent / 'package.json').read_text())['version']
        self.updater = ReleaseUpdater(decky.DECKY_PLUGIN_SETTINGS_DIR, version)
        self.demo = None
        self.operation_lock = threading.RLock()

    async def _unload(self):
        def close():
            with self.operation_lock:
                if self.demo:
                    self.demo.close()
                    self.demo = None
        await asyncio.to_thread(close)

    async def _call(self, method, *args):
        try:
            def invoke():
                with self.operation_lock:
                    if method == 'set_demo':
                        if args[0] and not self.demo:
                            self.demo = DemoSession()
                        elif not args[0] and self.demo:
                            self.demo.close()
                            self.demo = None
                        result = (self.demo.manager if self.demo else self.manager).status()
                    else:
                        if self.demo and method == 'configure':
                            raise UserError('Leave the offline demo before changing your real setup.')
                        manager = self.demo.manager if self.demo else self.manager
                        with manager.lock:
                            result = getattr(manager, method)(*args)
                    if method in ('status', 'configure', 'set_demo'):
                        result['demo'] = self.demo is not None
                    return result
            return {'ok': True, 'data': await asyncio.to_thread(invoke)}
        except UserError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            decky.logger.exception('CurseDeck operation failed')
            return {'ok': False, 'error': 'Operation failed. Check the Decky plugin log for details.'}

    async def set_demo(self, enabled):
        return await self._call('set_demo', bool(enabled))

    async def status(self):
        return await self._call('status')

    async def configure(self, path, flavor, key):
        return await self._call('configure', path, flavor, key)

    async def discover(self):
        return await self._call('discover')

    async def editions(self, key):
        return await self._call('editions', key)

    async def search(self, query, index):
        return await self._call('search', query, index)

    async def installed(self, check):
        return await self._call('installed', check)

    async def install(self, mod_id):
        return await self._call('install', mod_id)

    async def check_plugin_update(self, force=False):
        try:
            return {'ok': True, 'data': await asyncio.to_thread(self.updater.check, force)}
        except UserError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            decky.logger.exception('Plugin update check failed')
            return {'ok': False, 'error': 'Could not check plugin updates. Try again later.'}

    async def set_update_checks(self, enabled):
        try:
            result = await asyncio.to_thread(self.updater.set_automatic_checks, enabled)
            return {'ok': True, 'data': result}
        except Exception:
            return {'ok': False, 'error': 'Could not save update preferences.'}
