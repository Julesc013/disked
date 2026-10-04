"""Executable tests of the specification tools, not of DiskEd storage code.

All writes stay in temporary ordinary directories. No physical devices,
elevation, network calls, GitHub mutation or live AIDE process is used.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import specctl as sc

ROOT = Path(__file__).resolve().parents[2]

class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sc.Bundle(ROOT)

    def test_complete_structural_check(self):
        result = self.bundle.check()
        self.assertEqual('PASS', result['status'], result['errors'])
        self.assertIn('DiskEd runtime', result['not_validated'])

    def test_real_requirements_have_test_specifications(self):
        reqs, tests = self.bundle.requirements()
        authored={rid for id in self.bundle.concepts for rid in self.bundle.document(id)[1]['disked']['requirements']}
        self.assertTrue(authored)
        self.assertEqual(authored, {r['id'] for r in reqs})
        self.assertEqual(len(reqs), len(tests))
        self.assertEqual({r['id'] for r in reqs}, {t['requirement_ids'][0] for t in tests})
        self.assertTrue(all(t['status']=='definition_only' and not t['evidence'] for t in tests))

    def test_schema_registry_is_offline(self):
        with self.assertRaises(sc.SpecError):
            self.bundle.validate('https://untrusted.invalid/schema.json', {})

    def test_generation_is_deterministic(self):
        self.assertEqual(self.bundle.generated_files(), self.bundle.generated_files())

    def test_no_acceptance_is_manufactured(self):
        self.assertEqual(set(), self.bundle.accepted())
        self.assertFalse(self.bundle.meta['owner_accepted'])

    def test_only_first_review_is_dependency_ready(self):
        rows = self.bundle.next_work()
        self.assertEqual(['DE-W000'], [r['id'] for r in rows if not r['blockers']])
        self.assertTrue(all(r['execution_authorized'] is False for r in rows))

    def test_readiness_never_runs_commands(self):
        with mock.patch.object(sc.subprocess, 'run', side_effect=AssertionError('must not execute')):
            self.bundle.next_work()

    def test_show_unknown_concept_is_refused(self):
        with self.assertRaises(sc.SpecError): self.bundle.document('DE-NOT-THERE')

    def test_transitive_context_is_dependency_ordered(self):
        ids = self.bundle.context_ids(['DE-043'])
        self.assertIn('DE-001', ids)
        for id in ids:
            for dep in self.bundle.concepts[id]['depends_on']:
                self.assertLess(ids.index(dep), ids.index(id))

    def test_unknown_context_seed_is_refused(self):
        with self.assertRaises(sc.SpecError): self.bundle.context_ids(['DE-FAKE'])

    def test_all_target_claims_remain_unqualified(self):
        text=(ROOT/'catalog/targets.json').read_text()
        for target in sc.read_json(ROOT/'catalog/targets.json')['targets']:
            self.bundle.validate(sc.SCHEMA_PREFIX+'target:1',target)
        self.assertNotIn('"hardware-qualified"', text)

    def test_impact_is_conservative_and_named(self):
        result=self.bundle.impact(['source/runtime/journal/writer.cpp'])
        self.assertFalse(result['unknown_impact'])
        self.assertTrue(result['review_required'])
        self.assertTrue(result['test_ids'])

    def test_unknown_impact_is_not_no_impact(self):
        result=self.bundle.impact(['unmapped/new-module.c'])
        self.assertTrue(result['unknown_impact'])
        self.assertTrue(result['review_required'])

    def test_cli_error_is_structured_and_nonzero(self):
        proc=subprocess.run([sys.executable,str(ROOT/'tools/specctl.py'),'show','DE-UNKNOWN'],capture_output=True,text=True,timeout=15)
        self.assertEqual(2,proc.returncode)
        self.assertEqual('',proc.stdout)
        self.assertEqual('ERROR',json.loads(proc.stderr)['status'])

    def test_cli_doctor_reports_actual_environment(self):
        proc=subprocess.run([sys.executable,str(ROOT/'tools/specctl.py'),'doctor'],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,proc.returncode,proc.stderr)
        value=json.loads(proc.stdout)
        self.assertEqual('3.10',value['intended_minimum'])
        self.assertIn('jsonschema',value['packages'])

class ParserTests(unittest.TestCase):
    def test_duplicate_json_keys(self):
        with self.assertRaises(sc.SpecError):sc.parse_json('{"a":1,"a":2}')

    def test_nonfinite_json_values(self):
        for value in ['NaN','Infinity','-Infinity']:
            with self.subTest(value=value), self.assertRaises(sc.SpecError):sc.parse_json(value)

    def test_invalid_json(self):
        with self.assertRaises(sc.SpecError):sc.parse_json('{no}')

    def test_canonical_bytes_sort_keys(self):
        self.assertEqual(sc.canonical({'b':1,'a':'x'}),sc.canonical({'a':'x','b':1}))

    def test_duplicate_yaml_keys(self):
        with self.assertRaises(sc.SpecError):sc.parse_frontmatter('---\ntype: A\ntype: B\n---\nbody')

    def test_yaml_aliases_anchors_and_tags_refused(self):
        for content in ['a: &x [1]\nb: *x','type: !!str Thing','type: !Custom Thing']:
            with self.subTest(content=content),self.assertRaises(sc.SpecError):sc.parse_frontmatter('---\n'+content+'\n---\n')

    def test_yaml_safe_unknown_extensions_survive(self):
        m,body=sc.parse_frontmatter('---\ntype: Thing\nnew_extension:\n  value: 42\n---\n# Title\n')
        self.assertEqual({'value':42},m['new_extension'])
        self.assertEqual('# Title\n',body)

    def test_yaml_time_stays_text(self):
        m,_=sc.parse_frontmatter('---\ntype: Thing\nat: 2026-09-17T12:00:00Z\n---\n')
        self.assertIsInstance(m['at'],str)

    def test_yaml_nonmapping_is_refused(self):
        with self.assertRaises(sc.SpecError):sc.parse_frontmatter('---\n- a\n---\n')

    def test_missing_or_unterminated_frontmatter(self):
        for value in ['# no metadata','---\ntype: X']:
            with self.subTest(value=value), self.assertRaises(sc.SpecError):sc.parse_frontmatter(value)

    def test_oversized_frontmatter(self):
        value='---\ntype: '+('x'*(sc.MAX_FRONTMATTER+1))+'\n---\n'
        with self.assertRaises(sc.SpecError):sc.parse_frontmatter(value)

class PathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_safe_relative_file(self):
        self.assertEqual(self.root/'a/b.json',sc.safe_path(self.root,'a/b.json'))

    def test_ambiguous_and_escaping_paths(self):
        paths=['../escape','/absolute','C:/drive','C:relative','a\\b','a/../b','./a','a/./b','a//b','a/','a.','a ','NUL.txt','con','LPT1.log','a\x00b','']
        for value in paths:
            with self.subTest(path=value),self.assertRaises(sc.SpecError):sc.safe_path(self.root,value)

    def test_missing_existing_file(self):
        with self.assertRaises(sc.SpecError):sc.safe_path(self.root,'missing',existing=True)

    def test_symlink_path_is_refused(self):
        outside=self.root/'outside';outside.mkdir()
        try:(self.root/'link').symlink_to(outside,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlinks unavailable on coordinator')
        with self.assertRaises(sc.SpecError):sc.safe_path(self.root,'link/data')

    def test_duplicate_temporary_output_refused(self):
        (self.root/'x.json.tmp').write_text('do not overwrite')
        with self.assertRaises(sc.SpecError):sc.write_json(self.root/'x.json',{})
        self.assertEqual('do not overwrite',(self.root/'x.json.tmp').read_text())

    def test_json_write_roundtrip(self):
        sc.write_json(self.root/'x.json',{'a':1})
        self.assertEqual({'a':1},sc.read_json(self.root/'x.json'))
        self.assertFalse((self.root/'x.json.tmp').exists())

class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=sc.Bundle(ROOT)

    def test_action_cycle_refused(self):
        with self.assertRaises(sc.SpecError):sc.acyclic({'a':['b'],'b':['a']})

    def test_unknown_dependency_refused(self):
        with self.assertRaises(sc.SpecError):sc.acyclic({'a':['missing']})

    def test_shared_dag_dependency(self):
        sc.acyclic({'a':['c'],'b':['c'],'c':[]})

    def test_general_resource_graph_may_cycle(self):
        sc.semantic_validate('graph',{'nodes':[{'id':'a'},{'id':'b'}],'edges':[{'from':'a','to':'b'},{'from':'b','to':'a'}]})

    def test_resource_graph_dangling_edge(self):
        with self.assertRaises(sc.SpecError):sc.semantic_validate('graph',{'nodes':[{'id':'a'}],'edges':[{'from':'a','to':'missing'}]})

    def test_duplicate_node_id(self):
        with self.assertRaises(sc.SpecError):sc.unique_ids([{'id':'a'},{'id':'a'}],'node')

    def test_checked_extent_arithmetic(self):
        sc.semantic_validate('extent',{'start_lba':'2048','length_lba':'4096','logical_block_bytes':512})
        for v in [{'start_lba':str(sc.U64_MAX),'length_lba':'2','logical_block_bytes':512},
                  {'start_lba':'0','length_lba':'0','logical_block_bytes':512},
                  {'start_lba':'-1','length_lba':'2','logical_block_bytes':512},
                  {'start_lba':'0','length_lba':str(sc.U64_MAX),'logical_block_bytes':4096}]:
            with self.subTest(value=v), self.assertRaises(sc.SpecError):sc.semantic_validate('extent',v)

    def test_handoff_not_run_has_no_result(self):
        v=sc.read_json(ROOT/'examples/handoff-unrun.json')
        self.bundle.validate(sc.SCHEMA_PREFIX+'handoff:1',v,'handoff')
        v['tests'][0]['exit_code']=0
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'handoff:1',v,'handoff')

    def test_handoff_pass_requires_evidence(self):
        v=sc.read_json(ROOT/'examples/handoff-unrun.json')
        v['tests'][0].update(status='pass',exit_code=0,evidence_path=None)
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'handoff:1',v,'handoff')

    def test_work_grant_cannot_elevate(self):
        v=sc.read_json(ROOT/'examples/grant-fixture.json');v['elevation']=True
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'grant:1',v)

    def test_composition_rejects_unknown_target_and_optional_component(self):
        for field,value in [('target_id','missing'),('optional_runtime_components',['missing'])]:
            v=sc.read_json(ROOT/'examples/composition-fake.json');v[field]=value
            with self.subTest(field=field),self.assertRaises(sc.SpecError):
                self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',v)

    def test_artifact_finalization_rejects_mixed_cycles_and_accepts_finite_carrier(self):
        v=sc.read_json(ROOT/'examples/composition-fake.json')
        v['artifacts']=[{'id':'H','contains':[],'hash_dependencies':[]},
                        {'id':'D','contains':['H'],'hash_dependencies':[]},
                        {'id':'S','contains':['D'],'hash_dependencies':[]}]
        self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',v)
        v['artifacts'][0]['hash_dependencies']=['D']
        with self.assertRaisesRegex(sc.SpecError,'finalization graph cycle'):
            self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',v)

    def test_buildable_composition_requires_inspected_loader_inventory(self):
        v=sc.read_json(ROOT/'examples/composition-fake.json');v['status']='buildable'
        v['evidence']=['fixture only, not build evidence']
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',v)
        v['loader_inventory_status']='inspected'
        # An explicitly inspected empty inventory is valid for a dependency-free
        # artifact; schema conformance does not establish that it was built.
        self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',v)

    def test_target_qualification_needs_evidence_and_resolved_abi(self):
        v=copy.deepcopy(sc.read_json(ROOT/'catalog/targets.json')['targets'][0]);v['status']='qualified'
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'target:1',v)
        v['evidence']=['fixture only'];v['qualification']={
            'artifact_sha256':'sha256:'+'0'*64,'toolchain':'fixture','cpu_floor':'fixture',
            'memory_model':'fixture','address_bits':32,'imports':[],
            'provider_closure':[],'host_records':['fixture only']}
        self.bundle.validate(sc.SCHEMA_PREFIX+'target:1',v)
        v['abi']='real-mode or extender'
        with self.assertRaisesRegex(sc.SpecError,'unresolved abi'):
            self.bundle.validate(sc.SCHEMA_PREFIX+'target:1',v)

    def test_capability_eligibility_requires_every_dimension_and_never_grants(self):
        v=sc.read_json(ROOT/'examples/capability-denied.json')
        v.update(execution_eligible=True,blockers=[],provider_reference='fixture-provider')
        v['checks']={key:'satisfied' for key in v['checks']}
        self.bundle.validate(sc.SCHEMA_PREFIX+'capability-assessment:1',v)
        for key in v['checks']:
            invalid=copy.deepcopy(v);invalid['checks'][key]='unknown'
            with self.subTest(key=key),self.assertRaises(sc.SpecError):
                self.bundle.validate(sc.SCHEMA_PREFIX+'capability-assessment:1',invalid)
        v['authorizes_execution']=True
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'capability-assessment:1',v)

class TemporaryBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.repo=Path(self.temp.name)/'repo'
        self.root=self.repo/'spec'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
        self.bundle=sc.Bundle(self.root)
    def tearDown(self):self.temp.cleanup()

    def test_bootstrap_preview_has_no_write(self):
        result=self.bundle.bootstrap(self.repo)
        self.assertEqual('preview',result['mode'])
        self.assertFalse((self.repo/'AGENTS.md').exists())

    def test_bootstrap_applies_exact_template_bytes(self):
        self.bundle.bootstrap(self.repo,True)
        for item in sc.read_json(self.root/'templates/bootstrap-map.json')['files']:
            self.assertEqual((self.root/item['source']).read_bytes(),(self.repo/item['destination']).read_bytes())

    def test_bootstrap_refuses_any_existing_file_before_writing(self):
        (self.repo/'CLAUDE.md').write_text('existing user instructions')
        with self.assertRaises(sc.SpecError):self.bundle.bootstrap(self.repo,True)
        self.assertFalse((self.repo/'AGENTS.md').exists())
        self.assertEqual('existing user instructions',(self.repo/'CLAUDE.md').read_text())

    def test_bootstrap_refuses_symlink_root(self):
        link=Path(self.temp.name)/'link'
        try:link.symlink_to(self.repo,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlinks unavailable')
        with self.assertRaises(sc.SpecError):self.bundle.bootstrap(link,True)

    def test_bootstrap_relative_root(self):
        # Check relative path handling without changing the process working directory.
        # Windows TEMP may be on a different drive, where no relative path exists.
        import os
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            relative=Path(os.path.relpath(directory,Path.cwd()))
            self.assertFalse(relative.is_absolute())
            result=self.bundle.bootstrap(relative,False)
            self.assertIn('AGENTS.md',result['files'])

    def test_manifest_order_uses_serialized_paths_on_every_platform(self):
        (self.root/'Z-order.txt').write_text('upper')
        (self.root/'a-order.txt').write_text('lower')
        self.bundle.manifest()
        paths=[r['path'] for r in sc.read_json(self.root/'manifest.json')['files']]
        self.assertEqual(sorted(paths),paths)
        self.assertLess(paths.index('Z-order.txt'),paths.index('a-order.txt'))
        self.assertEqual('PASS',self.bundle.manifest(verify=True)['status'])

    def test_composition_rejects_component_cycle(self):
        registry=sc.read_json(self.root/'catalog/components.json')
        registry['components'][0]['depends_on']=['runtime']
        sc.write_json(self.root/'catalog/components.json',registry)
        with self.assertRaisesRegex(sc.SpecError,'component graph cycle'):
            self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',sc.read_json(self.root/'examples/composition-fake.json'))

    def test_composition_rejects_physical_provider_in_fake_scope(self):
        registry=sc.read_json(self.root/'catalog/components.json')
        next(c for c in registry['components'] if c['id']=='provider.fake')['storage_authority']='physical'
        sc.write_json(self.root/'catalog/components.json',registry)
        with self.assertRaisesRegex(sc.SpecError,'authority exceeds'):
            self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',sc.read_json(self.root/'examples/composition-fake.json'))

    def test_composition_rejects_multiple_gui_adapters(self):
        registry=sc.read_json(self.root/'catalog/components.json')
        other=copy.deepcopy(next(c for c in registry['components'] if c['role']=='gui'))
        other['id']='gui.fixture';registry['components'].append(other)
        sc.write_json(self.root/'catalog/components.json',registry)
        value=sc.read_json(self.root/'examples/composition-fake.json');value['components'].append(other['id'])
        with self.assertRaisesRegex(sc.SpecError,'multiple GUI'):
            self.bundle.validate(sc.SCHEMA_PREFIX+'composition:1',value)

    def test_context_is_deterministic_without_git(self):
        one=Path(self.temp.name)/'one';two=Path(self.temp.name)/'two'
        self.bundle.context('DE-W010',one,180000);self.bundle.context('DE-W010',two,180000)
        self.assertEqual((one/'context.md').read_bytes(),(two/'context.md').read_bytes())
        self.assertEqual((one/'manifest.json').read_bytes(),(two/'manifest.json').read_bytes())
        self.assertEqual('PASS',self.bundle.verify_context(one)['status'])

    def test_context_detects_source_change(self):
        out=Path(self.temp.name)/'context';self.bundle.context('DE-W010',out,180000)
        with (self.root/'foundation/charter.md').open('a') as f:f.write('\nChanged source.\n')
        with self.assertRaises(sc.SpecError):self.bundle.verify_context(out)

    def test_context_detects_payload_change(self):
        out=Path(self.temp.name)/'context';self.bundle.context('DE-W010',out,180000)
        with (out/'context.md').open('a') as f:f.write('tampered')
        with self.assertRaises(sc.SpecError):self.bundle.verify_context(out)

    def test_context_will_not_truncate_to_budget(self):
        out=Path(self.temp.name)/'context'
        with self.assertRaises(sc.SpecError):self.bundle.context('DE-W010',out,100)
        self.assertFalse(out.exists())

    def test_context_refuses_populated_destination(self):
        out=Path(self.temp.name)/'context';out.mkdir();(out/'keep').write_text('x')
        with self.assertRaisesRegex(sc.SpecError,'destination must be empty'):self.bundle.context('DE-W010',out,180000)
        self.assertFalse((out/'manifest.json').exists())

    def test_aide_exports_all_planned_non_authorizing(self):
        out=Path(self.temp.name)/'aide';result=self.bundle.aide_export(out)
        self.assertEqual(len(self.bundle.work),result['records'])
        self.assertFalse(result['upstream_cli_verified'])
        for p in out.glob('*.json'):
            v=sc.read_json(p)
            self.bundle.validate(sc.SCHEMA_PREFIX+'aide-workunit-projection:1',v)
            self.assertFalse(v['spec']['authorizes_implementation'])
            self.assertEqual('NOT_RUN',v['status']['result'])

    def test_aide_export_refuses_overwrite(self):
        out=Path(self.temp.name)/'aide';out.mkdir();(out/'keep').write_text('x')
        with self.assertRaises(sc.SpecError):self.bundle.aide_export(out)

    def test_integrity_manifest_detects_edit(self):
        self.bundle.manifest();self.bundle.manifest(True)
        (self.root/'bundle.json').write_text((self.root/'bundle.json').read_text()+' ')
        with self.assertRaises(sc.SpecError):self.bundle.manifest(True)

    def test_integrity_manifest_detects_extra_file(self):
        self.bundle.manifest();(self.root/'new.txt').write_text('x')
        with self.assertRaises(sc.SpecError):self.bundle.manifest(True)

    def test_generated_index_drift_fails(self):
        (self.root/'generated/index.json').write_text('{}\n')
        with self.assertRaises(sc.SpecError):self.bundle.index(True)

    def test_broken_link_is_reported(self):
        with (self.root/'foundation/charter.md').open('a') as f:f.write('\n[Missing](missing.md)\n')
        result=self.bundle.check(False)
        self.assertTrue(any('Broken link' in x for x in result['errors']))

    def test_legacy_acceptance_is_retained_but_cannot_authorize(self):
        w=self.bundle.work['DE-W000'];ids=self.bundle.context_ids(self.bundle.meta['mandatory_context']+w['context'])
        records=[{'schema':'org.disked.acceptance/1','subject_id':'DE-W000','subject_digest':sc.digest_bytes(sc.canonical(w)),
                  'reviewer':'human:test-fixture-not-real-approval','at':'2026-09-17T12:00:00Z','decision':'accept',
                  'evidence_refs':['fixture-only'],'limitations':['Test fixture; not runtime approval.'],
                  'input_files':[{'path':self.bundle.concepts[id]['path'],'sha256':sc.digest_bytes((self.root/self.bundle.concepts[id]['path']).read_bytes())} for id in ids]}]
        sc.write_json(self.root/'work/acceptances.json',{'records':records})
        self.assertEqual(set(),self.bundle.accepted())
        self.assertEqual('unverified_legacy',self.bundle.acceptance_projection()['receipts'][0]['historical_validity'])
        with (self.root/'foundation/charter.md').open('a') as f:f.write('\nDrift\n')
        self.assertEqual(set(),self.bundle.accepted())

    def test_legacy_claim_with_unverifiable_digest_cannot_authorize(self):
        # Shape is valid, but a fake digest cannot admit the work unit.
        p=self.root/'foundation/charter.md'
        record={'schema':'org.disked.acceptance/1','subject_id':'DE-W000','subject_digest':'sha256:'+'0'*64,
                'reviewer':'human:fixture','at':'2026-09-17T12:00:00Z','decision':'accept','evidence_refs':['fixture-only'],
                'limitations':[],'input_files':[{'path':'foundation/charter.md','sha256':sc.digest_bytes(p.read_bytes())}]}
        sc.write_json(self.root/'work/acceptances.json',{'records':[record]})
        self.assertEqual(set(),self.bundle.accepted())

class InvocationFixtures(unittest.TestCase):
    pass

for _case in sc.read_json(ROOT/'fixtures/invocation.json')['cases']:
    def _test(self, case=_case):
        self.assertEqual(case['expected'],sc.route_invocation(case['inputs']))
    setattr(InvocationFixtures,'test_'+_case['id'].replace('-','_'),_test)

class SchemaFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=sc.Bundle(ROOT)

for _index,_case in enumerate(sc.read_json(ROOT/'catalog/validation-cases.json')['cases']):
    def _test(self,case=_case):
        v=sc.read_json(ROOT/case['path'])
        if case['valid']:
            self.bundle.validate(case['schema'],v,case.get('semantic'))
        else:
            with self.assertRaises(sc.SpecError):self.bundle.validate(case['schema'],v,case.get('semantic'))
    setattr(SchemaFixtures,'test_%02d_%s'%(_index,Path(_case['path']).stem.replace('-','_')),_test)

if __name__=='__main__':unittest.main()
