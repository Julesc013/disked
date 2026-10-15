"""Independent NTFS filename/root recipes; guarded native supplied-byte APIs only."""
import argparse,copy,hashlib,json,struct,subprocess
from pathlib import Path

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(v):return 'sha256:'+hashlib.sha256(v).hexdigest()
def reference(number=5,sequence=3):return number|(sequence<<48)
def blank_name():
    return dict(raw_bytes='0',parent_reference='0',parent_record='0',parent_sequence=0,duplicated_hex='',name_length=0,namespace=0,name_hex='',suffix_hex='',fields_present=False,envelope_valid=False,namespace_known=False,issues=0)

def filename(name=b'A\0',namespace=1,parent=None,suffix=b'',info=None):
    parent=reference() if parent is None else parent
    info=bytes(range(56)) if info is None else info
    assert len(name)%2==0 and len(name)<=510 and len(info)==56
    length=len(name)//2
    raw=struct.pack('<Q',parent)+info+bytes([length,namespace])+name+suffix
    expected=dict(raw_bytes=str(len(raw)),parent_reference=str(parent),parent_record=str(parent&((1<<48)-1)),parent_sequence=parent>>48,
                  duplicated_hex=info.hex(),name_length=length,namespace=namespace,name_hex=name.hex(),suffix_hex=suffix.hex(),
                  fields_present=True,envelope_valid=bool(length),namespace_known=namespace<=3,
                  issues=(0 if length else 2)|(0 if namespace<=3 else 4)|(0 if parent>>48 else 8))
    return raw,expected

def entry(key=None,target=None,child=None,end=False,padding=0):
    if key is None:key=filename()
    blob,name=key
    if end:blob=b'';name=blank_name()
    target=reference(14,9) if target is None else target
    length=(16+len(blob)+(8 if child is not None else 0)+padding+7)&~7
    raw=bytearray(length);struct.pack_into('<QHHHH',raw,0,target,length,len(blob),(1 if child is not None else 0)|(2 if end else 0),0x5a17)
    raw[16:16+len(blob)]=blob
    padlen=length-16-len(blob)-(8 if child is not None else 0)
    raw[16+len(blob):16+len(blob)+padlen]=b'\xa7'*padlen
    if child is not None:struct.pack_into('<Q',raw,length-8,child)
    expected=dict(raw_bytes=str(length),record_length=length,key_length=len(blob),flags=(1 if child is not None else 0)|(2 if end else 0),
                  segment_reference='0' if end else str(target),record_number='0' if end else str(target&((1<<48)-1)),sequence=0 if end else target>>48,
                  child_vbn=str(child or 0),key_hex=blob.hex(),padding_hex=(b'\xa7'*padlen).hex(),filename=name,present=True,end_marker=end,has_child=child is not None,envelope_valid=True,issues=0)
    return bytes(raw),expected

