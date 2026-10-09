"""Export failures must not create a root or damage pre-existing source data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('export_native', ROOT/'release/bindings/universal-setup/export_native.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class SourceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'upstream'
        self.repo.mkdir()
        self.git('init', '-q')
        self.data = b'original source bytes\n'
        (self.repo/'source.c').write_bytes(self.data)
        self.git('add', 'source.c')
        self.git('-c', 'user.name=DiskEd fixture', '-c', 'user.email=fixture@invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'owned synthetic fixture')
        self.revision = self.git('rev-parse', 'HEAD')
        self.row = dict(path='source.c', bytes=len(self.data), sha256='sha256:'+hashlib.sha256(self.data).hexdigest(),
                        blob=self.git('rev-parse', 'HEAD:source.c'))
        self.lock = dict(revision=self.revision, tree=self.git('rev-parse', 'HEAD^{tree}'), files=[self.row])
        self.lock_path = self.root/'lock.json'
        self.output = self.root/'export'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def export(self):
        self.lock_path.write_text(json.dumps(self.lock), encoding='utf-8', newline='\n')
        with patch.object(exporter, 'LOCK', self.lock_path):
            return exporter.export(self.repo, self.output)

    def test_exact_git_blob_not_dirty_checkout(self):
        (self.repo/'source.c').write_bytes(b'dirty content must not be exported')
        self.export()
        self.assertEqual((self.output/'source.c').read_bytes(), self.data)
        self.assertEqual((self.repo/'source.c').read_bytes(), b'dirty content must not be exported')

    def test_occupied_root_preserves_foreign_file(self):
        self.output.mkdir()
        foreign = self.output/'foreign.bin'
        foreign.write_bytes(b'owned by another operation')
        with self.assertRaisesRegex(ValueError, 'new export root'):
            self.export()
        self.assertEqual(foreign.read_bytes(), b'owned by another operation')

    def test_content_identity_mismatch_creates_nothing(self):
        self.row['sha256'] = 'sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError, 'source content mismatch'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_byte_count_mismatch_creates_nothing(self):
        self.row['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'source content mismatch'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_git_blob_mismatch_creates_nothing(self):
        self.row['blob'] = '0'*40
        with self.assertRaisesRegex(ValueError, 'source blob mismatch'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_tree_mismatch_creates_nothing(self):
        self.lock['tree'] = '0'*40
        with self.assertRaisesRegex(ValueError, 'tree identity mismatch'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_duplicate_path_creates_nothing(self):
        self.lock['files'].append(dict(self.row))
        with self.assertRaisesRegex(ValueError, 'duplicate source path'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_parent_escape_creates_nothing(self):
        self.row['path'] = '../outside.c'
        with self.assertRaisesRegex(ValueError, 'unsafe source path'):
            self.export()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
