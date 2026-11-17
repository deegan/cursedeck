import asyncio
import threading
import json
import decky
import sys
from pathlib import Path

# Decky loads main.py dynamically; make bundled modules importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import Manager, UserError
from updates import ReleaseUpdater


class Plugin:
    async def _main(self):
        self.manager = Manager(decky.DECKY_PLUGIN_SETTINGS_DIR)
        version = json.loads((Path(__file__).parent / 'package.json').read_text())['version']
        self.updater = ReleaseUpdater(decky.DECKY_PLUGIN_SETTINGS_DIR, version)
        self.operation_lock = threading.RLock()

    async def _unload(self):
        pass

    async def _call(self, method, *args):
        try:
            def invoke():
                with self.operation_lock, self.manager.lock:
                    return getattr(self.manager, method)(*args)
            return {'ok': True, 'data': await asyncio.to_thread(invoke)}
        except UserError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            decky.logger.exception('CurseDeck operation failed')
            return {'ok': False, 'error': 'Operation failed. Check the Decky plugin log for details.'}

    async def status(self):
        return await self._call('status')

    async def configure_local(self, path):
        return await self._call('configure_local', path)

    async def configure(self, path, flavor, key):
        return await self._call('configure', path, flavor, key)

    async def discover(self, path=''):
        return await self._call('discover', path)

    async def key_from_file(self, path):
        return await self._call('key_from_file', path)

    async def home(self):
        return decky.DECKY_USER_HOME

    async def editions(self, key):
        return await self._call('editions', key)

    async def search(self, query, index):
        return await self._call('search', query, index)

    async def installed(self, check):
        return await self._call('installed', check)

    async def install(self, mod_id):
        return await self._call('install', mod_id)

    async def install_download(self, mod_id, path):
        return await self._call('install', mod_id, path)

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

    async def plugin_update_status(self):
        return {'ok': True, 'data': await asyncio.to_thread(self.updater.status)}

    async def prepare_plugin_update(self):
        try:
            result = await asyncio.to_thread(self.updater.prepare)
            decky.logger.info('Prepared verified CurseDeck update %s for Decky installation', result['version'])
            return {'ok': True, 'data': result}
        except UserError as error:
            return {'ok': False, 'error': str(error)}
        except Exception:
            decky.logger.exception('Could not prepare plugin update')
            return {'ok': False, 'error': 'Could not stage the update. Check disk space and plugin logs.'}

    async def update_handoff_failed(self, message):
        return {'ok': True, 'data': await asyncio.to_thread(self.updater.handoff_failed, message)}
