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

    def acquisition_definition(self):
        resources={}
        for role in ('source','destination','map','host','executable','provider'):
            resources[role]=dict(identity=role,epoch='generation',access={'source':'read','destination':'create-write','map':'create-append','executable':'read'}.get(role,'observe'),
                start='0',end='1' if role in ('source','destination') else '0',aliases=[role],failure_domain='fixture',
                verification={'destination':'readback-sha256','map':'ordered-hash-chain'}.get(role,'identity-epoch'))
        plan=dict(schema='org.disked.acquisition-plan-prototype/1',capture_epoch='fixture',resources=resources,
            bytes='1',chunk_bytes='65536',retry_limit='0',read_policy='ordinary',substitution='stop')
        return dict(schema='org.disked.acquisition-worker-definition/1',request=dict(source='C:\\fixture\\source.img',destination='C:\\fixture\\copy.img',map='C:\\fixture\\copy.map',
            resume=False,explicit_options=True,chunk_bytes='65536',retry_limit='0',read_policy='ordinary',substitution='stop'),plan=plan,
            store=dict(path='C:\\fixture\\state',generation=dict(volume_id='1',file_id='0'*32,created='1'),access='create-owned-metadata',
                children=['acquisition.request','acquisition.records','acquisition.cancel','acquisition.admission'],failure_domain='fixture'),
            host_id='0'*64,image_digest='0'*64,source_revision='0'*40,input_digest='sha256:'+'0'*64,target_profile='windows.nt10.x64.win32')

    def test_acquisition_phases_forbid_mixed_effects_and_require_actual_grants(self):
        uri=sc.SCHEMA_PREFIX+'acquisition-command-parameters:1'
        prepare=dict(phase='prepare',source='fixture',destination='copy',map='map',state_directory='C:\\fixture\\state')
        execute=dict(phase='execute',definition=self.acquisition_definition(),definition_digest='sha256:'+'0'*64,
            allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
        self.bundle.validate(uri,prepare);self.bundle.validate(uri,execute)
        for flag in ('allow_source_read','allow_destination_write','allow_map_write','allow_host_effects'):
            for v in [False,'true',None]:
                with self.subTest(flag=flag,value=v),self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(execute,**{flag:v}))
            with self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(prepare,**{flag:True}))
        for key in ('source','destination','map','state_directory','resume','chunk_bytes','retry_limit','read_policy','substitution'):
            with self.subTest(mixed=key),self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(execute,**{key:prepare.get(key,True)}))
        with self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(prepare,read_policy='failing-read-mostly',retry_limit='1'))

    def test_acquisition_definition_bounded_generation_and_request_plan_agreement(self):
        uri=sc.SCHEMA_PREFIX+'acquisition-worker-definition:1';value=self.acquisition_definition()
        self.bundle.validate(uri,value)
        for field in ('volume_id','created'):
            edge=copy.deepcopy(value);edge['store']['generation'][field]=str(sc.U64_MAX);self.bundle.validate(uri,edge)
            edge['store']['generation'][field]=str(sc.U64_MAX+1)
            with self.subTest(field=field),self.assertRaises(sc.SpecError):self.bundle.validate(uri,edge)
        for field,other in [('chunk_bytes','4096'),('retry_limit','1'),('read_policy','failing-read-mostly'),('substitution','zero-fill')]:
            bad=copy.deepcopy(value);bad['request'][field]=other
            with self.subTest(field=field),self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)
        bad=copy.deepcopy(value);bad['request']['source']='\u00e9'*600
        with self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)

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

    def acquisition_state(self):
        return dict(schema='org.disked.acquisition-worker-state/1',binding=dict(
            operation_id='image-op:'+'a'*32,worker_epoch='worker:'+'b'*32,attempt_id='attempt:'+'c'*32,
            definition_digest='sha256:'+'d'*64,image_digest='e'*64,host_id='f'*64,capture_epoch='fixture',
            process_id='1',process_created='1'),sequence='1',phase='active',checkpoint_bytes='0',source_bytes='0',
            substituted_bytes='0',observed_filetime='1',quiescent=False,outcome=None,receipt=None)

    def test_acquisition_observation_semantics_enforce_counter_relationships(self):
        uri=sc.SCHEMA_PREFIX+'acquisition-worker-state:1';state=self.acquisition_state();self.bundle.validate(uri,state)
        for key,value in [('sequence','0'),('sequence','65'),('checkpoint_bytes',str(sc.U64_MAX+1)),
            ('source_bytes','1'),('substituted_bytes','1'),('observed_filetime','0'),('quiescent',True)]:
            with self.subTest(field=key,value=value),self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(state,**{key:value}))
        for key,value in [('process_id','0'),('process_id',str(2**32)),('process_created',str(sc.U64_MAX+1))]:
            bad=copy.deepcopy(state);bad['binding'][key]=value
            with self.subTest(field=key),self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)
        state.update(phase='finished',quiescent=True,receipt={},outcome=dict(
            schema='org.disked.acquisition-outcome-prototype/1',status='completed',diagnostic='',consistency='live-uncoordinated',
            checkpoint_bytes='0',source_bytes='0',substituted_bytes='0',attempt_read_bytes='0',attempt_written_bytes='0',
            attempt_verified_bytes='0',records='1',uncertain_effect=False))
        self.bundle.validate(uri,state)
        for key,value in [('checkpoint_bytes','1'),('uncertain_effect',True),('attempt_verified_bytes',str(sc.U64_MAX+1))]:
            bad=copy.deepcopy(state);bad['outcome'][key]=value
            with self.subTest(outcome=key),self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)

    def test_acquisition_event_hash_and_identity_are_bound(self):
        row=dict(schema='org.disked.acquisition-worker-record/1',state=self.acquisition_state(),previous='0'*64)
        row['digest']=sc.hashlib.sha256(sc.acquisition_record_bytes(row)).hexdigest()
        event=dict(schema='org.disked.event/1',operation_id=row['state']['binding']['operation_id'],sequence='1',
            type='acquisition.operation.record',payload=dict(schema='org.disked.acquisition-operation-event/1',
                request_id='fixture',observer_epoch='watch:'+'1'*32,record=row))
        uri=sc.SCHEMA_PREFIX+'acquisition-operation-event:1';self.bundle.validate(uri,event)
        for key,value in [('sequence','2'),('operation_id','image-op:'+'f'*32)]:
            with self.subTest(field=key),self.assertRaises(sc.SpecError):self.bundle.validate(uri,dict(event,**{key:value}))
        bad=copy.deepcopy(event);bad['payload']['record']['digest']='f'*64
        with self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)
        bad=copy.deepcopy(event);bad['payload']['request_id']='\u00e9'*100
        with self.assertRaises(sc.SpecError):self.bundle.validate(uri,bad)

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

    def test_resize_quantity_schema_semantics_match_native_bounds(self):
        schema=sc.SCHEMA_PREFIX+'command-resize-proposal-parameters:1'
        for length in ['1B','50GiB',str(sc.U64_MAX)+'B','16777215TiB']:
            self.bundle.validate(schema,{'target_id':'fixture','length':length})
        for length in ['0B','01B','-1B','1.5GiB',str(sc.U64_MAX+1)+'B','16777216TiB',str(sc.U64_MAX)+'KiB','9'*100+'B']:
            with self.subTest(length=length),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,{'target_id':'fixture','length':length})

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
    # This live-repository fixture tests binding/freshness, not a fixed prose
    # size. Current declared inputs exceed the old 260 KB fixture allowance.
    # Explicit capacity changes no assertions; undersized payload/artifact
    # rejection remains tested separately with no truncation or partial output.
    context_budget=350000
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.repo=Path(self.temp.name)/'repo';self.root=self.repo/'spec'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('__pycache__'))
        (self.repo/'AGENTS.md').write_text('Fixture instructions: no real storage.\n')
        (self.repo/'CLAUDE.md').write_text('Fixture entrypoint: read AGENTS.md.\n')
        for item in sc.read_json(ROOT/'catalog/input-dependencies.json')['inputs']:
            name=item['path']
            if not name.startswith('spec/') and name not in ('AGENTS.md','CLAUDE.md'):
                source=ROOT.parent/name
                if source.is_file():
                    destination=self.repo/name;destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,destination)
        self.bundle=sc.Bundle(self.root);self.pack=Path(self.temp.name)/'pack'
    def tearDown(self):self.temp.cleanup()
    def pack_context(self,work='DE-W012'):
        self.bundle.context(work,self.pack,self.context_budget)

