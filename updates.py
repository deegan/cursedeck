"""Public GitHub release checks. Installation is delegated to Decky Loader."""
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

from backend import UserError, atomic_json

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
        with urllib.request.urlopen(request, timeout=15) as response:
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
    except (urllib.error.URLError, TimeoutError):
        raise UserError('Could not check GitHub releases. Try again when connected.') from None
    except (ValueError, TypeError):
        raise UserError('GitHub returned invalid release metadata.') from None


class ReleaseUpdater:
    def __init__(self, settings_dir, current_version, fetch=read_json):
        self.path = Path(settings_dir) / 'updates.json'
        self.current = current_version
        version_tuple(current_version)
        self.fetch = fetch
        self.lock = threading.Lock()
        self.cached = None
        self.checked_at = 0

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
                return dict(self.cached or self.empty(), **prefs)
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
            return dict(result, **prefs)

    def empty(self):
        return {'current': self.current, 'available': False, 'version': None,
                'artifact': None, 'sha256': None, 'checked': False}
