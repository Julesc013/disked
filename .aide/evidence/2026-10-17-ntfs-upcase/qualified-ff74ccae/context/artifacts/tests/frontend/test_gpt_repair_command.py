"""Independent ordinary-file GPT preview oracle and actual frontend journeys."""
import argparse,hashlib,json,os,queue,struct,subprocess,sys,tempfile,threading,time,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'property'))
from test_gpt import fixture,change_header,change_array,fix_header,equal_crc_patch
from gui_fixture import Gui,U,wait
from test_image_commands import Gate

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def image(f):
    unit=int(f['unit']);blocks=int(f['blocks']);raw=bytearray(blocks*unit);raw[510:512]=b'\x55\xaa'
    struct.pack_into('<B3sB3sII',raw,446,0,b'\x00\x02\x00',0xee,b'\xff'*3,1,min(blocks-1,2**32-1))
    for side in ['primary','backup']:
        h=bytes.fromhex(f[side]);a=bytes.fromhex(f[side+'_array']);where=struct.unpack_from('<Q',h,72)[0]*unit
        raw[(1 if side=='primary' else blocks-1)*unit:(2 if side=='primary' else blocks)*unit]=h
        assert where+len(a)<=len(raw);raw[where:where+len(a)]=a
    return bytes(raw)
def damaged(unit=512,side='backup'):
    f=fixture(unit=unit);change_array(f,lambda b:b.__setitem__(0,b[0]^1),side,False);return f
