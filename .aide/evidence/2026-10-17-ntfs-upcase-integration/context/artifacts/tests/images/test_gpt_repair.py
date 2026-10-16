"""Independent supplied-byte GPT repair preview oracles; never writes an image."""
import argparse,copy,hashlib,json,random,struct,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'property'))
from test_gpt import fixture,entry,change_array,change_header,fix_header,equal_crc_patch

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def capture(f):
    unit=int(f['unit']);blocks=int(f['blocks']);mbr=bytearray(unit);mbr[510:512]=b'\x55\xaa'
    struct.pack_into('<B3sB3sII',mbr,446,0,b'\x00\x02\x00',0xee,b'\xff'*3,1,min(blocks-1,2**32-1))
    return dict(image_id='image:gpt-fixture',epoch='1',blocks=str(blocks),block_bytes=str(unit),protective_mbr=mbr.hex(),primary_header=f['primary'],primary_array=f['primary_array'],backup_header=f['backup'],backup_array=f['backup_array'])
def metadata(c):
    v=dict(schema='org.disked.gpt-repair-capture-prototype/1',**{k:c[k] for k in ('image_id','epoch','blocks','block_bytes')})
    for k in ('protective_mbr','primary_header','primary_array','backup_header','backup_array'):
        raw=bytes.fromhex(c[k]);v[k]=dict(bytes=str(len(raw)),sha256=digest(raw))
    return v
def fingerprint(c):return digest(b'DiskEd.gpt-repair.capture/1\n'+canonical(metadata(c)))
def damaged(f,side='backup'):
    f=copy.deepcopy(f);raw=bytearray.fromhex(f[side+'_array']);raw[0]^=1;f[side+'_array']=raw.hex();return f

