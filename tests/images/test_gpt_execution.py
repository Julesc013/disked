"""Independent byte/journal oracles for new owned native image effects only."""
import argparse,copy,hashlib,json,os,queue,struct,subprocess,sys,tempfile,threading,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'property'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from test_gpt import fixture,change_array,change_header,fix_header,equal_crc_patch
from test_gpt_repair import capture,metadata,fingerprint
from test_gpt_repair_command import image as image_bytes

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent as managed_parent, managed_directory

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def regions(raw,c):
    unit=int(c['block_bytes']);blocks=int(c['blocks']);rows=[]
    for name,offset in [('protective_mbr',0),('primary_header',unit),('primary_array',struct.unpack_from('<Q',bytes.fromhex(c['primary_header']),72)[0]*unit),('backup_header',(blocks-1)*unit),('backup_array',struct.unpack_from('<Q',bytes.fromhex(c['backup_header']),72)[0]*unit)]:
        size=len(bytes.fromhex(c[name]));rows.append((name,offset,raw[offset:offset+size]))
    return rows
def current_capture(raw,c):
    v=copy.deepcopy(c)
    for name,offset,b in regions(raw,c):v[name]=b.hex()
    return v
def expected(f,source='primary',decision=None):
    c=capture(f);raw=image_bytes(f);target='backup' if source=='primary' else 'primary';unit=int(c['block_bytes']);sh=bytes.fromhex(c[source+'_header']);th=bytearray.fromhex(c[target+'_header']);count,size=struct.unpack_from('<II',sh,80);used=count*size;hs=struct.unpack_from('<I',th,12)[0]
    array=bytes.fromhex(c[source+'_array'])[:used];struct.pack_into('<I',th,88,zlib.crc32(array));fix_header(th);patches=[]
    for name,offset,before,after in [('target-array',struct.unpack_from('<Q',th,72)[0]*unit,bytes.fromhex(c[target+'_array'])[:used],array),('target-header',struct.unpack_from('<Q',th,24)[0]*unit,bytes.fromhex(c[target+'_header'])[:hs],bytes(th[:hs]))]:
        if before!=after:patches.append(dict(id=name,offset=offset,before=before,after=after))
    d=dict(schema='org.disked.gpt-repair-preview-prototype/1',operation='table.gpt.repair',profile='gpt-repair-planning-prototype/1',capture=metadata(c),capture_digest=fingerprint(c),authoritative_copy=source,target_copy=target,selection_decision_digest=decision,status='repair_preview' if patches else 'no_change',patches=[dict(id=p['id'],offset=str(p['offset']),bytes=str(len(p['before'])),before_sha256=sha(p['before']),after_sha256=sha(p['after']),depends_on=[] if i==0 else [patches[i-1]['id']]) for i,p in enumerate(patches)],execution_requirements=['fresh-exact-image-and-recapture','exclusive-access-and-resolved-dependencies','original-metadata-backup','accepted-journal-and-recovery-policy','admitted-provider-byte-write-scope','exact-plan-review-grant-admission','flush-reread-independent-verification'],simulation=dict(type='shared-parser-byte-overlay',both_copies_consistent=True,both_copies_agree=True,coverage='supplied-captures-only',independent_verification=False,whole_device_valid=False),authorizes_effects=False,writer_admitted=False,qualifies_durability=False,qualifies_recovery=False)
    md=[];payload=b''
    for name,offset,b in regions(raw,c):md.append(dict(name=name,image_offset=str(offset),payload_offset=str(len(payload)),bytes=str(len(b)),sha256=sha(b)));payload+=b
    backup_manifest=canonical(dict(schema='org.disked.gpt-fixture-backup/1',plan_digest=sha(canonical(d)),capture_digest=fingerprint(c),regions=md));backup=b'DEGBK001'+struct.pack('<I',len(backup_manifest))+backup_manifest+payload
    return dict(capture=c,raw=raw,definition=d,plan_digest=sha(canonical(d)),patches=patches,backup=backup)
def overlay(case,count):
    raw=bytearray(case['raw'])
    for patch in case['patches'][:count]:raw[patch['offset']:patch['offset']+len(patch['after'])]=patch['after']
    return bytes(raw)
