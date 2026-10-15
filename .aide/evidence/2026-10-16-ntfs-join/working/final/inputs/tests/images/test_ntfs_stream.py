"""Independent protected FILE/list constructors and exact ordinary-stream expectations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

CLUSTER=4096
BASE=5<<48
EXT=(9<<48)|7
CONTEXT=dict(source_id='generated-ntfs-stream',epoch='17',offset='4096',length=str(4096*CLUSTER))

def ref(number,sequence):return number|(sequence<<48)
def resident(value=b'original\0bytes',name=b'',kind=0x80,instance=11,flags=0,resident_flags=0):
    at=(24+len(name)+7)//8*8;size=(at+len(value)+7)//8*8;raw=bytearray(size)
    struct.pack_into('<IIBBHHH',raw,0,kind,size,0,len(name)//2,24,flags,instance)
    struct.pack_into('<IHBB',raw,16,len(value),at,resident_flags,0)
    raw[24:24+len(name)]=name;raw[at:at+len(value)]=value;return raw
def signed(value):
    for width in range(1,9):
        if -(1<<(width*8-1))<=value<(1<<(width*8-1)):return value.to_bytes(width,'little',signed=True)
    raise ValueError(value)
def nonresident(low=0,runs=((2,30),),allocated=5*CLUSTER,data=16000,initialized=13001,name=b'',instance=11,kind=0x80,flags=0,high=None):
    pairs=bytearray();previous=0;count=0
    for length,lcn in runs:
        n=signed(length);delta=b'' if lcn is None else signed(lcn-previous)
        pairs.append(len(n)|(len(delta)<<4));pairs+=n+delta;count+=length
        if lcn is not None:previous=lcn
    pairs.append(0);header=72 if low==0 and flags&0x80ff else 64
    at=(header+len(name)+7)//8*8;size=(at+len(pairs)+7)//8*8;raw=bytearray(size)
    struct.pack_into('<IIBBHHH',raw,0,kind,size,1,len(name)//2,header,flags,instance)
    struct.pack_into('<QQHHIQQQ',raw,16,low,low+count-1 if high is None else high,at,0,0,allocated,data,initialized)
    if header==72:struct.pack_into('<Q',raw,64,allocated)
    raw[header:header+len(name)]=name;raw[at:at+len(pairs)]=pairs;return raw
def record(attributes,number=0,sequence=5,base=0,flags=1,size=1024,usa=48,marker=True):
    payload=b''.join(attributes)+(b'\xff'*4 if marker else b'');start=(usa+2*(size//512+1)+7)//8*8
    assert start+len(payload)<=size
    logical=bytearray(size);struct.pack_into('<4sHHQHHHHIIQH',logical,0,b'FILE',usa,size//512+1,0,sequence,1,start,flags,start+len(payload),size,base,100)
    if usa>=48:struct.pack_into('<I',logical,44,number&0xffffffff)
    logical[start:start+len(payload)]=payload;raw=bytearray(logical);struct.pack_into('<H',raw,usa,0x67b4)
    for i,end in enumerate(range(512,size+1,512)):
        raw[usa+2+i*2:usa+4+i*2]=logical[end-2:end];raw[end-2:end]=b'\xb4\x67'
    return raw
def entry(reference=BASE,instance=11,low=0,name=b'',kind=0x80):
    size=(26+len(name)+7)//8*8;raw=bytearray(size)
    struct.pack_into('<IHBBQQH',raw,0,kind,size,len(name)//2,26,low,reference,instance)
    raw[26:26+len(name)]=name;return raw
def row(raw,number=0,**extra):return dict(number=str(number),hex=raw.hex(),**extra)
def request(records,**extra):
    value=dict(context=copy.deepcopy(CONTEXT),base=str(BASE),clusters='4096',name='',records=records)
    value.update(extra);return value
def stream(resident_value=None,name=b'',parts=None,runs=None,allocated=0,data=0,initialized=0,kind=0x80):
    resident_stream=resident_value is not None
    return dict(resident=resident_stream,type=str(kind),name=name.hex(),value=resident_value.hex() if resident_stream else '',
                allocated_bytes=str(allocated),data_bytes=str(len(resident_value) if resident_stream else data),initialized_bytes=str(len(resident_value) if resident_stream else initialized),
                parts=[dict(reference=str(r),instance=str(i),lowest_vcn=str(lo),highest_vcn=str(hi)) for r,i,lo,hi in parts],
                runs=[dict(vcn=str(v),clusters=str(n),lcn=str(l)) for v,n,l in (runs or [])])
def split(name=b'',reverse=False,extension_options=None,first_options=None,list_transform=None,base_extra=()):
    one=nonresident(name=name,**(first_options or {}));two=nonresident(low=2,runs=((3,50),),instance=13,name=name,allocated=(1<<64)-1,data=(1<<64)-1,initialized=(1<<64)-1)
    entries=[entry(name=name),entry(EXT,13,2,name=name)]
    if reverse:entries.reverse()
    if list_transform:entries=list_transform(entries)
    base_record=record([one,resident(b''.join(entries),kind=0x20,instance=1),*base_extra])
    extension_record=record([two],number=7,sequence=9,base=BASE,**(extension_options or {}))
    expected=stream(name=name,parts=[(BASE,11,0,1),(EXT,13,2,4)],runs=[(0,2,30),(2,3,50)],allocated=5*CLUSTER,data=16000,initialized=13001)
    return request([row(base_record),row(extension_record,7)],name=name.hex()),expected

def scenarios():
    def case(name,value,expected=None,diagnostic='',refusal='',missing=()):return name,value,expected,diagnostic,refusal,[str(n) for n in missing]
    plain=request([row(record([resident()]))]);plain_expected=stream(b'original\0bytes',parts=[(BASE,11,0,0)])
    yield case('resident-base',plain,plain_expected)
    yield case('missing-base',request([]),diagnostic='ntfs_join_record_missing',missing=[BASE])
    name=bytes(range(255))*2
    v=request([row(record([resident(name=name)]))],name=name.hex())
    yield case('maximum-lossless-name',v,stream(b'original\0bytes',name=name,parts=[(BASE,11,0,0)]))
    for value in (b'',b'\0',bytes(range(256)),bytes(700)):
        yield case('resident-value-'+str(len(value)),request([row(record([resident(value)]))]),stream(value,parts=[(BASE,11,0,0)]))
    for name in (b'A\0',b'\0\0',b'\0\xd8',b'\x1b\0',b'A\0'*100):
        v,w=split(name=name);yield case('split-raw-name-'+name[:4].hex(),v,w)
    for minor in ('0','1'):
        v,w=split();v['minor']=minor;yield case('split-version-'+minor,v,w)
    v,w=split(reverse=True);yield case('list-order-is-not-vcn-order',v,w)
    for low,count,label in [(3,2,'gap'),(1,4,'overlap')]:
        v,_=split(list_transform=lambda rows:[rows[0],entry(EXT,13,low)])
        v['records'][1]['hex']=record([nonresident(low=low,runs=((count,50),),instance=13)],number=7,sequence=9,base=BASE).hex()
        yield case('matching-list-vcn-'+label,v,diagnostic='ntfs_join_vcn_coverage')
    v,_=split(list_transform=lambda rows:[rows[0],entry(EXT,13,0)])
    v['records'][1]['hex']=record([resident(instance=13)],number=7,sequence=9,base=BASE).hex()
    yield case('matching-list-mixed-forms',v,diagnostic='ntfs_join_mixed_forms')
    v,w=split();v['records'].reverse();yield case('supplied-record-order',v,w)
    v,w=split(base_extra=[resident(kind=0x110,instance=99)]);yield case('opaque-unselected-type',v,w)
    payload=b'resident extension\0';listing=resident(entry(EXT,13),kind=0x20,instance=1)
    v=request([row(record([listing])),row(record([resident(payload,instance=13)],number=7,sequence=9,base=BASE),7)])
    yield case('resident-extension',v,stream(payload,parts=[(EXT,13,0,0)]))
    for usa in (42,48):
        number=(1<<40)+19 if usa==42 else (1<<32)-1;base=ref(number,65535)
        v=request([row(record([resident()],number=number,sequence=65535,usa=usa),number)]);v['base']=str(base)
        yield case('exact-high-reference-'+str(usa),v,stream(b'original\0bytes',parts=[(base,11,0,0)]))
    empty=nonresident(runs=(),high=(1<<64)-1,allocated=0,data=0,initialized=0)
    yield case('empty-nonresident',request([row(record([empty]))]),stream(parts=[(BASE,11,0,(1<<64)-1)]))
    a=nonresident(runs=((1,0),),allocated=CLUSTER,data=4,initialized=3)
    yield case('mapped-lcn-zero',request([row(record([a]))]),stream(parts=[(BASE,11,0,0)],runs=[(0,1,0)],allocated=CLUSTER,data=4,initialized=3))
    a=nonresident(runs=((1,200),(1,50),(1,0)),allocated=3*CLUSTER,data=11,initialized=10)
    yield case('backwards-physical-mappings',request([row(record([a]))]),stream(parts=[(BASE,11,0,2)],runs=[(0,1,200),(1,1,50),(2,1,0)],allocated=3*CLUSTER,data=11,initialized=10))
    a=nonresident(low=1,runs=((1,30),),allocated=CLUSTER,data=4,initialized=3)
    yield case('continuation-without-list',request([row(record([a]))]),diagnostic='ntfs_join_vcn_coverage')
    for count in (64,256):
        v=request([row(record([resident()]),n) for n in range(count)],limits={'records':str(count),'record_bytes':str(count*1024)})
        yield case('exact-supplied-record-budget-'+str(count),v,plain_expected)
    v=copy.deepcopy(plain);v['records'][0]['number']=str(1<<48);yield case('ordinal-outside48',v,refusal='ntfs_join_record_inputs')
    v=copy.deepcopy(plain);v['records'][0]['null_view']=True;yield case('null-nonempty-record-view',v,refusal='ntfs_join_record_inputs')
    v=copy.deepcopy(plain);v['records'][0]['hex']=bytes(49153).hex();yield case('oversized-record-view',v,refusal='ntfs_join_record_inputs')
    data=bytes(48000);v=request([row(record([resident(data)],size=49152))],record_bytes='49152')
    yield case('maximum-record-and-owned-value',v,stream(data,parts=[(BASE,11,0,0)]))
    for name,changes in [('record-count',dict(limits={'records':'1'})),('byte-count',dict(limits={'record_bytes':'2047'})),('attribute-count',dict(limits={'attributes':'2'})),('list-count',dict(limits={'list_entries':'1'})),('run-count',dict(limits={'runs':'1'}))]:
        v,_=split();v.update(changes);yield case('budget-'+name,v,diagnostic='ntfs_join_'+{'record-count':'record','byte-count':'byte','attribute-count':'attribute','list-count':'list','run-count':'run'}[name]+'_budget')
    v,w=split();v['limits']=dict(records='2',record_bytes='2048',attributes='3',list_entries='2',runs='2');yield case('exact-global-budgets',v,w)
    v,w=split();v['records'].pop();yield case('missing-extension',v,diagnostic='ntfs_join_record_missing',missing=[EXT])
    v,w=split();v['records'].append(copy.deepcopy(v['records'][0]));yield case('duplicate-ordinal',v,diagnostic='ntfs_join_record_ambiguous')
    for field,value in [('source_id','different'),('epoch','18'),('offset','4097'),('length',str(4096*CLUSTER-1))]:
        v,_=split();v['records'][1]['context']=dict(CONTEXT,**{field:value});yield case('context-'+field,v,diagnostic='ntfs_join_context')
    for sequence in (0,8,10):
        v,_=split();raw=bytearray.fromhex(v['records'][1]['hex']);struct.pack_into('<H',raw,16,sequence);v['records'][1]['hex']=raw.hex()
        yield case('extension-sequence-'+str(sequence),v,diagnostic='ntfs_join_sequence')
    for owner in (0,ref(1,5),ref(0,6)):
        v,_=split();raw=bytearray.fromhex(v['records'][1]['hex']);struct.pack_into('<Q',raw,32,owner);v['records'][1]['hex']=raw.hex()
        yield case('wrong-extension-base-'+str(owner),v,diagnostic='ntfs_join_base_reference')
    v=copy.deepcopy(plain);raw=bytearray.fromhex(v['records'][0]['hex']);struct.pack_into('<Q',raw,32,BASE);v['records'][0]['hex']=raw.hex();yield case('base-is-extension',v,diagnostic='ntfs_join_base_reference')
    v,_=split();raw=bytearray.fromhex(v['records'][1]['hex']);struct.pack_into('<I',raw,44,8);v['records'][1]['hex']=raw.hex();yield case('wrong-optional-record-number',v,diagnostic='ntfs_join_record_number')
    for at in (0,4,6,20,28,510,1022):
        v=copy.deepcopy(plain);raw=bytearray.fromhex(v['records'][0]['hex']);raw[at]^=0xff;v['records'][0]['hex']=raw.hex();yield case('malformed-file-'+str(at),v,diagnostic='ntfs_join_record_envelope')
    v=copy.deepcopy(plain);raw=bytearray.fromhex(v['records'][0]['hex']);raw[24]^=0xff;v['records'][0]['hex']=raw.hex()
    yield case('bounded-used-slack-after-end-marker',v,plain_expected)
    v=copy.deepcopy(plain);raw=bytearray.fromhex(v['records'][0]['hex']);struct.pack_into('<I',raw,24,1025);v['records'][0]['hex']=raw.hex()
    yield case('used-bytes-exceed-record',v,diagnostic='ntfs_join_record_envelope')
    for size in list(range(0,65))+[511,512,1023]:
        v=copy.deepcopy(plain);v['records'][0]['hex']=v['records'][0]['hex'][:size*2];yield case('short-file-'+str(size),v,diagnostic='ntfs_join_record_size')
    for flags in (0,2,5,0x8001):
        v=request([row(record([resident()],flags=flags))]);yield case('record-flags-'+str(flags),v,diagnostic='ntfs_join_record_flags')
    yield case('duplicate-instance',request([row(record([resident(),resident(kind=0x10)]))]),diagnostic='ntfs_join_instance_ambiguous')
    yield case('missing-attribute',request([row(record([resident(kind=0x10)]))]),diagnostic='ntfs_join_attribute_missing')
    yield case('ambiguous-without-list',request([row(record([resident(),resident(instance=12)]))]),diagnostic='ntfs_join_attribute_ambiguous')
    for payload,code in [(b'', 'list_empty'),(b'\xff'*4,'list'),(entry(reference=0),'list'),(entry()+b'\0','list')]:
        yield case('bad-list-'+code+'-'+str(len(payload)),request([row(record([resident(),resident(payload,kind=0x20,instance=1)]))]),diagnostic='ntfs_join_'+code)
    for transform,code in [(lambda e:e+[e[0]],'list_duplicate'),(lambda e:[entry(instance=12),e[1]],'instance_missing'),(lambda e:[entry(low=1),e[1]],'entry_mismatch'),(lambda e:[e[1]],'unlisted_attribute')]:
        v,_=split(list_transform=transform);yield case('bad-selected-'+code,v,diagnostic='ntfs_join_'+code)
    v,_=split(name=b'A\0');v['name']=b'a\0'.hex();yield case('case-not-normalized',v,diagnostic='ntfs_join_attribute_missing')
    for attrs,code in [([resident(entry(),kind=0x20,instance=1,name=b'N\0')],'list_unsupported'),([resident(entry(),kind=0x20,instance=1,flags=0x4000)],'list_unsupported'),([nonresident(kind=0x20,instance=1)],'nonresident_list_unsupported'),([resident(entry(),kind=0x20,instance=1),resident(entry(),kind=0x20,instance=2)],'list_ambiguous')]:
        yield case('unsupported-'+code,request([row(record([resident(),*attrs]))]),diagnostic='ntfs_join_'+code)
    v=copy.deepcopy(plain);v['type']='32';yield case('list-stream-query',v,diagnostic='ntfs_join_list_query_unsupported')
    for field,value in [('allocated',6*CLUSTER),('data',5*CLUSTER+1),('initialized',16001)]:
        v,_=split(first_options={field:value});yield case('first-size-'+field,v,diagnostic='ntfs_join_allocation' if field=='allocated' else 'ntfs_join_attributes')
    for name,second,code in [('gap',nonresident(low=3,runs=((2,50),),instance=13),'entry_mismatch'),('overlap',nonresident(low=1,runs=((4,50),),instance=13),'entry_mismatch'),('physical',nonresident(low=2,runs=((3,31),),instance=13),'physical_overlap'),('sparse',nonresident(low=2,runs=((3,None),),instance=13),'mapping'),('mixed',resident(instance=13),'entry_mismatch')]:
        v,_=split();v['records'][1]['hex']=record([second],number=7,sequence=9,base=BASE).hex();yield case('bad-extents-'+name,v,diagnostic='ntfs_join_'+code)
    for flags in (1,0x4000,0x8000):
        a=nonresident(flags=flags,runs=((1,30),),allocated=CLUSTER,data=4,initialized=3)
        yield case('unsupported-feature-'+str(flags),request([row(record([a]))]),diagnostic='ntfs_join_feature_unsupported')
    runs=[(1,200+i*2) for i in range(100)];a=nonresident(runs=runs,allocated=100*CLUSTER,data=400000,initialized=399999)
    wanted=stream(parts=[(BASE,11,0,99)],runs=[(i,1,lcn) for i,(_,lcn) in enumerate(runs)],allocated=100*CLUSTER,data=400000,initialized=399999)
    for limit in (16384,23807,23808):yield case('output-budget-'+str(limit),request([row(record([a]))],limits={'output_bytes':str(limit)}),wanted if limit==23808 else None,diagnostic='' if limit==23808 else 'ntfs_join_output_budget')
    for field,value in [('source_id',''),('source_id','x\0y'),('source_id','x'*129),('epoch','0'),('length','0'),('offset',str((1<<64)-1))]:
        v=copy.deepcopy(plain);v['context'][field]=value;yield case('invalid-context-'+field+'-'+str(len(value)),v,refusal='ntfs_join_inputs')
    for field,value in [('base','0'),('major','2'),('minor','2'),('type','17'),('clusters','0'),('cluster_bytes','513'),('record_bytes','513'),('name','00')]:
        v=copy.deepcopy(plain);v[field]=value;yield case('invalid-control-'+field,v,refusal='ntfs_join_inputs')
    for field,maximum in [('records',256),('record_bytes',1048576),('attributes',4096),('list_entries',4096),('runs',4096),('output_bytes',1048576)]:
        for limit in (0,maximum+1):
            v=copy.deepcopy(plain);v['limits']={field:str(limit)};yield case('invalid-limit-'+field+'-'+str(limit),v,refusal='ntfs_join_limits')
    randomizer=random.Random(0x4a4f494e)
    for i in range(96):
        payload=bytes(randomizer.randrange(256) for _ in range(randomizer.randrange(500)));name=bytes(randomizer.randrange(256) for _ in range(randomizer.randrange(16)*2))
        v=request([row(record([resident(payload,name=name)]))],name=name.hex());yield case('generated-resident-'+str(i),v,stream(payload,name=name,parts=[(BASE,11,0,0)]))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();evidence=[]
    cases=list(scenarios())
    for at in range(0,len(cases),8):
        rows=cases[at:at+8];data=json.dumps([r[1] for r in rows]).encode();result=subprocess.run([args.probe],input=data,capture_output=True,timeout=30)
        assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr.decode(errors='replace'))
        outputs=json.loads(result.stdout);assert len(outputs)==len(rows)
        for (name,request,wanted,diagnostic,refusal,missing),observed in zip(rows,outputs):
            assert observed['source_unchanged'] and observed['refusal']==refusal,(name,refusal,observed)
            assert observed['usable']==(wanted is not None),(name,wanted,observed)
            if refusal:assert 'stream' not in observed and 'observation' not in observed
            else:
                report=observed['observation'];assert report['diagnostic']==diagnostic,(name,diagnostic,report)
                assert report['required_records']==missing and observed['required_records']==missing,(name,missing,observed)
                assert report['complete']==(wanted is not None)
                assert not any(report[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
                if wanted is not None:
                    assert observed['stream']==wanted,(name,wanted,observed)
                    assert report['data_bytes']==wanted['data_bytes'] and report['initialized_bytes']==wanted['initialized_bytes']
                    assert report['name_hex']==request['name'] and report['context_matches']
                    if wanted['resident']:assert report['allocated_bytes'] is None and report['value_sha256']=='sha256:'+hashlib.sha256(bytes.fromhex(wanted['value'])).hexdigest()
                    else:assert report['allocated_bytes']==wanted['allocated_bytes']
                else:assert 'stream' not in observed
            evidence.append(dict(case=name,request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),result_sha256=hashlib.sha256(json.dumps(observed,sort_keys=True).encode()).hexdigest(),passed=True))
    Path(args.output).write_text(json.dumps(dict(count=len(evidence),cases=evidence,scope='Captured supplied-record stream joining only; no native acquisition/nonresident-list/full-NTFS admission',physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(len(evidence),'protected-record stream cases passed')
if __name__=='__main__':main()
