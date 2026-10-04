"""Correctness regressions for the 08a8246 review; ordinary temporary files only."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
ROOT=Path(__file__).resolve().parents[2]

class ProtocolCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=sc.Bundle(ROOT)

    def test_semantics_dispatch_from_schema_and_cannot_be_overridden(self):
        event=sc.read_json(ROOT/'examples/event-progress.json')
        for seq in ['0',str(sc.U64_MAX)]:
            event['sequence']=seq;self.bundle.validate(sc.SCHEMA_PREFIX+'event:1',event)
        for seq in [str(sc.U64_MAX+1),'9'*20,'-1','01','1.0',1]:
            event['sequence']=seq
            with self.subTest(sequence=seq),self.assertRaises(sc.SpecError):
                self.bundle.validate(sc.SCHEMA_PREFIX+'event:1',event)
        with self.assertRaises(sc.SpecError):
            self.bundle.validate(sc.SCHEMA_PREFIX+'plan:1',sc.read_json(ROOT/'examples/plan-invalid-cycle.json'))
        event['sequence']='1'
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'event:1',event,'graph')

    def test_running_response_needs_identity_completed_read_may_omit_it(self):
        response=sc.read_json(ROOT/'examples/response-refused.json');response['status']='accepted_running'
        for identity in [None,'']:
            response['operation_id']=identity
            with self.subTest(identity=identity),self.assertRaises(sc.SpecError):
                self.bundle.validate(sc.SCHEMA_PREFIX+'response:1',response)
        del response['operation_id']
        with self.assertRaises(sc.SpecError):self.bundle.validate(sc.SCHEMA_PREFIX+'response:1',response)
        response['operation_id']='operation-fixture';self.bundle.validate(sc.SCHEMA_PREFIX+'response:1',response)
        response.update(status='completed',operation_id=None);self.bundle.validate(sc.SCHEMA_PREFIX+'response:1',response)

    def test_explicit_and_inferred_cli_prompt_policy(self):
        for front in ['cli','auto','plain']:
            for terminal in ['capable','limited']:
                with self.subTest(front=front,terminal=terminal):
                    result=sc.route_invocation({'frontend':front,'command':True,'interactive':'yes','terminal':terminal})
                    self.assertTrue(result['interactive'])
                    self.assertIn(result['frontend'],['cli','plain'])
        for settings in [{'terminal':'none'},{'terminal':'capable','stdin':'pipe'},{'terminal':'capable','stdout':'file'}]:
            self.assertEqual({'error':'interaction_unavailable'},sc.route_invocation(dict(settings,frontend='cli',interactive='yes')))
        self.assertTrue(sc.route_invocation({'frontend':'cli','interactive':'yes','stdout':'pipe','prompt_channel':True})['interactive'])
        self.assertEqual({'error':'argument_conflict'},sc.route_invocation({'frontend':'cli','interactive':'yes','format':'json','prompt_channel':True}))

    def test_impact_reports_each_path_and_exact_module_boundaries(self):
        known='source/runtime/journal/writer.cpp';unknown='source/runtime-extra/new.cpp'
        result=self.bundle.impact([known,unknown])
        self.assertTrue(result['unknown_impact']);self.assertEqual([unknown],result['unmatched_paths'])
        self.assertEqual([known],result['matched_paths']);self.assertIn('runtime',result['matched_owners'][known])
        self.assertIn('DE-043',result['spec_ids'])
        self.assertFalse(self.bundle.impact([known])['unknown_impact'])
        for path in ['spec/catalog/commands.json','spec/schemas/event.schema.json','spec/fixtures/invocation.json','AGENTS.md','CMakeLists.txt']:
            with self.subTest(path=path):self.assertFalse(self.bundle.impact([path])['unknown_impact'])

class TemporaryCorrectiveFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.repo=Path(self.temp.name)/'repo';self.root=self.repo/'spec'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('__pycache__'))
        (self.repo/'AGENTS.md').write_text('Fixture instructions: no real storage.\n')
        (self.repo/'CLAUDE.md').write_text('Fixture entrypoint: read AGENTS.md.\n')
        self.bundle=sc.Bundle(self.root);self.pack=Path(self.temp.name)/'pack'
    def tearDown(self):self.temp.cleanup()
    def pack_context(self,work='DE-W012'):
        self.bundle.context(work,self.pack,180000)

class ContextCorrections(TemporaryCorrectiveFixture):
    def test_catalog_schema_fixture_and_instruction_changes_invalidate_same_revision(self):
        self.pack_context();manifest=sc.read_json(self.pack/'manifest.json')
        paths={f['path'] for f in manifest['files']}
        for name in ['spec/catalog/commands.json','spec/schemas/command.schema.json','spec/fixtures/invocation.json','AGENTS.md','CLAUDE.md']:
            with self.subTest(path=name):
                self.assertIn(name,paths);path=self.bundle.input_path(name);original=path.read_bytes()
                path.write_bytes(original+b'\n')
                with self.assertRaises(sc.SpecError):self.bundle.verify_context(self.pack)
                path.write_bytes(original)
        self.assertEqual('PASS',self.bundle.verify_context(self.pack)['status'])

    def test_required_artifacts_are_portable_and_bound(self):
        self.pack_context();artifact=self.pack/'artifacts/spec/catalog/commands.json'
        self.assertEqual((self.root/'catalog/commands.json').read_bytes(),artifact.read_bytes())
        artifact.write_bytes(artifact.read_bytes()+b' ')
        with self.assertRaisesRegex(sc.SpecError,'artifact changed'):self.bundle.verify_context(self.pack)

    def test_missing_manifest_entry_and_new_instruction_chain_are_detected(self):
        self.pack_context();m=sc.read_json(self.pack/'manifest.json');old=copy.deepcopy(m)
        m['files']=[f for f in m['files'] if f['path']!='spec/catalog/commands.json'];sc.write_json(self.pack/'manifest.json',m)
        with self.assertRaisesRegex(sc.SpecError,'closure'):self.bundle.verify_context(self.pack)
        sc.write_json(self.pack/'manifest.json',old)
        (self.repo/'source/runtime').mkdir(parents=True);(self.repo/'source/runtime/AGENTS.md').write_text('New local instruction')
        with self.assertRaisesRegex(sc.SpecError,'closure'):self.bundle.verify_context(self.pack)

    def test_optional_background_does_not_invalidate_pack(self):
        self.pack_context()
        with (self.root/'references/intent-ledger.json').open('a') as f:f.write(' ')
        self.assertEqual('PASS',self.bundle.verify_context(self.pack)['status'])

    def test_input_cycle_and_unknown_id_fail_closed(self):
        registry=sc.read_json(self.root/'catalog/input-dependencies.json');original=copy.deepcopy(registry)
        registry['inputs'][0]['depends_on']=[registry['inputs'][0]['id']]
        sc.write_json(self.root/'catalog/input-dependencies.json',registry)
        with self.assertRaisesRegex(sc.SpecError,'cycle'):self.bundle.resolve_inputs('DE-W012')
        original['always'].append('missing-input')
        sc.write_json(self.root/'catalog/input-dependencies.json',original)
        with self.assertRaisesRegex(sc.SpecError,'Unknown required input'):self.bundle.resolve_inputs('DE-W012')

    def test_pack_reads_fresh_work_definition(self):
        catalog=sc.read_json(self.root/'work/units.json')
        next(w for w in catalog['units'] if w['id']=='DE-W012')['title']='Fresh synthetic work title'
        sc.write_json(self.root/'work/units.json',catalog)
        self.pack_context()
        self.assertIn('Fresh synthetic work title',(self.pack/'context.md').read_text(encoding='utf-8'))

    def test_instruction_discovery_has_canonical_order(self):
        for name in ['source/runtime/z','source/runtime/a']:
            folder=self.repo/name;folder.mkdir(parents=True);(folder/'AGENTS.md').write_text('Fixture only.\n')
        instructions=self.bundle.input_view()['instructions']
        self.assertEqual(sorted(instructions),instructions)
        self.assertEqual(4,len(instructions))

    def test_artifact_budget_refuses_before_writing(self):
        with self.assertRaisesRegex(sc.SpecError,'artifact byte budget'):
            self.bundle.context('DE-W012',self.pack,180000,1)
        self.assertFalse(self.pack.exists())

class ReceiptCorrections(TemporaryCorrectiveFixture):
    # Inherit fixture creation only, not the context tests themselves.
    def git(self,*args):
        result=subprocess.run(['git','-c','core.autocrlf=false','-c','commit.gpgSign=false',
            '-c','core.hooksPath='+str(self.repo/'unused-hooks'),'-c','user.name=Fixture',
            '-c','user.email=fixture@example.invalid','-C',str(self.repo),*args],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr);return result.stdout.strip()
    def snapshot(self):
        if not (self.repo/'.git').exists():self.git('init','-q')
        self.git('add','-A');self.git('commit','-q','--allow-empty','-m','Synthetic review fixture')
        return self.git('rev-parse','HEAD')
    def receipt(self,id='receipt-one',supersedes=None,decision='accept'):
        revision=self.snapshot();view=self.bundle.input_view();subject='DE-W000'
        return {'schema':'org.disked.acceptance/2','receipt_id':id,'subject_id':subject,
            'subject_digest':sc.digest_bytes(sc.canonical(view['work'][subject])),
            'reviewed_revision':revision,'supersedes':supersedes,'reviewer':'fixture-not-owner-approval',
            'at':'2026-10-04T00:00:00Z','decision':decision,'evidence_refs':['synthetic fixture'],
            'limitations':['No real acceptance'],
            'input_files':[{'path':p,'sha256':sc.digest_bytes(self.bundle.input_path(p).read_bytes())} for p in self.bundle.review_inputs(subject)]}
    def ledger(self,records):sc.write_json(self.root/'work/acceptances.json',{'records':records})

    def test_stale_history_and_new_receipt_without_deleting_old(self):
        old=self.receipt();self.ledger([old]);self.assertEqual({'DE-W000'},self.bundle.accepted())
        with (self.root/'foundation/charter.md').open('a') as f:f.write('\nChanged fixture\n')
        self.assertEqual(set(),self.bundle.accepted())
        self.assertEqual('stale_inputs',self.bundle.acceptance_projection()['receipts'][0]['applicability'])
        new=self.receipt('receipt-two','receipt-one');self.ledger([old,new])
        projection=self.bundle.acceptance_projection()
        self.assertEqual(['DE-W000'],projection['accepted']);self.assertEqual(2,len(projection['receipts']))
        self.assertEqual('superseded',projection['receipts'][0]['applicability'])
        self.assertTrue(all(r['historical_validity']=='verified' for r in projection['receipts']))

    def test_rejection_revocation_and_explicit_supersession(self):
        old=self.receipt();self.ledger([old])
        for decision in ['reject','revoke']:
            new=self.receipt('receipt-'+decision,'receipt-one',decision);self.ledger([old,new])
            self.assertEqual(set(),self.bundle.accepted())
        new=self.receipt('ambiguous',None);self.ledger([old,new])
        with self.assertRaisesRegex(sc.SpecError,'supersede'):self.bundle.accepted()
        self.ledger([old,old])
        with self.assertRaisesRegex(sc.SpecError,'Duplicate receipt'):self.bundle.accepted()

    def test_invalid_historical_blob_is_not_excused_by_supersession(self):
        old=self.receipt();old['input_files'][0]['sha256']='sha256:'+'0'*64
        new=self.receipt('receipt-two','receipt-one');self.ledger([old,new])
        with self.assertRaisesRegex(sc.SpecError,'reviewed blob'):self.bundle.accepted()

    def test_historical_subject_digest_must_match(self):
        receipt=self.receipt();receipt['subject_digest']='sha256:'+'0'*64;self.ledger([receipt])
        with self.assertRaisesRegex(sc.SpecError,'subject does not match'):self.bundle.accepted()

    def test_missing_reviewed_revision_is_reported_without_authorizing(self):
        receipt=self.receipt();receipt['reviewed_revision']='0'*40;self.ledger([receipt])
        projection=self.bundle.acceptance_projection();self.assertEqual([],projection['accepted'])
        self.assertEqual('revision_unavailable',projection['receipts'][0]['historical_validity'])

    def test_superseded_receipt_never_reactivates_when_old_bytes_return(self):
        path=self.root/'foundation/charter.md';original=path.read_bytes();old=self.receipt()
        path.write_bytes(original+b'\nChanged\n');new=self.receipt('receipt-two','receipt-one')
        self.ledger([old,new]);path.write_bytes(original)
        projection=self.bundle.acceptance_projection();self.assertEqual([],projection['accepted'])
        self.assertEqual(['superseded','stale_inputs'],[r['applicability'] for r in projection['receipts']])

class CommandCorrections(TemporaryCorrectiveFixture):
    def test_alias_collision_with_later_canonical_spelling_is_rejected(self):
        catalog=sc.read_json(self.root/'catalog/commands.json')
        catalog['commands'][0]['aliases'].append(' '.join(catalog['commands'][-1]['words']))
        sc.write_json(self.root/'catalog/commands.json',catalog)
        with self.assertRaisesRegex(sc.SpecError,'Duplicate command spelling'):self.bundle.command_registry()

    def test_parameter_reference_and_binding_relationships(self):
        catalog=sc.read_json(self.root/'catalog/commands.json');original=copy.deepcopy(catalog)
        command=next(c for c in catalog['commands'] if c['syntax_status']=='defined')
        command['parameter_schema']='urn:disked:schema:missing:1'
        sc.write_json(self.root/'catalog/commands.json',catalog)
        with self.assertRaisesRegex(sc.SpecError,'Unknown command schema'):self.bundle.command_registry()
        command=next(c for c in original['commands'] if c['syntax_status']=='defined')
        command['argument_bindings']=[{'parameter':'invented','option':'--invented','completion':'none'}]
        sc.write_json(self.root/'catalog/commands.json',original)
        with self.assertRaisesRegex(sc.SpecError,'Unknown bound parameter'):self.bundle.command_registry()

    def test_defined_argument_bindings_and_completion_are_checked(self):
        catalog=sc.read_json(self.root/'catalog/commands.json')
        command=next(c for c in catalog['commands'] if c['syntax_status']=='defined')
        reference='urn:disked:schema:fixture-parameters:1'
        self.bundle.schemas[reference]=dict(self.bundle.schemas[command['parameter_schema']],properties={'first':{'type':'string','enum':['a']},'second':{'type':'string'}})
        command['parameter_schema']=reference
        command['argument_bindings']=[{'parameter':'first','option':'--first','completion':'schema-enum'},
            {'parameter':'second','option':'--second','completion':'none'}]
        sc.write_json(self.root/'catalog/commands.json',catalog);self.bundle.command_registry()
        bad=command['argument_bindings'][1]
        for update,error in [({'option':'--first'},'Duplicate argument'),({'completion':'schema-enum'},'parameter enum'),
            ({'completion':'observed-id'},'bounded observations')]:
            saved=bad.copy();bad.update(update);sc.write_json(self.root/'catalog/commands.json',catalog)
            with self.subTest(update=update),self.assertRaisesRegex(sc.SpecError,error):self.bundle.command_registry()
            bad.clear();bad.update(saved)
