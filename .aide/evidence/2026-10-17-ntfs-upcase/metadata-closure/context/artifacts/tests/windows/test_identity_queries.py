"""Independent generated Win32 device-ID/alignment/layout byte fixtures; no media access."""
import argparse,copy,hashlib,json,struct,subprocess
from pathlib import Path

def reply(data=b'',ok=True,error=0,returned=None):return dict(hex=data.hex(),ok=ok,error=str(error),returned=str(len(data) if returned is None else returned))
def identifiers(values=None):
    values=[(1,3,0,b'\x01\x00\x1b\xff')] if values is None else values
    blocks=[]
    for i,(code,kind,association,data) in enumerate(values):
        blocks.append(struct.pack('<IIHHI',code,kind,len(data),16+len(data) if i+1<len(values) else 0,association)+data)
    size=max(16,12+sum(map(len,blocks)));blob=struct.pack('<III',16,size,len(values))+b''.join(blocks)
    return blob.ljust(size,b'\0')
def alignment(logical=512,physical=4096,offset=1536):return struct.pack('<7I',28,28,64,0,logical,physical,offset)
def entry(style=1,start=4096,length=8192,number=1,guid=None,name=None,mbr_type=7):
    data=bytearray(144);struct.pack_into('<I4xqqIB',data,0,style,start,length,number,0)
    if style==0:struct.pack_into('<BBB1xI',data,32,mbr_type,1,1,8)
    else:
        data[32:48]=bytes.fromhex('112233445566778899aabbccddeeff00');data[48:64]=guid or bytes(range(16))
        struct.pack_into('<Q',data,64,0xf000000000000001);data[72:144]=(name or b'D\0\x1b\0\0\xd8\x2e\x20').ljust(72,b'\0')
    return bytes(data)
def layout(style=1,entries=None):
    entries=[entry()] if entries is None else entries;header=bytearray(48);struct.pack_into('<II',header,0,style,len(entries))
    if style==1:header[8:24]=bytes(range(16));struct.pack_into('<qqI',header,24,4096,1024*1024,128)
    elif style==0:struct.pack_into('<I',header,8,0x12345678)
    return bytes(header)+b''.join(entries)
