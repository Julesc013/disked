"""Independent MFT/list source reads, reference closure and captured-value binding."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from ntfs_closure_fixture import ClosureVolume
from test_ntfs_stream import BASE, EXT, entry, nonresident, record, request, split


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(value):return 'sha256:'+hashlib.sha256(value).hexdigest()


def good(report,v):
    assert report['complete'] and report['applicable'] and report['reread_equal'],report
    assert report['diagnostic']=='' and not any(report[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
    assert report['regions']==v.independent_regions(),(report['regions'],v.independent_regions())
    assert report['mft']==dict(mapping_valid=True,allocated_bytes=v.expected['allocated'],data_bytes=v.expected['allocated'],initialized_bytes=v.expected['initialized'],runs=v.expected['mft_runs'])
    closures=report['record_closures'];mft=closures['mft']
    assert mft['schema']=='org.disked.ntfs-record-closure-observation/1'
    assert mft['join_current'] and mft['join']['complete'] and mft['join']['required_records']==[]
    assert mft['base_reference']==str(v.base_reference) and len(mft['extensions'])==v.expected['mft_extensions']
    assert [row['expected_reference'] for row in mft['extensions']]==[str(v.first_reference)]+([] if v.first_reference==v.second_reference else [str(v.second_reference)])
    assert mft['attribute_list']['value_bytes']==v.expected['mft_list_bytes']
    assert mft['attribute_list']['value_sha256']==sha(v.mft_list_value)
    assert mft['attribute_list']['form']==str(int(v.nonresident_list))
    if v.nonresident_list:assert mft['join']['external_list_bound'] and mft['join']['external_list_bytes']==v.expected['mft_list_bytes']
    if v.volume_list:
        volume=closures['volume'];assert volume['join_current'] and volume['join']['complete']
        assert volume['base_reference']==str(v.volume_reference) and len(volume['extensions'])==1
        assert volume['extensions'][0]['expected_reference']==str(v.info_reference)
        assert volume['attribute_list']['value_sha256']==sha(v.volume_list_value)
        if v.volume_nonresident:assert volume['join']['external_list_bound']
    else:assert 'volume' not in closures
    for closure in closures.values():
        join=closure['join'];assert join['source_id']==report['source_id'] and join['epoch']==report['epoch']
        assert join['volume_offset']==v.input['offset'] and join['volume_bytes']==v.input['length']
        assert not any(join[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
    assert report['volume_information']['major']=='3' and report['volume_information']['minor']==v.input['minor']
    assert report['volume_information']['profile_matches'] and report['mirror_used_payload_equal']


def source_cases():
    def case(name,v,diagnostic='',controls=None,success=True):
        value=copy.deepcopy(v.input);value.update(controls or {})
        return name,v,value,diagnostic,success
    for minor,usa in [(0,42),(0,48),(1,48)]:
        for form in (False,True):
            yield case(f'profile-{minor}-{usa}-{form}',ClosureVolume(minor=minor,usa=usa,nonresident_list=form,volume_nonresident=form))
    for size in (512,2048,4096):yield case('record-size-'+str(size),ClosureVolume(size=size,nonresident_list=True))
    yield case('split-file3-and-list',ClosureVolume(cluster=512,nonresident_list=True,volume_nonresident=True,padding=20))
    yield case('list-larger-than-file-record',ClosureVolume(cluster=512,nonresident_list=True,padding=1600),controls={'limits':{'attributes':'4096'}})
    yield case('two-extents-one-record',ClosureVolume(same_extension=True,nonresident_list=True))
    yield case('forward-list-order',ClosureVolume(reverse=False))
    yield case('volume-no-list',ClosureVolume(volume_list=False))
    for offset in (173,(1<<32)+17,(1<<53)+13):yield case('absolute-offset-'+str(offset),ClosureVolume(offset=offset,nonresident_list=True))
    v=ClosureVolume(nonresident_list=True,volume_nonresident=True)
    count=len(v.initial_reads);total=sum(size for _,size in v.initial_reads)
    yield case('exact-read-and-retention-quotas',v,controls={'limits':{'read_requests':str(count*2),'read_bytes':str(total*2),'retained_bytes':str(total)}})
    yield case('read-quota-one-short',v,'ntfs_read_budget',{'limits':{'read_requests':str(count*2-1)}},False)
    yield case('read-byte-quota-one-short',v,'ntfs_read_budget',{'limits':{'read_bytes':str(total*2-1)}},False)
    yield case('output-quota',v,'ntfs_output_budget',{'limits':{'output_bytes':'16384'}},False)
    for n in range(1,count*2+1):
        for mode in ('short','null','oversize','throw'):
            yield case(f'{mode}-read-{n}',v,'ntfs_reader_failure' if mode=='throw' else 'ntfs_read_length',{'fault':dict(mode=mode,call=str(n))},False)
        if n>count:yield case('source-change-reread-'+str(n),v,'ntfs_source_changed',{'fault':dict(mode='change',call=str(n))},False)
    yield case('controls-owned-before-reads',v,controls={'fault':dict(mode='mutate-controls',call='1')})
    v=ClosureVolume(nonresident_list=True,padding=1600,cluster=512)
    yield case('list-byte-quota-before-value-read',v,'ntfs_attribute_list_budget',{'limits':{'retained_bytes':'10000','attributes':'4096'}},False)
    v=ClosureVolume(padding=8);yield case('derived-list-item-quota',v,'ntfs_mft_join_list_budget',{'limits':{'attributes':'6'}},False)
    for label,number,at,value,code in [
        ('stale-extension','first_extension',16,8,'ntfs_mft_extension_record'),
        ('wrong-extension-owner','first_extension',38,0,'ntfs_mft_extension_record'),
        ('bad-extension-map','first_extension',120,0x99,'ntfs_mft_extension_mapping'),
        ('stale-volume-extension','volume_extension',16,7,'ntfs_volume_extension_record'),
        ('torn-extension','first_extension',510,0,'ntfs_mft_extension_record')]:
        v=ClosureVolume(nonresident_list=True,volume_nonresident=True);v.mutate_record(getattr(v,number),at,value)
        yield case(label,v,code,success=False)
    for target,label,code in [(70,'cyclic-unreachable','ntfs_mft_unresolved_coverage'),(80,'outside-initialized-mft','ntfs_mft_reference_bounds')]:
        v=ClosureVolume();base=v.bytes(*v.record_regions[0][0]);attr=struct.unpack_from('<H',base,20)[0]+len(v.data)
        value_at=attr+struct.unpack_from('<H',base,attr+20)[0];reference=target|(9<<48)
        # Reversed entry1 is the first extension. Modify primary and mirror
        # together without altering the protected tails or the claimed list size.
        for i,b in enumerate(struct.pack('<Q',reference)):v.mutate_record(0,value_at+32+16+i,b)
        primary=v.bytes(*v.record_regions[0][0])
        for row in v.input['regions']:
            if int(row['offset'])==v.offset+5000*v.cluster:row['hex']=primary.hex()
        yield case(label,v,code,success=False)
    for mode in ('uninitialized','boot-alias','mft-alias'):
        v=ClosureVolume(nonresident_list=True);base=v.bytes(*v.record_regions[0][0]);attr=struct.unpack_from('<H',base,20)[0]+len(v.data)
        if mode=='uninitialized':at=attr+56;raw=struct.pack('<Q',len(v.mft_list_value)-1);code='ntfs_attribute_list_mapping'
        else:
            mapping_at=attr+struct.unpack_from('<H',base,attr+32)[0];at=mapping_at+2;raw=struct.pack('<h',0 if mode=='boot-alias' else 8);code='ntfs_metadata_physical_alias' if mode=='boot-alias' else 'ntfs_list_physical_alias'
        for i,b in enumerate(raw):v.mutate_record(0,at+i,b)
        primary=v.bytes(*v.record_regions[0][0])
        for row in v.input['regions']:
            if int(row['offset'])==v.offset+5000*v.cluster:row['hex']=primary.hex()
        yield case('list-'+mode,v,code,success=False)


def captured_list_cases():
    original,wanted=split();value=bytes(entry()+entry(EXT,13,2))
    root=record([nonresident(),nonresident(kind=0x20,instance=1,runs=((1,300),),high=0,allocated=4096,data=len(value),initialized=len(value))])
    original['records'][0]['hex']=root.hex()
    original['list_capture']=dict(base=str(BASE),instance='1',base_sha256=sha(root),hex=value.hex())
    def case(name,request,diagnostic='',stream=None,refusal=''):
        return name,copy.deepcopy(request),diagnostic,copy.deepcopy(stream),refusal
    yield case('bound-nonresident-value',original,stream=wanted)
    for field,wrong in [('base',str(BASE+1)),('instance','2'),('base_sha256','sha256:'+'0'*64)]:
        v=copy.deepcopy(original);v['list_capture'][field]=wrong;yield case('wrong-capture-'+field,v,'ntfs_join_list_binding')
    for field,wrong in [('source_id','other'),('epoch','18'),('offset','4097'),('length','8192')]:
        v=copy.deepcopy(original);v['list_capture']['context']=dict(v['context'],**{field:wrong});yield case('wrong-list-context-'+field,v,'ntfs_join_list_binding')
    for data in (b'',value[:-1],value+b'\0'):
        v=copy.deepcopy(original);v['list_capture']['hex']=data.hex();yield case('wrong-value-length-'+str(len(data)),v,'ntfs_join_list_sizes')
    v=copy.deepcopy(original);v['limits']={'list_bytes':'63'};yield case('list-byte-budget',v,'ntfs_join_list_byte_budget')
    for limit in (0,262145):
        v=copy.deepcopy(original);v['limits']={'list_bytes':str(limit)};yield case('invalid-list-quota-'+str(limit),v,refusal='ntfs_join_limits')
    v=copy.deepcopy(original);v.pop('list_capture');yield case('no-external-value-stays-unsupported',v,'ntfs_join_nonresident_list_unsupported')
    v,_=split();v['list_capture']=copy.deepcopy(original['list_capture']);yield case('resident-list-cannot-be-replaced',v,'ntfs_join_unexpected_list_capture')
    v=request([dict(number='0',hex=record([nonresident()]).hex())]);v['list_capture']=copy.deepcopy(original['list_capture']);yield case('absent-list-cannot-be-injected',v,'ntfs_join_unexpected_list_capture')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--join',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();receipts=[]
    cases=list(source_cases())
    for at in range(0,len(cases),4):
        rows=cases[at:at+4];p=subprocess.run([str(a.capture.resolve())],input=canonical([r[2] for r in rows]),capture_output=True,timeout=30)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stderr.decode(errors='replace'))
        outputs=json.loads(p.stdout);assert len(outputs)==len(rows)
        for (name,v,request_value,diagnostic,success),result in zip(rows,outputs):
            assert result['source_unchanged'] and result['refusal']=='',(name,result)
            report=result['report'];assert report['diagnostic']==diagnostic,(name,diagnostic,report)
            assert report['applicable']==success,(name,report)
            actual=[(int(r['offset']),int(r['bytes'])) for r in result['requests']]
            wanted=v.initial_reads*2
            assert actual==wanted[:len(actual)],(name,actual,wanted)
            assert int(report['read_requests'])==len(actual) and int(report['read_bytes'])==sum(n for _,n in actual)
            assert int(report['retained_bytes'])==sum(int(r['bytes']) for r in report['regions'])
            assert len(canonical(report))<=int(request_value.get('limits',{}).get('output_bytes','1048576'))
            assert not any(report[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
            if success:good(report,v);assert actual==wanted and int(report['reread_requests'])==len(v.initial_reads)
            else:assert not report['complete'] and not report['reread_equal']
            receipts.append(dict(case=name,request_sha256=sha(canonical(request_value)),result_sha256=sha(canonical(result)),passed=True))
    binding=list(captured_list_cases())
    for at in range(0,len(binding),4):
        rows=binding[at:at+4];p=subprocess.run([str(a.join.resolve())],input=canonical([r[1] for r in rows]),capture_output=True,timeout=30)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stderr.decode(errors='replace'))
        outputs=json.loads(p.stdout)
        for (name,request_value,diagnostic,wanted,refusal),result in zip(rows,outputs):
            assert result['source_unchanged'] and result['refusal']==refusal,(name,result)
            assert result['usable']==(wanted is not None),(name,result)
            if not refusal:
                assert result['observation']['diagnostic']==diagnostic,(name,diagnostic,result)
                if wanted is not None:assert result['stream']==wanted and result['observation']['external_list_bound']
                else:assert 'stream' not in result and result['required_records']==[]
            receipts.append(dict(case=name,request_sha256=sha(canonical(request_value)),result_sha256=sha(canonical(result)),passed=True))
    a.output.write_text(json.dumps(dict(count=len(receipts),cases=receipts,source_cases=len(cases),binding_cases=len(binding),scope='Supplied source-bound NTFS closure and captured-list binding only; native file/worker/frontend evidence is separate',physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(len(receipts),'source/binding closure cases passed')
if __name__=='__main__':main()
