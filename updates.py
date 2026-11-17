"""Public GitHub release checks. Installation is delegated to Decky Loader."""
import json
import hashlib
import io
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
import re
import threading
import time
import urllib.error
import urllib.request

from backend import UserError, atomic_json, network_reason, tls_context

REPOSITORY = 'deegan/cursedeck'
RELEASE_API = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
BASE = f'https://github.com/{REPOSITORY}/releases/download/'


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise UserError('Release version must use major.minor.patch format.')
    return tuple(int(part) for part in value.split('.'))


def read_json(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'CurseDeck-Updater', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15, context=tls_context()) as response:
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise UserError('Release metadata is too large.')
        return json.loads(body)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        if error.code in (403, 429):
            raise UserError('GitHub rate limit or access restriction. Try checking again later.') from None
        raise UserError(f'GitHub release check failed (HTTP {error.code}).') from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise UserError(f'Could not check GitHub releases ({network_reason(error)}). Try again when connected.') from None
    except (ValueError, TypeError):
        raise UserError('GitHub returned invalid release metadata.') from None


class ReleaseUpdater:
    def __init__(self, settings_dir, current_version, fetch=read_json):
        self.path = Path(settings_dir) / 'updates.json'
        self.current = current_version
        version_tuple(current_version)
        self.fetch = fetch
        self.lock = threading.RLock()
        self.cached = None
        self.checked_at = 0
        self.attempt_path = Path(settings_dir) / 'update-attempt.json'

    def attempt(self):
        if not self.attempt_path.exists():
            return None
        attempt = json.loads(self.attempt_path.read_text())
        if version_tuple(self.current) >= version_tuple(attempt['target']):
            return dict(attempt, status='installed', message=f"Installed CurseDeck {self.current}.")
        return attempt

    def status(self):
        with self.lock:
            return dict(self.cached or self.empty(), **self.preferences(), lastAttempt=self.attempt())

    def prepare(self, download=None):
        with self.lock:
            update = self.check(force=True)
            if not update['available']:
                raise UserError('No newer CurseDeck release is available.')
            try:
                data = (download or download_package)(update['artifact'])
                if hashlib.sha256(data).hexdigest() != update['sha256']:
                    raise UserError('The update checksum did not match. The installed plugin was not changed.')
                validate_package(data, update['version'])
                folder = self.path.parent / 'update-cache' / (update['version'] + '-' + update['sha256'])
                folder.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=folder)
                try:
                    with os.fdopen(fd, 'wb') as out:
                        out.write(data)
                        out.flush()
                        os.fsync(out.fileno())
                    destination = folder / 'CurseDeck.zip'
                    os.replace(temporary, destination)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
                atomic_json(self.attempt_path, {'target':update['version'], 'status':'pending',
                    'message':f"Update to {update['version']} prepared. Confirm Decky's dialog. If this version remains after installation, the update did not complete.",
                    'time':time.time()})
                # Decky's file:// installer strips the prefix without URL-decoding.
                return dict(update, installArtifact='file://' + str(destination.resolve()))
            except Exception as error:
                atomic_json(self.attempt_path, {'target':update['version'], 'status':'failed',
                    'message':str(error) if isinstance(error, UserError) else 'Could not stage the update package. Check disk space and plugin logs.',
                    'time':time.time()})
                raise

    def handoff_failed(self, message):
        with self.lock:
            attempt = self.attempt()
            if attempt and attempt['status'] != 'installed':
                atomic_json(self.attempt_path, dict(attempt, status='failed', message=str(message)[:500]))
            return self.status()

    def preferences(self):
        if self.path.exists():
            return {'automaticChecks': bool(json.loads(self.path.read_text()).get('automaticChecks', True))}
        return {'automaticChecks': True}

    def set_automatic_checks(self, enabled):
        with self.lock:
            atomic_json(self.path, {'automaticChecks': bool(enabled)})
            return self.preferences()

    def check(self, force=False):
        with self.lock:
            prefs = self.preferences()
            if not force and (not prefs['automaticChecks'] or
                              (self.cached is not None and time.monotonic() - self.checked_at < 6 * 3600)):
                return dict(self.cached or self.empty(), **prefs, lastAttempt=self.attempt())
            release = self.fetch(RELEASE_API)
            result = self.empty()
            if release is not None:
                if not isinstance(release, dict):
                    raise UserError('GitHub returned invalid release metadata.')
                tag = release.get('tag_name', '')
                version = tag.removeprefix('v')
                remote = version_tuple(version)
                if tag != 'v' + version:
                    raise UserError('Release tags must start with v.')
                if not release.get('draft') and not release.get('prerelease') and remote > version_tuple(self.current):
                    expected = BASE + tag + '/CurseDeck.zip'
                    manifest_url = BASE + tag + '/update.json'
                    assets = release.get('assets', [])
                    if (not any(a.get('name') == 'CurseDeck.zip' and a.get('browser_download_url') == expected for a in assets)
                            or not any(a.get('name') == 'update.json' and a.get('browser_download_url') == manifest_url for a in assets)):
                        raise UserError('The latest release is missing its installable package or update manifest.')
                    manifest = self.fetch(manifest_url)
                    if (not isinstance(manifest, dict) or manifest.get('version') != version
                            or manifest.get('artifact') != expected
                            or not isinstance(manifest.get('sha256'), str)
                            or not re.fullmatch('[a-f0-9]{64}', manifest['sha256'])):
                        raise UserError('The release update manifest is invalid.')
                    result.update(available=True, version=version, artifact=expected, sha256=manifest['sha256'])
            result['checked'] = True
            self.cached = result
            self.checked_at = time.monotonic()
            return dict(result, **prefs, lastAttempt=self.attempt())

    def empty(self):
        return {'current': self.current, 'available': False, 'version': None,
                'artifact': None, 'sha256': None, 'checked': False}


def download_package(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'CurseDeck-Updater'}), timeout=45, context=tls_context()) as response:
            data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise UserError('The plugin update exceeds the supported download size.')
        return data
    except (urllib.error.URLError, TimeoutError) as error:
        raise UserError(f'Could not download the plugin update ({network_reason(error)}). Check your connection and retry.') from None


def validate_package(data, version):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 64 * 1024 * 1024:
                raise UserError('The update archive is too large.')
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (not path.parts or path.parts[0] != 'CurseDeck' or path.is_absolute()
                        or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename
                        or stat.S_ISLNK(entry.external_attr >> 16)
                        or str(path).casefold() in seen):
                    raise UserError('The update archive contains unsafe or duplicate paths.')
                seen.add(str(path).casefold())
            required = {'CurseDeck/plugin.json', 'CurseDeck/package.json', 'CurseDeck/main.py',
                        'CurseDeck/backend.py', 'CurseDeck/dist/index.js'}
            if not required.issubset(set(archive.namelist())):
                raise UserError('The update is missing required plugin files.')
            if json.loads(archive.read('CurseDeck/package.json')).get('version') != version:
                raise UserError('The downloaded package version does not match the release.')
            if json.loads(archive.read('CurseDeck/plugin.json')).get('name') != 'CurseDeck':
                raise UserError('The downloaded package is not CurseDeck.')
            if archive.testzip() is not None:
                raise UserError('The update archive is corrupt.')
    except (zipfile.BadZipFile, ValueError, KeyError) as error:
        raise UserError('The downloaded plugin package is invalid.') from error
