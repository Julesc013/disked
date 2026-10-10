"""Independent binary vectors for the proposed native journal framing.

Only bounded in-memory byte sources are used. No journal/file effects are issued.
The reference framing follows DE-043's exact byte contract using struct/hashlib.
"""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path

H=192;P=112;T=32;PAYLOAD=65536;SOURCE=16777216;COUNT=4096
B=dict(journal=bytes(range(1,17)).hex(),plan=hashlib.sha256(b'immutable-plan').hexdigest(),
       targets=hashlib.sha256(b'exact-identities-and-epochs').hexdigest(),providers=hashlib.sha256(b'provider-and-code-closure').hexdigest())
PUB=bytes(range(32,48)).hex()
def sha(b):return hashlib.sha256(b).digest()
def header(b=B):
    pre=struct.pack('<8sHHIII',b'DEJPR001',1,0,H,0,PAYLOAD)
    pre+=b''.join(bytes.fromhex(b[k]) for k in ('journal','plan','targets','providers'))+bytes(24)
    assert len(pre)==160;return pre+sha(pre)
def record(h,seq,previous,payload=b'fixture',kind=5,flags=1,epoch=1,publisher=PUB):
    pre=struct.pack('<4sHHIIQ16sQ',b'JREC',kind,flags,P,len(payload),seq,bytes.fromhex(publisher),epoch)+previous+sha(payload)
    assert len(pre)==P;return pre+payload+sha(h[-32:]+pre+payload)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();root=a.root.resolve();a.probe=a.probe.resolve();requests=[];expectations=[];names=[]
    def add(name,v,check):names.append(name);requests.append(json.loads(canonical(v)));expectations.append(check)
    def same(expected):return lambda v:v==expected
    def scan(name,data,check,**extras):add(name,dict(op='scan',bindings=B,bytes=data.hex(),**extras),check)
    def accepted(records,bytes,last,terminal=False):
        return lambda v:v['disposition']=='valid_prefix' and not v['diagnostic'] and int(v['records'])==records and int(v['verified_bytes'])==bytes and v['last_digest']==last.hex() and v['terminal_record_observed']==terminal
    def failed(code,records=0,verified=H):
        return lambda v:v['disposition']=='invalid' and v['diagnostic']==code and int(v['records'])==records and int(v['verified_bytes'])==verified
    h=header();add('exact-header-bytes',dict(op='header',bindings=B),same(dict(bytes=h.hex(),decoded=B)))
    scan('header-only-no-operation',h,accepted(0,H,h[-32:]))
    f=record(h,1,h[-32:]);r=dict(op='record',kind='5',flags='1',sequence='1',publisher=PUB,publisher_epoch='1',previous=h[-32:].hex(),payload=b'fixture'.hex(),header_digest=h[-32:].hex())
    add('exact-record-bytes',r,same(dict(bytes=f.hex())))
    scan('one-record',h+f,accepted(1,H+len(f),f[-32:]))
    for size in (0,1,31,32,63,64,65,4096,PAYLOAD):
        payload=bytes((n*17+3)%256 for n in range(size));frame=record(h,1,h[-32:],payload)
        add('payload-encode-'+str(size),dict(r,payload=payload.hex()),same(dict(bytes=frame.hex())))
        scan('payload-scan-'+str(size),h+frame,lambda v,n=size,frame=frame:accepted(1,H+len(frame),frame[-32:])(v) and int(v['largest_read'])<=PAYLOAD and v['visited'][0]['payload_digest']==sha(bytes((x*17+3)%256 for x in range(n))).hex())
    # Every cut through the header and this complete frame has an exact outcome.
    for end in range(len(h+f)+1):
        if end<H:check=failed('journal_header_incomplete',verified=0)
        elif end==H:check=accepted(0,H,h[-32:])
        elif end<len(h+f):check=lambda v:v['disposition']=='torn_tail' and int(v['records'])==0 and int(v['verified_bytes'])==H and not v['terminal_record_observed']
        else:check=accepted(1,H+len(f),f[-32:])
        scan('cut-'+str(end),(h+f)[:end],check)
    for index in range(H):
        altered=bytearray(h);altered[index]^=128
        scan('header-bit-'+str(index),altered,lambda v:v['disposition']=='invalid' and int(v['records'])==0 and int(v['verified_bytes'])==0)
    for index in range(len(f)):
        altered=bytearray(f);altered[index]^=128
        scan('record-bit-'+str(index),h+altered,lambda v:v['disposition']!='valid_prefix' and int(v['records'])==0 and int(v['verified_bytes'])==H)
    for key in B:
        other=dict(B);other[key]='00'*(16 if key=='journal' else 32)
        add('empty-binding-'+key,dict(op='header',bindings=other),same(dict(error='journal_empty_binding')))
        other[key]='ff'*(16 if key=='journal' else 32)
        add('target-swap-'+key,dict(op='scan',bindings=other,bytes=(h+f).hex()),failed('journal_binding_mismatch',verified=0))
    for kind in range(1,10):
        frame=record(h,1,h[-32:],kind=kind)
        scan('known-critical-'+str(kind),h+frame,accepted(1,H+len(frame),frame[-32:],kind==9))
        add('producer-critical-bit-'+str(kind),dict(r,kind=str(kind),flags='0'),same(dict(error='journal_critical_bit')))
    for kind in (0,10,100,32767):
        scan('unknown-low-'+str(kind),h+record(h,1,h[-32:],kind=kind,flags=0),failed('journal_unknown_kind'))
    for kind in (32768,32769,65535):
        frame=record(h,1,h[-32:],kind=kind,flags=0)
        scan('compatible-observation-'+str(kind),h+frame,lambda v,frame=frame,kind=kind:accepted(1,H+len(frame),frame[-32:])(v) and v['visited'][0]['known']==(kind==32769))
        if kind!=32769:add('strict-producer-'+str(kind),dict(r,kind=str(kind),flags='0'),same(dict(error='journal_unknown_kind')))
        else:add('known-observation-encode',dict(r,kind=str(kind),flags='0'),same(dict(bytes=frame.hex())))
        scan('critical-high-'+str(kind),h+record(h,1,h[-32:],kind=kind,flags=1),failed('journal_observation_flags' if kind==32769 else 'journal_unknown_kind'))
    for flags in (2,3,65535):scan('unknown-flags-'+str(flags),h+record(h,1,h[-32:],flags=flags),failed('journal_record_flags'))
    for seq in (0,2,18446744073709551615):scan('sequence-'+str(seq),h+record(h,seq,h[-32:]),failed('journal_sequence'))
    for field in ('sequence','publisher_epoch'):
        for value in ('-1','01','18446744073709551616'):
            add('bounded-u64-'+field+'-'+value,dict(r,**{field:value}),same(dict(error='probe_u64')))
        add('producer-zero-'+field,dict(r,**{field:'0'}),same(dict(error='journal_record_identity')))
    frame=record(h,1,h[-32:],epoch=18446744073709551615)
    add('maximum-epoch-encoding',dict(r,publisher_epoch='18446744073709551615'),same(dict(bytes=frame.hex())))
    scan('maximum-epoch-reading',h+frame,accepted(1,H+len(frame),frame[-32:]))
    scan('zero-publisher',h+record(h,1,h[-32:],publisher='00'*16),failed('journal_record_identity'))
    scan('zero-epoch',h+record(h,1,h[-32:],epoch=0),failed('journal_record_identity'))
    scan('wrong-previous',h+record(h,1,bytes(32)),failed('journal_previous_digest'))
    add('producer-over-payload',dict(r,payload=bytes(PAYLOAD+1).hex()),same(dict(error='journal_payload_limit')))
    altered=bytearray(f);struct.pack_into('<I',altered,12,PAYLOAD+1)
    scan('oversized-length-no-body-read',h+altered,lambda v:failed('journal_payload_limit')(v) and v['read_calls']=='2')
    scan('source-budget-before-read',b'',lambda v:failed('journal_source_budget',verified=0)(v) and v['read_calls']=='0',announced=str(SOURCE+1))
    for fault in ('short','oversized','throw','size-throw'):
        scan('source-fault-'+fault,h+f,failed('journal_source_observation_failed' if fault.endswith('throw') else 'journal_source_length',verified=0),fault=fault)
    scan('announced-source-does-not-exist',h,failed('journal_source_length'),announced=str(SOURCE))
    scan('semantic-rejection',h+f,failed('journal_semantic_rejected'),reject_sequence='1')
    scan('semantic-throw',h+f,failed('journal_visitor_failed'),fault='visitor-throw')
    second=record(h,2,f[-32:],b'independent-observation',32769,0,epoch=7,publisher='77'*16)
    scan('two-sequence-domains',h+f+second,lambda v:accepted(2,H+len(f+second),second[-32:])(v) and [x['publisher_epoch'] for x in v['visited']]==['1','7'])
    scan('reordered-records',h+second+f,failed('journal_sequence'))
    scan('duplicate-record',h+f+f,failed('journal_sequence',records=1,verified=H+len(f)))
    seal=record(h,2,f[-32:],b'',9,1);scan('terminal',h+f+seal,accepted(2,H+len(f+seal),seal[-32:],True))
    scan('bytes-after-terminal',h+f+seal+b'x',failed('journal_after_terminal',records=2,verified=H+len(f+seal)))
    # Thousands of frames are streamed; the probe retains at most 64 metadata rows.
    chain=[];previous=h[-32:]
    for sequence in range(1,COUNT+2):
        frame=record(h,sequence,previous,b'',32769,0);chain.append(frame);previous=frame[-32:]
    scan('record-budget-exact',h+b''.join(chain[:-1]),lambda v:accepted(COUNT,H+sum(map(len,chain[:-1])),chain[-2][-32:])(v) and v['metadata_omitted'] and len(v['visited'])==64 and int(v['largest_read'])<=PAYLOAD)
    scan('record-budget-refusal',h+b''.join(chain),failed('journal_record_budget',COUNT,H+sum(map(len,chain[:-1]))))
    # Golden field inventory is checked independently from native declarations.
    profile=json.loads((root/'spec/catalog/journal-prototype.json').read_bytes())
    assert {k:profile[k] for k in ('header_bytes','prefix_bytes','trailer_bytes','max_payload_bytes','max_source_bytes','max_records')}==dict(header_bytes=H,prefix_bytes=P,trailer_bytes=T,max_payload_bytes=PAYLOAD,max_source_bytes=SOURCE,max_records=COUNT)
    for name,total in [('header_fields',H),('prefix_fields',P)]:
        offset=0
        for entry in profile[name]:assert entry['offset']==offset;offset+=entry['bytes']
        assert offset==total
    assert set(map(int,profile['critical_kinds']))==set(range(1,10)) and not profile['authenticates'] and profile['status']=='proposed'
    payload=b''.join(canonical(v)+b'\n' for v in requests)
    result=subprocess.run([str(a.probe)],input=payload,capture_output=True,cwd=root,timeout=100)
    assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
    responses=[json.loads(row) for row in result.stdout.splitlines()];assert len(responses)==len(requests)
    observations=[]
    for name,request,expect,response in zip(names,requests,expectations,responses):
        assert expect(response),(name,response)
        if request['op']=='scan' and 'error' not in response:
            assert not response['authorizes_effects'] and int(response['largest_read'])<=PAYLOAD
        observations.append(dict(name=name,passed=True,input_sha256='sha256:'+sha(canonical(request)).hex(),output_sha256='sha256:'+sha(canonical(response)).hex()))
    report=dict(passed=True,scope='private-native-binary-framing-only',cases=len(observations),observations=observations,file_io=False,physical_durability_qualified=False,production_writer_admitted=False,
                input_sha256='sha256:'+sha(payload).hex(),output_sha256='sha256:'+sha(result.stdout).hex())
    if a.evidence:a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS proposed journal codec:',len(observations),'independent binary/boundary/corruption/stream cases; no writer admission')

if __name__=='__main__':main()
