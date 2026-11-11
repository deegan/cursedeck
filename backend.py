"""CurseDeck core; only Python's standard library is required."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile

GAME_ID = 1
MAX_DOWNLOAD = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


class UserError(Exception):
    pass


def trusted_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host == 'api.curseforge.com' or host.endswith('.forgecdn.net')))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not trusted_url(newurl):
            raise UserError('Download redirected outside CurseForge; request refused.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.cursedeck-')
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Client:
    def __init__(self, key):
        self.key = key

    def request(self, url, limit):
        if not self.key:
            raise UserError('Save a CurseForge API key in Setup first.')
        if not trusted_url(url):
            raise UserError('CurseForge returned an unsupported download URL.')
        request = urllib.request.Request(url, headers={
            'x-api-key': self.key, 'User-Agent': 'CurseDeck/0.1', 'Accept': '*/*'})
        try:
            with urllib.request.build_opener(SafeRedirect()).open(request, timeout=45) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise UserError('Download exceeds the supported size limit.')
                return body
        except urllib.error.HTTPError as error:
            messages = {401: 'CurseForge rejected the API key.',
                        403: 'CurseForge denied access or the author disabled third-party downloads.',
                        429: 'CurseForge rate limit reached. Try again later.'}
            raise UserError(messages.get(error.code, f'CurseForge request failed (HTTP {error.code}).')) from None
        except (urllib.error.URLError, TimeoutError):
            raise UserError('Could not reach CurseForge. Check your connection and try again.') from None

    def api(self, route, **params):
        url = 'https://api.curseforge.com/v1/' + route
        if params:
            url += '?' + urllib.parse.urlencode(params)
        return json.loads(self.request(url, 8 * 1024 * 1024))['data']

    def latest(self, mod_id, flavor):
        # Filter on both the server and file metadata; never guess the WoW edition.
        candidates = []
        for index in range(0, 10000, 50):
            files = self.api(f'mods/{mod_id}/files', gameVersionTypeId=flavor, pageSize=50, index=index)
            eligible = [f for f in files if f.get('releaseType') == 1 and f.get('isAvailable')
                        and any(v.get('gameVersionTypeId') == flavor for v in f.get('sortableGameVersions', []))]
            candidates.extend(eligible)
            if len(files) < 50:
                break
        if candidates:
            return max(candidates, key=lambda f: (f['fileDate'], f['id']))
        raise UserError('No stable release is available for the selected WoW edition.')


def unpack(data, destination):
    """Validate the entire archive before writing any addon files."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 20000 or sum(e.file_size for e in entries) > MAX_EXPANDED:
            raise UserError('Addon archive is too large to extract safely.')
        seen = set()
        folders = set()
        spellings = {}
        for entry in entries:
            path = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (not path.parts or path.is_absolute() or '..' in path.parts
                    or '\\' in entry.filename or ':' in entry.filename
                    or any(p.startswith('.') for p in path.parts)
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise UserError('Addon contains an unsafe archive path.')
            for length in range(1, len(path.parts) + 1):
                prefix = '/'.join(path.parts[:length])
                previous = spellings.setdefault(prefix.casefold(), prefix)
                if previous != prefix:
                    raise UserError('Addon contains conflicting path capitalization.')
            normalized = str(path).casefold()
            if normalized in seen:
                raise UserError('Addon contains duplicate archive paths.')
            seen.add(normalized)
            if len(path.parts) < 2 and not entry.is_dir():
                raise UserError('Expected an archive containing addon folders.')
            folders.add(path.parts[0])
        if not folders:
            raise UserError('Addon archive is empty.')
        for folder in folders:
            if not any(len(PurePosixPath(e.filename).parts) == 2
                       and PurePosixPath(e.filename).parts[0] == folder
                       and e.filename.lower().endswith('.toc') for e in entries):
                raise UserError(f'Archive folder {folder} has no WoW addon manifest (.toc).')
        archive.extractall(destination)
        return sorted(folders)



def validate_registry(state):
    try:
        if not isinstance(state['flavor'], int) or not isinstance(state['addons'], dict):
            raise ValueError()
        owners = set()
        for key, addon in state['addons'].items():
            if str(addon['id']) != key or not isinstance(addon['fileId'], int):
                raise ValueError()
            if not isinstance(addon['name'], str) or not isinstance(addon['version'], str):
                raise ValueError()
            if not isinstance(addon['folders'], list) or not addon['folders']:
                raise ValueError()
            for folder in addon['folders']:
                if (not isinstance(folder, str) or not folder or folder.startswith('.')
                        or '/' in folder or '\\' in folder or ':' in folder
                        or folder.casefold() in owners):
                    raise ValueError()
                owners.add(folder.casefold())
    except (KeyError, TypeError, ValueError):
        raise UserError('The CurseDeck addon registry is invalid. Restore its backup before continuing.') from None


class Manager:
    def __init__(self, settings_dir, client_factory=Client):
        self.client_factory = client_factory
        self.settings_file = Path(settings_dir) / 'settings.json'
        self.lock = threading.RLock()

    def settings(self):
        if self.settings_file.exists():
            return json.loads(self.settings_file.read_text())
        return {'path': '', 'flavor': 0, 'key': ''}

    def discover(self, path=''):
        from discovery import discover_installations
        if path:
            selected = Path(path).expanduser()
            if not selected.is_absolute() or not selected.is_dir():
                raise UserError('Select a readable folder containing your WoW installation.')
            return discover_installations(selected_root=selected)
        return discover_installations()

    def client(self):
        return self.client_factory(self.settings()['key'])

    def root(self, create=True, path=None):
        raw = self.settings()['path'] if path is None else path
        if not raw:
            raise UserError('Choose your WoW edition folder in Setup first.')
        root = Path(raw).expanduser().resolve()
        if not root.is_dir() or not any((root / exe).is_file() for exe in ('Wow.exe', 'WowClassic.exe')):
            raise UserError('Choose the WoW edition folder containing Wow.exe or WowClassic.exe, such as _retail_.')
        def child(parent, name):
            matches = [p for p in parent.iterdir() if p.name.casefold() == name.casefold()] if parent.is_dir() else []
            if len(matches) > 1:
                raise UserError(f'Multiple folders match {name}; choose a single folder before continuing.')
            return matches[0] if matches else parent / name
        interface = child(root, 'Interface')
        if interface.is_symlink():
            raise UserError('Symlinked Interface or AddOns folders are not supported.')
        addons = child(interface, 'AddOns')
        if interface.is_symlink() or addons.is_symlink():
            raise UserError('Symlinked Interface or AddOns folders are not supported.')
        if (interface.exists() and not interface.is_dir()) or (addons.exists() and not addons.is_dir()):
            raise UserError('Interface and AddOns must be directories.')
        if create:
            addons.mkdir(parents=True, exist_ok=True)
        return addons

    def state(self):
        root = self.root(create=False)
        path = root / '.cursedeck.json'
        if path.is_symlink():
            raise UserError('Refusing a symlinked addon registry.')
        state = json.loads(path.read_text()) if path.exists() else {'flavor': self.settings()['flavor'], 'addons': {}}
        validate_registry(state)
        if state['flavor'] != self.settings()['flavor']:
            raise UserError('This folder is registered for a different WoW edition. Restore its edition in Setup.')
        return root, state

    def configure_local(self, path):
        with self.lock:
            addons = self.root(create=False, path=path)
            root = str(Path(path).expanduser().resolve())
            previous = self.settings()
            flavor = previous['flavor'] if previous['path'] == root else 0
            registry = addons / '.cursedeck.json'
            if registry.is_symlink():
                raise UserError('Refusing a symlinked addon registry.')
            if registry.exists():
                state = json.loads(registry.read_text())
                validate_registry(state)
                flavor = state['flavor']
            atomic_json(self.settings_file, dict(previous, path=root, flavor=flavor))
            return self.status()

    def configure(self, path, flavor, key):
        with self.lock:
            previous = self.settings()
            key = key.strip() or previous['key']
            types = self.client_factory(key).api(f'games/{GAME_ID}/version-types')
            if flavor not in [item['id'] for item in types]:
                raise UserError('Select a WoW edition from the list.')
            root = Path(path).expanduser().resolve()
            if not any((root / exe).is_file() for exe in ('Wow.exe', 'WowClassic.exe')):
                raise UserError('The chosen folder must contain Wow.exe or WowClassic.exe.')
            if (root / 'Interface').is_symlink() or (root / 'Interface' / 'AddOns').is_symlink():
                raise UserError('Symlinked Interface or AddOns folders are not supported.')
            registry = self.root(create=False, path=path) / '.cursedeck.json'
            if registry.is_symlink():
                raise UserError('Refusing a symlinked addon registry.')
            if registry.exists() and json.loads(registry.read_text())['flavor'] != flavor:
                raise UserError('That folder already uses another edition in CurseDeck.')
            atomic_json(self.settings_file, {'path': str(root), 'flavor': flavor, 'key': key})
            return self.status()

    def status(self):
        settings = self.settings()
        return {'path': settings['path'], 'flavor': settings['flavor'], 'hasKey': bool(settings['key'])}

    def editions(self, key):
        return self.client_factory(key.strip() or self.settings()['key']).api(f'games/{GAME_ID}/version-types')

    def search(self, query, index=0):
        settings = self.settings()
        if not settings['flavor']:
            raise UserError('Complete Setup before searching.')
        return self.client().api('mods/search', gameId=GAME_ID, searchFilter=query[:200],
                                 gameVersionTypeId=settings['flavor'], sortField=2, sortOrder='desc',
                                 pageSize=20, index=max(0, min(int(index), 9980)))

    def installed(self, check=False):
        with self.lock:
            root, state = self.state()
            result = []
            for mod in state['addons'].values():
                item = dict(mod, update=None, error=None,
                            missing=any((root / f).is_symlink() or not (root / f).is_dir()
                                or not any(p.is_file() and p.suffix.lower() == '.toc'
                                           for p in (root / f).iterdir()) for f in mod['folders']))
                if check:
                    try:
                        latest = self.client().latest(mod['id'], state['flavor'])
                        if latest['id'] > mod['fileId']:
                            item['update'] = latest['displayName']
                    except UserError as error:
                        item['error'] = str(error)
                result.append(item)
            managed = {f.casefold() for m in state['addons'].values() for f in m['folders']}
            unmanaged = sorted(p.name for p in (root.iterdir() if root.exists() else []) if p.is_dir()
                               and not p.name.startswith('.') and p.name.casefold() not in managed)
            from local_addons import read_addon
            local = [read_addon(root / name, Path(self.settings()['path']).name) for name in unmanaged]
            return {'addons': result, 'unmanaged': unmanaged, 'localAddons': local, 'path': str(root)}

    def install(self, mod_id):
        with self.lock:
            if not self.settings()['flavor']:
                raise UserError('Select and save your CurseForge WoW edition in Setup before installing addons.')
            root, state = self.state()
            self.root(create=True)
            client = self.client()
            plan = {}

            def resolve(project_id):
                if project_id in plan:
                    return
                if len(plan) >= 40:
                    raise UserError('Dependency tree is too large.')
                mod = client.api(f'mods/{project_id}')
                if mod['gameId'] != GAME_ID or mod.get('allowModDistribution') is False:
                    raise UserError('This addon is not available for third-party WoW installation.')
                file = client.latest(project_id, state['flavor'])
                plan[project_id] = (mod, file)
                for dependency in file.get('dependencies', []):
                    if dependency['relationType'] == 3:
                        resolve(dependency['modId'])

            resolve(int(mod_id))
            # Stage all dependencies before touching the live installation.
            with tempfile.TemporaryDirectory(prefix='.cursedeck-', dir=root) as temp:
                stage = Path(temp)
                records = {}
                claimed = {}
                for project_id, (mod, file) in plan.items():
                    old = state['addons'].get(str(project_id))
                    if old and old['fileId'] > file['id']:
                        continue  # Never silently downgrade an installed release.
                    url = file.get('downloadUrl') or client.api(f'mods/{project_id}/files/{file["id"]}/download-url')
                    if not url:
                        raise UserError(f'Download unavailable for {mod["name"]}.')
                    data = client.request(url, MAX_DOWNLOAD)
                    hashes = [h for h in file.get('hashes', []) if h['algo'] in (1, 2)]
                    if not hashes or len(data) != file['fileLength']:
                        raise UserError('Download size or checksum metadata is invalid.')
                    for digest in hashes:
                        algorithm = 'sha1' if digest['algo'] == 1 else 'md5'
                        if hashlib.new(algorithm, data).hexdigest().lower() != digest['value'].lower():
                            raise UserError('Addon checksum failed; no files were changed.')
                    target = stage / str(project_id)
                    folders = unpack(data, target)
                    for folder in folders:
                        if folder.casefold() in claimed:
                            raise UserError('Two addons in this install use the same folder.')
                        claimed[folder.casefold()] = str(project_id)
                    records[str(project_id)] = {'id': project_id, 'name': mod['name'],
                        'fileId': file['id'], 'version': file['displayName'], 'folders': folders}
                existing = {p.name.casefold(): p for p in root.iterdir()}
                owners = {f.casefold(): key for key, m in state['addons'].items() for f in m['folders']}
                for folder, owner in claimed.items():
                    if folder in existing and (owners.get(folder) != owner or existing[folder].is_symlink()):
                        raise UserError(f'Folder {existing[folder].name} already exists outside this addon. Move it aside before installing.')
                touched = set(f for r in records.values() for f in r['folders'])
                touched.update(f for key in records for f in state['addons'].get(key, {}).get('folders', []))
                backup = stage / 'backup'
                backup.mkdir()
                moved, placed = [], []
                try:
                    for folder in sorted(touched):
                        # Registry entries are local data, but still never allow path traversal.
                        if Path(folder).name != folder or folder.startswith('.') or (root / folder).is_symlink():
                            raise UserError('Unsafe managed addon folder.')
                        if (root / folder).exists():
                            os.replace(root / folder, backup / folder)
                            moved.append(folder)
                    for key, record in records.items():
                        for folder in record['folders']:
                            os.replace(stage / key / folder, root / folder)
                            placed.append(folder)
                    state['addons'].update(records)
                    atomic_json(root / '.cursedeck.json', state)
                except BaseException:
                    for folder in placed:
                        shutil.rmtree(root / folder)
                    for folder in moved:
                        os.replace(backup / folder, root / folder)
                    raise
            return self.installed()