class ContextCorrections(TemporaryCorrectiveFixture):
    def binary_input(self, delivery):
        name='spec/fixtures/binary-context-fixture.bin'
        data=b'\x89PNG\r\n\x1a\n\x00\xff\x80binary fixture'
        (self.repo/name).write_bytes(data)
        registry=sc.read_json(self.root/'catalog/input-dependencies.json')
        registry['inputs'].append(dict(id=name,path=name,kind='fixture',
            delivery=delivery,depends_on=[],spec_ids=[]))
        registry['always'].append(name)
        sc.write_json(self.root/'catalog/input-dependencies.json',registry)
        return name,data

    def test_binary_artifacts_bind_exact_bytes_and_detect_copy_and_source_changes(self):
        name,data=self.binary_input('artifact')
        self.pack_context()
        entry=next(f for f in sc.read_json(self.pack/'manifest.json')['files'] if f['path']==name)
        self.assertEqual(sc.digest_bytes(data),entry['sha256'])
        self.assertEqual(len(data),entry['bytes'])
        artifact=self.pack/'artifacts'/name
        self.assertEqual(data,artifact.read_bytes())
        self.assertEqual('PASS',self.bundle.verify_context(self.pack)['status'])
        artifact.write_bytes(data+b'changed')
        with self.assertRaisesRegex(sc.SpecError,'Context artifact changed'):
            self.bundle.verify_context(self.pack)
        artifact.write_bytes(data)
        (self.repo/name).write_bytes(data+b'changed')
        with self.assertRaisesRegex(sc.SpecError,'Context source changed'):
            self.bundle.verify_context(self.pack)

    def test_binary_required_content_is_rejected_without_partial_output(self):
        self.binary_input('content')
        with self.assertRaisesRegex(sc.SpecError,'Non UTF-8 text'):
            self.pack_context()
        self.assertFalse(self.pack.exists())

    def test_native_bootstrap_context_binds_build_source_and_acceptance_fixture(self):
        self.pack_context('DE-W010')
        paths={row['path'] for row in sc.read_json(self.pack/'manifest.json')['files']}
        for name in ['CMakeLists.txt','CMakePresets.json','tools/build-bootstrap.py',
                     'source/apps/disked/main.cpp','source/providers/fake/bootstrap.cpp',
                     'spec/catalog/native-bootstrap.json','spec/fixtures/native-bootstrap.json',
                     'tests/native/test_bootstrap.py','tests/native/provider_guard_probe.cpp']:
            self.assertIn(name,paths)
        source=self.repo/'source/apps/disked/main.cpp'
        source.write_bytes(source.read_bytes()+b'\n// changed after context capture\n')
        with self.assertRaisesRegex(sc.SpecError,'Context source changed'):
            self.bundle.verify_context(self.pack)

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
        (self.repo/'source/runtime').mkdir(parents=True,exist_ok=True);(self.repo/'source/runtime/AGENTS.md').write_text('New local instruction')
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
            folder=self.repo/name;folder.mkdir(parents=True,exist_ok=True);(folder/'AGENTS.md').write_text('Fixture only.\n')
        instructions=self.bundle.input_view()['instructions']
        self.assertEqual(sorted(instructions),instructions)
        self.assertEqual(4,len(instructions))

    def test_artifact_budget_refuses_before_writing(self):
        with self.assertRaisesRegex(sc.SpecError,'artifact byte budget'):
            self.bundle.context('DE-W012',self.pack,self.context_budget,1)
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
        command['argument_bindings']=[{'parameter':'invented','option':'--invented','option_aliases':[],'value_arity':1,'repeatable':False,'completion':'none'}]
        sc.write_json(self.root/'catalog/commands.json',original)
        with self.assertRaisesRegex(sc.SpecError,'Unknown bound parameter'):self.bundle.command_registry()

    def test_defined_argument_bindings_and_completion_are_checked(self):
        catalog=sc.read_json(self.root/'catalog/commands.json')
        command=next(c for c in catalog['commands'] if c['syntax_status']=='defined')
        reference='urn:disked:schema:fixture-parameters:1'
        self.bundle.schemas[reference]=dict(self.bundle.schemas[command['parameter_schema']],properties={'first':{'type':'string','enum':['a']},'second':{'type':'string'}})
        command['parameter_schema']=reference
        command['argument_bindings']=[{'parameter':'first','option':'--first','option_aliases':[],'value_arity':1,'repeatable':False,'completion':'schema-enum'},
            {'parameter':'second','option':'--second','option_aliases':[],'value_arity':1,'repeatable':False,'completion':'none'}]
        sc.write_json(self.root/'catalog/commands.json',catalog);self.bundle.command_registry()
        bad=command['argument_bindings'][1]
        for update,error in [({'option':'--first'},'Duplicate argument'),({'completion':'schema-enum'},'parameter enum'),
            ({'completion':'observed-id'},'bounded observations')]:
            saved=bad.copy();bad.update(update);sc.write_json(self.root/'catalog/commands.json',catalog)
            with self.subTest(update=update),self.assertRaisesRegex(sc.SpecError,error):self.bundle.command_registry()
            bad.clear();bad.update(saved)
