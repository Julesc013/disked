"""Native interrupted-owned-image restoration; independent whole-byte oracles."""
import argparse,copy,hashlib,json,queue,struct,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_gpt_execution import canonical,sha,expected,receipts,fixture,change_array

def request(case,source='primary',phase='create',**extra):
    v=dict(phase=phase,image_hex=case['raw'].hex(),logical_block_bytes=case['capture']['block_bytes'],authoritative_copy=source,expected_capture_digest=case['definition']['capture_digest'],expected_plan_digest=case['plan_digest']);v.update(extra);return v
def reader(process):
    rows=queue.Queue()
    def read():
        try:
            for line in process.stdout:rows.put(json.loads(line))
        finally:rows.put(None)
    thread=threading.Thread(target=read,daemon=True);thread.start();return rows,thread
def send(process,value):process.stdin.write(canonical(value)+b'\n');process.stdin.flush()
def close(process,thread):
    if process.poll() is None:process.kill();process.wait(timeout=5)
    thread.join(timeout=1)
    if not process.stdin.closed:process.stdin.close()
    process.stdout.close();process.stderr.close()
def recovery_receipts(prepared):
    d=prepared['definition'];review=dict(schema='org.disked.gpt-restoration-review/1',restoration_digest=prepared['restoration_digest'],observed_image_digest=d['observed_image_digest'],reviewed=True,issuer='fixture-controller',evidence_digest=sha(b'independent-restoration-byte-oracle'))
    grant=dict(schema='org.disked.gpt-restoration-grant/1',restoration_digest=prepared['restoration_digest'],review_digest=sha(canonical(review)),original_manifest_digest=d['original_manifest_digest'],executor_digest=d['resources']['executor_digest'],patch_ids=[p['id'] for p in d['patches']],allow_fixture_restoration=True,allow_new_recovery_journal=True,acknowledge_nonatomic_same_volume=True);return review,grant
def expected_patches(case,current):
    out=[]
    for p in reversed(case['patches']):
        before=current[p['offset']:p['offset']+len(p['before'])]
        if before!=p['before']:out.append(dict(id=p['id'],offset=str(p['offset']),bytes=str(len(before)),before_sha256=sha(before),after_sha256=sha(p['before']),depends_on=[] if not out else [out[-1]['id']]))
    return out