def root(entries=None,cluster=4096,index=4096,children=False,prefix=0,slack=0,suffix=b''):
    entries=entries if entries is not None else [entry(),entry(end=True)]
    first=16+prefix;body=b''.join(row[0] for row in entries);used=first+len(body);allocated=used+slack
    raw=bytearray(16+allocated);struct.pack_into('<IIIB',raw,0,0x30,1,index,index//(512 if index<cluster else cluster))
    raw[13:16]=b'\xf1\xf2\xf3';struct.pack_into('<IIIB',raw,16,first,used,allocated,int(children));raw[29:32]=b'\xf4\xf5\xf6'
    raw[32:16+first]=b'\xe2'*prefix;raw[16+first:16+used]=body;raw[16+used:]=b'\xe3'*slack;raw+=suffix
    expected=dict(root=dict(raw_bytes=str(len(raw)),type=0x30,collation=1,index_bytes=index,units=index//(512 if index<cluster else cluster),flags=int(children),first=first,used=used,allocated=allocated,child_unit_bytes=512 if index<cluster else cluster,
                            fields_present=True,envelope_valid=True,geometry_matches=True,directory_profile=True,issues=0),
                  items=[row[1] for row in entries],count=len(entries),offset=str(len(body)),issues=0,terminated=True,stopped=False,empty_unchanged=True)
    return bytes(raw),expected

def cases():
    def request(mode,raw,**kwargs):return dict(mode=mode,hex=raw.hex(),major='3',minor='1',cluster='4096',index_bytes='4096',budget='4096',**kwargs)
    def case(label,mode,raw,wanted,**controls):
        req=request(mode,raw);req.update({k:str(v) for k,v in controls.items()})
        return label,req,dict(init_status=0,outputs_unchanged=False,source_unchanged=True,**copy.deepcopy(wanted))
    for minor in (0,1):
        for n in range(1,256):
            name=bytes([n,255-n])*n;raw,wanted=filename(name,namespace=n%4)
            yield case(f'name-length-{minor}-{n}','name',raw,dict(name=wanted),minor=minor)
        for parent in [reference(0,1),reference((1<<48)-1,65535),reference(1<<40,0x8000),reference(1<<32,0x7fff)]:
            raw,wanted=filename(parent=parent);yield case('name-reference-'+str(parent)+'-'+str(minor),'name',raw,dict(name=wanted),minor=minor)
    for namespace in (0,1,2,3,4,127,255):
        raw,wanted=filename(struct.pack('<8H',0,9,27,47,92,0xd800,0xdfff,0xffff),namespace,suffix=b'\x99\x00\xff')
        yield case('lossless-namespace-'+str(namespace),'name',raw,dict(name=wanted))
    for parent in (0,5,(1<<48)-1):
        raw,wanted=filename(parent=parent);yield case('name-zero-parent-sequence-'+str(parent),'name',raw,dict(name=wanted))
    raw,wanted=filename(name=b'');yield case('empty-name','name',raw,dict(name=wanted))
    full,_=filename(b'A\0'*255)
    for n in range(len(full)):
        wanted=dict(raw_bytes=str(n),fields_present=n>=66,envelope_valid=False,issues=1 if n<66 else 3,name_hex='',suffix_hex='')
        yield case('name-truncation-'+str(n),'name',full[:n],dict(name=wanted))
    for minor in (0,1):
        for cluster,index in [(512,512),(512,4096),(4096,4096),(4096,1024),(2097152,32768),(512,32768)]:
            for children in (False,True):
                rows=[entry(child=0 if children else None),entry(key=filename(b'Z\0',3,suffix=b'\x88\x77'),target=reference((1<<48)-1,65535),child=(1<<63)-1 if children else None),entry(end=True,target=(1<<64)-1,child=16 if children else None,padding=16)]
                raw,wanted=root(rows,cluster,index,children,prefix=8,slack=5,suffix=b'\xef')
                yield case(f'root-geometry-{minor}-{cluster}-{index}-{children}','index',raw,wanted,minor=minor,cluster=cluster,index_bytes=index,budget=3)
    for children in (False,True):
        raw,wanted=root([entry(end=True,child=0 if children else None)],children=children)
        yield case('empty-directory-'+str(children),'index',raw,wanted,budget=1)
        for extra in (0,64928 if children else 64936):
            rows=[entry(key=filename(b'Z\0'*255,3),child=1 if children else None,padding=extra),entry(end=True,child=2 if children else None)]
            raw,wanted=root(rows,children=children)
            yield case(f'maximum-key-and-entry-{children}-{extra}','index',raw,wanted,budget=2)
    base,wanted=root()
    for n in range(len(base)):
        yield case('root-truncation-'+str(n),'index',base[:n],dict(root=dict(raw_bytes=str(n),fields_present=n>=32,envelope_valid=False,issues=1 if n<32 else 3),items=[],count=0,offset='0',terminated=False,stopped=True,issues=1 if n<32 else 3))
    for label,at,fmt,value,issue in [
        ('wrong-type',0,'I',0x40,8),('wrong-collation',4,'I',0x10,8),('block-zero',8,'I',0,16),('block-max',8,'I',0xffffffff,16),
        ('units-zero',12,'B',0,16),('units-signed-code',12,'B',0xf4,16),('root-flags',28,'B',0x80,32),
        ('first-overlap',16,'I',8,2),('first-misaligned',16,'I',17,4),('first-max',16,'I',0xffffffff,6),
        ('used-before-first',20,'I',15,2),('used-short-header',20,'I',31,2),('used-over-allocation',20,'I',len(base),2),('allocation-over-view',24,'I',len(base),3)]:
        raw=bytearray(base);struct.pack_into('<'+fmt,raw,at,value)
        yield case(label,'index',raw,dict(root=dict(issues=issue),items=[],count=0,offset='0',terminated=False,stopped=True,issues=issue))
    for label,at,value,issue in [('length-zero',8,0,2),('length-short',8,8,2),('length-unaligned',8,17,4),('length-max',8,65535,7),('key-empty',10,0,64),('key-short',10,65,64),('key-over-entry',10,65535,64),('unknown-entry-flags',12,4,32),('child-flag-in-leaf',12,1,32)]:
        raw=bytearray(base);struct.pack_into('<H',raw,32+at,value)
        yield case('entry-'+label,'index',raw,dict(root=dict(issues=0,directory_profile=True),items=[dict(issues=issue,envelope_valid=False,present=True)],count=1,offset='0',terminated=False,stopped=True,issues=issue))
    for label,rows,children,issue in [
        ('zero-reference',[entry(target=14),entry(end=True)],False,128),
        ('zero-parent',[entry(key=filename(parent=5)),entry(end=True)],False,64),
        ('unknown-key-namespace',[entry(key=filename(namespace=7)),entry(end=True)],False,64),
        ('negative-child',[entry(child=1<<63),entry(end=True,child=0)],True,256),
        ('negative-terminal-child',[entry(end=True,child=(1<<64)-1)],True,256),
        ('missing-node-flag',[entry(),entry(end=True,child=0)],True,32)]:
        raw,_=root(rows,children=children);yield case(label,'index',raw,dict(items=[dict(issues=issue,envelope_valid=False)],count=1,offset='0',terminated=False,stopped=True,issues=issue))
    raw,_=root([entry()]);yield case('missing-terminal','index',raw,dict(items=[dict(issues=0),dict(issues=512,present=False)],count=1,offset=str(len(entry()[0])),terminated=False,stopped=True,issues=512))
    for children in (False,True):
        whole,_=entry(child=0 if children else None)
        for n in range(16,len(whole)):
            raw,_=root([(whole[:n],{})],children=children)
            yield case(f'entry-body-truncation-{children}-{n}','index',raw,dict(items=[dict(present=True,envelope_valid=False,issues=3)],count=1,offset='0',terminated=False,stopped=True,issues=3))
    for n in range(1,16):
        first=entry();raw,_=root([first,(b'\xff'*n,{})])
        yield case('next-header-truncation-'+str(n),'index',raw,dict(items=[dict(issues=0),dict(present=False,issues=513)],count=1,offset=str(len(first[0])),terminated=False,stopped=True,issues=513))
    terminal,_=entry(end=True);raw,_=root([(terminal+b'\0'*8,{})]);yield case('trailing-used-bytes','index',raw,dict(items=[dict(issues=512)],count=1,offset='0',terminated=False,stopped=True,issues=512))
    raw=bytearray(24);struct.pack_into('<HH',raw,8,24,1);struct.pack_into('<H',raw,12,2)
    raw,_=root([(bytes(raw),{})]);yield case('terminal-key','index',raw,dict(items=[dict(issues=512)],count=1,offset='0',terminated=False,stopped=True,issues=512))
    raw,_=root();yield case('quota-before-terminal','index',raw,dict(items=[dict(issues=0),dict(issues=1024,present=False)],count=1,offset=str(len(entry()[0])),terminated=False,stopped=True,issues=1024),budget=1)
    for n in (1,3,63,4095):
        rows=[entry()]*n+[entry(end=True)];raw,wanted=root(rows)
        yield case('exact-quota-'+str(n+1),'index',raw,wanted,budget=n+1)
        yield case('quota-one-short-'+str(n),'index',raw,dict(count=n,offset=str(len(entry()[0])*n),terminated=False,stopped=True,issues=1024,items=[dict(issues=0)]*n+[dict(issues=1024,present=False)]),budget=n)
    for mode in ('name','index'):
        raw=filename()[0] if mode=='name' else base
        for major,minor in [(0,0),(2,1),(3,2),(4,0)]:
            label,req,_=case('invalid-version-'+mode+str((major,minor)),mode,raw,{},major=major,minor=minor)
            yield label,req,dict(init_status=1,outputs_unchanged=True,source_unchanged=True)
    for field,values in [('cluster',[0,1,511,513,2097153,0xffffffff]),('index_bytes',[0,1,511,513,49152,65536,0xffffffff]),('budget',[0,4097])]:
        for value in values:
            label,req,_=case('invalid-'+field+'-'+str(value),'index',base,{},**{field:value})
            yield label,req,dict(init_status=7,outputs_unchanged=True,source_unchanged=True)

def compare(actual,wanted,path=''):
    if isinstance(wanted,dict):
        for key,value in wanted.items():
            assert key in actual,(path,key,actual)
            compare(actual[key],value,path+'.'+key)
    elif isinstance(wanted,list):
        assert len(actual)==len(wanted),(path,len(actual),len(wanted))
        for i,(a,w) in enumerate(zip(actual,wanted)):compare(a,w,path+f'[{i}]')
    else:assert actual==wanted,(path,actual,wanted)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    rows=list(cases());receipts=[];at=0
    while at<len(rows):
        count=1 if len(rows[at][1]['hex'])>131072 else 8
        batch=[]
        for row in rows[at:at+count]:
            if batch and len(row[1]['hex'])>131072:break
            batch.append(row)
        p=subprocess.run([str(a.probe.resolve())],input=canonical([r[1] for r in batch]),capture_output=True,timeout=40)
        assert p.returncode==0 and not p.stderr,(batch[0][0],p.returncode,p.stderr.decode(errors='replace'))
        results=json.loads(p.stdout);assert len(results)==len(batch)
        for (label,request,wanted),actual in zip(batch,results):
            compare(actual,wanted,label)
            receipts.append(dict(case=label,input_sha256=sha(canonical(request)),expectation_sha256=sha(canonical(wanted)),result_sha256=sha(canonical(actual)),passed=True))
        at+=len(batch)
    a.output.write_text(json.dumps(dict(count=len(receipts),cases=receipts,scope='Private supplied-byte NTFS filename/index envelopes only; no native directory acquisition/traversal or full filesystem qualification',physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(len(receipts),'guarded filename/index cases passed')
if __name__=='__main__':main()
