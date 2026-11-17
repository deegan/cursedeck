"""Offline fixtures exercising the real manager in an isolated temporary directory."""
import hashlib
import io
from pathlib import Path
import tempfile
import zipfile

from backend import Manager, UserError, atomic_json

EDITION = 517
PROJECTS = {
    1001: ('Quest Compass (demo)', 'DemoQuestCompass', 'A sample quest tracker with a required library.'),
    1002: ('Raid Notes (demo)', 'DemoRaidNotes', 'A sample raid notebook to try installing.'),
    1003: ('Shared Library (demo)', 'DemoSharedLibrary', 'A required dependency installed automatically.'),
}


class DemoClient:
    def __init__(self, key=''):
        self.version = 1

    def api(self, route, **params):
        if route == 'games/1/version-types':
            return [{'id': EDITION, 'name': 'Retail (offline demo)'}]
        if route == 'mods/search':
            query = params.get('searchFilter', '').casefold()
            results = [self.api(f'mods/{pid}') for pid, values in PROJECTS.items()
                       if query in values[0].casefold()]
            index = params.get('index', 0)
            return results[index:index + params.get('pageSize', 20)]
        if route.startswith('mods/') and route.count('/') == 1:
            pid = int(route.split('/')[1])
            if pid not in PROJECTS:
                raise UserError('That project is not part of the offline demo.')
            name, _, summary = PROJECTS[pid]
            return {'id': pid, 'gameId': 1, 'name': name, 'summary': summary, 'allowModDistribution': True}
        raise UserError('Unsupported offline demo operation.')

    def post(self, route, body):
        if route == 'mods':
            return [self.api(f'mods/{pid}') for pid in body.get('modIds', []) if pid in PROJECTS]
        if route == 'fingerprints/1':
            return {'exactMatches': []}
        raise UserError('Unsupported offline demo operation.')

    def archive(self, pid):
        folder = PROJECTS[pid][1]
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as out:
            # Fixed ZIP dates make repeated downloads have identical checksums.
            for name, contents in {
                f'{folder}/{folder}.toc': f'## Title: {PROJECTS[pid][0]}\n## Version: {self.version}.0\ncore.lua\n',
                f'{folder}/core.lua': f'-- Offline demo release {self.version}\n',
            }.items():
                out.writestr(zipfile.ZipInfo(name), contents)
        return data.getvalue()

    def latest(self, pid, flavor):
        if flavor != EDITION:
            raise UserError('Unknown demo edition.')
        self.api(f'mods/{pid}')
        data = self.archive(pid)
        return {'id': pid * 10 + self.version, 'displayName': f'{self.version}.0 (demo)',
                'downloadUrl': f'demo://{pid}', 'fileLength': len(data),
                'hashes': [{'algo': 1, 'value': hashlib.sha1(data).hexdigest()}],
                'dependencies': [{'relationType': 3, 'modId': 1003}] if pid == 1001 else []}

    def request(self, url, limit):
        if not url.startswith('demo://'):
            raise UserError('Offline demo never makes network requests.')
        return self.archive(int(url.removeprefix('demo://')))


class DemoSession:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cursedeck-demo-')
        try:
            root = Path(self.temp.name)
            wow = root / '_retail_'
            wow.mkdir()
            (wow / 'Wow.exe').touch()
            self.client = DemoClient()
            self.manager = Manager(root / 'settings', client_factory=lambda key: self.client)
            atomic_json(self.manager.settings_file, {'path': str(wow), 'flavor': EDITION, 'key': ''})
            self.manager.install(1001)
            self.client.version = 2
        except BaseException:
            self.temp.cleanup()
            raise

    def close(self):
        self.temp.cleanup()