def journal(raw,definition,digest,review,grant,store):
    if len(raw)<192:return 0
    assert raw[:8]==b'DEJPR001' and raw[160:192]==hashlib.sha256(raw[:160]).digest() and raw[40:72]==bytes.fromhex(digest[7:]) and raw[24:40]==bytes.fromhex(store['identity'][7:])[:16]
    assert raw[72:104]==hashlib.sha256(canonical(dict(original=definition['resources'],recovery_store=store))).digest() and raw[104:136]==hashlib.sha256(canonical(dict(provider=definition['resources']['provider_id'],executor=store['executor_digest']))).digest()
    at=192;previous=raw[160:192];n=0
    while at<len(raw):
        if len(raw)-at<112:break
        prefix=raw[at:at+112];assert prefix[:4]==b'JREC';kind,flags,header,length,sequence=struct.unpack_from('<HHIIQ',prefix,4);assert flags==1 and header==112 and sequence==n+1 and prefix[24:40]==bytes.fromhex(store['publisher_identity']) and struct.unpack_from('<Q',prefix,40)[0]==int(store['publisher_epoch']) and prefix[48:80]==previous
        if len(raw)-at<144+length:break
        payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length];assert hashlib.sha256(payload).digest()==prefix[80:112] and hashlib.sha256(raw[160:192]+prefix+payload).digest()==trailer;v=json.loads(payload);assert canonical(v)==payload
        if n<3:assert kind==n+1 and v==[definition,review,grant][n]
        else:assert v['restoration_digest']==digest
        n+=1;previous=trailer;at+=144+length
    return n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--evidence',type=Path);a=ap.parse_args();a.probe=a.probe.resolve();a.root=a.root.resolve();records=[];passed=False;probe_sha=sha(a.probe.read_bytes())
    def record(name,**data):records.append(dict(name=name,**data));print('CASE '+ascii(name),flush=True)
    def make(parent,name,case,source='primary',fault=None,cancel='none'):
        folder=parent/name;folder.mkdir();process=subprocess.Popen([str(a.probe),'--fixture-parent',str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);rows,thread=reader(process)
        try:
            v=request(case,source)
            if fault:v['fault']=fault
            send(process,v);prepared=rows.get(timeout=15);assert prepared['phase']=='prepared' and prepared['definition']==case['definition'];review,grant=receipts(prepared);send(process,dict(phase='execute',review=review,grant=grant,cancel_at=cancel));process.stdin.close();finish=rows.get(timeout=15);code=process.wait(timeout=15);assert not process.stderr.read()
            assert code in (0,3,6,112),(code,finish);owned=Path(prepared['manifest']['directory']);assert owned.is_relative_to(folder);return dict(preparation=prepared,review=review,grant=grant,owned=owned,case=case,source=source,original_code=code)
        finally:close(process,thread)
    def restore(name,fixture_data,fault=None,mutate=None,change_after_review=None,expect_refusal=None,attempt=None,expect_effect_refusal=None):
        case=fixture_data['case'];owned=fixture_data['owned'];image=owned/'image.bin';before=image.read_bytes();old_artifacts={p.name:p.read_bytes() for p in owned.iterdir() if p.name!='image.bin'};files_before=set(old_artifacts);attempt=attempt or uuid.uuid4().hex
        v=request(case,fixture_data['source'],'restore',manifest=fixture_data['preparation']['manifest'],review=fixture_data['review'],grant=fixture_data['grant'],attempt_id=attempt)
        if fault:v['fault']=fault
        process=subprocess.Popen([str(a.probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);rows,thread=reader(process);prepared=store=finish=None;review=grant=None;fixture_added=set()
        try:
            send(process,v);first=rows.get(timeout=15)
            if first and first['phase']=='restoration_prepared':
                prepared=first;d=prepared['definition'];assert d['patches']==expected_patches(case,before) and d['original_image_digest']==sha(case['raw']) and d['observed_image_digest']==sha(before) and d['backup_digest']==sha(old_artifacts['backup.bin']) and d['original_journal_digest']==sha(old_artifacts['journal.bin']) and d['resources']==fixture_data['preparation']['manifest'];assert prepared['restoration_digest']==sha(canonical(d));assert not prepared['execution_authorized'] and not any('.write.' in e['stage'] or '.flush.' in e['stage'] for e in prepared['events'])
                assert set(p.name for p in owned.iterdir())==files_before|{'image.bin'}
                review,grant=recovery_receipts(prepared);instruction=dict(phase='restore-execute',review=copy.deepcopy(review),grant=copy.deepcopy(grant))
                if mutate:mutate(instruction)
                if change_after_review:
                    change_after_review(owned);fixture_added={p.name for p in owned.iterdir()}-files_before-{'image.bin'}
                send(process,instruction);process.stdin.close();next_row=rows.get(timeout=15)
                if next_row and next_row['phase']=='restoration_store':store=next_row['store'];finish=rows.get(timeout=15)
                else:finish=next_row
            else:finish=first;process.stdin.close()
            code=process.wait(timeout=15);assert not process.stderr.read();thread.join(timeout=1)
            while not rows.empty():assert rows.get_nowait() is None
            current=image.read_bytes();new_files={p.name for p in owned.iterdir()}-files_before-{'image.bin'}-fixture_added
            for file,data in old_artifacts.items():assert (owned/file).read_bytes()==data,'Changed retained artifact '+file
            if expect_refusal:
                assert code==3 and finish['phase']=='refused' and finish['diagnostic']==expect_refusal,(code,finish)
                assert current==before and not new_files
            elif mutate:
                assert code==3 and finish['phase']=='refused' and current==before and not new_files
            elif code==0:
                assert finish['phase']=='restoration_finished' and finish['restoration']['status'] in ('restored_original_basis','unchanged') and current==case['raw']
                assert len(new_files)==1 and store and new_files=={store['name']}
            elif code in (3,6):
                assert finish['phase']=='restoration_finished' and finish['restoration']['status'] in ('refused','unresolved'),finish
                if fault:assert finish['fault_fired']
                if expect_effect_refusal:assert code==3 and finish['restoration']['diagnostic']==expect_effect_refusal and not finish['restoration']['possible_image_effects']
            else:assert code==112 and finish is None and fault
            if not change_after_review:
                assert all(now==old or any(int(p['offset'])<=i<int(p['offset'])+int(p['bytes']) for p in (prepared['definition']['patches'] if prepared else [])) for i,(now,old) in enumerate(zip(current,before))),'Changed outside restoration patches'
            raw=b''
            if store:
                raw=(owned/store['name']).read_bytes();journal(raw,prepared['definition'],prepared['restoration_digest'],review,grant,store)
            record(name,exit_code=code,preparation=prepared,store=store,finish=finish,review=review,grant=grant,image_before_sha256=sha(before),image_after_sha256=sha(current),original_image_sha256=sha(case['raw']),journal_hex=raw.hex(),old_artifacts_sha256={n:sha(data) for n,data in old_artifacts.items()},fault=fault)
            return finish,prepared,store
        finally:close(process,thread)
    try:
        parent=a.root/'.aide-local';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='gpt-restore-',dir=parent) as directory:
            parent=Path(directory);assert parent.resolve().is_relative_to((a.root/'.aide-local').resolve())
            def case_for(unit=512,source='primary'):
                target='backup' if source=='primary' else 'primary';f=fixture(unit=unit);change_array(f,lambda b:b.__setitem__(0,b[0]^1),target,False)
                header=bytearray.fromhex(f[target]);header[16]^=1;f[target]=header.hex();return expected(f,source)
            normal=None;basic=case_for()
            for unit in (512,4096):
                for source in ('primary','backup'):
                    case=case_for(unit,source);data=make(parent,str(unit)+'-'+source,case,source,fault=dict(stage='image.write.2',action='crash_after'));result=restore(str(unit)+'-'+source,data)
                    if unit==512 and source=='primary':normal=result[0]
            stages=[e['stage'] for e in normal['events'] if '.write.' in e['stage'] or '.flush.' in e['stage']];assert stages and all(int(e['bytes'])<=65536 for e in normal['events'] if '.write.' in e['stage'])
            for index,stage in enumerate(stages):
                for action in ('crash_before','crash_after','before_error','after_error'):
                    name='restore-'+str(index)+'-'+action;data=make(parent,name,basic,fault=dict(stage='image.write.2',action='crash_after'));restore(name,data,fault=dict(stage=stage,action=action))
                if '.write.' in stage:
                    name='restore-'+str(index)+'-partial';data=make(parent,name,basic,fault=dict(stage='image.write.2',action='crash_after'));restore(name,data,fault=dict(stage=stage,action='partial_error'))
            for key in ['restoration_digest','review_digest','original_manifest_digest','executor_digest']:
                data=make(parent,'grant-'+key,basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-'+key,data,mutate=lambda v,key=key:v['grant'].__setitem__(key,sha(b'wrong')))
            for key in ['allow_fixture_restoration','allow_new_recovery_journal','acknowledge_nonatomic_same_volume']:
                data=make(parent,'grant-'+key,basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-'+key,data,mutate=lambda v,key=key:v['grant'].__setitem__(key,False))
            data=make(parent,'grant-scope',basic,fault=dict(stage='image.write.1',action='crash_after'));restore('grant-scope',data,mutate=lambda v:v['grant'].__setitem__('patch_ids',[]))
            data=make(parent,'completed',basic);restore('completed-refused',data,expect_refusal='restoration_completed_operation')
            data=make(parent,'cancelled',basic,cancel='after-first-patch');restore('cancelled-prefix',data)
            data=make(parent,'before-effects',basic,fault=dict(stage='image.write.1',action='crash_before'));restore('already-original',data)
            data=make(parent,'foreign',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'image.bin';raw=bytearray(p.read_bytes());raw[20*512]=0x80;p.write_bytes(raw);restore('foreign-byte-refused',data,expect_refusal='restoration_foreign_bytes')
            data=make(parent,'backup',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'backup.bin';p.write_bytes(p.read_bytes()[:-1]);restore('backup-refused',data,expect_refusal='restoration_backup_invalid')
            data=make(parent,'history',basic,fault=dict(stage='image.write.1',action='crash_after'));p=data['owned']/'journal.bin';raw=bytearray(p.read_bytes());raw[160]^=1;p.write_bytes(raw);restore('history-refused',data,expect_refusal='restoration_history_invalid')
            data=make(parent,'repeated',basic,fault=dict(stage='image.write.1',action='crash_after'));restore('repeated-first',data,fault=dict(stage='image.write.1',action='partial_error'));restore('repeated-second',data)
            # A grant binds the reviewed full snapshot, not merely object IDs.
            data=make(parent,'stale-snapshot',basic,fault=dict(stage='image.write.1',action='crash_after'))
            def alter_snapshot(root):
                p=root/'image.bin';v=bytearray(p.read_bytes());v[20*512]^=0x80;p.write_bytes(v)
            restore('snapshot-changed-after-review',data,change_after_review=alter_snapshot,expect_effect_refusal='restoration_snapshot_changed')
            data=make(parent,'swapped-after-review',basic,fault=dict(stage='image.write.1',action='crash_after'))
            def replace_object(root):
                p=root/'image.bin';v=p.read_bytes();p.rename(root/'retired-image.bin');p.write_bytes(v)
            restore('identity-changed-after-review',data,change_after_review=replace_object,expect_refusal='fixture_file_changed')
            data=make(parent,'journal-collision',basic,fault=dict(stage='image.write.2',action='crash_after'));attempt=uuid.uuid4().hex
            restore('journal-collision-first',data,fault=dict(stage='recovery.write.1',action='partial_error'),attempt=attempt);restore('journal-collision-refused',data,attempt=attempt,expect_refusal='fixture_open')
            # Partial large-array restoration must retain old image and journals
            # outside its exact reverse patch, then admit only a new fresh plan.
            f=fixture(blocks=8192,count=1024,size=1024);f['backup_array']=bytes(b^0x5a for b in bytes.fromhex(f['backup_array'])).hex();large=expected(f)
            for index,stage in enumerate(['image.write.8','image.write.16','image.flush.1']):
                data=make(parent,'large-'+str(index),large,fault=dict(stage='image.write.16',action='crash_after'))
                restore('large-interruption-'+str(index),data,fault=dict(stage=stage,action='crash_after'));restore('large-restoration-'+str(index),data)
        passed=True
    finally:
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),probe_sha256=probe_sha,records=records),indent=2)+'\n',encoding='utf8',newline='\n')
    print('Owned GPT restoration PASS '+str(len(records)),flush=True)
if __name__=='__main__':main()
