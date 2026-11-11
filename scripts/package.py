"""Create the directory layout expected by Decky's ZIP installer."""
from pathlib import Path
import zipfile

FILES = ('plugin.json', 'package.json', 'main.py', 'backend.py', 'demo.py', 'README.md', 'dist/index.js')


def package(root):
    root = Path(root)
    for name in FILES:
        if not (root / name).is_file():
            raise ValueError(f'Missing {name}. Run npm run build before packaging.')
    out = root / 'out' / 'CurseDeck.zip'
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(root / name, 'CurseDeck/' + name)
    return out


if __name__ == '__main__':
    print(package(Path(__file__).resolve().parent.parent))