def fixture(ids=None,align=None,table=None):
    ids=identifiers() if ids is None else ids;align=alignment() if align is None else align;table=layout() if table is None else table
    sizes=[];n=192
    while len(table)>n:sizes.append(reply(ok=False,error=122));n*=2
    return dict(profile='identity-layout',subjects=[dict(replies=dict(identifiers=[reply(ids[:8]),reply(ids)],alignment=[reply(align)],layout=sizes+[reply(table)]))])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,required=True);a=p.parse_args();a.output.mkdir();checks=[];runs=[]
    def check(label,ok):checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def run(name,f,exit_code=0):
        raw=json.dumps(f,separators=(',',':')).encode();(a.output/(name+'.request.json')).write_bytes(raw)
        result=subprocess.run([a.probe],input=raw,capture_output=True,timeout=15);(a.output/(name+'.stdout')).write_bytes(result.stdout);(a.output/(name+'.stderr')).write_bytes(result.stderr)
        check(name+' exit',result.returncode==exit_code);value=json.loads(result.stdout);check(name+' pointer',int(value['pointer_bytes'])==a.pointer_bytes)
        runs.append(dict(name=name,exit_code=result.returncode,api_calls=int(value['api_calls'])));return value
    def state(name,f,component,wanted):
        value=run(name,f);check(name+' state',value[component]['state']==wanted);return value
    base=fixture();v=run('gpt-complete',base)
    for k in ('identifiers','alignment','layout'):
        check(k+' observed',v[k]['state']=='observed');data=v[k]['data'];check(k+' no authority',data['physical_identity']=='unknown' and data['physical_admission'] is False and data['mutation_authority'] is False)
        for receipt in v[k]['receipts']:
            if receipt['returned_hex'] is not None:check(k+' receipt digest',receipt['returned_sha256']=='sha256:'+hashlib.sha256(bytes.fromhex(receipt['returned_hex'])).hexdigest())
    check('ID bytes',v['identifiers']['data']['identifiers'][0]['original_hex']=='01001bff')
    check('alignment exact',v['alignment']['data']['sector_alignment_offset_bytes']=='1536' and v['alignment']['data']['physical_sector_bytes']=='4096')
    row=v['layout']['data']['partitions'][0];check('original name units',row['gpt_name']['original_hex']==entry()[72:144].hex());check('unsigned attributes',row['gpt_attributes']==str(0xf000000000000001))
    check('partition bytes',row['entry_hex']==entry().hex());check('OS report not raw verification',v['layout']['data']['raw_metadata_independently_verified'] is False)
    check('property identities',v['identifiers']['receipts'][0]['property_id']=='2' and v['alignment']['receipts'][0]['property_id']=='6')
    check('explicit query sequence',[x['component'] for x in v['trace']]==['identifiers','identifiers','alignment','layout'])
    state('raw-empty',fixture(table=layout(2,[])),'layout','observed')
    mbr=layout(0,[entry(0,number=i+1,mbr_type=7 if i==0 else 0) for i in range(4)]);v=state('mbr-four',fixture(table=mbr),'layout','observed');check('MBR signature',v['layout']['data']['mbr_signature_raw']==str(0x12345678))
    v=state('duplicate-identifiers',fixture(ids=identifiers([(1,3,0,b'A'),(1,3,0,b'A')])),'identifiers','observed');check('duplicates retained',len(v['identifiers']['data']['identifiers'])==2 and all(x['duplicate_in_reply'] for x in v['identifiers']['data']['identifiers']))
    state('unknown-ID-enums',fixture(ids=identifiers([(99,99,99,b'A')])),'identifiers','observed')
    state('empty-ID-array',fixture(ids=identifiers([])),'identifiers','observed')
    v=state('duplicate-layout',fixture(table=layout(entries=[entry(),entry(start=8192)])),'layout','observed');check('layout conflicts explicit',all(set(['duplicate_partition_guid','duplicate_partition_number','reported_range_overlap'])<=set(x['issues']) for x in v['layout']['data']['partitions']))
    table=layout(entries=[entry(start=0)]);v=state('outside-usable',fixture(table=table),'layout','observed');check('outside flagged','outside_reported_usable_range' in v['layout']['data']['partitions'][0]['issues'])
    for name,offset,fmt,value in [('id-over-count',8,'I',33),('id-unknown-version',0,'I',20),('id-bad-length',20,'H',500),('id-last-offset',22,'H',1)]:
        data=bytearray(identifiers());struct.pack_into('<'+fmt,data,offset,value);wanted='budget_exhausted' if name=='id-over-count' else 'unsupported_version' if name=='id-unknown-version' else 'malformed';state(name,fixture(ids=bytes(data)),'identifiers',wanted)
    f=fixture();f['subjects'][0]['replies']['identifiers'][1]['returned']='15';state('truncated-ID-body',f,'identifiers','malformed')
    f=fixture();raw=bytearray(identifiers());struct.pack_into('<I',raw,4,len(raw)+1);f['subjects'][0]['replies']['identifiers'][1]=reply(raw);state('changed-ID-size',f,'identifiers','changed')
    for name,next_offset in [('id-overlapping-chain',16),('id-chain-outside',65535),('id-early-chain-end',0)]:
        data=bytearray(identifiers([(1,3,0,b'A'),(1,3,0,b'B')]));struct.pack_into('<H',data,22,next_offset);state(name,fixture(ids=bytes(data)),'identifiers','malformed')
    f=fixture();f['subjects'][0]['replies']['identifiers'][0]['returned']='9';v=state('id-header-over-return',f,'identifiers','malformed');check('invalid header stops body',len(v['identifiers']['receipts'])==1)
    data=identifiers([(1,3,0,b'A'*257)]);state('id-value-budget',fixture(ids=data),'identifiers','budget_exhausted')
    data=bytearray(identifiers());struct.pack_into('<I',data,4,4097);state('id-descriptor-budget',fixture(ids=bytes(data)),'identifiers','budget_exhausted')
    for name,args in [('zero-logical',(0,4096,0)),('physical-mismatch',(512,4097,0)),('bad-sector-offset',(512,4096,1)),('offset-outside',(512,4096,4096))]:state(name,fixture(align=alignment(*args)),'alignment','malformed')
    state('non-power-sector',fixture(align=alignment(520,4160,1040)),'alignment','observed')
    data=bytearray(alignment());struct.pack_into('<I',data,12,64);state('cache-offset-outside',fixture(align=bytes(data)),'alignment','malformed')
    data=bytearray(alignment());struct.pack_into('<I',data,0,32);state('alignment-unknown-version',fixture(align=bytes(data)),'alignment','unsupported_version')
    for name,table,wanted in [('negative-start',layout(entries=[entry(start=-1)]),'malformed'),('end-overflow',layout(entries=[entry(start=(1<<63)-1,length=1)]),'malformed'),('mbr-count',layout(0,[entry(0)]),'malformed'),('raw-with-entry',layout(2,[entry(2)]),'malformed'),('unknown-style',layout(3,[]),'unsupported_style')]:state(name,fixture(table=table),'layout',wanted)
    state('maximum-64-layout',fixture(table=layout(entries=[entry(start=4096+i*8192,number=i+1,guid=i.to_bytes(16,'little')) for i in range(64)])),'layout','observed')
    state('over-partition-count',fixture(table=layout(entries=[entry() for _ in range(65)])),'layout','budget_exhausted')
    f=fixture();f['subjects'][0]['replies']['layout'][0]['returned']='193';state('layout-over-return',f,'layout','malformed')
    state('layout-short-prefix',fixture(table=layout(2,[])[:47]),'layout','malformed')
    state('layout-short-entry',fixture(table=layout()[:-1]),'layout','malformed')
    state('layout-mixed-style',fixture(table=layout(entries=[entry(0)])),'layout','malformed')
    table=bytearray(layout(entries=[entry(guid=b'\0'*16)]));table[8:24]=b'\0'*16;struct.pack_into('<I',table,40,0)
    v=state('layout-zero-IDs',fixture(table=bytes(table)),'layout','observed');check('zero disk and max conflicts',set(v['layout']['data']['issues'])=={'zero_disk_guid','count_exceeds_reported_max'});check('zero partition issue','zero_partition_guid' in v['layout']['data']['partitions'][0]['issues'])
    f=fixture();f['subjects'][0]['replies']['layout']=[reply(ok=False,error=122)]*7;v=state('layout-growth-budget',f,'layout','budget_exhausted');check('finite doubling',[x['output_bytes'] for x in v['trace'] if x['component']=='layout']==list(map(str,[192,384,768,1536,3072,6144,12288])))
    for name,component,error,state_name in [('denied-ID','identifiers',5,'denied'),('unsupported-alignment','alignment',50,'unsupported'),('removed-layout','layout',1167,'unavailable')]:
        f=fixture();f['subjects'][0]['replies'][component]=[reply(ok=False,error=error)];state(name,f,component,state_name)
    f=fixture();f['subjects'][0]['replies']['identifiers']=[reply(ok=False,error=997,returned=9999)];v=state('pending-invalid-count',f,'identifiers','unresolved');check('quarantine',v['api_calls']=='1' and v['unresolved'] and v['alignment']['state']=='unresolved' and v['layout']['state']=='unresolved')
    f=fixture();f['cancel_after_io']='1';v=state('cancel-before-ID-body',f,'identifiers','cancelled');check('no calls after cancel',v['api_calls']=='1')
    f=fixture();f['subjects'][0]['replies']['layout']=[reply(ok=False,error=122)];f['cancel_after_io']='4';v=state('cancel-layout-growth',f,'layout','cancelled');check('growth cancellation bounded',v['api_calls']=='4' and len(v['layout']['receipts'])==2)
    f=fixture();f['subjects'][0]['replies']['layout']=[reply(ok=False,error=997)];v=state('pending-layout',f,'layout','unresolved');check('layout quarantine',v['unresolved'] and v['api_calls']=='4')
    for name,value in [('native-table','native'),('mixed-io','mixed-io'),('mixed-error','mixed-error')]:
        f=fixture();f['api']=value;v=run(name,f,3);check(name+' no dispatch',v['api_calls']=='0')
    for name,key,value in [('construction','mode','construction'),('reuse','mode','reuse'),('bad-handle','invalid_handle',True)]:
        f=fixture();f[key]=value;run(name,f,3 if name!='construction' else 0)
    f=fixture();f['subjects'][0]['replies']['identifiers']=[dict(reply(),throw=True)];v=run('callback-exception',f,3);check('exception quarantined',v['unresolved'] and v['api_calls']=='1')
    for component in ('identifiers','alignment','layout'):
        f=fixture();f['subjects'][0]['replies'][component]=[dict(reply(),throw_invalid_argument=True)];v=run(component+'-callback-invalid-argument',f,3);check(component+' exception remains unresolved',v['unresolved'] and v['reason']=='injected_callback_exception')
    result=dict(status='pass',native_executions=len(runs),assertions=len(checks),pointer_bytes=a.pointer_bytes,executions=runs,checks=checks,physical_access=False,provider_admitted=False,owner_accepted=False)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('executions','checks')}))
if __name__=='__main__':main()
