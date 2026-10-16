"""Independent directory graph expectations through guarded supplied readers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from ntfs_directory_fixture import DirectoryVolume, ref, sha

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def good(report,v):
    assert report['schema']=='org.disked.ntfs-directory-observation-prototype/1'
    assert report['complete'] and report['applicable'] and report['reread_equal'],report
    assert report['diagnostic']==''
    assert not any(report[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
    assert report['directory_record']['flags']=='3' and report['directory_record']['attributes_complete']
    assert report['regions']==v.regions(),(report['regions'],v.regions())
    assert report['read_requests']==str(len(v.initial_reads)*2)
    assert report['reread_requests']==str(len(v.initial_reads))
    assert report['read_bytes']==str(sum(n for _,n in v.initial_reads)*2)
    assert report['retained_bytes']==str(sum(n for _,n in v.initial_reads))
    d=report['directory']
    assert d['schema']=='org.disked.ntfs-index-collection/1' and d['reference']==str(v.reference)
    assert d['index_complete'] and d['bitmap_complete'] and d['diagnostic']==''
    assert not any(d[k] for k in ('namespace_verified','collation_verified','target_membership_verified','cluster_allocation_verified'))
    assert d['header_count']==str(len(v.expected_rows))
    assert d['name_count']==str(sum(not row[1]['end_marker'] for _,row in v.expected_rows))
    assert d['queued_blocks']==d['observed_blocks']==str(len(v.blocks))
    assert len(d['entries'])==len(v.expected_rows)
    for (vbn,(raw,wanted)),actual in zip(v.expected_rows,d['entries']):
        assert actual['index_vbn']==(None if vbn is None else str(vbn))
        assert actual['present'] and actual['issues']=='0' and actual['envelope_valid']
        assert actual['end_marker']==wanted['end_marker'] and actual['has_child']==wanted['has_child']
        assert actual['child_vbn']==(wanted['child_vbn'] if wanted['has_child'] else None)
        if not wanted['end_marker']:
            assert actual['reference']==wanted['segment_reference']
            assert actual['parent_reference']==str(v.reference) and actual['parent_matches']
            assert actual['namespace']==str(wanted['filename']['namespace'])
            assert actual['name_hex']==wanted['filename']['name_hex']
            assert actual['key_sha256']==sha(bytes.fromhex(wanted['key_hex']))
    assert d['root']['value_sha256']==sha(v.root_value)
    assert d['root']['child_unit_bytes']==str(v.child_unit)
    assert len(d['blocks'])==len(v.blocks)
    for (ordinal,(raw,logical,_,_)),actual in zip(v.blocks.items(),d['blocks']):
        assert actual['vbn']==str(v.vbn(ordinal)) and actual['ordinal']==str(ordinal)
        assert actual['raw_sha256']==sha(raw) and actual['restored_sha256']==sha(logical)
        assert actual['issues']=='0' and actual['envelope_valid'] and actual['fixups_valid']
    expected_queries=[dict(type='144',present=True),dict(type='160',present=v.with_allocation),dict(type='176',present=v.with_allocation)]
    assert report['directory_stream_queries']==expected_queries
    if v.with_allocation:
        assert d['bitmap']['sha256']==sha(v.bitmap_value)
        assert d['bitmap']['set_bits']==str(len(v.blocks))
    else:assert d['bitmap'] is None

def cases():
    def case(label,v=None,diagnostic='',refusal='',controls=None,reads=None,check=None):
        v=v or DirectoryVolume();value=copy.deepcopy(v.input);value.update(controls or {})
        return label,v,value,diagnostic,refusal,reads,check
    for kind in ('leaf','empty','single','siblings','deep','preallocated'):
        yield case('kind-'+kind,DirectoryVolume(kind=kind))
    for minor in (0,1):
        for form in ('resident','nonresident'):
            for bitmap in ('resident','nonresident'):
                yield case(f'lists-{minor}-{form}-{bitmap}',DirectoryVolume(kind='deep',minor=minor,list_form=form,bitmap_form=bitmap,fragmented_allocation=True,split_allocation=True))
    for cluster,index,size in [(512,512,512),(512,4096,1024),(4096,512,1024),(8192,4096,1024),(4096,8192,4096),(4096,4096,2048),(512,8192,4096)]:
        split=(2*index+cluster-1)//cluster>=2
        yield case(f'geometry-{cluster}-{index}-{size}',DirectoryVolume(cluster=cluster,index=index,size=size,fragmented_allocation=True,list_form='nonresident',bitmap_form='nonresident',split_allocation=split))
    for offset in (173,(1<<32)+17,(1<<53)+13):
        yield case('absolute-offset-'+str(offset),DirectoryVolume(offset=offset,bitmap_form='nonresident',fragmented_allocation=True))
    for namespace in (0,1,2,3):
        yield case('namespace-'+str(namespace),DirectoryVolume(namespace=namespace,name=b'\x1b\0\0\xd8\xff\xdc'))
    yield case('long-original-name',DirectoryVolume(kind='single',size=4096,name=bytes([27,0,0,216,255,220])*85))
    yield case('mft-volume-directory-closure',DirectoryVolume(mft_closure=True,list_form='nonresident',bitmap_form='nonresident',split_allocation=True,fragmented_allocation=True))
    yield case('reverse-directory-list',DirectoryVolume(list_form='resident',split_allocation=True,reverse_list=True,fragmented_allocation=True))
    for number,sequence in [(5,65535),(17,9)]:
        v=DirectoryVolume(number=number,sequence=sequence);value=copy.deepcopy(v.input);value['directory']={'reference':str(v.reference)}
        yield case(f'explicit-reference-{number}-{sequence}',v,controls={'directory':value['directory']})
    v=DirectoryVolume(kind='deep',bitmap_form='nonresident',list_form='nonresident',fragmented_allocation=True,split_allocation=True)
    count=len(v.initial_reads);total=sum(n for _,n in v.initial_reads)
    yield case('exact-source-quotas',v,controls={'limits':dict(read_requests=str(count*2),read_bytes=str(total*2),retained_bytes=str(total))})
    headers=len(v.expected_rows)
    yield case('exact-directory-quotas',v,controls={'directory':dict(limits=dict(entries=str(headers),blocks=str(len(v.blocks)),bitmap_bytes=str(len(v.bitmap_value))))})
    for n in range(1,count*2+1):
        for mode in ('short','null','oversize','throw'):
            yield case(f'{mode}-callback-{n}',v,diagnostic='ntfs_reader_failure' if mode=='throw' else 'ntfs_read_length',controls={'fault':dict(mode=mode,call=str(n))},reads=n)
        if n>count:
            yield case('changed-reread-'+str(n),v,diagnostic='ntfs_source_changed',controls={'fault':dict(mode='change',call=str(n))},reads=n)
    yield case('immutable-request-and-callback',v,controls={'fault':dict(mode='mutate-controls',call='1')})
    for field,value in [('entries',0),('entries',4097),('blocks',0),('blocks',129),('bitmap_bytes',0),('bitmap_bytes',65537)]:
        yield case('invalid-'+field+'-'+str(value),v,refusal='ntfs_directory_limits',controls={'directory':dict(limits={field:str(value)})},reads=0)
    yield case('reference-without-sequence',v,refusal='ntfs_directory_reference',controls={'directory':dict(reference='5')},reads=0)
    yield case('empty-reader',v,refusal='ntfs_capture_reader',controls={'empty_reader':True},reads=0)
    yield case('wrong-sequence',v,diagnostic='ntfs_directory_record',controls={'directory':dict(reference=str(ref(5,4)))},reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    yield case('reference-outside-mft',v,diagnostic='ntfs_directory_reference_bounds',controls={'directory':dict(reference=str(ref((1<<48)-1,3)))},reads=len(v.bootstrap_reads))
    v=DirectoryVolume(parent=ref(5,4));yield case('stale-parent-reference',v,diagnostic='ntfs_directory_parent_reference',reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    v=DirectoryVolume(namespace=4);yield case('unknown-key-namespace',v,diagnostic='ntfs_directory_entry',reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    v=DirectoryVolume(kind='mixed');yield case('mixed-leaf-depths',v,diagnostic='ntfs_directory_leaf_depth',reads=len(v.initial_reads))
    v=DirectoryVolume(kind='orphan');yield case('unreachable-set-bit',v,diagnostic='ntfs_directory_bitmap_unreachable',reads=len(v.initial_reads))
    for field,value,code in [('read_requests','1','ntfs_read_budget'),('retained_bytes','512','ntfs_retained_budget'),('output_bytes','16384','ntfs_output_budget')]:
        # The output quota needs enough retained variable metadata to exceed16KiB.
        v=DirectoryVolume(mft_closure=True,list_form='nonresident',bitmap_form='nonresident',split_allocation=True)
        yield case('source-budget-'+field,v,diagnostic=code,controls={'limits':{field:value}})
    v=DirectoryVolume(kind='siblings')
    yield case('child-queue-one-short',v,diagnostic='ntfs_directory_block_budget',controls={'directory':dict(limits=dict(blocks='1'))},reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    yield case('entry-before-root-terminal',v,diagnostic='ntfs_directory_entry_budget',controls={'directory':dict(limits=dict(entries='1'))},reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    yield case('entry-before-child-streams',v,diagnostic='ntfs_directory_entry_budget',controls={'directory':dict(limits=dict(entries='2'))},reads=len(v.bootstrap_reads)+len(v.record_regions[v.number]))
    yield case('entry-before-last-terminal',v,diagnostic='ntfs_directory_entry_budget',controls={'directory':dict(limits=dict(entries='5'))},reads=len(v.initial_reads))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    rows=list(cases());receipts=[]
    for at in range(0,len(rows),4):
        batch=rows[at:at+4]
        p=subprocess.run([str(a.probe.resolve())],input=canonical([r[2] for r in batch]),capture_output=True,timeout=90)
        assert p.returncode==0 and not p.stderr,(batch[0][0],p.returncode,p.stderr.decode(errors='replace'))
        results=json.loads(p.stdout);assert len(results)==len(batch)
        for (label,v,value,diagnostic,refusal,reads,check),actual in zip(batch,results):
            try:
                assert actual['source_unchanged'] and actual['refusal']==refusal,actual
                if refusal:
                    assert actual['report'] is None and actual['requests']==[]
                else:
                    report=actual['report'];assert report['diagnostic']==diagnostic,report
                    if not diagnostic:
                        good(report,v);assert actual['requests']==v.requests(),(actual['requests'],v.requests())
                    else:
                        assert not report['complete'] and not report['applicable']
                        if reads is not None:assert actual['requests']==v.requests()[:reads],(actual['requests'],v.requests()[:reads])
                if check:check(actual)
            except AssertionError as error:
                a.output.write_text(json.dumps(dict(failed_case=label,request=value,result=actual),indent=2)+'\n',encoding='utf-8')
                raise AssertionError(label,error) from error
            receipts.append(dict(case=label,input_sha256=sha(canonical(value)),expected_diagnostic=diagnostic,expected_refusal=refusal,expected_read_prefix=reads,result_sha256=sha(canonical(actual)),passed=True))
    a.output.write_text(json.dumps(dict(count=len(receipts),cases=receipts,scope='Private supplied-reader directory-index acquisition/framing; no held native file, complete namespace or original0.1.0 qualification',physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(len(receipts),'guarded source-bound directory cases passed')
if __name__=='__main__':main()
