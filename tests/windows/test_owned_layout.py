"""Owned ordinary-image capture versus separately owned injected /2 layout; no devices."""
import argparse,copy,ctypes,hashlib,json,struct,subprocess,time
from ctypes import wintypes
from pathlib import Path
from test_raw_layout import gpt_image,fixture,recipes,table,mbr_entry
from test_storage_queries import digest,packet

def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()

def metadata(path):
    """Independent native metadata query, closed before a child can open the file."""
    class Basic(ctypes.Structure):
        _fields_=[(k,ctypes.c_longlong) for k in ('created','accessed','written','changed')]+[('attributes',wintypes.DWORD)]
    class Identity(ctypes.Structure):
        _fields_=[('volume',ctypes.c_ulonglong),('identity',ctypes.c_ubyte*16)]
    class Standard(ctypes.Structure):
        _fields_=[('allocated',ctypes.c_longlong),('size',ctypes.c_longlong),('links',wintypes.DWORD),('deleted',ctypes.c_ubyte),('directory',ctypes.c_ubyte)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE);k.CreateFileW.restype=wintypes.HANDLE
    k.GetFileInformationByHandleEx.argtypes=(wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD);k.GetFileInformationByHandleEx.restype=wintypes.BOOL
    k.CloseHandle.argtypes=(wintypes.HANDLE,)
    h=k.CreateFileW(str(path),0x80000000,1,None,3,0x00200000,None)
    if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        basic=Basic();identity=Identity();standard=Standard()
        for code,value in [(0,basic),(1,standard),(18,identity)]:
            if not k.GetFileInformationByHandleEx(h,code,ctypes.byref(value),ctypes.sizeof(value)):raise ctypes.WinError(ctypes.get_last_error())
        return dict(volume_id=str(identity.volume),file_id=bytes(identity.identity).hex(),bytes=str(standard.size),created=str(basic.created),written=str(basic.written),changed=str(basic.changed),attributes=str(basic.attributes),hardlinks=str(standard.links))
    finally:k.CloseHandle(h)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();images=out/'images';images.mkdir();checks=[];runs=[];children=set();manifest=[];probe=a.probe.absolute();code=hashlib.sha256(probe.read_bytes()).hexdigest()
    def check(label,ok):checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def request(name,data,facts,unit=512):
        path=images/(name+'.img');path.write_bytes(data);before=metadata(path);manifest.append(dict(path=str(path),bytes=len(data),sha256=sha(data),metadata=before))
        return dict(mode='compare',image=str(path),unit=str(unit),subject='disk',expected_source=before,expected_content_digest=sha(data),storage=fixture(facts,unit,(len(data)+unit-1)//unit))
    def samples(v):
        rows=list(v.get('image_samples',[]))+list(v.get('storage_samples',[]))
        rows.extend(v[k] for k in ('image_worker','before','cancelled','retirement') if k in v)
        return rows
    def run(name,value,expected=0,state=None,raw_state=None):
        payload=json.dumps(value,separators=(',',':')).encode();(out/(name+'.request.json')).write_bytes(payload);start=time.monotonic()
        r=subprocess.run([probe],input=payload,capture_output=True,timeout=20);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,exit_code=r.returncode,expected_exit=expected,expected_state=state,expected_raw_state=raw_state,elapsed_seconds=round(time.monotonic()-start,3)))
        check(name+' exact exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout);check(name+' architecture',v['pointer_bytes']==str(a.pointer_bytes))
        for row in samples(v):
            w=row['worker'];check(name+' code identity',row['code_sha256']==code)
            check(name+' no worker authority',not row['claims']['physical_admission'] and not row['claims']['mutation_authority'])
            if int(w['pid']):
                check(name+' native creation',int(w['created'])>0);children.add((w['pid'],w['created']))
            if row['status']=='completed':check(name+' actual request bound',len(row['request_digest'])==64 and row['admitted'])
        if v.get('has_file_snapshot'):
            receipt=v['file_receipt'];raw=v['raw'];context=v['file_context'];last=v['image_samples'][-1]
            check(name+' independent source metadata',receipt['source_before']==value['expected_source'])
            check(name+' source bytes hash',receipt['sha256']==value['expected_content_digest']==raw['source']['sha256'])
            check(name+' byte coverage',int(receipt['captured_bytes'])==int(receipt['source_before']['bytes']) and receipt['whole_file_hashed'])
            check(name+' unit and epoch',receipt['logical_sector_bytes']==value['unit'] and receipt['capture_epoch']==value.get('file_capture','1'))
            check(name+' actual file process/context',all(context[k]==last[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256','capture_epoch')) and context['pid']==last['worker']['pid'] and context['created']==last['worker']['created'])
            check(name+' source observation only',raw['source']['consistency']=='unknown' and not raw['claims']['mutation_authority'])
        if state is not None:
            c=v['comparison'];pure=c['common_fields'];fc=v['file_context'];sc=v['storage_context']
            check(name+' expected comparison',c['state']==state)
            if raw_state:check(name+' expected raw state',v['raw']['state']==raw_state)
            check(name+' independent frame/raw digests',pure['binding']['frame_digest']==digest(v['frame']) and pure['binding']['raw_digest']==digest(v['raw']))
            check(name+' independent file/context digests',c['file_context_digest']==digest(fc) and c['storage_context_digest']==digest(sc) and c['file_capture_digest']==digest(dict(receipt=v['file_receipt'],context=fc,raw_digest=digest(v['raw']))))
            check(name+' independent processes',(fc['pid'],fc['created'])!=(sc['pid'],sc['created']))
            check(name+' owned storage context',sc['code_sha256']==code and sc['pid']==v['storage_samples'][-1]['worker']['pid'] and sc['created']==v['storage_samples'][-1]['worker']['created'])
            check(name+' comparison makes no API call',v['comparison_api_calls']=='0')
            check(name+' exact conservative claims',c['claims']==dict(owned_process_bindings_verified=True,physical_identity='unknown',physical_association='unproven',current_resource_freshness='unknown',source_consistency='live-uncoordinated',atomic_snapshot=False,mutation_authority=False))
            check(name+' pure scope remains separate',not pure['claims']['owned_reader_authenticated'] and pure['claims']['binding_scope']=='fixture-declared-pairing')
            check(name+' current accepted capture',v['has_storage_snapshot'] and v['capture_epoch']=='1' and not v['capture_sources'][0]['outstanding'])
        return v
    try:
        corpus=recipes();mbr=next(x['data'] for x in corpus if x['name']=='mbr-two')
        facts=dict(style=0,rows=[dict(start=512,length=31*512,type=7,boot=0),dict(start=40*512,length=60*512,type=0x83,boot=0)])
        base=request('mbr',mbr,facts);v=run('mbr',base,state='agree-within-scope',raw_state='complete');check('MBR every entry',len(v['comparison']['common_fields']['matches'])==2)
        wide=copy.deepcopy(facts)
        for row in wide['rows']:row['start']*=8;row['length']*=8
        run('mbr-4096',request('mbr-4096',mbr+b'\0'*(256*4096-len(mbr)),wide,4096),state='agree-within-scope',raw_state='complete')
        for unit,count in [(512,1),(4096,1),(512,10),(4096,10),(512,64),(4096,64)]:
            data,gfacts=gpt_image(unit,count);req=request('gpt-'+str(unit)+'-'+str(count),data,gfacts,unit);v=run('gpt-'+str(unit)+'-'+str(count),req,state='agree-within-scope',raw_state='complete')
            check('GPT every row '+str(unit)+'/'+str(count),len(v['comparison']['common_fields']['matches'])==count)
            if count==1:check('GPT all36 UTF16 units '+str(unit),v['raw']['entries'][0]['gpt_name_hex']==gfacts['rows'][0]['name'].hex())
        ebr=bytearray(256*512);ebr[:512]=table([mbr_entry(15,10,200)]);rows=[dict(start=5120,length=200*512,type=15)]
        for i in range(10):
            lba=10+3*i;entries=[mbr_entry(7,1,1)]
            if i<9:entries.append(mbr_entry(15,3*(i+1),200-3*(i+1)))
            ebr[lba*512:(lba+1)*512]=table(entries);rows.append(dict(start=(lba+1)*512,length=512,type=7))
        req=request('ebr-ten',ebr,dict(style=0,rows=rows));v=run('ebr-ten',req,state='agree-within-scope',raw_state='complete');check('all10 EBR entries',len(v['raw']['entries'])==11)
        req['policy']=dict(partitions='64',ebr_nodes='1');run('ebr-budget',req,state='incomparable',raw_state='budget_exhausted')
        req=request('exact-byte-boundary',mbr+b'\0'*(16*1024*1024-len(mbr)),facts);run('exact-byte-boundary',req,state='agree-within-scope',raw_state='complete')
        for name,data,raw_state in [('partial-block',mbr+b'\0','complete'),('short-image',mbr[:100],'incomplete'),('unrecognized',b'\0'*512,'unrecognized')]:
            req=request(name,data,facts);v=run(name,req,state='incomparable',raw_state=raw_state)
            if name=='partial-block':check('partial final block explicit',v['file_receipt']['partial_final_block'])
        data,gfacts=gpt_image();damaged=bytearray(data);damaged[512+16]^=1;run('GPT-corrupt',request('GPT-corrupt',damaged,gfacts),state='incomparable',raw_state='incomparable')
        changed=copy.deepcopy(base);changed['storage']['subjects'][0]['replies']['layout']=[packet(b'\0'*47)];run('native-layout-malformed',changed,state='incomparable')
        changed=copy.deepcopy(base);changed['storage']=fixture(dict(style=0,signature=1,rows=facts['rows']));run('native-signature-disagrees',changed,state='disagree')
        for fault in ('reread_changed','reread_error','short_reread','metadata_changed','metadata_error'):
            req=copy.deepcopy(base);req['fixture']=dict(capture_fault=fault);v=run(fault,req,state='incomparable',raw_state='complete');check(fault+' source unstable',not v['file_receipt']['observed_stable'])
        for fault in ('read_error','short_read'):
            req=copy.deepcopy(base);req['fixture']=dict(capture_fault=fault);v=run(fault,req);check(fault+' no captured layout',not v['has_file_snapshot'] and v['image_samples'][-1]['result']['status']=='unavailable')
        for fault in ('content','size','writer_open','replace'):
            req=request('source-'+fault,mbr,facts);req['source_fault']=fault;v=run('source-'+fault,req);check(fault+' expected source refused',not v['has_file_snapshot'])
        for name,data in [('empty',b''),('over-byte-boundary',b'\0'*(16*1024*1024+1))]:
            req=request(name,data,facts);v=run(name,req);check(name+' budget unavailable',not v['has_file_snapshot'] and v['image_samples'][-1]['result']['diagnostic']['code']=='file_layout_input_budget')
        req=copy.deepcopy(base);req['expected_content_digest']='sha256:'+'0'*64;v=run('old-content-hash',req);check('old content refused',not v['has_file_snapshot'])
        for fault in ('corrupt_payload','corrupt_layout','corrupt_receipt','claims'):
            req=copy.deepcopy(base);req['fixture']=dict(worker_fault=fault);v=run(fault,req);check(fault+' cannot construct owned value',not v['has_file_snapshot'])
        for fault in ('capture','worker','shape','status','claims','schema','digest','code','request','scope','host','observer','attempt','pid','created'):
            req=copy.deepcopy(base);req['fixture']=dict(reply_fault=fault);v=run('reply-'+fault,req);check(fault+' cannot construct owned value',not v['has_file_snapshot'])
        for fault in ('before_spawn','after_spawn','after_spawn_alloc'):
            req=copy.deepcopy(base);req['fixture']=dict(startup_fault=fault);v=run('startup-'+fault,req);check(fault+' exact startup ownership',v['never_launched']==(fault=='before_spawn'))
            if fault!='before_spawn':check(fault+' exact owned exit',v['retirement']['worker']['observation']=='exited')
        req=copy.deepcopy(base);req['cancel']=True;v=run('cancel-before-release',req);check('cancellation has no captured layout',not v['has_file_snapshot'] and v['image_samples'][-1]['cancellation_requested'])
        req=copy.deepcopy(base);req.update(mode='pending',fixture=dict(worker_fault='hang'),cancel=True);v=run('hung-reader',req);check('hang retains running identity',v['before']['worker']['observation']=='running' and not v['has_snapshot']);check('owned retirement exact exit',v['retirement']['worker']['observation']=='exited')
        req=copy.deepcopy(base);req['fixture']=dict(worker_fault='late');run('late-same-image-reader',req,state='agree-within-scope')
        req=copy.deepcopy(base);req['advance_capture']=True;v=run('retained-old-capture',req,state='agree-within-scope');check('old capture not current',not v['old_frame_available'])
        req=copy.deepcopy(base);req['advance_before_storage']=True;v=run('superseded-storage-capture',req);check('superseded reply cannot construct frame',not v['has_storage_snapshot'])
        req=copy.deepcopy(base);req['mode']='construction';v=run('prepare-without-launch',req);check('no launch at preparation',v['prepared'] and v['never_launched'])
        for role,count in [('__disked_nt_image_layout_fixture_worker',5),('__disked_nt_image_layout_fixture_worker',7),('__disked_nt_identity_fixture_worker',4),('__disked_nt_identity_fixture_worker',6)]:
            name='role-arity-'+role+'-'+str(count);args=[str(probe),role,*(['0']*count)];r=subprocess.run(args,capture_output=True,timeout=5);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
            runs.append(dict(label=name,command=args,exit_code=r.returncode,expected_exit=2));check(name+' rejects before handles',r.returncode==2 and not r.stdout and not r.stderr)
        for field,value in [('capture','2'),('worker','0'),('source','other'),('subject','other'),('frame_digest','sha256:'+'0'*64),('raw_digest','sha256:'+'0'*64),('file_capture_digest','sha256:'+'0'*64),('file_context_digest','sha256:'+'0'*64),('storage_context_digest','sha256:'+'0'*64)]:
            req=copy.deepcopy(base);req['binding']={field:value};v=run('binding-'+field,req,expected=3);check(field+' retains both exact readers',v['has_file_snapshot'] and v['has_storage_snapshot'] and bool(v['join_error']))
        req=copy.deepcopy(base);req['file_capture']='2';v=run('file-capture-mismatch',req,expected=3);check('capture mismatch retains readers',v['has_file_snapshot'] and v['has_storage_snapshot'])
        for field,value in [('unit','520'),('file_capture','0'),('expected_content_digest','bad'),('fixture',dict(unrecognized='yes')),('policy',dict(partitions='0',ebr_nodes='128'))]:
            req=copy.deepcopy(base);req[field]=value;v=run('request-'+field,req,expected=3);check(field+' before launch','image_samples' not in v)
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=runs,children=sorted(children),live_storage_qualified=False,physical_association='unproven',mutation_authority=False,unit_complete=False)
    except BaseException as error:
        result=dict(status='fail',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=runs,error=str(error));raise
    finally:
        (out/'image-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        if 'result' in locals():(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],controllers=len(runs),children=len(children),assertions=len(checks))))

if __name__=='__main__':main()
