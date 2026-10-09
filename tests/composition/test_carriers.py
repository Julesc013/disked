"""Synthetic contract fixtures; no native/installed-state qualification inferred."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
servicing=module('servicing','release/carriers/servicing_preview.py')
carrier=servicing.carrier
pf,ac=carrier.pf,carrier.ac


def ownership():
    resource=dict(id='disked.payload',generation='v1',sha256='sha256:'+'a'*64,path='payload/v1',role='payload',owner='universal-setup')
    ref={key:resource[key] for key in ('id','generation','sha256')}
    view=dict(schema='org.disked.servicing-view-prototype/1',ownership_epoch='1',capture_epoch='6',capture_complete=True,
              selections=['console'],exclusions=['gui','drivers'],policy_digest='sha256:'+'b'*64,resources=[resource],operations=[])
    request=dict(schema='org.disked.servicing-request-prototype/1',ownership_epoch='1',capture_epoch='6',actor='universal-setup',
                 action='remove',resources=[ref])
    return view,request


def operation(ref,**changes):
    return dict(dict(operation_id='op.fixture',attempt_id='attempt.1',worker_epoch='1',capture_epoch='6',logical='completed',
                     worker='exited',effect='certain',cancellation='not_requested',release='released',recovery_required=False,
                     dependencies=[dict(ref,purpose='execution')]),**changes)


class ServicingTests(unittest.TestCase):
    def test_complete_empty_capture_preserves_selections_without_authority(self):
        view,request=ownership();request['action']='repair';value=servicing.preview(view,request)
        self.assertEqual(value['status'],'eligible')
        self.assertEqual(value['preserved_selections'],['console'])
        self.assertEqual(value['preserved_exclusions'],['gui','drivers'])
        self.assertEqual(value['preserved_policy_digest'],view['policy_digest'])
        self.assertFalse(value['authorizes_lifecycle']);self.assertTrue(value['requires_atomic_recheck'])

    def test_each_unsafe_dimension_retains_generation(self):
        for change in (dict(logical='active'),dict(logical='unresolved'),dict(worker='running'),dict(worker='unreachable'),
                       dict(effect='uncertain'),dict(release='held'),dict(release='unknown'),dict(recovery_required=True),dict(capture_epoch='5')):
            with self.subTest(change=change):
                view,request=ownership();view['operations']=[operation(request['resources'][0],**change)]
                value=servicing.preview(view,request)
                self.assertEqual(value['status'],'deferred')
                self.assertEqual(value['retained_generations'],request['resources'])
                self.assertEqual(value['retirement_candidates'],[])

    def test_requested_or_acknowledged_cancel_is_not_release(self):
        for cancellation in ('requested','acknowledged'):
            view,request=ownership();view['operations']=[operation(request['resources'][0],logical='active',worker='running',cancellation=cancellation)]
            self.assertEqual(servicing.preview(view,request)['status'],'deferred')

    def test_terminal_exit_requires_certain_effect_and_recovery_discharge(self):
        view,request=ownership();view['operations']=[operation(request['resources'][0])]
        self.assertEqual(servicing.preview(view,request)['status'],'eligible')
        view['operations'][0]['effect']='uncertain'
        self.assertEqual(servicing.preview(view,request)['status'],'deferred')

    def test_incomplete_capture_deferred(self):
        view,request=ownership();view['capture_complete']=False
        self.assertEqual(servicing.preview(view,request)['status'],'deferred')

    def test_other_generation_can_be_retained_without_replacing_identity(self):
        view,request=ownership();other=dict(view['resources'][0],generation='v2',path='payload/v2',sha256='sha256:'+'c'*64)
        view['resources'].append(other)
        otherref={key:other[key] for key in ('id','generation','sha256')}
        view['operations']=[operation(otherref,logical='active',worker='running')]
        value=servicing.preview(view,request)
        self.assertEqual(value['status'],'eligible')
        view['operations'][0]['worker']='unreachable'
        self.assertEqual(servicing.preview(view,request)['status'],'deferred')

    def test_competing_msi_msix_or_os_owner_refuses(self):
        for owner in ('windows-installer','windows-package-deployment','os-servicing'):
            view,request=ownership();view['resources'][0]['owner']=owner
            value=servicing.preview(view,request)
            self.assertEqual(value['status'],'refused');self.assertIn('servicing_owner_conflict',value['reasons'])

    def test_unmanaged_external_and_data_never_acquire_payload_ownership(self):
        for role in ('configuration','case','evidence','recovery','external-tool'):
            view,request=ownership();view['resources'][0]['role']=role
            self.assertEqual(servicing.preview(view,request)['status'],'refused')
        for owner in ('unmanaged','external'):
            view,request=ownership();view['resources'][0]['owner']=owner
            self.assertEqual(servicing.preview(view,request)['status'],'refused')

    def test_withdraw_proposes_denial_with_retained_required_provider(self):
        view,request=ownership();view['resources'][0]['role']='provider';request['action']='withdraw'
        view['operations']=[operation(request['resources'][0],logical='unresolved',effect='uncertain',recovery_required=True)]
        value=servicing.preview(view,request)
        self.assertEqual(value['proposed_admission'],'deny_new_work');self.assertEqual(value['status'],'deferred')
        self.assertEqual(value['retirement_candidates'],[]);self.assertEqual(value['retained_generations'],request['resources'])
        self.assertFalse(value['authorizes_lifecycle'])

    def test_stale_view_and_requested_policy_selection_changes_refuse(self):
        for key in ('ownership_epoch','capture_epoch'):
            view,request=ownership();request[key]='5'
            self.assertEqual(servicing.preview(view,request)['status'],'refused')
        for key in ('selections','policy_digest','force','transfer_owner'):
            view,request=ownership();request[key]=True
            with self.assertRaises(ac.Rejected):servicing.preview(view,request)

    def test_stale_or_duplicate_generation_digest_references_refuse(self):
        for key,value in [('generation','v3'),('sha256','sha256:'+'d'*64)]:
            view,request=ownership();request['resources'][0][key]=value
            with self.assertRaises(ac.Rejected):servicing.preview(view,request)
        view,request=ownership();request['resources'].append(dict(request['resources'][0]))
        with self.assertRaises(ac.Rejected):servicing.preview(view,request)

    def test_overlapping_roots_and_unknown_dependency_refuse(self):
        for path in ('PAYLOAD/v1','payload/v1/child'):
            view,request=ownership();view['resources'].append(dict(view['resources'][0],id='other',path=path))
            with self.assertRaises(ac.Rejected):servicing.preview(view,request)
        view,request=ownership();view['operations']=[operation(dict(request['resources'][0],generation='missing'))]
        with self.assertRaises(ac.Rejected):servicing.preview(view,request)

    def test_u64_and_array_limits_are_enforced(self):
        for epoch in ('0','18446744073709551616',True,'01'):
            view,request=ownership();view['capture_epoch']=epoch
            with self.assertRaises(ac.Rejected):servicing.preview(view,request)
        view,request=ownership();view['operations']=[operation(request['resources'][0])]*33
        with self.assertRaises(ac.Rejected):servicing.preview(view,request)

    def test_operation_must_bind_execution_closure(self):
        view,request=ownership();view['operations']=[operation(request['resources'][0],dependencies=[])]
        with self.assertRaises(ac.Rejected):servicing.preview(view,request)

    def test_view_and_request_remain_byte_identical(self):
        view,request=ownership();before=ac.canonical([view,request])
        servicing.preview(view,request)
        self.assertEqual(ac.canonical([view,request]),before)

    def test_cli_eligible_deferred_and_malformed_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);view,request=ownership();v=root/'view.json';r=root/'request.json'
            v.write_bytes(ac.canonical(view));r.write_bytes(ac.canonical(request))
            cmd=[sys.executable,str(ROOT/'release/carriers/servicing_preview.py'),'--view',str(v),'--request',str(r)]
            result=subprocess.run(cmd,capture_output=True);self.assertEqual(result.returncode,0)
            self.assertEqual(json.loads(result.stdout)['status'],'eligible')
            view['capture_complete']=False;v.write_bytes(ac.canonical(view))
            result=subprocess.run(cmd,capture_output=True);self.assertEqual(result.returncode,0)
            self.assertEqual(json.loads(result.stdout)['status'],'deferred')
            r.write_bytes(b'{"schema":1,"schema":2}')
            result=subprocess.run(cmd,capture_output=True);self.assertEqual(result.returncode,1)
            self.assertEqual(json.loads(result.stdout)['status'],'refused')


class CarrierTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.stage=self.root/'original';self.stage.mkdir()
        (self.stage/'disked.exe').write_bytes(b'generated D bytes, not native evidence')
        self.host=self.root/'H-fixture.exe';self.host.write_bytes(b'generated H bytes, not native evidence')
        self.expected=ac.inventory(self.stage,['disked.exe'])
        # Synthetic identity data matches the earlier authored package fixture;
        # it is not a claim that these generated byte files are executables.
        self.info=dict(product='DiskEd',version='0.1.0-dev.36',source_state='clean',source_revision='e'*40,
                       input_digest='sha256:'+'a'*64,target='windows.nt10.x64.win32',composition='windows.native.image.prototype')
        self.observation=dict(carrier.profile()['host_observation'],source_revision='1'*40,source_state='clean',
                              setup_revision=pf.read_json(ROOT/'external/universal-setup/native-source-lock.json')['revision'])
        h=pf.file_row(self.host)
        self.receipt=dict(schema='org.disked.carrier-host-input/1',artifact={key:h[key] for key in ('bytes','sha256')},observation=self.observation)
        self.workspace=pf.init_fixtures(self.root/'package-workspace')
        pf.assemble(self.workspace,'package',self.stage,self.expected,self.info)
        self.package=self.workspace/'package';self.output=self.root/'carrier'

    def assemble(self, output=None):
        return carrier.assemble(self.package,self.host,self.expected,self.info,self.receipt,output or self.output)

    def test_exact_finite_manifest_and_archive_bytes(self):
        self.assertEqual(self.assemble()['status'],'pass')
        carrier.verify(self.output,self.expected,self.info,self.receipt)
        manifest=pf.read_json(self.output/'staging/carrier-manifest.json')
        self.assertEqual(manifest['containment'],{'H':[],'D':[],'S':['H','D']})
        self.assertNotIn('S',manifest['artifacts'])
        with zipfile.ZipFile(self.output/'carrier.zip') as archive:
            self.assertEqual(archive.read('payload/disked.exe'),(self.stage/'disked.exe').read_bytes())
            self.assertEqual(archive.read('host/disked-setup-host-fixture.exe'),self.host.read_bytes())

    def test_deterministic_archive_and_no_source_mutation(self):
        before=[self.host.read_bytes(),(self.stage/'disked.exe').read_bytes()]
        self.assemble();other=self.root/'other';self.assemble(other)
        self.assertEqual((self.output/'carrier.zip').read_bytes(),(other/'carrier.zip').read_bytes())
        self.assertEqual(before,[self.host.read_bytes(),(self.stage/'disked.exe').read_bytes()])

    def test_cycles_embedding_and_recursive_ancestor_containment_refuse(self):
        for graph in ({'H':['D'],'D':[],'S':['H','D']},{'H':[],'D':['S'],'S':['D']},
                      {'H':[],'D':['H'],'S':['D']},{'H':[],'D':[],'S':['S']}):
            with self.assertRaises(ac.Rejected):carrier.topology(graph)

    def test_host_claim_cannot_promote_lifecycle_or_embed_payload_hash(self):
        for key,value in [('live_lifecycle',True),('embedded_final_payload_hash',True),('contained_payloads',['D']),
                          ('product_id','other'),('abi',False),('source_state','modified')]:
            receipt=copy.deepcopy(self.receipt);receipt['observation'][key]=value
            with self.assertRaises(ac.Rejected):carrier.definitions(self.expected,self.info,receipt)

    def test_changed_host_refuses_before_output_creation(self):
        self.host.write_bytes(b'replaced H')
        with self.assertRaises(ac.Rejected):self.assemble()
        self.assertFalse(self.output.exists())

    def test_existing_roots_preserve_foreign_and_recovery_data(self):
        self.output.mkdir();foreign=self.output/'foreign.bin';foreign.write_bytes(b'foreign generated bytes')
        with self.assertRaises(OSError):self.assemble()
        self.assertEqual(foreign.read_bytes(),b'foreign generated bytes')

    def test_changed_payload_or_manifest_refuses(self):
        self.assemble()
        (self.output/'staging/payload/disked.exe').write_bytes(b'changed D')
        with self.assertRaises(ac.Rejected):carrier.verify(self.output,self.expected,self.info,self.receipt)

    def test_numeric_value_cannot_replace_boolean_binding_claim(self):
        self.assemble();path=self.output/'carrier-binding.json';value=pf.read_json(path)
        value['fixture_only']=1
        path.write_bytes(ac.canonical(value)+b'\n')
        with self.assertRaisesRegex(ac.Rejected,'carrier_external_binding'):
            carrier.verify(self.output,self.expected,self.info,self.receipt)

    def test_consistent_replacement_cannot_replace_separate_expected_host(self):
        self.assemble();otherhost=self.root/'different-H.exe';otherhost.write_bytes(b'consistent different host bytes')
        row=pf.file_row(otherhost)
        other=dict(self.receipt,artifact={key:row[key] for key in ('bytes','sha256')})
        otherroot=self.root/'different-carrier'
        carrier.assemble(self.package,otherhost,self.expected,self.info,other,otherroot)
        with self.assertRaisesRegex(ac.Rejected,'carrier_independent_inventory'):
            carrier.verify(otherroot,self.expected,self.info,self.receipt)

    def test_partial_assembly_is_retained_without_replay(self):
        original=carrier.ac.verify_zip
        def fault(*args):
            if self.output.exists():raise ac.Rejected('injected_verify')
            return original(*args)
        with patch.object(carrier.ac,'verify_zip',side_effect=fault):
            with self.assertRaises(ac.Rejected):self.assemble()
        self.assertTrue(self.output.is_dir())
        with self.assertRaises(OSError):self.assemble()


if __name__=='__main__':unittest.main()