def audit(value,raw,source):
    result=value['result'];d=result['definition'];receipt=result['capture'];unit=int(d['capture']['block_bytes']);blocks=len(raw)//unit
    assert value['status']=='completed' and value['operation_id'] is None
    assert result['plan_digest']==digest(canonical(d)) and result['scope']=='ordinary-local-raw-file'
    assert d['authoritative_copy']==source and d['target_copy']==('backup' if source=='primary' else 'primary')
    assert d['capture']['image_id']==digest(canonical(receipt['source_before'])) and d['capture']['epoch']==receipt['started_filetime']
    assert receipt['observed_stable'] and receipt['regions_complete'] and receipt['reread_regions_complete']
    assert not receipt['whole_file_hashed'] and not receipt['atomic_snapshot'] and receipt['source_consistency']=='live-uncoordinated'
    assert int(receipt['requests'])==5 and int(receipt['unique_regions'])==5 and int(receipt['requested_bytes'])<=2109440
    assert receipt['region_manifest_sha256']==digest(canonical(receipt['regions'])) and receipt['omitted_regions']=='0'
    expected_regions=[(0,unit),(unit,2*unit),((blocks-1)*unit,blocks*unit)]
    parts={'protective_mbr':raw[:unit]}
    for side in ['primary','backup']:
        lba=1 if side=='primary' else blocks-1;h=raw[lba*unit:(lba+1)*unit];count,size=struct.unpack_from('<II',h,80);start=struct.unpack_from('<Q',h,72)[0]*unit;span=((count*size+unit-1)//unit)*unit
        parts[side+'_header']=h;parts[side+'_array']=raw[start:start+span]
        expected_regions.append((start,start+span))
    for region,(start,end) in zip(receipt['regions'],expected_regions):
        assert region==dict(start=str(start),end=str(end),bytes=str(end-start),sha256=digest(raw[start:end]),read_error=None,reread_bytes=str(end-start),reread_sha256=digest(raw[start:end]),reread_error=None,equal=True)
    c=d['capture'];assert c['blocks']==str(blocks)
    for k,b in parts.items():assert c[k]==dict(bytes=str(len(b)),sha256=digest(b))
    assert d['capture_digest']==digest(b'DiskEd.gpt-repair.capture/1\n'+canonical(c))
    target=d['target_copy'];th=bytearray(parts[target+'_header']);sh=parts[source+'_header'];count,size=struct.unpack_from('<II',sh,80);used=count*size;hs=struct.unpack_from('<I',th,12)[0];expected_array=parts[source+'_array'][:used]
    struct.pack_into('<I',th,88,zlib.crc32(expected_array));fix_header(th);expected=[]
    if expected_array!=parts[target+'_array'][:used]:expected.append(('target-array',struct.unpack_from('<Q',th,72)[0]*unit,parts[target+'_array'][:used],expected_array))
    if bytes(th[:hs])!=parts[target+'_header'][:hs]:expected.append(('target-header',struct.unpack_from('<Q',th,24)[0]*unit,parts[target+'_header'][:hs],bytes(th[:hs])))
    assert len(expected)==len(d['patches'])
    for i,(patch,(name,offset,before,after)) in enumerate(zip(d['patches'],expected)):
        assert patch==dict(id=name,offset=str(offset),bytes=str(len(before)),before_sha256=digest(before),after_sha256=digest(after),depends_on=[] if i==0 else [expected[i-1][0]])
    assert d['status']==('repair_preview' if expected else 'no_change')
    for k in ['authorizes_effects','writer_admitted','qualifies_durability','qualifies_recovery']:assert d[k] is False
    assert d['simulation']['both_copies_agree'] and not d['simulation']['independent_verification'] and not d['simulation']['whole_device_valid']
    assert not any('hex' in key for key in d) and len(canonical(value))<65536

def main():
    p=argparse.ArgumentParser()
    for n in ['exe','fault','root']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--evidence',type=Path);a=p.parse_args()
    for n in ['exe','fault','root']:setattr(a,n,getattr(a,n).resolve())
    sys.path.insert(0,str(a.root/'spec/tools'));import specctl;bundle=specctl.Bundle(a.root/'spec')
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_IMAGE_TEST_')};records=[];passed=False
    def record(name,**extra):print('CASE '+ascii(name),flush=True);records.append(dict(name=name,**extra))
    def launch(name,args,code=0,diagnostic=None,exe=None,data=b'',fault=None,cwd=None):
        e=env.copy()
        if fault:e['DISKED_IMAGE_TEST_'+fault]='1'
        call=[str(exe or a.exe),*args];r=subprocess.run(call,input=data,capture_output=True,cwd=cwd,env=e,timeout=15)
        assert r.returncode==code,(name,r.returncode,r.stdout,r.stderr);assert not r.stderr
        values=[json.loads(line) for line in r.stdout.splitlines()];assert values
        for v in values:
            bundle.validate('urn:disked:schema:response:1',v)
            if v['result'] is not None and v['result'].get('schema')=='org.disked.gpt-repair-command-result/1':bundle.validate('urn:disked:schema:gpt-repair-command-result:1',v['result'])
        if diagnostic:assert diagnostic in [d['code'] for d in values[0]['diagnostics']],(name,values)
        record(name,command=call,exit_code=r.returncode,stdout_sha256=digest(r.stdout),stdout_bytes=len(r.stdout));return values
    def request(path,source='primary',**extra):
        v=dict(schema='org.disked.request/1',request_id='gpt:preview',command='table.gpt.repair.plan',parameters=dict(path=str(path),authoritative_copy=source),required_features=[]);v.update(extra);return v
    def preview(path,source='primary',unit=512,decision=None,**kw):
        args=['--json','table','repair',str(path),'--authoritative-copy',source,'--logical-block-bytes',str(unit)]
        if decision:args+=['--selection-decision-digest',decision]
        return launch(path.name+'-'+source,args,**kw)[0]
    try:
        with tempfile.TemporaryDirectory(prefix='gpt-command-',dir=a.root/'.aide-local') as directory:
            directory=Path(directory);files=[];raws={}
            def put(name,f):
                path=directory/(name+'.img');raw=image(f);path.write_bytes(raw);files.append(path);raws[path]=raw;return path
            for unit in [512,4096]:
                for source in ['primary','backup']:
                    target='backup' if source=='primary' else 'primary';path=put(str(unit)+'-'+target,damaged(unit,target));audit(preview(path,source,unit),raws[path],source)
                    f=damaged(unit,target);h=bytearray.fromhex(f[target]);h[16]^=1;f[target]=h.hex();path=put(str(unit)+'-both-'+target,f);audit(preview(path,source,unit),raws[path],source)
                    f=fixture(unit=unit);h=bytearray.fromhex(f[target]);h[16]^=1;f[target]=h.hex();path=put(str(unit)+'-header-'+target,f);v=preview(path,source,unit);audit(v,raws[path],source);assert len(v['result']['definition']['patches'])==1
            valid=put('agree',fixture());first=preview(valid);audit(first,raws[valid],'primary');assert first['result']['definition']['patches']==[]
            f=fixture();change_array(f,lambda b:b.__setitem__(slice(56,64),'Swap'.encode('utf-16-le')),'backup');disagree=put('disagree',f)
            decision=digest(b'explicit-fixture-selection')
            for source in ['primary','backup']:
                preview(disagree,source,code=3,diagnostic='repair_selection_required');v=preview(disagree,source,decision=decision);audit(v,raws[disagree],source);assert v['result']['definition']['selection_decision_digest']==decision
            f=fixture(count=2);b=bytearray.fromhex(f['backup_array']);old=zlib.crc32(b[:256]);changed=bytearray(b[:256]);changed[56:64]='Move'.encode('utf-16-le');equal_crc_patch(changed,124,old);b[:256]=changed;f['backup_array']=b.hex();collision=put('crc-collision',f)
            preview(collision,code=3,diagnostic='repair_selection_required');audit(preview(collision,decision=decision),raws[collision],'primary')
            f=damaged();change_header(f,72,'<Q',10,'primary');change_header(f,72,'<Q',79,'backup');noncanonical=put('noncanonical',f);audit(preview(noncanonical),raws[noncanonical],'primary')
            maximal=put('max-array',damaged());f=fixture(blocks=8192,count=1024,size=1024);change_array(f,lambda b:b.__setitem__(0,b[0]^1),'backup',False);raws[maximal]=image(f);maximal.write_bytes(raws[maximal]);audit(preview(maximal),raws[maximal],'primary')
            for name,offset,fmt,value,code in [('unknown-header',0,'<8s',b'NO TABLE','repair_target_structure'),('mismatched-guid',56,'<16s',b'\xff'*16,'repair_layout_conflict')]:
                f=fixture();change_header(f,offset,fmt,value,'backup');path=put(name,f);preview(path,code=3,diagnostic=code)
            unusable=put('unusable-source',damaged(side='primary'));preview(unusable,code=3,diagnostic='repair_source_unusable')
            budget=put('over-budget',fixture(blocks=1024,count=1025));preview(budget,code=3,diagnostic='repair_budget')
            partial=directory/'partial.img';raws[partial]=raws[valid][:-1];partial.write_bytes(raws[partial]);files.append(partial);preview(partial,code=3,diagnostic='image_geometry')
            for name,raw in [('empty',b''),('short',b'X'),('two-blocks',b'\0'*1024)]:
                path=directory/(name+'.img');path.write_bytes(raw);raws[path]=raw;files.append(path);preview(path,code=3,diagnostic='image_geometry')
            missing=directory/'missing.img';preview(missing,code=3,diagnostic='image_source_open')
            unicode=put('磁盘-🙂',damaged());audit(preview(unicode),raws[unicode],'primary')
            delayed=put('test-wait-preview',damaged())
            raw_before={p.name:digest(p.read_bytes()) for p in files};directory_before={p.name for p in directory.iterdir()}
            for fault,diagnostic in [('READ_ERROR','image_capture_incomplete'),('SHORT_READ','image_capture_incomplete'),('GPT_HEADER_SHORT','image_capture_incomplete'),('GPT_ARRAY_SHORT','image_capture_incomplete'),('GPT_ARRAY_ERROR','image_capture_incomplete'),('VERIFY_ERROR','image_capture_incomplete'),('CHANGED','image_source_changed'),('METADATA_CHANGED','image_source_changed')]:
                v=preview(valid,exe=a.fault,fault=fault,code=4,diagnostic=diagnostic);assert v['result']['plan_digest'] is None and v['result']['definition'] is None
            audit(preview(valid,fault='GPT_ARRAY_ERROR'),raws[valid],'primary')
            # The existing parser reports schema-rejected option values with
            # invalid_option_value; stdio typed parameters use invalid_parameter.
            for tail,diagnostic in [([], 'missing_parameter'),(['--authoritative-copy','auto'],'invalid_option_value'),(['--authoritative-copy','primary','--authoritative-copy','backup'],'duplicate_option'),(['--authoritative-copy','primary','--selection-decision-digest','sha256:'+'0'*64],'invalid_option_value'),(['--authoritative-copy','primary','--selection-decision-digest','broken'],'invalid_option_value'),(['--authoritative-copy','primary','--unknown'],'unknown_option')]:
                launch('parse-before-open-'+diagnostic,['--json','table','repair',str(missing),*tail],2,diagnostic,exe=a.fault,fault='OPEN_GUARD')
            for argv in [['--json','table','repair','--help'],['--json','commands'],['--json','build','inspect']]:launch('essential-no-open',argv,exe=a.fault,fault='OPEN_GUARD')
            for params,extra,diagnostic in [(dict(path=str(missing)),{},'missing_parameter'),(dict(path=str(missing),authoritative_copy='primary',extra=True),{},'unexpected_parameter'),(dict(path=str(missing),authoritative_copy='primary',selection_decision_digest='broken'),{},'invalid_parameter'),(dict(path=str(missing),authoritative_copy='primary'),{'expected_revision':'sha256:'+'0'*64},'unexpected_revision')]:
                wire=request(missing);wire['parameters']=params;wire.update(extra);launch('stdio-before-open-'+diagnostic,['protocol','serve','--json'],2,diagnostic,exe=a.fault,fault='OPEN_GUARD',data=canonical(wire))
            wire=launch('stdio-preview',['protocol','serve','--json'],data=canonical(request(noncanonical)))[0];audit(wire,raws[noncanonical],'primary')
            later=preview(noncanonical);audit(later,raws[noncanonical],'primary');assert wire['result']['definition']['patches']==later['result']['definition']['patches']
            # Wall-clock planning timestamps can repeat. The transport epoch
            # includes process creation and sequence; equal definitions may hash
            # equally, and neither digest proves independently approved freshness.
            assert wire['result']['capture']['capture_epoch']!=later['result']['capture']['capture_epoch']
            g=Gui(a.exe,['--gui','table','repair',str(noncanonical),'--authoritative-copy','primary'],render=True)
            try:
                assert not U.IsWindowEnabled(g.child(110));g.click(109);assert g.details()['reviewed'] and 'status' not in g.details();g.click(110)
                value=wait(lambda:g.details() if 'status' in g.details() else None);bundle.validate('urn:disked:schema:gpt-repair-command-result:1',value['result']);audit(value,raws[noncanonical],'primary');record('gui-preview',response=value,native=g.observation())
                if a.evidence:g.screenshot(a.evidence.parent/'gpt-repair-preview.png')
            finally:g.close()
            assert g.code==0 and not g.output and not g.error and not g.created_files
            for frontend in ['tui','shell']:
                report=directory/'console-result.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                r=subprocess.run([sys.executable,str(a.root/'tests/frontend/image_console_fixture.py'),str(a.exe),frontend,'table.repair',str(noncanonical),'512',str(report),json.dumps(['--authoritative-copy','primary'])],cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=30)
                value=json.loads(report.read_bytes());assert r.returncode==0,value;audit(value['response'],raws[noncanonical],'primary');bundle.validate('urn:disked:schema:gpt-repair-command-result:1',value['response']['result']);record(frontend+'-preview',observation=value);report.unlink()
            gate=Gate();e=env.copy();e['DISKED_IMAGE_TEST_GATE']=gate.name;process=None;reader=None
            try:
                # Hold a real in-flight preview across the existing wait boundary.
                process=subprocess.Popen([str(a.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=e)
                lines=queue.Queue()
                def readlines():
                    for line in process.stdout:lines.put(json.loads(line))
                reader=threading.Thread(target=readlines,daemon=True);reader.start()
                def send(v):process.stdin.write(canonical(v)+b'\n');process.stdin.flush()
                started=time.monotonic();send(request(delayed));gate.entered();expired=lines.get(timeout=5);elapsed=time.monotonic()-started
                assert expired['status']=='unknown' and expired['operation_id'] is None and expired['diagnostics'][0]['code']=='request_wait_expired' and 3.8<=elapsed<5
                send(request(valid,request_id='busy'));busy=lines.get(timeout=1);assert busy['diagnostics'][0]['code']=='request_resource_limit'
                send(dict(schema='org.disked.request/1',request_id='essential',command='build.inspect',parameters={},required_features=[]));assert lines.get(timeout=1)['status']=='completed'
                gate.release();retries=[];end=time.monotonic()+8
                for i in range(40):
                    wire=request(noncanonical,request_id='after:'+str(i));send(wire);after=lines.get(timeout=2);assert after['request_id']==wire['request_id'];retries.append(after)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit' and time.monotonic()<end;time.sleep(.2)
                audit(after,raws[noncanonical],'primary');assert lines.empty(),'Unsolicited late wire response';process.stdin.close();assert process.wait(timeout=5)==6 and not process.stderr.read()
                record('stdio-expired-preview-slot',expired=expired,busy=busy,release_observations=retries,elapsed_seconds=elapsed)
            finally:
                if process is not None:
                    if process.poll() is None:process.kill();process.wait(timeout=5)
                    if reader is not None:reader.join(timeout=1)
                    process.stdout.close();process.stderr.close()
                gate.close()
            assert raw_before=={p.name:digest(p.read_bytes()) for p in files},'Source changed'
            assert directory_before=={p.name for p in directory.iterdir()},'Created an unrequested file'
        passed=True
    finally:
        if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf8',newline='\n')
    print('GPT repair command PASS '+str(len(records)),flush=True)
if __name__=='__main__':main()