def receipts(prepared):
    m=prepared['manifest'];review=dict(schema='org.disked.gpt-fixture-review/1',plan_digest=prepared['plan_digest'],capture_digest=prepared['definition']['capture_digest'],manifest_digest=sha(canonical(m)),reviewed=True,issuer='fixture-controller',evidence_digest=sha(b'independent-fixture-oracle'))
    grant=dict(schema='org.disked.gpt-fixture-grant/1',plan_digest=prepared['plan_digest'],review_digest=sha(canonical(review)),manifest_digest=sha(canonical(m)),provider_id=m['provider_id'],executor_digest=m['executor_digest'],image_identity=m['image_identity'],backup_identity=m['backup_identity'],journal_identity=m['journal_identity'],patch_ids=[p['id'] for p in prepared['definition']['patches']],allow_fixture_writes=True,acknowledge_proposed_journal=True)
    return review,grant
def journal(raw,case,prepared,review,grant):
    m=prepared['manifest'];base=dict(disposition='invalid',diagnostic='journal_header_incomplete',records=0,verified_bytes=0,completed=0,pending=False,sealed=False,outcome='',bootstrap=0)
    if len(raw)<192:return base
    assert raw[:8]==b'DEJPR001' and struct.unpack_from('<HHIII',raw,8)==(1,0,192,0,65536) and raw[136:160]==b'\0'*24 and raw[160:192]==hashlib.sha256(raw[:160]).digest()
    assert raw[24:40]==bytes.fromhex(m['journal_identity'][7:])[:16] and raw[40:72]==bytes.fromhex(case['plan_digest'][7:])
    assert raw[72:104]==hashlib.sha256(canonical(dict(root=m['root_identity'],image=m['image_identity'],backup=m['backup_identity'],journal=m['journal_identity'],image_bytes=m['image_bytes']))).digest()
    assert raw[104:136]==hashlib.sha256(canonical(dict(provider=m['provider_id'],executor=m['executor_digest']))).digest()
    admission=dict(schema='org.disked.gpt-fixture-admission/1',plan_digest=case['plan_digest'],capture_digest=case['definition']['capture_digest'],review_digest=sha(canonical(review)),grant_digest=sha(canonical(grant)),manifest_digest=sha(canonical(m)),backup_digest=sha(case['backup']),fixture_only=True)
    bootstrap=[case['definition'],review,grant,admission];at=192;previous=raw[160:192];base.update(disposition='valid_prefix',diagnostic='',verified_bytes=192);cancelled=False
    while at<len(raw):
        if len(raw)-at<112:base.update(disposition='torn_tail',diagnostic='journal_final_prefix_incomplete');break
        prefix=raw[at:at+112];assert prefix[:4]==b'JREC';kind,flags,prefix_bytes,length,seq=struct.unpack_from('<HHIIQ',prefix,4);assert flags==1 and prefix_bytes==112 and length<=65536 and seq==base['records']+1 and prefix[24:40]==bytes.fromhex(m['publisher_identity']) and struct.unpack_from('<Q',prefix,40)[0]==int(m['publisher_epoch']) and prefix[48:80]==previous
        if len(raw)-at<112+length+32:base.update(disposition='torn_tail',diagnostic='journal_final_record_incomplete');break
        payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length];assert hashlib.sha256(payload).digest()==prefix[80:112] and hashlib.sha256(raw[160:192]+prefix+payload).digest()==trailer
        value=json.loads(payload);assert canonical(value)==payload
        if base['records']<4:assert kind==base['records']+1 and value==bootstrap[base['records']];base['bootstrap']+=1
        else:
            index=base['completed']+(kind==6);event={5:'intention',6:'completion',7:'cancellation',9:'seal-cancelled' if cancelled else 'seal-completed'}[kind]
            want=dict(schema='org.disked.gpt-fixture-journal/1',event=event,plan_digest=case['plan_digest'],backup_digest=sha(case['backup']),prefix=str(index),capture_digest=fingerprint(current_capture(overlay(case,index),case['capture'])))
            if kind in (5,6):want['patch']=case['definition']['patches'][base['completed']]
            assert value==want
            if kind==5:assert not base['pending'] and not cancelled;base['pending']=True
            elif kind==6:assert base['pending'];base['pending']=False;base['completed']+=1
            elif kind==7:assert not base['pending'] and base['completed'] and not cancelled;cancelled=True
            else:assert not base['pending'] and (cancelled or base['completed']==len(case['patches']));base['sealed']=True;base['outcome']=event;assert at+144+length==len(raw)
        at+=144+length;previous=trailer;base['records']+=1;base['verified_bytes']=at
    return base

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--evidence',type=Path);a=ap.parse_args();a.probe=a.probe.resolve();a.root=a.root.resolve();records=[];passed=False;binary_sha=sha(a.probe.read_bytes())
    def report(name,**extra):records.append(dict(name=name,**extra));print('CASE '+ascii(name),flush=True)
    def input(case,source='primary',decision=None,phase='create',fault=None):
        v=dict(phase=phase,image_hex=case['raw'].hex(),logical_block_bytes=case['capture']['block_bytes'],authoritative_copy=source,expected_capture_digest=case['definition']['capture_digest'],expected_plan_digest=case['plan_digest'])
        if decision:v['selection_decision_digest']=decision
        if fault:v['fault']=fault
        return v
    def inspected(case,prepared,review,grant,source,decision=None):
        call=input(case,source,decision,'inspect');call.update(manifest=prepared['manifest'],review=review,grant=grant);r=subprocess.run([str(a.probe)],input=canonical(call)+b'\n',capture_output=True,timeout=15);assert r.returncode==0 and not r.stderr,(r.returncode,r.stdout,r.stderr);v=json.loads(r.stdout);assert v['phase']=='inspected' and all('.write.' not in e['stage'] and '.flush.' not in e['stage'] for e in v['events']);return v['inspection']
    def run(parent,name,case,source='primary',decision=None,fault=None,cancel='none',mutate=None,inspect=True,live_inspect=False):
        folder=parent/name;folder.mkdir();process=subprocess.Popen([str(a.probe),'--fixture-parent',str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);lines=queue.Queue()
        def readlines():
            try:
                for line in process.stdout:lines.put(json.loads(line))
            finally:lines.put(None)
        reader=threading.Thread(target=readlines,daemon=True);reader.start();prepared=None;review=grant=None;finish=None
        try:
            process.stdin.write(canonical(input(case,source,decision,fault=fault))+b'\n');process.stdin.flush()
            try:first=lines.get(timeout=15)
            except queue.Empty:first=None
            if first and first['phase']=='prepared':
                prepared=first;assert prepared['definition']==case['definition'] and prepared['plan_digest']==case['plan_digest'] and prepared['backup_digest']==sha(case['backup']) and prepared['backup_bytes']==str(len(case['backup']));m=prepared['manifest'];assert m['image_before_sha256']==sha(case['raw']) and m['executor_digest']==binary_sha and m['storage_independent'] is False
                review,grant=receipts(prepared);instruction=dict(phase='execute',review=copy.deepcopy(review),grant=copy.deepcopy(grant),cancel_at=cancel)
                if live_inspect:
                    call=input(case,source,decision,'inspect');call.update(manifest=m,review=review,grant=grant);other=subprocess.run([str(a.probe)],input=canonical(call)+b'\n',capture_output=True,timeout=15);assert other.returncode==3 and not other.stderr and json.loads(other.stdout)['diagnostic']=='fixture_open','Live fixture was not exclusively held'
                if mutate:mutate(instruction)
                process.stdin.write(canonical(instruction)+b'\n');process.stdin.flush();process.stdin.close()
                try:finish=lines.get(timeout=15)
                except queue.Empty:finish=None
            else:
                if first:assert first['phase']=='refused';finish=first
                process.stdin.close()
            code=process.wait(timeout=15);assert not process.stderr.read();reader.join(timeout=1)
            while not lines.empty():assert lines.get_nowait() is None,'Unexpected extra response'
            artifacts=list(folder.iterdir());assert len(artifacts)==1 and artifacts[0].is_dir();directory=artifacts[0];assert {p.name for p in directory.iterdir()}=={'image.bin','backup.bin','journal.bin'}
            current=(directory/'image.bin').read_bytes();retained=(directory/'backup.bin').read_bytes();history=(directory/'journal.bin').read_bytes()
            if prepared:
                assert len(current)==len(case['raw']);touched=set()
                for patch in case['patches']:touched.update(range(patch['offset'],patch['offset']+len(patch['before'])))
                assert all(x==y or i in touched for i,(x,y) in enumerate(zip(current,case['raw']))),'Changed unrelated bytes'
                observed=inspected(case,prepared,review,grant,source,decision) if inspect else None
                if observed:
                    oracle=journal(history,case,prepared,review,grant);assert observed['journal']['disposition']==oracle['disposition'] and observed['journal']['records']==str(oracle['records']) and observed['journal']['verified_bytes']==str(oracle['verified_bytes']) and observed['journal']['confirmed_prefix']==str(oracle['completed']) and observed['journal']['pending_intention']==oracle['pending'] and observed['journal']['sealed']==oracle['sealed'];assert observed['backup_exact']==(retained==case['backup'])
                    assert observed['matching_prefixes']==[str(i) for i in range(len(case['patches'])+1) if current==overlay(case,i)]
                    assert not observed['authorizes_effects'] and not observed['qualifies_power_loss'] and not observed['qualifies_recovery']
                if code==0:
                    assert finish['phase']=='finished';status=finish['execution']['status'];count=int(finish['execution']['completed_patches']);assert current==overlay(case,count)
                    if status=='completed':assert count==len(case['patches']) and observed['current_matches_seal'] and not observed['recovery_required'] and retained==case['backup']
                    elif status=='unchanged':assert not case['patches'] and not history and not retained
                    elif status=='cancelled_before_effects':assert count==0 and not history and not retained
                    else:assert status in ('cancelled_partial','cancelled_after_complete') and observed['current_matches_seal'];assert observed['recovery_required']==(count!=len(case['patches']))
                elif code in (3,6):
                    assert finish['phase']=='finished' and finish['execution']['status'] in ('refused','unresolved');assert not observed['current_matches_seal'] or observed['journal']['sealed'];assert finish['fault_fired'] if fault else mutate
                    if mutate:assert current==case['raw'] and not retained and not history
                else:assert code==112 and finish is None and fault and fault['action'].startswith('crash_')
            else:
                assert code in (3,112) and fault and fault['stage'].startswith('image.seed.') and not retained and not history
            record=dict(exit_code=code,prepared=prepared is not None,image_sha256=sha(current),image_before_sha256=sha(case['raw']),backup_sha256=sha(retained),backup_bytes=len(retained),journal_sha256=sha(history),journal_hex=history.hex(),fault=fault,cancel=cancel,input_sha256=sha(canonical(input(case,source,decision,fault=fault))))
            if prepared:record.update(preparation=prepared,review=review,grant=grant)
            if len(retained)<=8192:record['backup_hex']=retained.hex()
            elif len(retained)>=12 and retained[:8]==b'DEGBK001':
                length=struct.unpack_from('<I',retained,8)[0];assert length<=4096;record['backup_header_hex']=retained[:min(len(retained),12+length)].hex()
            if finish:record['finish']=finish
            if prepared and inspect:record['inspection']=observed
            report(name,**record);return finish,prepared,review,grant,directory
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=5)
            reader.join(timeout=1);process.stdout.close();process.stderr.close()
    try:
        parent=managed_parent();parent.mkdir(exist_ok=True)
        with managed_directory(prefix='gpt-effects-') as directory:
            directory=Path(directory);assert directory.resolve().is_relative_to(parent.resolve());normal=None
            for unit in (512,4096):
                for source in ('primary','backup'):
                    target='backup' if source=='primary' else 'primary';f=fixture(unit=unit);change_array(f,lambda b:b.__setitem__(0,b[0]^1),target,False);h=bytearray.fromhex(f[target]);h[16]^=1;f[target]=h.hex();case=expected(f,source);result=run(directory,str(unit)+'-'+source,case,source)
                    if unit==512 and source=='primary':normal=(case,result)
            case,result=normal;successful=result[0];stages=[e['stage'] for e in successful['events'] if '.write.' in e['stage'] or '.flush.' in e['stage']];assert len(stages)==len(set(stages)) and all(int(e['bytes'])<=65536 for e in successful['events'] if '.write.' in e['stage'])
            # Every successful-run native write/flush call is interrupted on both
            # sides with real own-process exit, and with returned I/O errors.
            for index,stage in enumerate(stages):
                for action in ('crash_before','crash_after','before_error','after_error'):
                    run(directory,'fault-'+str(index)+'-'+action,case,fault=dict(stage=stage,action=action))
                if '.write.' in stage:run(directory,'fault-'+str(index)+'-partial',case,fault=dict(stage=stage,action='partial_error'))
            for stage in ['image.read.1','backup.read.1','journal.read.1']:
                for action in ('short_read','alter_read'):run(directory,stage+'-'+action,case,fault=dict(stage=stage,action=action))
            for key in ['plan_digest','review_digest','manifest_digest','executor_digest','image_identity','backup_identity','journal_identity']:
                run(directory,'bad-grant-'+key,case,mutate=lambda v,key=key:v['grant'].__setitem__(key,sha(b'wrong-'+key.encode())))
            for key in ['allow_fixture_writes','acknowledge_proposed_journal']:run(directory,'bad-grant-'+key,case,mutate=lambda v,key=key:v['grant'].__setitem__(key,False))
            run(directory,'bad-grant-scope',case,mutate=lambda v:v['grant'].__setitem__('patch_ids',[]))
            run(directory,'bad-review',case,mutate=lambda v:v['review'].__setitem__('reviewed',False))
            for cancel in ('before-effects','after-first-patch'):run(directory,'cancel-'+cancel,case,cancel=cancel)
            run(directory,'no-change',expected(fixture()))
            f=fixture();h=bytearray.fromhex(f['backup']);h[16]^=1;f['backup']=h.hex();run(directory,'header-only',expected(f))
            f=fixture(count=2);b=bytearray.fromhex(f['backup_array']);payload=bytearray(b[:256]);crc=zlib.crc32(payload);payload[56:64]='Move'.encode('utf-16-le');equal_crc_patch(payload,124,crc);b[:256]=payload;f['backup_array']=b.hex();decision=sha(b'explicit-crc-collision-selection');run(directory,'crc-collision',expected(f,decision=decision),decision=decision)
            f=fixture();change_array(f,lambda b:b.__setitem__(0,b[0]^1),'backup',False);change_header(f,72,'<Q',10,'primary');change_header(f,72,'<Q',79,'backup');run(directory,'noncanonical',expected(f))
            f=fixture(blocks=8192,count=1024,size=1024);change_array(f,lambda b:b.__setitem__(0,b[0]^1),'backup',False);run(directory,'max-array',expected(f))
            # Exercise actual mid-array and backup chunks with many changed bytes,
            # so an interrupted write cannot accidentally equal the full result.
            f['backup_array']=bytes(b^0x5a for b in bytes.fromhex(f['backup_array'])).hex();large=expected(f)
            for index,stage in enumerate(['image.write.8','image.write.16','image.flush.1','backup.write.17','backup.flush.1','journal.write.6','journal.flush.6']):
                for action in ('crash_before','crash_after'):run(directory,'multi-'+str(index)+'-'+action,large,fault=dict(stage=stage,action=action))
                if '.write.' in stage:run(directory,'multi-'+str(index)+'-partial',large,fault=dict(stage=stage,action='partial_error'))
            for key in ['plan_digest','capture_digest','manifest_digest','evidence_digest']:
                run(directory,'bad-review-'+key,case,mutate=lambda v,key=key:v['review'].__setitem__(key,sha(b'wrong-'+key.encode())))
            repeated=run(directory,'repeat-old-admission',case,mutate=lambda v:v.__setitem__('repeat',True),live_inspect=True)[0]
            assert repeated['repeat_execution']['status']=='refused' and repeated['repeat_execution']['diagnostic']=='fixture_basis_changed' and not repeated['repeat_execution']['possible_image_effects']
            # Read-only inspection preserves corrupt/torn files and requires the
            # original resource identity; history cannot manufacture authority.
            result=run(directory,'inspect-tamper',case);_,prepared,review,grant,owned=result
            original=(owned/'journal.bin').read_bytes()
            def forge_record(raw,number,mutate):
                at=192
                for _ in range(number-1):at+=144+struct.unpack_from('<I',raw,at+12)[0]
                length=struct.unpack_from('<I',raw,at+12)[0];prefix=bytearray(raw[at:at+112]);v=json.loads(raw[at+112:at+112+length]);mutate(v);payload=canonical(v);struct.pack_into('<I',prefix,12,len(payload));prefix[80:112]=hashlib.sha256(payload).digest();trailer=hashlib.sha256(raw[160:192]+prefix+payload).digest();return raw[:at]+prefix+payload+trailer+raw[at+144+length:]
            for label,data,records_before in [('critical-review',forge_record(original,2,lambda v:v.__setitem__('issuer','other-controller')),1),('critical-completion',forge_record(original,6,lambda v:v.__setitem__('capture_digest',sha(b'wrong-completion'))),5)]:
                (owned/'journal.bin').write_bytes(data);before={p.name:p.read_bytes() for p in owned.iterdir()};observed=inspected(case,prepared,review,grant,'primary');assert observed['journal']['diagnostic']=='journal_semantic_rejected' and observed['journal']['records']==str(records_before) and observed['recovery_required'];assert before=={p.name:p.read_bytes() for p in owned.iterdir()};report('readonly-'+label,inspection=observed,journal_hex=data.hex(),preparation=prepared,review=review,grant=grant)
            for label,data,diagnostic in [('torn-header',original[:191],'journal_header_incomplete'),('torn-tail',original[:-1],'journal_final_record_incomplete'),('header-checksum',original[:160]+bytes([original[160]^1])+original[161:],'journal_header_checksum')]:
                (owned/'journal.bin').write_bytes(data);before={p.name:p.read_bytes() for p in owned.iterdir()};observed=inspected(case,prepared,review,grant,'primary');assert observed['journal']['diagnostic']==diagnostic and observed['recovery_required'];assert before=={p.name:p.read_bytes() for p in owned.iterdir()};report('readonly-'+label,inspection=observed)
            (owned/'journal.bin').write_bytes(original)
            b=(owned/'backup.bin').read_bytes();(owned/'backup.bin').write_bytes(b[:-1]);observed=inspected(case,prepared,review,grant,'primary');assert not observed['backup_exact'] and observed['recovery_required'];report('readonly-corrupt-backup',inspection=observed)
            (owned/'backup.bin').write_bytes(b)
            p=owned/'image.bin';saved=p.read_bytes();changed=bytearray(saved);changed[case['patches'][0]['offset']]^=0x80;p.write_bytes(changed);observed=inspected(case,prepared,review,grant,'primary');assert not observed['matching_prefixes'] and observed['recovery_required'];report('readonly-foreign-effect',inspection=observed);p.write_bytes(saved)
            alias=owned/'image-alias.bin';os.link(p,alias)
            call=input(case,phase='inspect');call.update(manifest=prepared['manifest'],review=review,grant=grant);r=subprocess.run([str(a.probe)],input=canonical(call)+b'\n',capture_output=True,timeout=15);assert r.returncode==3 and not r.stderr and json.loads(r.stdout)['diagnostic']=='image_file_aliases';report('readonly-hardlink-refused',exit_code=r.returncode);alias.unlink()
            retired=owned/'retired-image.bin';p.rename(retired);p.write_bytes(saved);r=subprocess.run([str(a.probe)],input=canonical(call)+b'\n',capture_output=True,timeout=15);assert r.returncode==3 and not r.stderr and json.loads(r.stdout)['diagnostic']=='fixture_file_changed';report('readonly-swapped-object-refused',exit_code=r.returncode)
            for name,path in [('device-path',r'\\.\PhysicalDrive0'),('unc-path',r'\\localhost\share')]:
                r=subprocess.run([str(a.probe),'--fixture-parent',path],input=canonical(input(case))+b'\n',capture_output=True,timeout=15);assert r.returncode==3 and not r.stderr;v=json.loads(r.stdout);assert v['phase']=='refused' and v['diagnostic']=='image_path_profile';report(name,exit_code=r.returncode)
            request=input(case);request['expected_capture_digest']=sha(b'wrong-capture');before=set(directory.iterdir());r=subprocess.run([str(a.probe),'--fixture-parent',str(directory)],input=canonical(request)+b'\n',capture_output=True,timeout=15);assert r.returncode==3 and json.loads(r.stdout)['diagnostic']=='repair_capture_mismatch' and set(directory.iterdir())==before;report('basis-binding-before-create',exit_code=r.returncode)
        passed=True
    finally:
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),probe_sha256=binary_sha,records=records),indent=2)+'\n',encoding='utf8',newline='\n')
    print('Owned GPT execution PASS '+str(len(records)),flush=True)
if __name__=='__main__':main()
