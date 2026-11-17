from pathlib import Path
import tempfile
import json
import hashlib
import unittest
import zipfile

from scripts.package import FILES, package


class PackageTests(unittest.TestCase):
    def test_bundle_contains_runtime_modules_but_no_local_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"version":"0.2.0"}' if name == 'package.json' else 'test fixture')
            (root / 'settings.json').write_text('private-key-fixture')
            artifact = package(root)
            metadata = json.loads((root / 'out' / 'update.json').read_text())
            self.assertEqual(metadata['sha256'], hashlib.sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(metadata['version'], '0.2.0')
            self.assertTrue(metadata['artifact'].endswith('/v0.2.0/CurseDeck.zip'))
            with zipfile.ZipFile(artifact) as bundle:
                self.assertEqual(set(bundle.namelist()), {'CurseDeck/' + f for f in FILES})
                self.assertNotIn('CurseDeck/demo.py', bundle.namelist())
                self.assertIsNone(bundle.testzip())

    def test_missing_build_does_not_create_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                package(root)
            self.assertFalse((root / 'out').exists())
