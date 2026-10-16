"""Independent supplied-byte content, allocation continuation and page oracles."""
import argparse,copy,hashlib,json,struct,subprocess,unittest
from pathlib import Path
from test_fat_traversal import Tree
from test_fat_directory import short
from test_fat import boot,MASKS
from test_fat_walk import pack
PROBE=None;RECORDS=[]

def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def fixture(bits=16,clusters=12000,unit=512,nodes=None,size=None,copy_index=0,per_cluster=1):
    raw,g=boot(clusters,unit,per_cluster=per_cluster);nodes=list(nodes if nodes is not None else [10,12,11]);bits=g['bits'];cluster_bytes=unit*per_cluster
    record=short(name=b'CONTENT BIN',cluster=nodes[0] if nodes else 0,size=(len(nodes)*cluster_bytes-7 if size is None else size))
    first=g['first']*unit;offset=12345;root=first if bits==32 else (g['reserved']+2*g['fat_sectors'])*unit
    if bits==32:struct.pack_into('<I',raw,44,2)
    mapping={0:MASKS[bits]&~255|0xf8,1:MASKS[bits]}
    for a,b in zip(nodes,nodes[1:]+[MASKS[bits]]):mapping[a]=b
    if bits==32 and 2 not in mapping:mapping[2]=MASKS[bits]
    table=pack(bits,mapping)
    request=dict(source_bytes=str(offset+g['total']*unit),offset=str(offset),length=str(g['total']*unit),copy=str(copy_index),record_offset=str(offset+root),record=bytes(record).hex(),
        regions=[dict(offset=str(offset),hex=bytes(raw).hex()),dict(offset=str(offset+root),hex=bytes(record).hex()),
                 *[dict(offset=str(offset+(g['reserved']+n*g['fat_sectors'])*unit),hex=table.hex()) for n in (0,1)]],
        patterns=[dict(offset=str(offset+first),bytes=str(g['clusters']*cluster_bytes),salt='91')],
        oracle=dict(data_source_offset=offset+first,cluster_bytes=cluster_bytes,nodes=nodes))
    size_value=int.from_bytes(record[28:32],'little');original=bytes((((cluster-2)*cluster_bytes+i)*37+(((cluster-2)*cluster_bytes+i)>>8)*11+91)%256 for cluster in nodes for i in range(cluster_bytes))[:size_value]
    return request,original,g,nodes

