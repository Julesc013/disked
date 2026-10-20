"""Synthetic finalized packets challenge consistency; they do not execute probes."""
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from compare import compare
from evidence import Artifacts, canonical_digest, digest


HERE = Path(__file__).resolve().parent


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT'))
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def artifact(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return dict(path=name, bytes=len(body), sha256=digest(body))

    def packet(self, *, common=True):
        entry = bytes([0, 0, 2, 0, 0x83, 255, 255, 255]) + struct.pack('<II', 1, 1)
        data = bytearray(1024); data[446:462] = entry; data[510:512] = b'\x55\xaa'; data = bytes(data)
        case = dict(name='control', family='mbr', common_projection=common, bytes=1024,
                    unit=512, blocks=2, sha256=digest(data), checks={'mbr.issues': 0, 'mbr.entries.0.start': '1'})
        generator = self.artifact('recipe/generator.py', b'# Synthetic fixture recipe, never executed\n')
        manifest = dict(cases=[case], generator_sha256=generator['sha256'], expected_observations=[],
                        evidence=dict(schema='org.disked.differential-evidence/1',
                            contract=self.artifact('recipe/CONTRACT.md', (HERE/'CONTRACT.md').read_bytes()),
                            generator=generator, fixtures={'control': self.artifact('fixtures/control.img', data)}, participants={}))
        raw_native = dict(mbr=dict(issues=0, entries=[dict(active=True, range_valid=True, start='1', end='2', raw=entry.hex())]), walks=[])
        native_projection = dict(label='dos', candidates=[dict(role='mbr', rows=[dict(slot=1, start=1, end=2, type='83')], issues=0, walks=[])])
        receipts = {}
        for participant, kinds in [('native', ['native']), ('reference', ['sfdisk-json', 'sfdisk-verify'])]:
            profile = dict(os='synthetic/no-execution', build='fixture-only', architecture='synthetic',
                           runtime='unit-test-data', token='declared-test-data', workspace='/frozen', path_style='posix')
            executable = '/synthetic/native-probe' if participant == 'native' else '/synthetic/sfdisk'
            binary_hash = digest(b'synthetic binary identity, not an executable')
            identity = dict(schema='org.disked.differential-identity/1', participant=participant,
                role='native' if participant=='native' else 'reference', profile=profile,
                source=dict(revision='a'*40 if participant=='native' else None,
                            inputs={'synthetic-source': digest(b'synthetic source')}, upstream_source_verified=False),
                build=dict(configuration='synthetic metadata only', toolchain={'synthetic': digest(b'not a compiler')},
                           executables={executable: binary_hash}))
            descriptor = self.artifact('identities/'+participant+'.json', json.dumps(identity).encode())
            manifest['evidence']['participants'][participant] = dict(role=identity['role'], profile=profile, identity=descriptor)
            receipt = dict(participant=participant, identity_sha256=descriptor['sha256'], observations=[])
            input_path = 'copies/'+participant+'/control.img'
            for kind in kinds:
                name = participant+'-'+kind
                argv = [executable] if participant=='native' else [executable, '/frozen/'+input_path]
                policy = dict(comparison='native' if participant=='native' else 'diagnostic' if kind=='sfdisk-verify' else 'projection',
                              argv=argv, input_path=input_path, allowed_outcomes=['completed'], timeout_seconds=5)
                manifest['expected_observations'].append(dict(name='control', participant=participant, kind=kind, policy=policy))
                if participant == 'native':
                    stdout = json.dumps(raw_native).encode(); projection = native_projection
                elif kind == 'sfdisk-json':
                    stdout = json.dumps(dict(partitiontable=dict(label='dos', unit='sectors', sectorsize=512,
                        partitions=[dict(node='/frozen/'+input_path+'1', start=1, size=1, type='83')]))).encode()
                    projection = dict(label='dos', rows=[dict(slot=1, start=1, end=2, type='83')], fields=['slot','start','end','type','uuid'])
                else:
                    stdout = b'synthetic diagnostic observation'; projection = None
                row = dict(name='control', participant=participant, kind=kind, identity_sha256=descriptor['sha256'],
                    sha256=case['sha256'], bytes=1024, unit=512, blocks=2, projection=copy.deepcopy(projection),
                    outcome='exited', exit_code=0, argv=argv, stdout=stdout.decode(), stderr='',
                    stdout_sha256=digest(stdout), stderr_sha256=digest(b''),
                    executable_before_sha256=binary_hash, executable_after_sha256=binary_hash,
                    execution=dict(status='completed', argv=argv, exit_code=0, elapsed_seconds=.01),
                    input_before=self.artifact('before/'+name+'.img', data),
                    input_after=self.artifact(input_path, data), input_unchanged=True,
                    raw=dict(stdout=self.artifact('raw/'+name+'.stdout', stdout), stderr=self.artifact('raw/'+name+'.stderr', b'')))
                if participant == 'native':
                    request = dict(blocks='2', unit='512', limit='128', heads='0', sectors='0',
                                   image={'0':data[:512].hex(), '1':data[512:].hex()})
                    body = (json.dumps(request, separators=(',', ':'))+'\n').encode()
                    row['raw']['request'] = self.artifact('raw/native.request', body); row['input_sha256'] = digest(body)
                receipt['observations'].append(row)
            receipts[participant] = receipt
        return manifest, receipts['native'], dict(reference=receipts['reference'])

    def verify(self, packet, snapshot=None):
        manifest, native, external = packet
        return compare(manifest, native, external, artifact_root=self.root,
                       expected_manifest_sha256=snapshot or canonical_digest(manifest))

    def test_complete_synthetic_packet_verifies_without_claiming_execution_authentication(self):
        packet=self.packet(); result=self.verify(packet)
        self.assertEqual(result['evidence_status'],'complete',result.get('evidence_validation'))
        self.assertTrue(result['complete_success'])
        self.assertEqual(result['comparison_status'],'agreement')
        self.assertIn('not execution authentication',result['evidence_validation']['scope'])
        self.assertEqual(len(result['diagnostic_observations']),1)

    def test_caller_snapshot_and_participant_identity_are_required(self):
        packet=self.packet(); snapshot=canonical_digest(packet[0])
        self.assertFalse(compare(*packet,artifact_root=self.root)['complete_success'])
        packet[0]['cases'][0]['common_projection']=False
        self.assertEqual(self.verify(packet,snapshot)['evidence_status'],'invalid')
        packet=self.packet();packet[2]['reference']['identity_sha256']='sha256:'+'f'*64
        self.assertEqual(self.verify(packet)['evidence_status'],'invalid')

    def test_changed_raw_fixture_or_executable_cannot_pass(self):
        for mode in ('stdout','fixture','binary'):
            packet=self.packet(); row=packet[2]['reference']['observations'][0]
            if mode=='stdout':(self.root/row['raw']['stdout']['path']).write_bytes(b'changed')
            elif mode=='fixture':(self.root/row['input_after']['path']).write_bytes(b'changed')
            else:row['executable_after_sha256']='sha256:'+'f'*64
            with self.subTest(mode=mode):self.assertFalse(self.verify(packet)['complete_success'])

    def test_projection_cannot_disagree_with_its_retained_raw_bytes(self):
        packet=self.packet();packet[2]['reference']['observations'][0]['projection']['rows'][0]['start']=0
        result=self.verify(packet)
        self.assertEqual(result['evidence_status'],'invalid')
        self.assertIn('raw_projection_binding',result['evidence_validation']['errors'])

    def test_extra_native_kind_cannot_avoid_required_comparisons(self):
        packet=self.packet();manifest,native,external=packet
        declaration=copy.deepcopy(manifest['expected_observations'][0]);declaration['kind']='another-native-kind'
        manifest['expected_observations'].append(declaration)
        row=copy.deepcopy(native['observations'][0]);row['kind']='another-native-kind'
        native['observations'].append(row)
        result=self.verify(packet)
        self.assertFalse(result['complete_success'])
        self.assertEqual(result['evidence_status'],'invalid')
        self.assertEqual(len(result['unvalidated_inputs']['native']['observations']),2)

    def test_refusal_timeout_crash_and_unavailability_are_distinct_complete_observations(self):
        for status, outcome, code in [('refused','exited',1),('timed_out','timeout',-1),('crashed','exited',-2),('unavailable','unavailable',None)]:
            packet=self.packet();row=packet[2]['reference']['observations'][1]
            row.update(outcome=outcome,exit_code=code);row['execution'].update(status=status,exit_code=code)
            if status=='refused':packet[0]['expected_observations'][2]['policy']['allowed_outcomes'].append('refused')
            result=self.verify(packet)
            with self.subTest(status=status):
                self.assertEqual(result['evidence_status'],'complete',result.get('evidence_validation'))
                observed={(v['participant'],v['kind']):v['status'] for v in result['execution']}
                self.assertEqual(observed[('reference','sfdisk-verify')],status)
                self.assertEqual(observed[('native','native')],'completed')
                self.assertEqual(result['complete_success'],status=='refused')

    def test_projection_refusal_does_not_pass_a_common_control(self):
        packet=self.packet();row=packet[2]['reference']['observations'][0]
        row.update(outcome='exited',exit_code=1,projection=None);row['execution'].update(status='refused',exit_code=1)
        packet[0]['expected_observations'][1]['policy']['allowed_outcomes'].append('refused')
        result=self.verify(packet)
        self.assertEqual(result['evidence_status'],'complete')
        self.assertFalse(result['adapter_controls_passed']);self.assertFalse(result['complete_success'])

    def test_complete_disagreement_is_retained_separately_from_evidence_completeness(self):
        packet=self.packet(common=False);row=packet[2]['reference']['observations'][0]
        raw=json.loads(row['stdout']);raw['partitiontable']['partitions'][0]['start']=0
        body=json.dumps(raw).encode();row['raw']['stdout']=self.artifact(row['raw']['stdout']['path'],body)
        row.update(stdout=body.decode(),stdout_sha256=digest(body))
        row['projection']['rows'][0].update(start=0,end=1)
        result=self.verify(packet)
        self.assertTrue(result['complete_success'],result.get('evidence_validation'))
        self.assertEqual(result['comparison_status'],'disagreement')
        self.assertEqual(result['comparisons'][0]['matching_candidates'],[])

    def test_bad_contract_generator_profile_and_argv_cannot_pass_even_with_fresh_artifact_hashes(self):
        for mode in ('contract','generator','profile','argv'):
            packet=self.packet();manifest,native,external=packet
            if mode=='contract':manifest['evidence']['contract']=self.artifact('recipe/CONTRACT.md',b'wrong contract')
            elif mode=='generator':manifest['generator_sha256']='sha256:'+'f'*64
            elif mode=='profile':manifest['evidence']['participants']['reference']['profile']['build']='changed'
            else:external['reference']['observations'][0]['argv']=['different command']
            with self.subTest(mode=mode):self.assertFalse(self.verify(packet)['complete_success'])

    def test_artifact_traversal_hardlink_and_postread_changes_are_refused(self):
        reader=Artifacts(self.root)
        for path in ('../outside','/outside','a/../outside','stream:secret','a\\outside'):
            with self.subTest(path=path),self.assertRaises(ValueError):reader.read(dict(path=path,bytes=0,sha256=digest(b'')))
        descriptor=self.artifact('sample',b'first');reader.read(descriptor)
        (self.root/'sample').write_bytes(b'other')
        with self.assertRaises(ValueError):reader.recheck()
        descriptor=self.artifact('hardlink',b'data');os.link(self.root/'hardlink',self.root/'alias')
        with self.assertRaises(ValueError):Artifacts(self.root).read(descriptor)

    def test_identical_copies_are_all_verified_without_duplicate_payload_storage(self):
        first=self.artifact('copy-one',b'same known bytes');second=self.artifact('copy-two',b'same known bytes')
        reader=Artifacts(self.root);reader.read(first);reader.read(second);reader.recheck()
        self.assertEqual(len(reader.files),2)
        self.assertEqual(reader.total,len(b'same known bytes'))
        self.assertEqual(reader.bytes_read,2*len(b'same known bytes'))

    def test_typed_identity_and_effect_relationships_cannot_be_replaced_by_consistent_hashes(self):
        for mode in ('source','build','revision','changed_after','display','elapsed','exit','request'):
            packet=self.packet();manifest,native,external=packet;row=native['observations'][0]
            if mode in ('source','build','revision'):
                participant=manifest['evidence']['participants']['native'];desc=participant['identity']
                value=json.loads((self.root/desc['path']).read_bytes())
                if mode=='source':value['source']['inputs']={}
                elif mode=='build':value['build']['toolchain']={}
                else:value['source']['revision']=None
                desc=self.artifact(desc['path'],json.dumps(value).encode());participant['identity']=desc
                native['identity_sha256']=desc['sha256'];row['identity_sha256']=desc['sha256']
            elif mode=='changed_after':
                desc=row['input_after'];data=bytearray((self.root/desc['path']).read_bytes());data[-1]^=1
                row['input_after']=self.artifact(desc['path'],bytes(data))
            elif mode=='display':row['stdout']='invented display'
            elif mode=='elapsed':row['execution']['elapsed_seconds']=float('nan')
            elif mode=='exit':row['execution']['exit_code']=1;row['exit_code']=1
            else:
                body=b'{}\n';row['raw']['request']=self.artifact('raw/native.request',body);row['input_sha256']=digest(body)
            with self.subTest(mode=mode):self.assertFalse(self.verify(packet)['complete_success'])

    def test_caller_bound_cli_verifies_a_complete_synthetic_packet(self):
        packet=self.packet();paths=[]
        for name,value in zip(('manifest','native','reference'),(packet[0],packet[1],packet[2]['reference'])):
            path=self.root/(name+'.json');path.write_text(json.dumps(value),encoding='utf-8');paths.append(path)
        output=self.root/'comparison.json'
        result=subprocess.run([sys.executable,'-B',str(HERE/'compare.py'),'--manifest',str(paths[0]),
            '--native',str(paths[1]),'--external','reference='+str(paths[2]),'--artifact-root',str(self.root),
            '--expected-manifest-sha256',canonical_digest(packet[0]),'--output',str(output)],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(output.read_bytes())['complete_success'])

    def test_gpt_candidate_selection_remains_unresolved_in_complete_evidence(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('binding_corpus',HERE.parent/'corpus/partition_images.py')
        corpus=importlib.util.module_from_spec(spec);spec.loader.exec_module(corpus)
        packet=self.packet(common=False);manifest,native,external=packet
        recipe=next(v for v in corpus.recipes() if v['name']=='gpt-valid-disagreement');data=recipe['data']
        case=manifest['cases'][0];case.update(family='gpt',bytes=len(data),blocks=256,sha256=digest(data),checks=recipe['checks'])
        manifest['evidence']['fixtures']['control']=self.artifact('fixtures/control.img',data)
        raw=dict(comparison=2,copies=[]);candidates=[]
        for role,first in [('primary',34),('backup',35)]:
            entries=[dict(active=True,range_valid=True,first=str(start),end=str(end),type_guid=str(corpus.TYPE),
                          unique_guid=str(corpus.uuid.UUID(int=i+1))) for i,(start,end) in enumerate([(first,61),(70,91)])]
            raw['copies'].append(dict(header=dict(disk_guid=str(corpus.DISK),issues=0),candidate=dict(
                entries=entries,issues=0,complete=True,consistent=True)))
            candidates.append(dict(role=role,rows=[dict(slot=i+1,start=start,end=end,type=str(corpus.TYPE),uuid=str(corpus.uuid.UUID(int=i+1)))
                for i,(start,end) in enumerate([(first,61),(70,91)])],disk_uuid=str(corpus.DISK),header_issues=0,array_issues=0,complete=True,consistent=True))
        for receipt in [native,external['reference']]:
            for row in receipt['observations']:
                row.update(bytes=len(data),blocks=256,sha256=digest(data))
                row['input_before']=self.artifact(row['input_before']['path'],data)
                row['input_after']=self.artifact(row['input_after']['path'],data)
                if row['participant']=='native':
                    body=json.dumps(raw).encode();row['projection']=dict(label='gpt',comparison=2,candidates=candidates)
                    request=dict(blocks='256',unit='512',max_entries='1024',max_entry_size='4096',max_bytes='1048576',
                        primary=data[512:1024].hex(),primary_array=data[1024:1024+16384].hex(),
                        backup=data[-512:].hex(),backup_array=data[223*512:223*512+16384].hex())
                    request=(json.dumps(request,separators=(',',':'))+'\n').encode()
                    row['raw']['request']=self.artifact('raw/native.request',request);row['input_sha256']=digest(request)
                elif row['kind']=='sfdisk-json':
                    rows=candidates[1]['rows'];prefix='/frozen/'+row['input_after']['path']
                    body=json.dumps(dict(partitiontable=dict(label='gpt',id=str(corpus.DISK),unit='sectors',sectorsize=512,
                        partitions=[dict(node=prefix+str(v['slot']),start=v['start'],size=v['end']-v['start'],type=v['type'],uuid=v['uuid']) for v in rows]))).encode()
                    row['projection']=dict(label='gpt',rows=copy.deepcopy(rows),disk_uuid=str(corpus.DISK),fields=['slot','start','end','type','uuid'])
                else:continue
                row['raw']['stdout']=self.artifact(row['raw']['stdout']['path'],body)
                row.update(stdout=body.decode(),stdout_sha256=digest(body))
        result=self.verify(packet)
        self.assertTrue(result['complete_success'],result.get('evidence_validation'))
        self.assertEqual(result['comparisons'][0]['matching_candidates'],['backup'])
        self.assertEqual(result['comparisons'][0]['native']['comparison'],2)
        self.assertEqual([v['rows'][0]['start'] for v in result['comparisons'][0]['native']['candidates']],[34,35])


if __name__=='__main__':unittest.main()
