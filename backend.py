"""CurseDeck core; only Python's standard library is required."""
import hashlib
import io
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import ssl
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


CA_FILES = ('/etc/ssl/certs/ca-certificates.crt', '/etc/ssl/cert.pem', '/etc/pki/tls/certs/ca-bundle.crt')


def tls_context():
    """Certificate store that works inside Decky's bundled Python.

    Decky Loader's PyInstaller build looks for CA certificates where its build
    system kept them (/usr/lib/ssl), which SteamOS lacks, so the default context
    rejects every HTTPS certificate. Decky ships certifi for its own requests.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass
    for path in CA_FILES:
        if os.path.isfile(path):
            try:
                return ssl.create_default_context(cafile=path)
            except (OSError, ssl.SSLError):
                continue
    return ssl.create_default_context()


def network_reason(error):
    reason = getattr(error, 'reason', error)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return 'secure connection could not be verified'
    if isinstance(reason, (TimeoutError, OSError)) and 'timed out' in str(reason):
        return 'connection timed out'
    return 'no connection'


def trusted_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host == 'api.curseforge.com' or host.endswith('.forgecdn.net')))


def api_url(url):
    """The API key is only ever sent to this host, never to download CDNs."""
    return trusted_url(url) and urllib.parse.urlsplit(url).hostname == 'api.curseforge.com'


def read_key_file(path):
    """Return the API key stored in a text file the user picked: its first non-empty line."""
    file = Path(path).expanduser()
    try:
        if not file.is_absolute() or not file.is_file() or file.stat().st_size > 4096:
            raise UserError('Select a small text file containing only your CurseForge API key.')
        lines = file.read_text(encoding='utf-8-sig').split()
    except (OSError, UnicodeDecodeError):
        raise UserError('Could not read that file as text.') from None
    key = lines[0] if len(lines) == 1 else ''
    if not 20 <= len(key) <= 200 or not key.isprintable():
        raise UserError('That file does not contain a CurseForge API key. It should hold the key and nothing else.')
    return key


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not trusted_url(newurl):
            raise UserError('Download redirected outside CurseForge; request refused.')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and not api_url(newurl):
            for store in (redirected.headers, redirected.unredirected_hdrs):
                for name in [n for n in store if n.lower() == 'x-api-key']:
                    del store[name]
        return redirected


def hashes_match(data, file):
    hashes = [h for h in file.get('hashes', []) if h.get('algo') in (1, 2) and isinstance(h.get('value'), str)]
    return bool(hashes) and all(
        hashlib.new('sha1' if h['algo'] == 1 else 'md5', data).hexdigest().lower() == h['value'].lower() for h in hashes)


def download_page(website, file_id):
    """CurseForge's own download page for one file, or '' when the project link is unexpected."""
    parsed = urllib.parse.urlsplit(website or '')
    if (parsed.scheme != 'https' or parsed.hostname != 'www.curseforge.com' or parsed.query or parsed.fragment
            or not re.fullmatch(r'/wow/addons/[a-z0-9-]+', parsed.path or '') or not isinstance(file_id, int)):
        return ''
    return f'https://www.curseforge.com{parsed.path}/download/{file_id}'


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

    def request(self, url, limit, body=None):
        if not self.key:
            raise UserError('Save a CurseForge API key in Setup first.')
        if not trusted_url(url):
            raise UserError('CurseForge returned an unsupported download URL.')
        request = urllib.request.Request(url, headers={'User-Agent': 'CurseDeck/0.1', 'Accept': '*/*'})
        if body is not None:
            if not api_url(url):
                raise UserError('Refusing to send data outside the CurseForge API.')
            request.data = json.dumps(body).encode()
            request.add_header('Content-Type', 'application/json')
        if api_url(url):
            request.add_header('x-api-key', self.key)
        try:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()), SafeRedirect())
            with opener.open(request, timeout=45) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise UserError('Download exceeds the supported size limit.')
                return body
        except urllib.error.HTTPError as error:
            messages = {401: 'CurseForge rejected the API key.',
                        403: 'CurseForge denied access or the author disabled third-party downloads.',
                        429: 'CurseForge rate limit reached. Try again later.'}
            raise UserError(messages.get(error.code, f'CurseForge request failed (HTTP {error.code}).')) from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise UserError(f'Could not reach CurseForge ({network_reason(error)}). Check your connection and try again.') from None

    def api(self, route, **params):
        url = 'https://api.curseforge.com/v1/' + route
        if params:
            url += '?' + urllib.parse.urlencode(params)
        return json.loads(self.request(url, 8 * 1024 * 1024))['data']

    def post(self, route, body):
        return json.loads(self.request('https://api.curseforge.com/v1/' + route, 8 * 1024 * 1024, body))['data']

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
                    or path.parts[0].startswith('.')  # Hidden files inside an addon (.gitignore) are fine.
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

    def key_from_file(self, path):
        return read_key_file(path)

    def editions(self, key):
        return self.client_factory(key.strip() or self.settings()['key']).api(f'games/{GAME_ID}/version-types')

    def search(self, query, index=0):
        settings = self.settings()
        if not settings['flavor']:
            raise UserError('Complete Setup before searching.')
        return self.client().api('mods/search', gameId=GAME_ID, searchFilter=query[:200],
                                 gameVersionTypeId=settings['flavor'], sortField=2, sortOrder='desc',
                                 pageSize=20, index=max(0, min(int(index), 9980)))

    def fingerprints(self, root, folders):
        """Folder fingerprints, cached until a file in the folder changes."""
        from fingerprint import folder_fingerprint
        cache_file = self.settings_file.parent / 'fingerprints.json'
        try:
            cache = json.loads(cache_file.read_text())
        except (OSError, ValueError):
            cache = {}
        result, fresh = {}, {}
        for name in folders:
            folder = root / name
            signature = []
            for dirpath, dirnames, filenames in os.walk(folder):
                dirnames.sort()
                for file in sorted(filenames):
                    try:
                        info = os.lstat(os.path.join(dirpath, file))
                    except OSError:
                        continue
                    signature.append(f'{os.path.relpath(os.path.join(dirpath, file), folder)}:{info.st_size}:{info.st_mtime_ns}')
            digest = hashlib.sha256('\n'.join(signature).encode('utf-8', 'surrogateescape')).hexdigest()
            key = str(folder)
            cached = cache.get(key)
            if isinstance(cached, dict) and cached.get('signature') == digest:
                fingerprint = cached.get('fingerprint')
            else:
                computed = folder_fingerprint(folder)
                fingerprint = computed[0] if computed else None
            fresh[key] = {'signature': digest, 'fingerprint': fingerprint}
            if fingerprint is not None:
                result[name] = fingerprint
        cache = {k: v for k, v in cache.items() if not k.startswith(str(root) + os.sep)}
        cache.update(fresh)
        atomic_json(cache_file, cache)
        return result

    def match_existing(self, root, state, client):
        """Adopt addons installed another way when CurseForge recognises their exact files.

        Nothing on disk changes. An adopted addon is updated like one CurseDeck
        installed: its folders are replaced by the newer release.
        """
        owned = {f.casefold() for m in state['addons'].values() for f in m['folders']}
        local = {p.name.casefold(): p.name for p in root.iterdir()
                 if p.is_dir() and not p.is_symlink() and not p.name.startswith('.') and p.name.casefold() not in owned}
        summary = {'matched': 0, 'unmatched': [], 'modified': []}
        if not local:
            return summary
        prints = self.fingerprints(root, sorted(local.values()))
        if not prints:
            summary['unmatched'] = sorted(local.values())
            return summary
        data = client.post(f'fingerprints/{GAME_ID}', {'fingerprints': sorted(set(prints.values()))})
        records = {}
        claimed = set()
        for match in data.get('exactMatches') or []:
            file = match.get('file') or {}
            modules = file.get('modules') or []
            if not isinstance(match.get('id'), int) or not isinstance(file.get('id'), int) or not modules:
                continue
            if str(match['id']) in state['addons'] or str(match['id']) in records:
                continue
            folders, usable = [], True
            for module in modules:
                name = module.get('name')
                if not isinstance(name, str) or not name or Path(name).name != name or name.startswith('.'):
                    usable = False
                    break
                present = local.get(name.casefold())
                if present is None:
                    continue  # Not installed locally; a later update adds it.
                if prints.get(present) != module.get('fingerprint'):
                    summary['modified'].append(present)
                    usable = False
                    break
                folders.append(present)
            if not usable or not folders or claimed & {f.casefold() for f in folders}:
                continue
            claimed.update(f.casefold() for f in folders)
            records[str(match['id'])] = {'id': match['id'], 'name': folders[0], 'fileId': file['id'],
                                         'version': str(file.get('displayName') or file['id']),
                                         'folders': sorted(folders), 'adopted': True}
        if records:
            try:
                for mod in client.post('mods', {'modIds': [r['id'] for r in records.values()]}):
                    if str(mod.get('id')) in records and isinstance(mod.get('name'), str) and mod['name'].strip():
                        records[str(mod['id'])]['name'] = mod['name'].strip()[:200]
            except UserError:
                pass  # Folder names still identify the addons.
            state['addons'].update(records)
            validate_registry(state)
            atomic_json(root / '.cursedeck.json', state)
        summary['matched'] = len(records)
        summary['unmatched'] = sorted(name for key, name in local.items() if key not in claimed
                                      and name not in summary['modified'])
        return summary

    def installed(self, check=False):
        with self.lock:
            root, state = self.state()
            matching = None
            if check:
                matching = self.match_existing(root, state, self.client())
            result = []
            blocked = {}
            if check and state['addons']:
                try:
                    projects = self.client().post('mods', {'modIds': [m['id'] for m in state['addons'].values()]})
                    blocked = {m.get('id'): (m.get('links') or {}).get('websiteUrl') for m in projects
                               if m.get('allowModDistribution') is False}
                except UserError:
                    pass  # Installing still checks each project before downloading.
            for mod in state['addons'].values():
                item = dict(mod, update=None, error=None, blocked=mod['id'] in blocked,
                            missing=any((root / f).is_symlink() or not (root / f).is_dir()
                                or not any(p.is_file() and p.suffix.lower() == '.toc'
                                           for p in (root / f).iterdir()) for f in mod['folders']))
                if check:
                    try:
                        latest = self.client().latest(mod['id'], state['flavor'])
                        if latest['id'] > mod['fileId']:
                            item['update'] = latest['displayName']
                            if item['blocked']:
                                item['download'] = {'fileName': str(latest.get('fileName') or ''),
                                                    'page': download_page(blocked[mod['id']], latest['id'])}
                    except UserError as error:
                        item['error'] = str(error)
                result.append(item)
            managed = {f.casefold() for m in state['addons'].values() for f in m['folders']}
            unmanaged = sorted(p.name for p in (root.iterdir() if root.exists() else []) if p.is_dir()
                               and not p.name.startswith('.') and p.name.casefold() not in managed)
            from local_addons import read_addon
            local = [read_addon(root / name, Path(self.settings()['path']).name) for name in unmanaged]
            library = {'addons': result, 'unmanaged': unmanaged, 'localAddons': local, 'path': str(root)}
            if matching is not None:
                library['matching'] = matching
            return library

    def install(self, mod_id, downloaded=None):
        """Install a project and its required dependencies.

        ``downloaded`` is a ZIP the player fetched from CurseForge's website for a
        project whose author disallows third-party downloads. It is installed only
        if its size and checksums match the release CurseForge lists.
        """
        local = None
        if downloaded:
            path = Path(downloaded)
            try:
                if not path.is_absolute() or not path.is_file() or path.suffix.lower() != '.zip':
                    raise UserError('Choose the addon ZIP file you downloaded.')
                if path.stat().st_size > MAX_DOWNLOAD:
                    raise UserError('Download exceeds the supported size limit.')
                local = path.read_bytes()
            except OSError:
                raise UserError('Could not read that ZIP file.') from None
        with self.lock:
            if not self.settings()['flavor']:
                raise UserError('Select and save your CurseForge WoW edition in Setup before installing addons.')
            root, state = self.state()
            self.root(create=True)
            client = self.client()
            plan = {}

            requested = int(mod_id)

            def resolve(project_id):
                if project_id in plan:
                    return
                if len(plan) >= 40:
                    raise UserError('Dependency tree is too large.')
                mod = client.api(f'mods/{project_id}')
                if mod['gameId'] != GAME_ID:
                    raise UserError('This addon is not available for third-party WoW installation.')
                file = None
                if mod.get('allowModDistribution') is False:
                    if project_id != requested:
                        if str(project_id) in state['addons']:
                            return  # Keep the installed copy; it is updated through its own download.
                        raise UserError(f'{mod["name"]} is required. Its author only allows downloads through '
                                        'CurseForge, so install it first from its own downloaded ZIP.')
                    if local is None:
                        raise UserError(f'{mod["name"]} can only be downloaded through CurseForge. Open its download '
                                        'page, then install the downloaded ZIP.')
                    file = client.latest(project_id, state['flavor'])
                    if len(local) != file['fileLength'] or not hashes_match(local, file):
                        raise UserError(f'That ZIP is not {file.get("fileName") or "the expected release"}. Download '
                                        'the file from the link shown and choose it again.')
                plan[project_id] = (mod, file or client.latest(project_id, state['flavor']))
                for dependency in plan[project_id][1].get('dependencies', []):
                    if dependency['relationType'] == 3:
                        resolve(dependency['modId'])

            resolve(requested)
            # Stage all dependencies before touching the live installation.
            with tempfile.TemporaryDirectory(prefix='.cursedeck-', dir=root) as temp:
                stage = Path(temp)
                records = {}
                claimed = {}
                for project_id, (mod, file) in plan.items():
                    old = state['addons'].get(str(project_id))
                    if old and old['fileId'] > file['id']:
                        continue  # Never silently downgrade an installed release.
                    if project_id == requested and local is not None and mod.get('allowModDistribution') is False:
                        data = local
                    else:
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
                    # Another CurseDeck-managed project may bundle the same folder (Questie ships
                    # QuestieTrace); the release being installed takes it over. Folders CurseDeck
                    # does not manage are never overwritten.
                    if folder in existing and (owners.get(folder) is None or existing[folder].is_symlink()):
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
                    for key, other in list(state['addons'].items()):
                        if key in records:
                            continue
                        kept = [f for f in other['folders'] if f.casefold() not in claimed]
                        if not kept:
                            del state['addons'][key]
                        elif len(kept) != len(other['folders']):
                            state['addons'][key] = dict(other, folders=kept)
                    state['addons'].update(records)
                    validate_registry(state)
                    atomic_json(root / '.cursedeck.json', state)
                except BaseException:
                    for folder in placed:
                        shutil.rmtree(root / folder)
                    for folder in moved:
                        os.replace(backup / folder, root / folder)
                    raise
            return self.installed()