class RepairTests(unittest.TestCase):
    def invoke(self,c,source='primary',decision=None,expected=None,mode='plan',changed=None,refusal=None):
        p=dict(mode=mode,capture=c,source=source,expected_capture_digest=expected or fingerprint(c),selection_decision_digest=decision)
        if changed is not None:p['changed_capture']=changed
        raw=canonical(p);self.inputs.append(dict(input_sha256=digest(raw),input_bytes=len(raw),source=source,mode=mode))
        before=list(self.empty.iterdir());r=subprocess.run([self.probe],input=raw,capture_output=True,cwd=self.empty,timeout=12)
        self.assertFalse(r.stderr);self.assertEqual(before,list(self.empty.iterdir()));v=json.loads(r.stdout)
        self.outputs.append(dict(exit_code=r.returncode,output_sha256=digest(r.stdout),output_bytes=len(r.stdout)))
        if refusal is not None:self.assertEqual(3,r.returncode);self.assertEqual(refusal,v['code']);self.assertFalse(v['authorizes_effects']);return v
        self.assertEqual(0,r.returncode);self.assertTrue(v['input_unchanged']);self.assertTrue(v['matches_original']);self.audit(c,source,decision,v);return v
    def audit(self,c,source,decision,v):
        definition=v['definition'];self.assertEqual(digest(canonical(definition)),v['plan_digest']);self.assertEqual(metadata(c),definition['capture']);self.assertEqual(fingerprint(c),definition['capture_digest'])
        self.assertEqual(source,definition['authoritative_copy']);target='backup' if source=='primary' else 'primary';self.assertEqual(target,definition['target_copy']);self.assertEqual(decision,definition['selection_decision_digest'])
        for k in ('authorizes_effects','writer_admitted','qualifies_durability','qualifies_recovery'):self.assertFalse(definition[k])
        simulation=definition['simulation'];self.assertEqual('shared-parser-byte-overlay',simulation['type']);self.assertTrue(simulation['both_copies_agree']);self.assertTrue(simulation['both_copies_consistent']);self.assertFalse(simulation['independent_verification']);self.assertFalse(simulation['whole_device_valid'])
        original={k:bytearray.fromhex(c[k]) for k in ('protective_mbr','primary_header','primary_array','backup_header','backup_array')};overlay=copy.deepcopy(original)
        sh=original[source+'_header'];th=original[target+'_header'];count,size=struct.unpack_from('<II',sh,80);used=count*size;hs=struct.unpack_from('<I',th,12)[0];unit=int(c['block_bytes'])
        expected_array=bytes(original[source+'_array'][:used]);expected_header=bytearray(th);struct.pack_into('<I',expected_header,88,zlib.crc32(expected_array));fix_header(expected_header)
        wanted=[]
        if original[target+'_array'][:used]!=expected_array:wanted.append(('target-array',struct.unpack_from('<Q',th,72)[0]*unit,bytes(original[target+'_array'][:used]),expected_array,target+'_array'))
        if th[:hs]!=expected_header[:hs]:wanted.append(('target-header',struct.unpack_from('<Q',th,24)[0]*unit,bytes(th[:hs]),bytes(expected_header[:hs]),target+'_header'))
        self.assertEqual(len(wanted),len(definition['patches']));self.assertEqual(len(wanted),len(v['patch_bytes']))
        for i,((name,offset,before,after,key),patch,values) in enumerate(zip(wanted,definition['patches'],v['patch_bytes'])):
            self.assertEqual(name,patch['id']);self.assertEqual(str(offset),patch['offset']);self.assertEqual(str(len(before)),patch['bytes']);self.assertEqual(digest(before),patch['before_sha256']);self.assertEqual(digest(after),patch['after_sha256']);self.assertEqual([] if i==0 else [wanted[i-1][0]],patch['depends_on']);self.assertEqual(before,bytes.fromhex(values['before_hex']));self.assertEqual(after,bytes.fromhex(values['after_hex']));overlay[key][:len(after)]=after
        self.assertEqual('repair_preview' if wanted else 'no_change',definition['status']);self.assertEqual(original['protective_mbr'],overlay['protective_mbr']);self.assertEqual(original[source+'_header'],overlay[source+'_header']);self.assertEqual(original[source+'_array'],overlay[source+'_array'])
        self.assertEqual(original[target+'_array'][used:],overlay[target+'_array'][used:]);self.assertEqual(original[target+'_header'][hs:],overlay[target+'_header'][hs:])
        self.assertEqual(overlay['primary_array'][:used],overlay['backup_array'][:used])
        for side in ('primary','backup'):
            h=bytearray(overlay[side+'_header']);crc=struct.unpack_from('<I',h,16)[0];struct.pack_into('<I',h,16,0);self.assertEqual(crc,zlib.crc32(h[:hs]));self.assertEqual(zlib.crc32(overlay[side+'_array'][:used]),struct.unpack_from('<I',h,88)[0])
    def test_repair_both_roles_and_block_sizes(self):
        for unit in (512,513,4096,65536):
            for source in ('primary','backup'):
                target='backup' if source=='primary' else 'primary';f=damaged(fixture(unit=unit),target);self.invoke(capture(f),source)
    def test_header_checksum_and_combined_damage(self):
        for source in ('primary','backup'):
            target='backup' if source=='primary' else 'primary'
            for array in (False,True):
                f=damaged(fixture(),target) if array else fixture();raw=bytearray.fromhex(f[target]);raw[16]^=1;f[target]=raw.hex();v=self.invoke(capture(f),source);self.assertEqual('target-header',v['definition']['patches'][-1]['id'])
    def test_consistent_disagreement_requires_explicit_decision(self):
        f=fixture();change_array(f,lambda data:data.__setitem__(slice(56,64),'Swap'.encode('utf-16-le')));c=capture(f)
        self.invoke(c,'backup',refusal='repair_selection_required');self.invoke(c,'backup',decision=digest(b'selection-record'))
    def test_equal_crc_is_not_equal_payload(self):
        f=fixture(count=2);data=bytearray.fromhex(f['backup_array']);payload=bytearray(data[:256]);crc=zlib.crc32(payload);payload[56:64]='Move'.encode('utf-16-le');equal_crc_patch(payload,124,crc);data[:256]=payload;f['backup_array']=data.hex()
        self.assertEqual(zlib.crc32(bytes.fromhex(f['primary_array'])[:256]),zlib.crc32(data[:256]));c=capture(f)
        # CRC patch is after the existing name terminator and is preserved as
        # original representation; both arrays retain valid semantic entries.
        self.invoke(c,'primary',refusal='repair_selection_required')
        self.invoke(c,'primary',decision=digest(b'explicit-selected-source'))
    def test_already_agree_is_empty_preview(self):
        for source in ('primary','backup'):self.assertEqual([],self.invoke(capture(fixture()),source)['definition']['patches'])
    def test_exact_names_guids_attributes_and_declared_locations(self):
        f=fixture(entries=[entry(34,38,identity=123,name='A\u030a \U0001f4be',attributes=1<<63)])
        # Actual array locations are explicit metadata, not inferred defaults.
        change_header(f,72,'<Q',10,'primary');change_header(f,72,'<Q',79,'backup')
        raw=bytearray.fromhex(f['primary_array']);raw[90:96]=b'opaque';f['primary_array']=raw.hex()
        # Representation after NUL is preserved while display ends at NUL.
        h=bytearray.fromhex(f['primary']);struct.pack_into('<I',h,88,zlib.crc32(raw[:512]));fix_header(h);f['primary']=h.hex()
        c=capture(f);self.invoke(c,refusal='repair_selection_required');v=self.invoke(c,decision=digest(b'keep-exact-source'))
        self.assertEqual('40448',v['definition']['patches'][0]['offset'])
        self.assertEqual(bytes.fromhex(c['primary_array']),bytes.fromhex(v['patch_bytes'][0]['after_hex']))
    def test_explicit_source_and_probe_type_refusals(self):
        c=capture(damaged(fixture()));self.invoke(c,source='auto',refusal='probe_shape')
        changed=copy.deepcopy(c);changed['epoch']='01';self.invoke(changed,refusal='probe_shape')
    def test_exact_high_addresses(self):
        c=capture(damaged(fixture(blocks=2**54+19)));v=self.invoke(c);self.assertGreater(int(v['definition']['patches'][0]['offset']),2**53)
    def test_selected_profile_maxima(self):
        self.invoke(capture(damaged(fixture(blocks=8192,count=1024,size=1024))))
        self.invoke(capture(damaged(fixture(unit=1048576))))
    def test_input_binding_and_plan_ownership(self):
        c=capture(damaged(fixture()));v=self.invoke(c,mode='mutate_after_build');self.assertFalse(v['matches_changed']);self.assertTrue(v['definition_unchanged'])
        for field in ('image_id','epoch','blocks','block_bytes','protective_mbr','primary_header','primary_array','backup_header','backup_array'):
            changed=copy.deepcopy(c)
            if field in ('image_id','epoch','blocks','block_bytes'):changed[field]={'image_id':'image:other','epoch':'2','blocks':'101','block_bytes':'4096'}[field]
            else:raw=bytearray.fromhex(changed[field]);raw[-1]^=1;changed[field]=raw.hex()
            self.invoke(changed,expected=fingerprint(c),refusal='repair_capture_mismatch');self.assertFalse(self.invoke(c,mode='check_binding',changed=changed)['matches_changed'])
    def test_source_truncation_corruption_and_budget(self):
        f=damaged(fixture());f['primary']=f['primary'][:-2];self.invoke(capture(f),refusal='repair_source_unusable')
        f=damaged(fixture());f['primary_array']=f['primary_array'][:-2];self.invoke(capture(f),refusal='repair_source_unusable')
        for key in ('primary','primary_array'):
            f=fixture();f[key]+='00';self.invoke(capture(f),refusal='repair_source_unusable')
        self.invoke(capture(damaged(fixture(),'primary')),refusal='repair_source_unusable')
        f=fixture(blocks=1024,count=1025);self.invoke(capture(f),refusal='repair_budget')
    def test_unknown_target_layout_never_guesses(self):
        for offset,fmt,value in ((0,'8s',b'NO TABLE'),(24,'Q',97),(72,'Q',2),(56,'16s',b'\xff'*16),(80,'I',3),(48,'Q',64)):
            f=fixture();change_header(f,offset,'<'+fmt,value,'backup');c=capture(f);code='repair_layout_conflict' if offset in (56,80,48) else 'repair_target_structure';self.invoke(c,refusal=code)
        f=fixture();f['backup_array']=f['backup_array'][:-2];self.invoke(capture(f),refusal='repair_target_structure')
    def test_padding_and_pmbr_are_never_normalized(self):
        f=fixture(count=3);raw=bytearray.fromhex(f['backup_array']);raw[-1]=1;f['backup_array']=raw.hex();self.invoke(capture(f),refusal='repair_target_structure')
        for offset,value in ((510,0),(450,0x07),(462,1),(440,1)):
            c=capture(damaged(fixture()));raw=bytearray.fromhex(c['protective_mbr']);raw[offset]=value;c['protective_mbr']=raw.hex();self.invoke(c,refusal='repair_protective_mbr')
    def test_declared_selection_changes_identity(self):
        c=capture(damaged(fixture()));a=self.invoke(c);b=self.invoke(c,decision=digest(b'extra-decision'));self.assertNotEqual(a['plan_digest'],b['plan_digest'])
        self.invoke(c,decision='sha256:'+'0'*64,refusal='repair_input_invalid')
    def test_overflow_and_profile_limit(self):
        c=capture(damaged(fixture()));c['blocks']=str(2**64-1);self.invoke(c,refusal='repair_offset_overflow')
        c=capture(damaged(fixture()));c['epoch']='0';self.invoke(c,refusal='repair_input_invalid')
    def test_deterministic_corruption_campaign(self):
        rng=random.Random(4104)
        for _ in range(40):
            source=rng.choice(('primary','backup'));target='backup' if source=='primary' else 'primary';f=fixture(count=7);data=bytearray.fromhex(f[target+'_array']);index=rng.randrange(7*128);data[index]^=1<<rng.randrange(8);f[target+'_array']=data.hex();self.invoke(capture(f),source)

def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--evidence',type=Path);args=p.parse_args();RepairTests.probe=str(args.probe.resolve());RepairTests.inputs=[];RepairTests.outputs=[]
    with tempfile.TemporaryDirectory(prefix='disked-gpt-preview-') as folder:
        RepairTests.empty=Path(folder);suite=unittest.defaultTestLoader.loadTestsFromTestCase(RepairTests);r=unittest.TextTestRunner(verbosity=2).run(suite)
    value=dict(passed=r.wasSuccessful(),tests=r.testsRun,executions=len(RepairTests.outputs),inputs=RepairTests.inputs,outputs=RepairTests.outputs,probe_sha256=digest(args.probe.read_bytes()),scope='Pure supplied-byte previews, independent Python exact patch/CRC/untouched-byte checks and bounded corruptions; no image writes, provider/public/writer/recovery/other-platform admission')
    if args.evidence:args.evidence.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('inputs','outputs')}));sys.exit(0 if r.wasSuccessful() else 1)
if __name__=='__main__':main()
