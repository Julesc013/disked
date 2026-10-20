"""Actual tiny Git fixtures for exact, bounded, history-free source transport."""
import ast
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
definition = importlib.util.spec_from_file_location('snapshot', ROOT / 'tools/source-snapshot.py')
S = importlib.util.module_from_spec(definition)
definition.loader.exec_module(S)


class SnapshotTests(unittest.TestCase):
    def test_stable_input_ids_and_prerequisites_resolve_at_exact_revision(self):
        def put(name,value):
            path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n')
        (self.source/'code/helper.h').write_text('// owned helper\n')
        put('tools/build-inputs.json',dict(files=['code/main.cpp']))
        put('spec/bundle.json',dict(mandatory_context=[]));put('spec/catalog/concepts.json',dict(concepts=[]));put('spec/catalog/decisions.json',dict(decisions=[]))
        put('spec/work/units.json',dict(units=[dict(id='DE-TEST',context=[],required_inputs=['stable:old-module-name'],allowed_paths=['code/**'])]))
        registry=dict(always=[],inputs=[dict(id='stable:old-module-name',path='code/main.cpp',kind='build',delivery='artifact',depends_on=['stable:helper'],spec_ids=[]),dict(id='stable:helper',path='code/helper.h',kind='build',delivery='artifact',depends_on=[],spec_ids=[])])
        put('spec/catalog/input-dependencies.json',registry);self.commit();revision=self.git('rev-parse','HEAD')
        selected=S.selected_inputs(self.source,'DE-TEST',revision=revision)
        self.assertIn('code/main.cpp',selected);self.assertIn('code/helper.h',selected);self.assertNotIn('stable:old-module-name',selected)
        registry['inputs'][0]['path']='unselected/bulk.bin';put('spec/catalog/input-dependencies.json',registry)
        self.assertEqual(S.selected_inputs(self.source,'DE-TEST',revision=revision),selected)
        self.assertIn('unselected/bulk.bin',S.selected_inputs(self.source,'DE-TEST'))
    def test_registered_native_python_inputs_are_transported(self):
        cmake=(ROOT/'CMakeLists.txt').read_text(encoding='utf-8')
        scripts=set(re.findall(r'\$\{CMAKE_CURRENT_SOURCE_DIR\}/((?:tests|tools)/[A-Za-z0-9_./-]+\.py)',cmake))
        self.assertTrue(scripts)
        selected=set(S.selected_inputs(ROOT,'DE-W105'))
        self.assertFalse(scripts-selected,'Native source transport omitted registered Python inputs')

    def test_semantic_validator_siblings_are_transported(self):
        selected = set(S.selected_inputs(ROOT, 'DE-W105'))
        directory = ROOT / 'spec/tools'
        tree = ast.parse((directory / 'specctl.py').read_bytes())
        siblings = {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                    and (directory / (node.module + '.py')).is_file()}
        self.assertGreaterEqual(len(siblings), 3)
        self.assertFalse({'spec/tools/' + name + '.py' for name in siblings} - selected,
                         'Native source transport omitted a local semantic validator')

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

    def test_materialization_ignores_caller_git_routing_and_config(self):
        manifest=self.export();outside=self.case/'outside';outside.mkdir();config=outside/'config'
        config.write_bytes(b'[core]\n\tbare = true\n')
        overrides=dict(GIT_DIR=str(outside/'wrong-repository'),GIT_WORK_TREE=str(outside),
                       GIT_CONFIG=str(config),GIT_CONFIG_GLOBAL=str(config),GIT_INDEX_FILE=str(outside/'wrong-index'),
                       GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='core.worktree',GIT_CONFIG_VALUE_0=str(outside),GIT_TRACE=str(outside/'trace'))
        with mock.patch.dict(os.environ,overrides):
            S.materialize(self.case/'export/source.pack',manifest,self.case/'checkout')
            self.assertTrue(all(os.environ[k]==v for k,v in overrides.items()))
        self.assertEqual(config.read_bytes(),b'[core]\n\tbare = true\n')
        self.assertEqual({p.name for p in outside.iterdir()},{'config'})
        self.assertEqual(S.git(self.case/'checkout','status','--porcelain'),b'')

    def test_large_excluded_tree_uses_only_exact_selected_paths(self):
        special='code/name with space-\u03bb.cpp'
        (self.source/special).write_bytes(b'int selected_name;\n');self.commit()
        blob=self.git('rev-parse','HEAD:unselected/bulk.bin')
        def plumbing(*arguments,data=None):
            r=subprocess.run(['git','-C',str(self.source),*arguments],input=data,capture_output=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr);return r.stdout.strip()
        # Tens of thousands of tracked paths, with no corresponding disk files.
        entries=b''.join(('100644 blob '+blob+'\tunused-'+str(i).zfill(5)+'.bin\n').encode() for i in range(64000))
        subtree=plumbing('mktree',data=entries)
        tree=plumbing('mktree',data=plumbing('ls-tree','HEAD')+b'\n040000 tree '+subtree+b'\tarchive\n')
        revision=plumbing('-c','user.name=DiskEd fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false',
                          'commit-tree',tree.decode(),'-p',self.git('rev-parse','HEAD'),'-m','virtual excluded paths').decode()
        manifest=S.export(self.source,['.gitattributes','.gitignore','code/main.cpp',special],self.case/'export',self.work,revision=revision)
        destination=self.case/'checkout';phases=[]
        result=S.materialize(self.case/'export/source.pack',manifest,destination,progress=phases.append)
        self.assertEqual(result['revision'],revision);self.assertEqual((destination/special).read_bytes(),b'int selected_name;\n')
        self.assertFalse((destination/'archive').exists());self.assertFalse((destination/'unselected').exists())
        self.assertEqual(S.git(destination,'status','--porcelain'),b'');S.git(destination,'diff','--quiet','HEAD','--')
        self.assertTrue(S.git(destination,'ls-files','-v','--','archive/unused-00000.bin').startswith(b'S '))
        self.assertTrue(S.git(destination,'ls-files','-v','--','code/main.cpp').startswith(b'H '))
        self.assertTrue(phases);self.assertEqual(phases[-1]['state'],'complete')

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
        (self.source / 'spec/catalog').mkdir()
        for name,value in [('bundle.json',dict(mandatory_context=[])),('catalog/concepts.json',dict(concepts=[])),('catalog/decisions.json',dict(decisions=[])),
                           ('catalog/input-dependencies.json',dict(always=[],inputs=[dict(id='.gitignore',path='.gitignore',kind='build',delivery='artifact',depends_on=[],spec_ids=[])]))]:
            (self.source/'spec'/name).write_text(json.dumps(value))
        (self.source / 'spec/work/units.json').write_text(json.dumps([
            {'id': 'DE-WTEST', 'required_inputs': ['.gitignore'],'context':[],'allowed_paths':['code/**']}]))
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
