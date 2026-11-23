"""Find the CurseForge release in Downloads or a matching GitHub or Wago release."""
from html.parser import HTMLParser
import http.client
import json
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request

from backend import MAX_DOWNLOAD, UserError, hashes_match, network_reason, release_hashes, tls_context


REPOSITORY = r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+'
ASSET_HOSTS = {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}


def _https_url(url):
    if not isinstance(url, str) or not url or any(c.isspace() or ord(c) < 32 or c == '\\' for c in url):
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme == 'https' and parsed.hostname and parsed.port in (None, 443)
                and parsed.username is None and parsed.password is None and not parsed.fragment):
            return parsed
    except ValueError:
        pass
    return None


def github_repository(source_url):
    parsed = _https_url(source_url)
    if not parsed or parsed.hostname != 'github.com' or parsed.query:
        return ''
    match = re.fullmatch(r'/(' + REPOSITORY + r')(?:/tree/[^?#]+|/(?:wiki|issues)(?:/[a-zA-Z0-9_-]+)?)?/?', parsed.path)
    if not match:
        return ''
    repository = match[1].removesuffix('.git')
    return repository if repository.split('/')[1] not in ('', '.', '..') else ''


def _asset_path(url):
    parsed = _https_url(url)
    if not parsed or parsed.hostname != 'github.com' or parsed.query:
        return None
    match = re.fullmatch(r'/(' + REPOSITORY + r')/releases/download/([^/]+)/([^/]+)', parsed.path)
    if not match:
        return None
    repository, tag, name = match.groups()
    decoded_tag, decoded_name = urllib.parse.unquote(tag), urllib.parse.unquote(name)
    if (repository.split('/')[1] in ('.', '..') or '/' in decoded_name or
            any(part in ('', '.', '..') for part in [*decoded_tag.split('/'), decoded_name]) or
            any(c == '\\' or ord(c) < 32 for c in decoded_tag + decoded_name)):
        return None
    return repository, decoded_name


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = _https_url(newurl)
        origin = urllib.parse.urlsplit(req.full_url)
        if origin.hostname in ('addons.wago.io', 'cdn.wago.io'):
            if origin.path.startswith('/addons/'):
                allowed = parsed and parsed.hostname == origin.hostname and parsed.path == origin.path
            else:
                allowed = parsed and parsed.hostname == 'cdn.wago.io'
        elif origin.hostname == 'api.github.com':
            allowed = (parsed and parsed.hostname == 'api.github.com' and
                       re.fullmatch(r'/(?:repos/' + REPOSITORY + r'|repositories/[0-9]+)/releases', parsed.path))
        else:
            allowed = parsed and parsed.hostname in ASSET_HOSTS
        if not allowed:
            raise UserError('The release request redirected to an unsupported URL.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read(url, limit, metadata=False, service='GitHub'):
    accept = 'application/octet-stream'
    if metadata:
        accept = 'text/html' if service == 'Wago' else 'application/vnd.github+json'
    request = urllib.request.Request(url, headers={
        'User-Agent': 'CurseDeck', 'Accept': accept})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()), ReleaseRedirect())
    try:
        with opener.open(request, timeout=15 if metadata else 45) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise UserError(f'The {service} release exceeds the supported size.')
        return data
    except urllib.error.HTTPError as error:
        error.close()
        if metadata and error.code == 404:
            return None
        if error.code in (403, 429):
            raise UserError(f'{service} rate limit or access restriction. Try again later.') from None
        raise UserError(f'{service} release request failed (HTTP {error.code}).') from None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
        raise UserError(f'Could not fetch the {service} release ({network_reason(error)}).') from None


def _usable_archive(file):
    name, size = file.get('fileName'), file.get('fileLength')
    return (isinstance(name, str) and name.lower().endswith('.zip') and not name.startswith('.')
            and not any(c in '/\\:' or ord(c) < 32 for c in name)
            and type(size) is int and 0 < size <= MAX_DOWNLOAD and bool(release_hashes(file)))


def local_release_zip(downloads, file):
    if downloads is None or not downloads.is_absolute() or not _usable_archive(file):
        return None
    size = file['fileLength']
    try:
        directory = os.open(downloads, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            # O_PATH pins the inode without opening a device or waiting for a FIFO.
            candidate = os.open(file['fileName'], os.O_PATH | os.O_NOFOLLOW, dir_fd=directory)
        finally:
            os.close(directory)
        try:
            info = os.fstat(candidate)
            if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                return None
            # Read the pinned regular file even if the browser replaces its directory entry.
            with open(f'/proc/self/fd/{candidate}', 'rb') as archive:
                data = archive.read(size + 1)
        finally:
            os.close(candidate)
    except OSError:
        return None
    return data if len(data) == size and hashes_match(data, file) else None


def find_release_asset(source_url, file):
    repository = github_repository(source_url)
    if not repository or not _usable_archive(file):
        return ''
    name, size = file['fileName'], file['fileLength']
    data = _read(f'https://api.github.com/repos/{repository}/releases?per_page=10', 4 * 1024 * 1024, metadata=True)
    if data is None:
        return ''
    try:
        releases = json.loads(data)
    except ValueError:
        releases = None
    if not isinstance(releases, list):
        raise UserError('GitHub returned invalid release metadata.')
    for release in releases:
        if (not isinstance(release, dict) or release.get('draft') is not False or release.get('prerelease') is not False
                or not isinstance(release.get('assets'), list)):
            continue
        for asset in release['assets']:
            if (isinstance(asset, dict) and asset.get('state') == 'uploaded'
                    and asset.get('name') == name and asset.get('size') == size):
                url = asset.get('browser_download_url')
                path = _asset_path(url)
                if path and path[0].lower() == repository.lower() and path[1] == name:
                    return url
    return ''


def download_release_asset(url, limit):
    if not _asset_path(url):
        raise UserError('Invalid GitHub release asset URL.')
    if type(limit) is not int or limit <= 0:
        raise UserError('Invalid GitHub release asset size.')
    return _read(url, min(limit, MAX_DOWNLOAD))


class _WagoPage(HTMLParser):
    """Wago embeds its public release listing in the page's data-page attribute."""
    page = None

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            value = dict(attrs).get('data-page')
            if value:
                self.page = json.loads(value)


def wago_release_zip(slug, file):
    if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9-]+', slug) or not _usable_archive(file):
        return None
    data = _read(f'https://addons.wago.io/addons/{slug}/versions', 4 * 1024 * 1024, metadata=True, service='Wago')
    if data is None:
        return None
    page = _WagoPage()
    try:
        page.feed(data.decode('utf-8'))
        props = page.page['props']
        if props['addon']['slug'] != slug:
            return None
        releases = props['releases']['data']
        if not isinstance(releases, list):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise UserError('Wago returned an unreadable release listing.') from None
    mismatched = False
    for release in releases:
        if (not isinstance(release, dict) or release.get('stability') != 'stable'
                or release.get('size') != file['fileLength']):
            continue
        url = release.get('download_link')
        parsed = _https_url(url)
        if parsed and parsed.hostname == 'addons.wago.io' and re.fullmatch(r'/download/[A-Za-z0-9]+', parsed.path):
            data = _read(url, file['fileLength'], service='Wago')
            if len(data) == file['fileLength'] and hashes_match(data, file):
                return data
            mismatched = True
    if mismatched:
        raise UserError('Wago checksum or size mismatch.')
    return None
