"""Independent directory graph expectations through guarded supplied readers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from ntfs_directory_fixture import DirectoryVolume, ref, sha, I30, resident, nonresident, index_entry, index_root

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
    assert d['leaf_depth']==str(v.expected_leaf_depth)
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
    yield case('empty-root-minimum-quotas',DirectoryVolume(kind='empty'),controls={'directory':dict(limits=dict(entries='1',blocks='1',bitmap_bytes='1'))})
    v=DirectoryVolume(kind='preallocated');v.data_blocks=0;v.allocation_bytes=0;v.allocation_runs=[]
    v.replace_attribute(0xa0,lambda _:nonresident(runs=[],allocated=0,data=0,initialized=0,name=I30,kind=0xa0,instance=13,high=(1<<64)-1))
    v.replace_bitmap(b'')
    yield case('empty-nonresident-allocation-pair',v)
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
    for kind in ('leaf','deep'):
        yield case('old-file-header-'+kind,DirectoryVolume(kind=kind,minor=0,usa=42,list_form='nonresident',bitmap_form='nonresident'))
    v=DirectoryVolume(bitmap_form='nonresident');v.replace_bitmap(b'\x03'+bytes(65535))
    yield case('exact-bitmap-byte-cap',v)
    v=DirectoryVolume(kind='single',index=512)
    v.data_blocks=128;v.allocation_bytes=65536;v.allocation_runs=[(16,1000)]
    v.replace_attribute(0xa0,lambda _:nonresident(runs=v.allocation_runs,allocated=65536,data=65536,initialized=65536,
                                                name=I30,kind=0xa0,instance=13,high=15))
    v.replace_bitmap(bytes([255])*16)
    v.blocks={};v.block_reads={};v.block_recipes={}
    for ordinal in range(128):
        rows=[index_entry(end=True,child=v.vbn(ordinal+1))] if ordinal<127 else [index_entry(end=True)]
        v.block_recipes[ordinal]=(rows,ordinal<127);v.replace_block(ordinal,rows,children=ordinal<127)
        v.block_reads[ordinal]=[(v.offset+1000*v.cluster+ordinal*v.index,v.index)]
    v.initial_reads=v.metadata_reads+[span for spans in v.block_reads.values() for span in spans]
    v.expected_leaf_depth=128
    v.expected_rows=[(None,row) for row in v.root_rows]+[(v.vbn(i),row) for i,(rows,_) in v.block_recipes.items() for row in rows]
    yield case('exact-128-node-chain',v,controls={'directory':dict(limits=dict(blocks='128',entries='129')),'limits':dict(read_requests='512')})
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
    # Single-defect cases retain independent expected stopping prefixes; these
    # recipes do not consult native observations to choose their expected result.
    v=DirectoryVolume(bitmap_form='nonresident');v.replace_bitmap(b'\x03'+bytes(65535))
    yield case('bitmap-one-byte-short',v,diagnostic='ntfs_directory_bitmap_budget',controls={'directory':dict(limits=dict(bitmap_bytes='65535'))},reads=len(v.metadata_reads))
    for value,label,code in [(b'', 'short', 'ntfs_directory_bitmap_capacity'),(b'\x01','missing-child-bit','ntfs_directory_child_unallocated'),(b'\x83','past-allocation','ntfs_directory_bitmap_range')]:
        v=DirectoryVolume();v.replace_bitmap(value)
        reads=len(v.metadata_reads)+(len(v.block_reads[0]) if label=='missing-child-bit' else 0)
        yield case('bitmap-'+label,v,diagnostic=code,reads=reads)
    v=DirectoryVolume(bitmap_form='nonresident')
    def uninitialized(a):struct.pack_into('<Q',a,56,0);return a
    v.replace_attribute(0xb0,uninitialized)
    yield case('bitmap-not-initialized',v,diagnostic='ntfs_directory_bitmap_sizes',reads=len(v.metadata_reads))
    for kind,label in [(0x90,'root'),(0xa0,'allocation'),(0xb0,'bitmap')]:
        v=DirectoryVolume()
        def wrong_name(a):
            at=struct.unpack_from('<H',a,10)[0];a[at:at+8]='$BAD'.encode('utf-16le');return a
        v.replace_attribute(kind,wrong_name)
        code='ntfs_directory_root_missing' if kind==0x90 else 'ntfs_directory_stream_pair'
        yield case('exact-name-required-'+label,v,diagnostic=code,reads=len(v.metadata_reads))
    for at,value,label in [(0,0x80,'type'),(4,2,'collation'),(8,8192,'block-size'),(16,0xffffffff,'first'),(20,0xffffffff,'used')]:
        v=DirectoryVolume();raw=bytearray(v.root_value);struct.pack_into('<I',raw,at,value);v.replace_root(value=raw)
        yield case('root-header-'+label,v,diagnostic='ntfs_directory_root_header',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='leaf');v.replace_root(rows=v.root_rows[:-1],children=False)
    yield case('root-terminal-missing',v,diagnostic='ntfs_directory_entry',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single');v.replace_root(rows=[index_entry(end=True,child=(1<<63)-1)])
    yield case('child-offset-overflow',v,diagnostic='ntfs_directory_child_bounds',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single',cluster=512,index=4096);v.replace_root(rows=[index_entry(end=True,child=1)])
    yield case('child-not-block-aligned',v,diagnostic='ntfs_directory_child_bounds',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single');v.replace_root(rows=[index_entry(end=True,child=1<<63)])
    yield case('negative-child',v,diagnostic='ntfs_directory_entry',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single');v.replace_block(0,[index_entry(end=True,child=0)],children=True)
    yield case('child-cycle',v,diagnostic='ntfs_directory_child_repeated',reads=len(v.initial_reads))
    v=DirectoryVolume();v.replace_root(rows=[v.root_rows[0],index_entry(end=True,child=0)])
    yield case('shared-child',v,diagnostic='ntfs_directory_child_repeated',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single');v.replace_attribute(0xa0,uninitialized)
    yield case('child-outside-initialized-data',v,diagnostic='ntfs_directory_child_bounds',reads=len(v.metadata_reads))
    for at,raw,label in [(0,b'BAAD','signature'),(16,struct.pack('<Q',8),'vbn'),(4,struct.pack('<H',39),'array'),(510,b'\0\0','torn'),(24,struct.pack('<I',0xffffffff),'first')]:
        v=DirectoryVolume(kind='single');v.mutate_block(0,at,raw)
        yield case('block-'+label,v,diagnostic='ntfs_directory_block_header',reads=len(v.initial_reads))
    v=DirectoryVolume(kind='single');v.replace_attribute(0xa0,lambda _:resident(bytes(8),name=I30,kind=0xa0,instance=13))
    yield case('resident-allocation-unsupported',v,diagnostic='ntfs_directory_allocation_sizes',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single')
    def odd_data(a):struct.pack_into('<Q',a,48,4095);struct.pack_into('<Q',a,56,4095);return a
    v.replace_attribute(0xa0,odd_data)
    yield case('allocation-size-not-block-aligned',v,diagnostic='ntfs_directory_allocation_sizes',reads=len(v.metadata_reads))
    for lcn,label,code in [(0,'boot','ntfs_metadata_physical_alias'),(8,'mft','ntfs_directory_physical_alias'),(5000,'mirror','ntfs_metadata_physical_alias')]:
        v=DirectoryVolume(kind='single')
        v.replace_attribute(0xa0,lambda _,lcn=lcn:nonresident(runs=[(1,lcn)],allocated=4096,data=4096,initialized=4096,name=I30,kind=0xa0,instance=13,high=0))
        yield case('allocation-alias-'+label,v,diagnostic=code,reads=len(v.metadata_reads))
    v=DirectoryVolume(bitmap_form='nonresident')
    v.replace_attribute(0xb0,lambda _:nonresident(runs=[(1,1000)],allocated=4096,data=1,initialized=1,name=I30,kind=0xb0,instance=17,high=0))
    yield case('bitmap-aliases-allocation',v,diagnostic='ntfs_directory_physical_alias',reads=len(v.metadata_reads))
    v=DirectoryVolume(list_form='nonresident')
    v.replace_attribute(0xa0,lambda _:nonresident(runs=[(2,1200)],allocated=8192,data=8192,initialized=8192,name=I30,kind=0xa0,instance=13,high=1))
    yield case('allocation-aliases-directory-list',v,diagnostic='ntfs_directory_physical_alias',reads=len(v.metadata_reads))
    for at,value,label in [(16,struct.pack('<H',0),'zero-sequence'),(22,struct.pack('<H',1),'not-directory'),(32,struct.pack('<Q',ref(8,3)),'unexpected-owner'),(44,struct.pack('<I',6),'wrong-number')]:
        v=DirectoryVolume();v.mutate_record(v.number,at,value)
        yield case('directory-record-'+label,v,diagnostic='ntfs_directory_record',reads=len(v.metadata_reads))
    for at,value,label in [(16,struct.pack('<H',7),'sequence'),(32,struct.pack('<Q',ref(5,4)),'owner'),(510,b'\0\0','torn')]:
        v=DirectoryVolume(list_form='resident');v.mutate_record(12,at,value)
        yield case('directory-extension-'+label,v,diagnostic='ntfs_directory_extension_record',reads=len(v.metadata_reads))
    v=DirectoryVolume(list_form='resident');v.mutate_record(12,22,struct.pack('<H',3))
    yield case('extension-directory-bit-is-not-kind',v)
    v=DirectoryVolume()
    # Duplicate resident roots remain ambiguous; no first-match shortcut.
    v.base_attributes.append(v.root_attribute);v.render_records()
    yield case('ambiguous-root-instance',v,diagnostic='ntfs_directory_join_instance_ambiguous',reads=len(v.metadata_reads))
    for code in (0,128,240,3):
        v=DirectoryVolume();row=v.input['regions'][0];raw=bytearray.fromhex(row['hex']);raw[68]=code;row['hex']=raw.hex()
        yield case('unsupported-boot-index-'+str(code),v,diagnostic='ntfs_directory_index_size',reads=len(v.bootstrap_reads))
    for kind in (0x90,0xa0,0xb0):
        v=DirectoryVolume()
        def feature(a):struct.pack_into('<H',a,12,0x4000);return a
        v.replace_attribute(kind,feature)
        yield case('unsupported-stream-feature-'+str(kind),v,diagnostic='ntfs_directory_join_feature_unsupported',reads=len(v.metadata_reads))
    v=DirectoryVolume(kind='single');v.replace_block(0,[v.block_recipes[0][0][0]],children=False)
    yield case('block-terminal-missing',v,diagnostic='ntfs_directory_entry',reads=len(v.initial_reads))
    v=DirectoryVolume(kind='single');rows=v.block_recipes[0][0]
    raw=bytearray(rows[0][0]);struct.pack_into('<Q',raw,16,ref(5,4))
    v.replace_block(0,[(bytes(raw),rows[0][1]),rows[1]])
    yield case('block-parent-reference',v,diagnostic='ntfs_directory_parent_reference',reads=len(v.initial_reads))
    for at,raw,label in [(6,struct.pack('<H',0),'array-count'),(36,b'\x02','flags')]:
        v=DirectoryVolume(kind='single');v.mutate_block(0,at,raw)
        yield case('block-'+label,v,diagnostic='ntfs_directory_block_header',reads=len(v.initial_reads))

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
