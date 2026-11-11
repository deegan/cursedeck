"""Read installed addon metadata without requiring a CurseForge account."""
import re


def clean_title(value):
    value = re.sub(r'\|c[0-9a-fA-F]{8}|\|r', '', value)
    return re.sub(r'\|[TA].*?\|[ta]', '', value).strip()


def read_addon(folder, edition):
    result = {'folder': folder.name, 'name': folder.name, 'version': None, 'notes': '', 'error': None}
    if folder.is_symlink():
        result['error'] = 'Linked addon folder; automatic management is unavailable.'
        return result
    try:
        manifests = [p for p in folder.iterdir() if p.suffix.lower() == '.toc' and not p.is_symlink() and p.is_file()]
        suffix = {'_retail_': '_mainline', '_classic_era_': '_vanilla'}.get(edition, '')
        def priority(path):
            stem = path.stem.lower()
            return (0 if suffix and stem.endswith(suffix) else 1 if stem == folder.name.lower() else 2, path.name)
        manifests.sort(key=priority)
        if not manifests:
            result['error'] = 'No addon manifest (.toc) found in this folder.'
            return result
        fields = {}
        with manifests[0].open(encoding='utf-8-sig', errors='replace') as stream:
            for line in stream.read(128 * 1024).splitlines():
                if line.startswith('##') and ':' in line:
                    key, value = line[2:].split(':', 1)
                    fields[key.strip().lower()] = value.strip()
        result.update(name=clean_title(fields.get('title', '')) or folder.name,
                      version=fields.get('version') or None, notes=fields.get('notes', ''))
    except OSError:
        result['error'] = 'Could not read addon metadata. Check folder permissions.'
    return result
