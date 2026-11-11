"""Exercise install, dependency resolution, update, and repair without network access."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from demo import DemoSession

session = DemoSession()
try:
    manager = session.manager
    library = manager.installed(True)
    assert len(library['addons']) == 2
    assert all(addon['update'] for addon in library['addons'])
    manager.install(1001)
    assert not any(addon['update'] for addon in manager.installed(True)['addons'])
    assert len(manager.search('Raid')) == 1
    manager.install(1002)
    manifest = manager.root() / 'DemoRaidNotes' / 'DemoRaidNotes.toc'
    assert 'Version: 2.0' in manifest.read_text()
    manifest.unlink()
    assert next(a for a in manager.installed()['addons'] if a['id'] == 1002)['missing']
    manager.install(1002)
    assert manifest.is_file()
    print('Offline smoke test passed: search, install, dependencies, update, repair.')
finally:
    session.close()
