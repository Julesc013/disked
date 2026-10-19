"""Independent readonly restoration-history framing/semantic/current-state fixtures."""
import argparse,copy,json,os,struct,subprocess,tempfile
from pathlib import Path
from test_gpt_restoration import canonical,sha,expected,receipts,fixture,change_array,request,Replies,send,close,fixture_parent,recovery_receipts,inspect_fixture

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent as managed_parent, managed_directory

def make_fixture(probe,parent,name,case,observations,source='primary'):
    folder=parent/name;folder.mkdir();process=subprocess.Popen([str(probe),'--fixture-parent',str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);rows=Replies(process)
    try:
        send(process,request(case,source,fault=dict(stage='image.write.2',action='crash_after')));prepared=rows.get(timeout=15,phase=name+':preparation');review,grant=receipts(prepared);send(process,dict(phase='execute',review=review,grant=grant));process.stdin.close();assert rows.get(timeout=15,phase=name+':execution') is None and rows.wait(timeout=15)==112;rows.assert_drained()
        data=dict(preparation=prepared,review=review,grant=grant,owned=Path(prepared['manifest']['directory']),case=case,source=source)
    finally:close(process,rows,observations)
    before=(data['owned']/'image.bin').read_bytes();old_journal=(data['owned']/'journal.bin').read_bytes();process=subprocess.Popen([str(probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);rows=Replies(process)
    try:
        send(process,request(case,source,'restore',manifest=prepared['manifest'],review=review,grant=grant,attempt_id=sha(name.encode())[7:39]));proposal=rows.get(timeout=15,phase=name+':restoration-preparation');assert proposal['phase']=='restoration_prepared';review,grant=recovery_receipts(proposal);send(process,dict(phase='restore-execute',review=review,grant=grant));process.stdin.close();store=rows.get(timeout=15,phase=name+':restoration-store')['store'];finish=rows.get(timeout=15,phase=name+':restoration-execution');assert finish['restoration']['status']=='restored_original_basis' and rows.wait(timeout=15)==0;rows.assert_drained()
    finally:close(process,rows,observations)
    return data,proposal,review,grant,store,before,old_journal

def decode_records(raw):
    rows=[];at=192
    while at<len(raw):
        length=struct.unpack_from('<I',raw,at+12)[0];rows.append([bytearray(raw[at:at+112]),raw[at+112:at+112+length]]);at+=144+length
    assert at==len(raw);return rows

def rebuild(raw,mutate=None,header_mutate=None):
    header=bytearray(raw[:192]);rows=decode_records(raw)
    if header_mutate:header_mutate(header)
    header[160:192]=bytes.fromhex(sha(header[:160])[7:]);out=bytes(header);previous=out[160:192]
    if mutate:mutate(rows)
    for i,(prefix,payload) in enumerate(rows):
        struct.pack_into('<I',prefix,12,len(payload));prefix[48:80]=previous;prefix[80:112]=bytes.fromhex(sha(payload)[7:]);trailer=bytes.fromhex(sha(out[160:192]+prefix+payload)[7:]);out+=bytes(prefix)+payload+trailer;previous=trailer
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--evidence',type=Path);a=ap.parse_args();a.probe=a.probe.resolve();a.root=a.root.resolve();records=[];passed=False;observations=[];fixture_state={}
    def record(name,code,output,raw,prepared,store):records.append(dict(name=name,exit_code=code,inspection=output,journal_hex=raw.hex(),definition=prepared['definition'],restoration_digest=prepared['restoration_digest'],store=store));print('CASE '+ascii(name),flush=True)
    try:
        with fixture_parent(a.root,fixture_state,observations) as directory:
            parent=Path(directory);assert parent.resolve().is_relative_to((managed_parent()).resolve())
            def case_for(unit,source):
                target='backup' if source=='primary' else 'primary';f=fixture(unit=unit);change_array(f,lambda b:b.__setitem__(0,b[0]^1),target,False);header=bytearray.fromhex(f[target]);header[16]^=1;f[target]=header.hex();return expected(f,source)
            context=None
            for unit in (512,4096):
                for source in ('primary','backup'):
                    values=make_fixture(a.probe,parent,str(unit)+'-'+source,case_for(unit,source),observations,source);code,output=inspect_fixture(a.probe,*values);assert code==0 and output['inspection']['current_matches_seal'];data,prepared,review,grant,store,before,old_journal=values;record(str(unit)+'-'+source,code,output,(data['owned']/store['name']).read_bytes(),prepared,store)
                    if unit==512 and source=='primary':context=values
            data,prepared,review,grant,store,before,old_journal=context;path=data['owned']/store['name'];original=path.read_bytes();rows=decode_records(original)
            def inspect(name,raw=None,mutate=None,diagnostic=None,refusal=None,fault=None):
                if raw is not None:path.write_bytes(raw)
                code,output=inspect_fixture(a.probe,*context,mutate=mutate,fault=fault)
                if refusal:assert code==3 and output['diagnostic']==refusal,(name,code,output)
                else:
                    assert code==0
                    if diagnostic:assert output['inspection']['journal']['diagnostic']==diagnostic,(name,output)
                record(name,code,output,path.read_bytes(),prepared,store);return output
            # Mutate each critical record and rebuild all checksums/hash links.
            for i in range(len(rows)):
                def payload_change(values,i=i):
                    v=json.loads(values[i][1]);v['unrecognised_critical_field']=True;values[i][1]=canonical(v)
                output=inspect('critical-'+str(i+1),rebuild(original,payload_change),diagnostic='journal_semantic_rejected');assert output['inspection']['journal']['records']==str(i)
            # Concrete relationship changes, beyond rejecting an extra property.
            fields=[(1,'issuer','other-controller'),(2,'allow_fixture_restoration',False),(3,'grant_digest',sha(b'changed-grant')),(4,'prefix','1'),(5,'image_digest',sha(b'wrong-completion')),(6,'patch',{}),(7,'prefix','1'),(8,'image_digest',sha(b'false-original-seal'))]
            for i,key,value in fields:
                def payload_change(values,i=i,key=key,value=value):
                    v=json.loads(values[i][1]);v[key]=value;values[i][1]=canonical(v)
                inspect('relationship-'+str(i)+'-'+key,rebuild(original,payload_change),diagnostic='journal_semantic_rejected')
            for label,offset,fmt,value,diagnostic in [('publisher',24,None,b'\x42'*16,'journal_semantic_rejected'),('epoch',40,'<Q',int(store['publisher_epoch'])+1,'journal_semantic_rejected'),('zero-epoch',40,'<Q',0,'journal_record_identity'),('sequence',16,'<Q',17,'journal_sequence'),('critical-kind',4,'<H',123,'journal_unknown_kind'),('flags',6,'<H',2,'journal_record_flags'),('critical-bit',6,'<H',0,'journal_critical_bit')]:
                def prefix_change(values,offset=offset,fmt=fmt,value=value):
                    if fmt:struct.pack_into(fmt,values[4][0],offset,value)
                    else:values[4][0][offset:offset+len(value)]=value
                inspect(label,rebuild(original,prefix_change),diagnostic=diagnostic)
            def observational(values):struct.pack_into('<HH',values[4][0],4,32769,0)
            inspect('unregistered-observation',rebuild(original,observational),diagnostic='journal_semantic_rejected')
            def noncanonical(values):values[4][1]=json.dumps(json.loads(values[4][1]),indent=2).encode()
            inspect('noncanonical-critical-json',rebuild(original,noncanonical),diagnostic='journal_semantic_rejected')
            def out_of_order(values):values[4][1],values[5][1]=values[5][1],values[4][1]
            inspect('out-of-order-completion',rebuild(original,out_of_order),diagnostic='journal_semantic_rejected')
            def append_after_seal(values):
                p=copy.deepcopy(values[4]);struct.pack_into('<Q',p[0],16,len(values)+1);values.append(p)
            inspect('post-seal-record',rebuild(original,append_after_seal),diagnostic='journal_after_terminal')
            for label,offset,diagnostic in [('journal-id',24,'journal_binding_mismatch'),('plan-binding',40,'journal_binding_mismatch'),('resources',72,'journal_binding_mismatch'),('code',104,'journal_binding_mismatch'),('reserved',136,'journal_header_flags')]:
                def header_change(h,offset=offset):h[offset]^=1
                inspect('header-'+label,rebuild(original,header_mutate=header_change),diagnostic=diagnostic)
            # Independent byte cut locations across every prefix/payload/trailer.
            cuts={0,1,191,192};at=192
            for prefix,payload in rows:
                cuts.update([at+1,at+111,at+112,at+112+len(payload)//2,at+143+len(payload),at+144+len(payload)]);at+=144+len(payload)
            for cut in sorted(cuts):inspect('cut-'+str(cut),original[:cut])
            inspect('restored-valid',original)
            image=data['owned']/'image.bin';image.write_bytes(before);output=inspect('historical-seal-current-prefix');assert output['inspection']['journal']['sealed'] and not output['inspection']['current_matches_seal'] and output['inspection']['matching_prefixes']==['0'];image.write_bytes(data['case']['raw'])
            raw=bytearray(image.read_bytes());raw[20*512]^=0x80;image.write_bytes(raw);output=inspect('foreign-current-byte');assert output['inspection']['journal']['sealed'] and not output['inspection']['current_known_bytes'];image.write_bytes(data['case']['raw'])
            backup=data['owned']/'backup.bin';saved=backup.read_bytes();backup.write_bytes(saved[:-1]);output=inspect('old-backup-inapplicable');assert output['inspection']['journal']['sealed'] and not output['inspection']['backup_exact'] and not output['inspection']['current_matches_seal'];backup.write_bytes(saved)
            old=data['owned']/'journal.bin';saved=old.read_bytes();old.write_bytes(saved[:-1]);output=inspect('old-journal-inapplicable');assert output['inspection']['journal']['sealed'] and not output['inspection']['original_journal_unchanged'] and not output['inspection']['current_matches_seal'];old.write_bytes(saved)
            inspect('retained-observation-mismatch',mutate=lambda v:v[1].__setitem__('image_hex',data['case']['raw'].hex()),refusal='restoration_retained_binding')
            inspect('retained-journal-mismatch',mutate=lambda v:v[2].__setitem__('journal_hex',old_journal[:-1].hex()),refusal='restoration_retained_binding')
            inspect('reference-digest-mismatch',mutate=lambda v:v[0].__setitem__('restoration_digest',sha(b'wrong-reference')),refusal='restoration_retained_binding')
            inspect('historical-grant-mismatch',mutate=lambda v:v[0]['restoration_grant'].__setitem__('review_digest',sha(b'wrong-review')),refusal='restoration_grant_binding')
            # Restore expected controller object after mutation to a deep copy.
            context=(data,prepared,review,recovery_receipts(prepared)[1],store,before,old_journal)
            inspect('retained-size-mismatch',mutate=lambda v:v[1].__setitem__('image_hex',(before+b'\x00').hex()),refusal='restoration_retained_budget')
            inspect('new-journal-budget',raw=b'x'*1048577,refusal='fixture_journal_budget');path.write_bytes(original)
            for stage in ('image.read.1','backup.read.1','journal.read.1','recovery.read.1'):
                for action,diagnostic in [('before_error','fixture_injected_before'),('after_error','fixture_injected_after'),('short_read','fixture_injected_short_read')]:
                    inspect('read-fault-'+stage+'-'+action,refusal=diagnostic,fault=dict(stage=stage,action=action))
            inspect('unstable-image-observation',refusal='restoration_inspection_snapshot_changed',fault=dict(stage='image.read.1',action='alter_read'))
            alias=data['owned']/'same-journal-link.bin';os.link(path,alias);inspect('aliased-store',refusal='image_file_aliases');alias.unlink()
            raw=path.read_bytes();path.rename(data['owned']/'retired-recovery.bin');path.write_bytes(raw);inspect('replaced-store',refusal='fixture_restoration_store_changed')
        passed=True
    finally:
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),probe_sha256=sha(a.probe.read_bytes()),records=records,fixture=fixture_state,process_observations=observations),indent=2)+'\n',encoding='utf8',newline='\n')
    print('Read-only GPT restoration inspection PASS '+str(len(records)),flush=True)
if __name__=='__main__':main()
