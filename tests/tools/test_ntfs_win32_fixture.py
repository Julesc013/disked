"""Generate small CMake fixtures without configuring or executing native code."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / 'tools/ntfs-win32-fixture.py'
spec = importlib.util.spec_from_file_location('ntfs_fixture', TOOL)
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


class NtfsWin32FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-fixture-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root, self.work = self.base / 'source', self.base / 'work'
        self.root.mkdir()
        self.work.mkdir()
        self.dump(self.work / 'owner.json', dict(root=str(self.root)))
        self.build = self.work / 'model'
        self.output = self.work / 'fixture'
        self.reply = self.build / '.cmake/api/v1/reply'
        self.reply.mkdir(parents=True)
        self.records = []
        self.target('reader', 'source/portable/reader.c')
        for name in F.VARIANTS:
            definition = [dict(define='DISKED_FIXTURE_FAULT=1')] if name.endswith('_fault') else []
            self.target(name, 'source/providers/' + name.removesuffix('_fault') + '.cpp',
                        ['reader'], definition)
        for name in F.PROBES:
            variant = {'ntfs_file_probe': 'disked_ntfs_file', 'ntfs_file_fault': 'disked_ntfs_file_fault',
                       'ntfs_worker_probe': 'disked_ntfs_worker', 'ntfs_worker_fault': 'disked_ntfs_worker_fault'}.get(name)
            self.target(name, 'tests/native/' + name + '.cpp', ['reader'] + ([variant] if variant else []))
        for header in F.HEADERS:
            self.write(self.root / 'source' / header, '/* standalone fixture */\n')
        for kind in F.TESTS:
            self.write(self.root / 'tests/images' / ('test_ntfs_' + kind + '.py'), 'pass\n')
        self.write(self.root / 'tools/workspace.cmake', '# fixture gate\n')
        self.dump(self.root / 'spec/catalog/native-bootstrap.json',
                  dict(compiler_version='19.44.35228.0', toolset='14.44.35207', sdk='10.0.19041.0',
                       language='C++14', crt='static-release-MT', target_id='windows.nt10.x64.win32'))
        self.model = dict(paths=dict(source=str(self.root), build=str(self.build)),
                          configurations=[dict(name='Release', targets=self.records)])
        self.flush_model()
        self.dump(self.reply / 'index-001.json', dict(objects=[dict(kind='codemodel', version=dict(major=2),
                                                                jsonFile='codemodel.json')]))

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))

    def dump(self, path, value):
        self.write(path, json.dumps(value, indent=2) + '\n')

    def target(self, name, source, dependencies=(), definitions=()):
        self.write(self.root / source, '/* fixture source */\n')
        filename = name + '.json'
        self.records.append(dict(id=name, name=name, jsonFile=filename))
        self.dump(self.reply / filename, dict(sources=[dict(path=source)],
                  dependencies=[dict(id=n) for n in dependencies],
                  compileGroups=[dict(defines=list(definitions))]))

    def flush_model(self):
        self.dump(self.reply / 'codemodel.json', self.model)

    def prepare(self):
        return F.prepare(self.root, self.build, self.output, self.work)

    def test_matches_historical_groups_arguments_headers_and_probes_as_data(self):
        # Read literal expectations only; never import/execute the historical recipe.
        tree = ast.parse((REPO / '.aide/evidence/2026-10-17-ntfs-name-order-command/reproduce-win32.py').read_text())
        old_tests = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == 'tests' for t in n.targets))
        old_probes = next(ast.literal_eval(n.value.generators[0].iter) for n in tree.body
                         if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'probes' for t in n.targets))
        old_headers = next(ast.literal_eval(n.iter.args[0]) for n in tree.body
                           if isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
                           and isinstance(n.iter.func, ast.Name) and n.iter.func.id == 'enumerate')
        expected = {}
        for kind, aliases in F.TESTS.items():
            args = []
            for alias in aliases:
                flag, name = F.ARGUMENTS[alias]
                args += [flag, '$<TARGET_FILE:' + name + '>']
            expected[kind] = args
        self.assertEqual(expected, old_tests)
        self.assertEqual(F.PROBES, old_probes)
        self.assertEqual(F.HEADERS, old_headers)
        self.assertEqual((len(expected), len(F.PROBES), len(F.HEADERS)), (18, 9, 12))

    def test_complete_bounded_generation_and_no_source_mutation(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        result = self.prepare()
        self.assertEqual(result['status'], 'prepared_not_qualified')
        self.assertFalse(result['native_execution_performed'])
        self.assertFalse(result['execution_input_closure_complete'])
        self.assertFalse(result['hard_storage_boundary_demonstrated'])
        self.assertEqual(result['fixture_architecture'], 'Win32')
        self.assertNotIn('target_id', result['compiler_profile'])
        self.assertEqual(len(list(self.output.glob('header-*.cpp'))), 12)
        self.assertLessEqual(sum(p.stat().st_size for p in self.output.iterdir()), F.OUTPUT_LIMIT)
        cmake = (self.output / 'CMakeLists.txt').read_text()
        self.assertEqual(cmake.count('add_test(NAME '), 18)
        self.assertIn('include("' + (self.root / 'tools/workspace.cmake').as_posix() + '")', cmake)
        self.assertIn('--pure "$<TARGET_FILE:ntfs_capture_probe>"', cmake)
        self.assertIn('/GS /sdl /guard:cf', cmake)
        self.assertIn('"19.44.35228.0"', cmake)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.root.rglob('*') if p.is_file()})

    def test_cli_prepares_without_launching_a_compiler(self):
        env = dict(os.environ, DISKED_WORK_ROOT=str(self.work))
        p = subprocess.run([sys.executable, str(TOOL), '--root', str(self.root),
                            '--build', str(self.build), '--output', str(self.output)],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(json.loads(p.stdout)['native_execution_performed'])
        self.assertFalse(list(self.work.rglob('*.exe')))

    def test_missing_header_refuses_before_any_output(self):
        (self.root / 'source' / F.HEADERS[0]).unlink()
        with self.assertRaisesRegex(F.FixtureError, 'Missing'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_wrong_source_root_model_refuses(self):
        self.model['paths']['source'] = str(self.base / 'other')
        self.flush_model()
        with self.assertRaisesRegex(F.FixtureError, 'another source/build'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_output_outside_work_is_preserved(self):
        outside = self.base / 'other-project'
        outside.mkdir()
        self.write(outside / 'keep', 'keep')
        with self.assertRaises(F.FixtureError):
            F.prepare(self.root, self.build, outside, self.work)
        self.assertEqual((outside / 'keep').read_text(), 'keep')

    def test_mismatched_workspace_owner_refuses(self):
        self.dump(self.work / 'owner.json', dict(root=str(self.base / 'other')))
        with self.assertRaisesRegex(F.FixtureError, 'another source checkout'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_escaping_metadata_response_refuses(self):
        self.dump(self.reply / 'index-001.json', dict(objects=[dict(kind='codemodel', version=dict(major=2),
                                                                 jsonFile='../../../../../outside.json')]))
        with self.assertRaises(F.FixtureError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_cycle_refuses_before_output(self):
        p = self.reply / 'reader.json'
        d = json.loads(p.read_bytes())
        d['dependencies'] = [dict(id='ntfs_file_probe')]
        self.dump(p, d)
        with self.assertRaisesRegex(F.FixtureError, 'Cyclic'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_fault_definition_cannot_be_silently_used_as_normal(self):
        p = self.reply / 'disked_ntfs_file.json'
        d = json.loads(p.read_bytes())
        d['compileGroups'] = [dict(defines=[dict(define='DISKED_FIXTURE_FAULT=1')])]
        self.dump(p, d)
        with self.assertRaisesRegex(F.FixtureError, 'Normal/fault'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_oversized_output_refuses_without_truncating_contract(self):
        with mock.patch.object(F, 'OUTPUT_LIMIT', 1):
            with self.assertRaisesRegex(F.FixtureError, 'nothing written'):
                self.prepare()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        self.write(self.output / 'keep', 'keep')
        with self.assertRaises(F.FixtureError):
            self.prepare()
        self.assertEqual((self.output / 'keep').read_text(), 'keep')

    def test_source_runtime_profile_must_match_generated_fixture(self):
        path = self.root / 'spec/catalog/native-bootstrap.json'
        profile = json.loads(path.read_bytes())
        profile['crt'] = 'dynamic-debug'
        self.dump(path, profile)
        with self.assertRaisesRegex(F.FixtureError, 'Unsupported source compiler/runtime'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_linked_source_ancestor_is_not_followed(self):
        folder = self.root / 'source/portable'
        outside = self.base / 'outside-source'
        folder.rename(outside)
        if os.name == 'nt':
            p = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(folder), str(outside)],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
        else:
            folder.symlink_to(outside, target_is_directory=True)
        before = (outside / 'reader.c').read_bytes()
        try:
            with self.assertRaisesRegex(F.FixtureError, 'Linked'):
                self.prepare()
            self.assertFalse(self.output.exists())
            self.assertEqual((outside / 'reader.c').read_bytes(), before)
        finally:
            folder.rmdir() if os.name == 'nt' else folder.unlink()


if __name__ == '__main__':
    unittest.main()
