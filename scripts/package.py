"""Create the directory layout expected by Decky's ZIP installer."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent.parent
bundle = root / 'dist' / 'index.js'
if not bundle.is_file():
    raise SystemExit('Missing dist/index.js. Run npm run build first.')
out = root / 'out' / 'CurseDeck.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in ('plugin.json', 'package.json', 'main.py', 'backend.py', 'README.md', 'dist/index.js'):
        archive.write(root / name, 'CurseDeck/' + name)
print(out)
