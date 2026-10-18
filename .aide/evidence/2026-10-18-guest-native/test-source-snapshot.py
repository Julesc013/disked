"""Actual tiny Git fixtures for exact, bounded, history-free source transport."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
definition = importlib.util.spec_from_file_location('snapshot', HERE / 'source-snapshot.py')
S = importlib.util.module_from_spec(definition)
definition.loader.exec_module(S)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(os.environ['DISKED_WORK_ROOT'])
        self.case = self.work / self._testMethodName
        self.case.mkdir()
        self.source = self.case / 'source'
        self.source.mkdir()
        empty = self.case / 'empty-template'
        empty.mkdir()
        self.git('init', '-q', '--template=' + str(empty))
        (self.source / '.gitattributes').write_bytes(b'* text eol=lf\n')
        (self.source / 'code').mkdir()
        (self.source / 'code/main.cpp').write_bytes(b'int main() { return 1; }\n')
        (self.source / 'unselected').mkdir()
        (self.source / 'unselected/bulk.bin').write_bytes(os.urandom(1048576))
        self.commit()
        (self.source / 'code/main.cpp').write_bytes(b'int main() { return 0; }\n')
        self.commit()

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
        return S.export(self.source, ['.gitattributes', 'code/main.cpp'], self.case / name, self.work)

    def test_exact_clean_sparse_head_without_history_or_unselected_blob(self):
        manifest = self.export()
        destination = self.case / 'checkout'
        result = S.materialize(self.case / 'export/source.pack', manifest, destination)
        self.assertEqual(result['revision'], self.git('rev-parse', 'HEAD'))
        self.assertEqual((destination / 'code/main.cpp').read_bytes(), b'int main() { return 0; }\n')
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
    import io
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotTests)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    import hashlib
    record = {'status': 'pass' if result.wasSuccessful() else 'fail', 'tests_run': result.testsRun,
              'source_sha256': hashlib.sha256((HERE / 'source-snapshot.py').read_bytes()).hexdigest(),
              'failures': len(result.failures), 'errors': len(result.errors), 'log': log.getvalue()}
    (HERE / 'source-snapshot-tests.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in record.items() if k != 'log'}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
