"""Actual tiny Git fixtures for exact, bounded, history-free source transport."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
definition = importlib.util.spec_from_file_location('snapshot', ROOT / 'tools/source-snapshot.py')
S = importlib.util.module_from_spec(definition)
definition.loader.exec_module(S)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='disked-source-snapshot-')
        self.work = Path(self.temporary.name)
        self.case = self.work / self._testMethodName
        self.case.mkdir()
        self.source = self.case / 'source'
        self.source.mkdir()
        empty = self.case / 'empty-template'
        empty.mkdir()
        self.git('init', '-q', '--template=' + str(empty))
        (self.source / '.gitattributes').write_bytes(b'* text=auto\n*.cpp text eol=lf\n')
        (self.source / '.gitignore').write_bytes(b'build/\n')
        (self.source / 'code').mkdir()
        (self.source / 'code/main.cpp').write_bytes(b'int main() { return 1; }\n')
        (self.source / 'unselected').mkdir()
        (self.source / 'unselected/bulk.bin').write_bytes(os.urandom(1048576))
        self.commit()
        (self.source / 'code/main.cpp').write_bytes(b'int main() { return 0; }\n')
        self.commit()

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *arguments, check=True):
        result = subprocess.run(['git', '-C', str(self.source), *arguments], capture_output=True, timeout=30)
        if check and result.returncode:
            self.fail(result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def commit(self):
        self.git('add', '--all')
        self.git('-c', 'user.name=DiskEd fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'fixture')

    def export(self, name='export'):
        return S.export(self.source, ['.gitattributes', '.gitignore', 'code/main.cpp'], self.case / name, self.work)

    def test_exact_clean_sparse_head_without_history_or_unselected_blob(self):
        manifest = self.export()
        destination = self.case / 'checkout'
        result = S.materialize(self.case / 'export/source.pack', manifest, destination)
        self.assertEqual(result['revision'], self.git('rev-parse', 'HEAD'))
        self.assertEqual((destination / 'code/main.cpp').read_bytes(), b'int main() { return 0; }\n')
        self.assertEqual((destination / '.gitignore').read_bytes(), b'build/\n')
        self.assertFalse((destination / 'unselected').exists())
        self.assertLess(manifest['pack_bytes'], 65536)
        self.assertEqual(S.git(destination, 'status', '--porcelain'), b'')
        self.assertEqual(S.git(destination, 'rev-list', '--count', 'HEAD').strip(), b'1')
        missing = self.git('rev-parse', 'HEAD:unselected/bulk.bin')
        result = subprocess.run(['git', '-C', str(destination), 'cat-file', '-e', missing], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_dirty_source_refused_before_export(self):
        (self.source / 'code/main.cpp').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'clean'):
            self.export()
        self.assertFalse((self.case / 'export').exists())

    def test_explicit_revision_uses_exact_blobs_and_preserves_dirty_work(self):
        revision = self.git('rev-parse', 'HEAD')
        path = self.source / 'code/main.cpp'
        path.write_bytes(b'unsaved local source')
        manifest = S.export(self.source, ['.gitattributes', '.gitignore', 'code/main.cpp'],
                            self.case / 'export', self.work, revision=revision)
        self.assertTrue(manifest['exporter_worktree_dirty'])
        S.materialize(self.case / 'export/source.pack', manifest, self.case / 'checkout')
        self.assertEqual((self.case / 'checkout/code/main.cpp').read_bytes(), b'int main() { return 0; }\n')
        self.assertEqual(path.read_bytes(), b'unsaved local source')

    def test_revision_requires_exact_commit_id(self):
        for value in ('HEAD', '--help', 'a'*39, 'a'*40+'\n'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'exact Git'):
                S.export(self.source, ['code/main.cpp'], self.case / 'export', self.work, revision=value)
        self.assertFalse((self.case / 'export').exists())

    def test_explicit_revision_uses_reviewed_input_catalogs(self):
        (self.source / 'tools').mkdir()
        (self.source / 'spec/work').mkdir(parents=True)
        catalog = self.source / 'tools/build-inputs.json'
        catalog.write_text(json.dumps({'files': ['code/main.cpp']}))
        (self.source / 'spec/work/units.json').write_text(json.dumps([
            {'id': 'DE-WTEST', 'required_inputs': ['.gitignore']}]))
        self.commit()
        revision = self.git('rev-parse', 'HEAD')
        catalog.write_text(json.dumps({'files': ['unreviewed.cpp']}))
        selected = S.selected_inputs(self.source, 'DE-WTEST', revision=revision)
        self.assertIn('code/main.cpp', selected)
        self.assertNotIn('unreviewed.cpp', selected)

    def test_tampered_pack_refused_before_checkout(self):
        manifest = self.export()
        pack = self.case / 'export/source.pack'
        data = bytearray(pack.read_bytes())
        data[-1] ^= 1
        pack.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'hash'):
            S.materialize(pack, manifest, self.case / 'checkout')
        self.assertFalse((self.case / 'checkout').exists())

    def test_path_escape_and_glob_refused(self):
        for name in ('../escape', 'C:/escape', '.git/HEAD', 'foo\\bar', 'foo/*', 'foo./bar'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                S.relative(name)

    def test_existing_destination_and_source_output_refused(self):
        with self.assertRaisesRegex(ValueError, 'Fresh snapshot'):
            S.export(self.source, ['code/main.cpp'], self.source / 'export', self.work)
        self.assertFalse((self.source / 'export').exists())

    def test_linked_output_ancestor_is_refused(self):
        target = self.case / 'ordinary'
        target.mkdir()
        link = self.case / 'junction'
        subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                       check=True, capture_output=True, timeout=10)
        try:
            with self.assertRaisesRegex(ValueError, 'Linked'):
                S.export(self.source, ['code/main.cpp'], link / 'export', self.work)
            self.assertFalse((target / 'export').exists())
        finally:
            link.rmdir()

    def test_oversized_manifest_refused_before_checkout(self):
        manifest = self.export()
        manifest['content_bytes'] = S.SOURCE_LIMIT + 1
        with self.assertRaisesRegex(ValueError, 'bounded'):
            S.materialize(self.case / 'export/source.pack', manifest, self.case / 'checkout')
        self.assertFalse((self.case / 'checkout').exists())


if __name__ == '__main__':
    unittest.main()
