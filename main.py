import asyncio
import decky
import sys
from pathlib import Path

# Decky loads main.py dynamically; make the bundled backend importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import Manager, UserError


class Plugin:
    async def _main(self):
        self.manager = Manager(decky.DECKY_PLUGIN_SETTINGS_DIR)

    async def _unload(self):
        pass

    async def _call(self, method, *args):
        try:
            def invoke():
                with self.manager.lock:
                    return getattr(self.manager, method)(*args)
            result = await asyncio.to_thread(invoke)
            return {'ok': True, 'data': result}
        except UserError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            decky.logger.exception('CurseDeck operation failed')
            return {'ok': False, 'error': 'Operation failed. Check the Decky plugin log for details.'}

    async def status(self):
        return await self._call('status')

    async def configure(self, path, flavor, key):
        return await self._call('configure', path, flavor, key)

    async def editions(self, key):
        return await self._call('editions', key)

    async def search(self, query, index):
        return await self._call('search', query, index)

    async def installed(self, check):
        return await self._call('installed', check)

    async def install(self, mod_id):
        return await self._call('install', mod_id)