def run(request,expected=None,complete=True):
    r=subprocess.run([str(PROBE)],input=json.dumps(request,separators=(',',':')).encode(),capture_output=True,timeout=120)
    assert r.returncode==0 and not r.stderr,r.stderr.decode(errors='replace')
    rows=[json.loads(line) for line in r.stdout.splitlines()];assert rows[-1]['kind']=='summary'
    pages=[x['page'] for x in rows[:-1]];assert pages and int(rows[-1]['pages'])==len(pages) and int(rows[-1]['refused'])==21
    previous=None;data=bytearray();cells=[];default=dict(bytes=65536,reads=256,read_bytes=196608,cells=256,output_bytes=1048576);default.update({k:int(v) for k,v in request.get('budget',{}).items()})
    for n,p in enumerate(pages,1):
        assert p['sequence']==str(n) and p['previous_page_digest']==previous
        body=dict(p);previous=body.pop('page_digest');assert sha(b'disked:fat-content-stream-page:1\n'+json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==previous
        assert len(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())<=default['output_bytes']
        assert p['selection']==dict(source_id='fixture-source',capture_id='fixture-capture',capture_epoch='17',source_bytes=request['source_bytes'],volume_offset=request['offset'],volume_bytes=request['length'],fat_copy=request['copy'],record_source_offset=request['record_offset'],raw_record=request['record'])
        assert p['file_offset']==str(len(data));part=bytes.fromhex(p['data']);assert sha(part)==p['data_sha256'] and len(part)==int(p['returned_bytes'])<=default['bytes']
        assert int(p['read_count'])<=default['reads'] and int(p['read_bytes'])<=default['read_bytes'] and len(p['cells'])<=default['cells']
        at=0
        for chunk in p['chunks']:
            count=int(chunk['bytes']);piece=part[at:at+count];assert sha(piece)==chunk['sha256'] and chunk['file_offset']==str(len(data)+at);at+=count
            o=request['oracle'];logical=int(chunk['file_offset']);index=logical//o['cluster_bytes'];within=logical%o['cluster_bytes']
            assert int(chunk['source_offset'])==o['data_source_offset']+(o['nodes'][index]-2)*o['cluster_bytes']+within
            assert count<=o['cluster_bytes']-within
        assert at==len(part);data.extend(part);assert p['next_file_offset']==str(len(data));cells.extend(p['cells'])
        assert not p['authorizes_effects'] and p['directory_membership']=='caller_not_authenticated' and p['atomic_snapshot']=='not_established'
    assert len({c['cluster'] for c in cells})==len(cells)
    assert [int(c['ordinal']) for c in cells]==list(range(len(cells)))
    if complete:
        assert pages[-1]['status']=='complete' and pages[-1]['diagnostic'] is None and bytes(data)==expected
        assert rows[-1]['terminal']['status']=='complete'
    else:assert pages[-1]['status']=='partial' and pages[-1]['diagnostic'] is not None
    RECORDS.append(dict(pages=len(pages),bytes=len(data),sha256=sha(data),cells=len(cells),status=pages[-1]['status'],diagnostic=pages[-1]['diagnostic'],budget=default,fault=request.get('fault'),bitmap=request.get('bitmap_bytes')))
    return bytes(data),cells,pages

class ContentStreams(unittest.TestCase):
    def test_bytes_page_partition_and_noncontiguous_chains(self):
        for bits,clusters in ((12,2847),(16,12000),(32,65525)):
            request,original,g,nodes=fixture(bits,clusters)
            for budget in ({},dict(bytes=113,reads=4,read_bytes=4096,cells=1),dict(bytes=1024,reads=8,cells=2)):
                v=copy.deepcopy(request);v['budget']={k:str(x) for k,x in budget.items()};data,cells,pages=run(v,original)
                self.assertEqual(nodes,[int(c['cluster']) for c in cells]);self.assertFalse(pages[-1]['excess_allocation'])
    def test_large_file_beyond_resident_chain_cap(self):
        nodes=list(range(3,33003));request,original,_,_=fixture(16,40000,nodes=nodes)
        data,cells,pages=run(request,original);self.assertEqual(33000,len(cells));self.assertGreater(len(pages),128);self.assertGreater(len(data),16000000)
    def test_empty_and_excess_allocation_exclude_slack(self):
        for nodes,size in (([],0),([10,12,11],7),([10],512)):
            v,original,_,_=fixture(nodes=nodes,size=size);data,cells,pages=run(v,original)
            self.assertEqual(len(nodes)>((size+511)//512),pages[-1]['excess_allocation'])
        # The existing directory decoder marks allocated zero-length records
        # contradictory; preserve that refusal rather than infer live content.
        v,_,_,_=fixture(nodes=[10],size=0);_,cells,pages=run(v,complete=False)
        self.assertEqual('fat_content_stream_record',pages[-1]['diagnostic']);self.assertFalse(cells)
    def test_nonzero_copy_and_conflicting_unselected_table(self):
        v,original,g,nodes=fixture(copy_index=1);zero=next(r for r in v['regions'] if int(r['offset'])==12345+g['reserved']*512)
        zero['hex']=pack(16,{n:0 for n in nodes}).hex();run(v,original)
    def test_invalid_terminal_short_chain_and_cycle_keep_unique_prefix(self):
        for terminal in (0,1,0xfff7,10):
            v,_,g,nodes=fixture(size=1536);mapping={10:12,12:11,11:terminal}
            for row in v['regions'][2:]:row['hex']=pack(16,mapping).hex()
            data,cells,pages=run(v,complete=False);self.assertLessEqual(len(data),1536);self.assertEqual(3,len(cells))
        v,_,_,_=fixture(nodes=[10],size=1024);run(v,complete=False)
    def test_metadata_rechecks_and_source_withdrawal(self):
        request,_,_,_=fixture()
        for mode,at in [('reader_throw',1),('short',1),('overlong',1),('record_change',2),('record_change',5),('withdraw',1),('withdraw',8),('applicable_throw',3)]:
            v=copy.deepcopy(request);v['budget']=dict(bytes='113',reads='4',read_bytes='4096',cells='1');v['fault']=dict(mode=mode,at=str(at));run(v,complete=False)
    def test_bitmap_geometry_and_record_failures(self):
        v,_,_,_=fixture();v['bitmap_bytes']='1';run(v,complete=False)
        for field,value in [(11,0x10),(11,0xc0),(0,0xe5)]:
            v,_,_,_=fixture();record=bytearray.fromhex(v['record']);record[field]=value;v['record']=record.hex();v['regions'][1]['hex']=record.hex();run(v,complete=False)
        v,_,_,_=fixture();boot=bytearray.fromhex(v['regions'][0]['hex']);boot[510]=0;v['regions'][0]['hex']=boot.hex();run(v,complete=False)
    def test_declared_sector_recheck_and_time_issues_preserved(self):
        v,original,_,_=fixture(16,12000,unit=4096);run(v,original)
        v['fault']=dict(mode='boot_change',at='2');run(v,complete=False)
        v,original,_,_=fixture();raw=bytearray.fromhex(v['record']);struct.pack_into('<H',raw,22,0xffff);v['record']=raw.hex();v['regions'][1]['hex']=raw.hex();run(v,original)
    def test_multisector_clusters_and_interrupted_cluster_data(self):
        for bits,clusters in ((12,2847),(16,12000),(32,65525)):
            v,original,_,_=fixture(bits,clusters,per_cluster=8)
            v['budget']=dict(bytes='3071',reads='4',read_bytes='4096',cells='1')
            run(v,original)

def main():
    global PROBE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();PROBE=a.probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContentStreams))
    if a.output:a.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECORDS),records=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
