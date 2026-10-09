"""Owned synthetic package tests; no live Setup/installation qualification."""
from contextlib import contextmanager
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('setup_fixture', ROOT / 'release/bindings/universal-setup/package_fixture.py')
pf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pf)


class PackageFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-setup-owned-')
        self.base = Path(self.temp.name)
        self.root = pf.init_fixtures(self.base / 'fixtures')
        self.stage = self.base / 'staging'
        self.stage.mkdir()
        (self.stage / 'disked.exe').write_bytes(b'synthetic-not-a-native-executable\x00' * 10)
        (self.stage / 'share').mkdir()
        (self.stage / 'share/message.txt').write_bytes('Exact fixture bytes, caf\u00e9.\n'.encode())
        self.expected = pf.ac.inventory(self.stage, ['disked.exe'])
        self.info = {'product': 'DiskEd', 'version': '0.1.0-dev.36', 'source_state': 'clean',
                     'source_revision': 'e' * 40, 'input_digest': 'sha256:' + 'a' * 64,
                     'target': 'windows.nt10.x64.win32', 'composition': 'windows.native.image.prototype'}

    def tearDown(self):
        # TemporaryDirectory owns only this generated fixture tree.
        self.temp.cleanup()

    def package(self, name='package'):
        return pf.assemble(self.root, name, self.stage, self.expected, self.info)

    def rewrite(self, root, name, value):
        (root / name).write_bytes(pf.ac.canonical(value) + b'\n')

    def resign_fixture(self, root):
        """Recompute unsigned hashes to test semantic relationships, not authority."""
        lock, _, _ = pf.pinned_contracts()
        self.rewrite(root, 'binding.json', pf.binding(root, lock, pf.read_json(pf.PROFILE)))

    def rejected(self, function, code=None):
        with self.assertRaises(pf.ac.Rejected) as caught:
            function()
        if code:
            self.assertEqual(str(caught.exception), code)

    def test_exact_schema_mapping_and_extracted_bytes(self):
        root = self.package()
        result = pf.verify(root, self.expected, self.info)
        self.assertEqual(result['files'], '2')
        self.assertEqual(result['live_setup'], 'not_run')
        package = pf.read_json(root / 'product-package.json')
        recipe = pf.read_json(root / 'setup-recipe.json')
        self.assertEqual(package['mutable_paths'], [])
        self.assertEqual(package['preserved_paths'], [])
        self.assertEqual(package['authenticity_refs'], [])
        self.assertEqual(recipe['lifecycle_operations'], ['verify'])
        output = pf.extract_fixture(self.root, 'extracted', root, self.expected, self.info)
        self.assertEqual(pf.ac.inventory(output, ['disked.exe']), self.expected)
        for row in self.expected['files']:
            self.assertEqual((output / row['path']).read_bytes(), (self.stage / row['path']).read_bytes())

    def test_deterministic_archive_and_exact_inventory(self):
        first = self.package('first'); second = self.package('second')
        self.assertEqual((first / 'payload.zip').read_bytes(), (second / 'payload.zip').read_bytes())
        self.assertEqual(pf.read_json(first / 'inventory.json'), self.expected)
        with zipfile.ZipFile(first / 'payload.zip') as z:
            self.assertEqual(z.namelist(), [r['path'] for r in self.expected['files']])

    def test_upstream_schema_validation_rejects_independent_field_types(self):
        root = self.package(); package = pf.read_json(root / 'product-package.json')
        _, schemas, registry = pf.pinned_contracts()
        for bad in (None, [], {**package, 'product_version': 36},
                    {**package, 'unknown': True}, {**package, 'source': {}}):
            with self.subTest(value=bad):
                self.rejected(lambda: pf.upstream_validate(bad, 'product_package.v1.schema.json', schemas, registry),
                              'upstream_contract_shape')

    def test_semantically_changed_recipe_refuses_even_with_recomputed_hashes(self):
        root = self.package(); original = pf.read_json(root / 'setup-recipe.json')
        changes = [('product_version', '0.1.0'), ('product_id', 'org.other'),
                   ('component_ids', ['other']), ('package_digest', '0' * 64),
                   ('lifecycle_operations', ['install']), ('rollback_disposition', 'supported'),
                   ('recovery_disposition', 'supported'), ('migrations', [{'migration_id':'x',
                    'from_version':'1', 'to_version':'2', 'required':False}])]
        for field, value in changes:
            with self.subTest(field=field):
                changed = copy.deepcopy(original); changed[field] = value
                self.rewrite(root, 'setup-recipe.json', changed); self.resign_fixture(root)
                self.rejected(lambda: pf.verify(root, self.expected, self.info), 'package_recipe_binding')
        for scope in ('per_user', 'machine'):
            changed = copy.deepcopy(original); changed['target_topology']['scope'] = scope
            self.rewrite(root, 'setup-recipe.json', changed); self.resign_fixture(root)
            self.rejected(lambda: pf.verify(root, self.expected, self.info), 'package_recipe_binding')

    def test_semantically_changed_package_refuses_even_with_recomputed_hashes(self):
        root = self.package(); original = pf.read_json(root / 'product-package.json')
        changes = [('immutable_paths', ['disked.exe']), ('mutable_paths', ['share']),
                   ('preserved_paths', ['disked.exe']), ('authenticity_refs', ['invented-signature']),
                   ('license_refs', ['invented-license']), ('sbom_refs', ['invented-sbom']),
                   ('product_id', 'org.other')]
        for field, value in changes:
            with self.subTest(field=field):
                changed = copy.deepcopy(original); changed[field] = value
                self.rewrite(root, 'product-package.json', changed); self.resign_fixture(root)
                self.rejected(lambda: pf.verify(root, self.expected, self.info), 'package_recipe_binding')
        for key, value in [('sha256', '0' * 64), ('size_bytes', 1), ('path', 'other.exe')]:
            changed = copy.deepcopy(original); changed['components'][0]['entries'][0][key] = value
            self.rewrite(root, 'product-package.json', changed); self.resign_fixture(root)
            self.rejected(lambda: pf.verify(root, self.expected, self.info), 'package_recipe_binding')

    def test_changed_payload_archive_is_rejected(self):
        root = self.package()
        with (root / 'payload.zip').open('r+b') as file:
            file.seek(40); value = file.read(1); file.seek(40); file.write(bytes([value[0] ^ 1]))
        self.resign_fixture(root)
        self.rejected(lambda: pf.verify(root, self.expected, self.info))

    def test_consistent_replacement_bundle_cannot_replace_independent_inputs(self):
        root = self.package()
        original = self.expected
        (self.stage/'disked.exe').write_bytes(b'wholly different synthetic payload')
        replacement = pf.ac.inventory(self.stage, ['disked.exe'])
        second = pf.assemble(self.root, 'replacement', self.stage, replacement, self.info)
        self.assertEqual(pf.verify(second, replacement, self.info)['status'], 'pass')
        self.rejected(lambda: pf.verify(second, original, self.info), 'independent_inputs_changed')
        self.rejected(lambda: pf.extract_fixture(self.root, 'should-not-exist', second, original, self.info),
                      'independent_inputs_changed')
        self.assertFalse((self.root/'should-not-exist').exists())
        changed_info = {**self.info, 'source_revision': 'd'*40}
        self.rejected(lambda: pf.verify(root, original, changed_info), 'independent_inputs_changed')

    def test_failed_assembly_retains_partial_archive_without_completion_or_reuse(self):
        original = pf.ac.pinned
        reads = 0
        @contextmanager
        def fail_after_inventory(path):
            nonlocal reads
            with original(path) as value:
                if Path(path) == self.stage/'disked.exe':
                    reads += 1
                    if reads == 2:
                        raise OSError('injected source open after output creation')
                yield value
        with patch.object(pf.ac, 'pinned', fail_after_inventory):
            with self.assertRaisesRegex(OSError, 'injected source'): self.package('partial-package')
        partial = self.root/'partial-package'
        self.assertTrue((partial/'payload.zip').is_file())
        self.assertFalse((partial/'binding.json').exists())
        before = (partial/'payload.zip').read_bytes()
        with self.assertRaises(FileExistsError): self.package('partial-package')
        self.assertEqual((partial/'payload.zip').read_bytes(), before)

    def test_archive_missing_extra_empty_and_unsafe_content(self):
        root = self.package()
        for files in ({}, {'disked.exe': b'wrong'},
                      {'disked.exe': (self.stage/'disked.exe').read_bytes(), 'foreign': b'x'},
                      {'../disked.exe': b'x'}):
            with self.subTest(files=list(files)):
                with zipfile.ZipFile(root / 'payload.zip', 'w') as archive:
                    for name, data in files.items(): archive.writestr(name, data)
                self.resign_fixture(root)
                self.rejected(lambda: pf.verify(root, self.expected, self.info))

    def test_metadata_closure_and_no_claim_promotion(self):
        root = self.package()
        for key, value in [('live_setup', 'pass'), ('owner_accepted', True), ('authenticity', 'verified')]:
            original = pf.binding(root, pf.read_json(pf.LOCK), pf.read_json(pf.PROFILE))
            original['claims'][key] = value
            self.rewrite(root, 'binding.json', original)
            self.rejected(lambda: pf.verify(root, self.expected, self.info), 'bundle_binding')
        self.resign_fixture(root)
        (root / 'foreign.txt').write_bytes(b'foreign')
        self.rejected(lambda: pf.verify(root, self.expected, self.info), 'bundle_closure')
        self.assertEqual((root/'foreign.txt').read_bytes(), b'foreign')

    def test_duplicate_metadata_and_budget_rejected(self):
        root = self.package()
        (root/'build-info.json').write_bytes(b'{"product":"DiskEd","product":"other"}')
        self.rejected(lambda: pf.verify(root, self.expected, self.info), 'duplicate_json_key')
        (root/'build-info.json').write_bytes(b' ' * (pf.META_MAX + 1))
        self.rejected(lambda: pf.verify(root, self.expected, self.info), 'metadata_budget')

    def test_stale_source_lock_and_profile_binding(self):
        root = self.package()
        manifest = pf.read_json(root/'binding.json')
        for key in ('source_lock_sha256', 'profile_sha256', 'setup_source'):
            changed = copy.deepcopy(manifest); changed[key] = 'wrong'
            self.rewrite(root, 'binding.json', changed)
            self.rejected(lambda: pf.verify(root, self.expected, self.info), 'bundle_binding')

    def test_changed_vendored_schema_is_rejected(self):
        lock = pf.read_json(pf.LOCK)
        lock['setup']['retained'][1]['sha256'] = 'sha256:' + '0'*64
        original = pf.read_json
        with patch.object(pf, 'read_json', side_effect=lambda path: lock if path == pf.LOCK else original(path)):
            self.rejected(pf.pinned_contracts, 'pinned_contract_changed')

    def test_occupied_extraction_roots_preserve_case_foreign_and_recovery_bytes(self):
        root = self.package()
        for name, files in [('empty', {}), ('occupied', {'disked.exe': b'foreign-owned-product',
                             'case/image.bin': b'generated-case', 'evidence/report.json': b'generated-evidence',
                             'recovery/journal.bin': b'generated-unresolved-recovery', 'preferences.json': b'prefs'})]:
            target = self.root/name; target.mkdir()
            for rel, data in files.items():
                p = target/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
            before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            with self.assertRaises(FileExistsError): pf.extract_fixture(self.root, name, root, self.expected, self.info)
            after = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(set(files), set(after))

    def test_existing_package_file_and_workspace_refuse_without_overwrite(self):
        root = self.package(); before = {p.name:p.read_bytes() for p in root.iterdir()}
        with self.assertRaises(FileExistsError): self.package()
        self.assertEqual(before, {p.name:p.read_bytes() for p in root.iterdir()})
        (self.root/'existing-file').write_bytes(b'foreign')
        with self.assertRaises(FileExistsError): pf.extract_fixture(self.root, 'existing-file', root, self.expected, self.info)
        self.assertEqual((self.root/'existing-file').read_bytes(), b'foreign')
        with self.assertRaises(FileExistsError): pf.init_fixtures(self.root)

    def test_workspace_marker_and_output_names_fail_closed(self):
        bad = self.base/'unowned'; bad.mkdir()
        with self.assertRaises(FileNotFoundError): pf.assemble(bad, 'new', self.stage, self.expected, self.info)
        marker = pf.read_json(self.root/pf.MARKER); marker['root'] = str(self.base)
        self.rewrite(self.root, pf.MARKER, marker)
        self.rejected(lambda: self.package(), 'fixture_workspace_required')
        self.rewrite(self.root, pf.MARKER, {'schema':'org.disked.setup-fixture-workspace/1',
                                          'root':str(self.root), 'purpose':'disposable-fixtures-only'})
        for name in ('../escape', 'a/b', '.', 'CON', 'x:ads', '\\outside', 'a'*97):
            with self.subTest(name=name): self.rejected(lambda: self.package(name))
        self.assertFalse((self.base/'escape').exists())

    def test_unsupported_identity_and_entrypoint_refuse_before_output_creation(self):
        original = self.info
        for field, value in [('target','windows.xp.x86'), ('composition','other'), ('source_state','dirty'),
                             ('version','0.1.0'), ('source_revision','main'), ('input_digest','wrong')]:
            self.info = {**original, field:value}
            self.rejected(lambda: self.package())
            self.assertFalse((self.root/'package').exists())
        self.info = original
        bad = copy.deepcopy(self.expected); bad['required_entrypoints'] = ['share/message.txt']
        self.rejected(lambda: pf.assemble(self.root, 'package', self.stage, bad, self.info), 'entrypoint_selection')
        self.assertFalse((self.root/'package').exists())

    def test_changed_staging_refuses_before_output_creation(self):
        (self.stage/'disked.exe').write_bytes(b'changed')
        self.rejected(lambda: self.package(), 'staging_inventory_changed')
        self.assertFalse((self.root/'package').exists())

    def test_links_and_namespace_sources_refuse(self):
        for value in ('\\\\.\\PhysicalDrive0', '//server/share', 'D:/fixture:ads', '/device/unknown'):
            with self.subTest(path=value): self.rejected(lambda: pf.ac.local_source(value), 'unsupported_source_path')
        os.link(self.stage/'disked.exe', self.stage/'linked.exe')
        self.rejected(lambda: self.package(), 'link_rejected')

    def test_source_output_overlap_rejected(self):
        self.rejected(lambda: pf.assemble(self.root, 'staging', self.root, self.expected, self.info), 'source_output_overlap')
        root = self.package()
        self.rejected(lambda: pf.extract_fixture(self.root, 'package', root, self.expected, self.info), 'source_output_overlap')
        alias_parent = self.base/'alias-parent'; alias_parent.mkdir()
        alias = alias_parent/'..'/'fixtures'
        self.rejected(lambda: pf.assemble(alias, 'new', self.root, self.expected, self.info), 'source_output_overlap')
        self.assertFalse((self.root/'new').exists())

    def test_interrupted_extraction_retains_partial_bytes_without_retry(self):
        root = self.package(); original = Path.open
        @contextmanager
        def failing(path, *args, **kwargs):
            with original(path, *args, **kwargs) as file:
                if path.name == 'message.txt' and args and args[0] == 'xb':
                    class Broken:
                        def write(self, data):
                            file.write(data[:3]); file.flush()
                            raise OSError('injected fixture destination failure')
                    yield Broken()
                else: yield file
        with patch.object(Path, 'open', failing):
            with self.assertRaisesRegex(OSError, 'injected fixture'): pf.extract_fixture(self.root, 'partial', root, self.expected, self.info)
        partial = self.root/'partial'
        self.assertEqual((partial/'disked.exe').read_bytes(), (self.stage/'disked.exe').read_bytes())
        self.assertEqual((partial/'share/message.txt').read_bytes(), (self.stage/'share/message.txt').read_bytes()[:3])
        with self.assertRaises(FileExistsError): pf.extract_fixture(self.root, 'partial', root, self.expected, self.info)
        self.assertEqual(pf.verify(root, self.expected, self.info)['status'], 'pass')

    def test_cli_positive_negative_and_unsupported_mode_outcomes(self):
        self.rewrite(self.base, 'inventory.json', self.expected); self.rewrite(self.base, 'info.json', self.info)
        base = [sys.executable, str(ROOT/'release/bindings/universal-setup/package_fixture.py')]
        args = ['assemble', '--workspace', str(self.root), '--staging', str(self.stage),
                '--inventory', str(self.base/'inventory.json'), '--build-info', str(self.base/'info.json'), '--output', 'cli']
        first = subprocess.run(base+args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout+first.stderr)
        self.assertEqual(subprocess.run(base+args, capture_output=True).returncode, 1)
        unsupported = subprocess.run(base+['install', '--root', str(self.root)], capture_output=True)
        self.assertEqual(unsupported.returncode, 2)
        verify = subprocess.run(base+['verify','--bundle',str(self.root/'cli'),'--inventory',str(self.base/'inventory.json'),'--build-info',str(self.base/'info.json')], capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stdout+verify.stderr)
        self.assertEqual(json.loads(verify.stdout)['live_setup'], 'not_run')


if __name__ == '__main__':
    unittest.main()
