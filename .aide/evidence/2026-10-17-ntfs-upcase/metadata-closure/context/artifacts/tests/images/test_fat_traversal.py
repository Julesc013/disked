"""Independent sparse-byte tree, metadata, pagination and scope oracles."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'property'))
from test_fat import boot, MASKS
from test_fat_walk import pack
from test_fat_directory import short, slots, escaped

PROBE=None
RECEIPTS=[]


class Tree:
    def __init__(self,bits=12,offset=0,unit=512):
        self.bits=bits;self.offset=offset;self.unit=unit;self.fat_copy=0
        self.boot,self.g=boot({12:2847,16:12000,32:65525}[bits],unit)
        if bits!=32:
            difference=1024*32//unit-self.g['root_entries']*32//unit
            self.g['first']+=difference;self.g['total']+=difference;self.g['root_entries']=1024
            struct.pack_into('<H',self.boot,17,1024)
            if int.from_bytes(self.boot[19:21],'little'):struct.pack_into('<H',self.boot,19,self.g['total'])
            else:struct.pack_into('<I',self.boot,32,self.g['total'])
        self.length=self.g['total']*unit
        self.data=self.g['first']*unit
        self.table=self.g['fat_sectors']*unit
        self.regions={0:bytes(self.boot)}
        self.mapping={0:MASKS[bits]&~255|0xf8,1:MASKS[bits]}
        self.root=self.data if bits==32 else (self.g['reserved']+2*self.g['fat_sectors'])*unit
        self.expected={}
        if bits==32:self.chain([2])

    def cluster(self,n):return self.data+(n-2)*self.unit

    def chain(self,nodes,terminal=None):
        for a,b in zip(nodes,nodes[1:]+[MASKS[self.bits] if terminal is None else terminal]):self.mapping[a]=b

    def directory(self,records,parent='root',clusters=None,end=True):
        data=b''.join(bytes(r) for r in records)+(bytes(32) if end else b'')
        if clusters is None:
            offsets=[self.root]
            capacity=self.unit if self.bits==32 else 1024*32
        else:
            offsets=[self.cluster(n) for n in clusters];capacity=len(clusters)*self.unit
        assert len(data)<=capacity
        if clusters is None:
            self.regions[offsets[0]]=data
        else:
            for i,at in enumerate(offsets):self.regions[at]=data[i*self.unit:(i+1)*self.unit]
        for i,raw in enumerate(records):
            if raw[0] and raw[11]!=0x0f:
                offset=(offsets[i*32//self.unit]+i*32%self.unit if clusters is not None else offsets[0]+i*32)+self.offset
                self.expected[offset]=(parent,bytes(raw))

    def request(self,**extra):
        regions=dict(self.regions)
        for n in range(2):regions[(self.g['reserved']+n*self.g['fat_sectors'])*self.unit]=pack(self.bits,self.mapping)
        return dict(source_bytes=str(self.offset+self.length),offset=str(self.offset),length=str(self.length),copy=str(self.fat_copy),
            regions=[dict(offset=str(self.offset+p),hex=bytes(b).hex()) for p,b in sorted(regions.items())],**extra)


def files(count):return [short(name=f'{n:08d}'.encode()+b'BIN') for n in range(count)]


def run(tree,budget=None,fault=None,resources=None):
    extra={}
    if budget:extra['budget']={k:str(v) for k,v in budget.items()}
    if fault:extra['fault']=dict(mode=fault[0],at=str(fault[1]))
    if resources:extra['resources']={k:str(v) for k,v in resources.items()}
    request=tree.request(**extra);data=json.dumps(request,separators=(',',':')).encode()+b'\n'
    result=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=150)
    assert result.returncode==0 and not result.stderr,result.stderr.decode(errors='replace')
    output=json.loads(result.stdout);pages=output['pages'];assert pages
    events=[];previous=None
    limits=dict(records=256,events=256,reads=512,read_bytes=65536,output_bytes=65536)
    limits.update(budget or {})
    for n,page in enumerate(pages,1):
        assert page['sequence']==str(n) and page['previous_page_digest']==previous
        body=dict(page);digest=body.pop('page_digest')
        encoded=json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        assert digest=='sha256:'+hashlib.sha256(b'disked:fat-traversal-page:1\n'+encoded).hexdigest()
        previous=digest
        assert len(json.dumps(page,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())<=limits['output_bytes']
        assert len(page['events'])<=limits['events']
        for key in ('records','reads','read_bytes'):assert int(page['page_work'][key])<=limits[key]
        assert page['binding']==dict(source_id='fixture-source',capture_id='fixture-capture',capture_epoch='17',
            source_bytes=request['source_bytes'],volume_offset=request['offset'],volume_bytes=request['length'],fat_copy=request['copy'])
        assert page['atomic_snapshot']=='not_established' and page['filesystem_health']=='not_established'
        events.extend(page['events'])
    assert pages[-1]['status'] in ('complete','partial')
    assert int(output['binding_refusals']) in (7,14)
    record_events=[e for e in events if e['type']=='record']
    assert len({e['key'] for e in record_events})==len(record_events)
    assert all(e['key']=='entry:'+e['source_offset'] for e in record_events)
    RECEIPTS.append(dict(bits=tree.bits,pages=len(pages),events=len(events),entries=len(record_events),
        status=pages[-1]['status'],diagnostic=pages[-1]['diagnostic'],binding_refusals=output['binding_refusals'],
        budget=limits,fault=fault,resources=resources,
        input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    return events,pages,output


def check_metadata(tree,events,complete=True):
    observed={int(e['source_offset']):e for e in events if e['type']=='record'}
    if complete:assert set(observed)==set(tree.expected)
    for offset,e in observed.items():
        parent,raw=tree.expected[offset]
        assert e['directory']==parent and e['raw']==raw.hex()
        # Deleted records expose no live metadata; their original bytes remain.
        if raw[0]==0xe5:
            assert e['kind']=='2' and e['attributes']=='0' and e['case_flags']=='0' and e['file_bytes']=='0'
            continue
        assert e['attributes']==str(raw[11]) and e['case_flags']==str(raw[12])
        assert e['creation_fraction']==str(raw[13])
        for name,position in (('creation_time',14),('creation_date',16),('access_date',18),('write_time',22),('write_date',24)):
            assert int(e[name])==int.from_bytes(raw[position:position+2],'little')
        original=(int.from_bytes(raw[20:22],'little')<<16)|int.from_bytes(raw[26:28],'little')
        assert int(e['raw_cluster'])==original
        assert int(e['cluster'])==(original&0x0fffffff if tree.bits==32 else original&0xffff)
        assert int(e['file_bytes'])==int.from_bytes(raw[28:32],'little')


class TraversalTests(unittest.TestCase):
    def test_invalid_starts_geometry_copy_and_short_allocation_cells(self):
        for bits in (12,16,32):
            for first,ending in ((0,'empty'),(1,'invalid_start'),(({12:2847,16:12000,32:65525}[bits])+2,'invalid_start')):
                tree=Tree(bits);tree.directory([short(name=b'DIR        ',attributes=16,cluster=first)])
                events,pages,_=run(tree)
                self.assertEqual('partial',pages[-1]['status'])
                self.assertIn(ending,[e['chain'] for e in events if e['type']=='directory_end'])
            tree=Tree(bits);damaged=bytearray(tree.boot);damaged[510]=0;tree.regions[0]=damaged
            events,pages,_=run(tree)
            self.assertEqual('fat_traversal_layout_unusable',pages[-1]['diagnostic'])
            self.assertTrue(any(e['type']=='volume' and not e['usable_layout'] and e['boot_raw']==damaged.hex() for e in events))
            tree=Tree(bits);tree.fat_copy=2
            events,pages,_=run(tree)
            self.assertEqual('fat_traversal_copy_range',pages[-1]['diagnostic'])
            self.assertFalse(next(e for e in events if e['type']=='volume')['active_copy_selected'])
            self.assertFalse(any(e['type']=='allocation' for e in events))
            tree=Tree(bits);tree.chain([10]);tree.directory([short(name=b'DIR        ',attributes=16,cluster=10)])
            tree.directory(files(1),parent='entry:'+str(tree.root),clusters=[10])
            # The fixed root needs two reads, FAT32 root needs three. The next
            # read is the child's selected allocation cell, not its payload.
            child_cell=3 if bits!=32 else 4
            events,pages,_=run(tree,fault=('short',child_cell))
            self.assertEqual('partial',pages[-1]['status'])
            self.assertTrue(any(e['type']=='allocation' and not e['entry_present'] for e in events))
            check_metadata(tree,events,complete=False)

    def test_interrupted_long_names_keep_original_pending_slots(self):
        for bits in (12,16,32):
            tree=Tree(bits);tree.chain([10,12]);tree.directory([short(name=b'DIR        ',attributes=16,cluster=10)])
            entry=short();name,_=slots([ord('x')]*20,entry)
            tree.directory(files(15)+[name[:32],name[32:],entry],parent='entry:'+str(tree.root),clusters=[10,12])
            # Stop on the next allocation read after the first long-name slot.
            failing_read=5 if bits!=32 else 6
            events,pages,_=run(tree,{'records':1,'events':1},fault=('reader_throw',failing_read))
            self.assertEqual('partial',pages[-1]['status'])
            orphan=next(e for e in events if e['type']=='orphan')
            self.assertEqual('interrupted',orphan['reason'])
            self.assertEqual(name[:32].hex(),orphan['raw_slots'])
            self.assertEqual([str(tree.cluster(10)+15*32)],orphan['source_offsets'])

    def test_contradictory_directory_metadata_is_preserved_without_following(self):
        for bits in (12,16,32):
            for raw in (short(name=b'DIR        ',attributes=0x90,cluster=10),
                        short(name=b'DIR        ',attributes=16,cluster=10,size=1),
                        short(name=b'DIR        ',attributes=16,cluster=0xf000000a if bits==32 else 0x1000a)):
                tree=Tree(bits);tree.directory([raw]);tree.chain([10]);tree.directory(files(2),parent='entry:'+str(tree.root),clusters=[10])
                events,pages,output=run(tree,{'records':1,'events':1})
                self.assertEqual('partial',pages[-1]['status']);check_metadata(tree,events,complete=False)
                self.assertEqual(1,sum(e['type']=='record' for e in events))
                self.assertEqual(1,sum(e['type']=='directory_not_followed' for e in events))
                self.assertFalse(any(tree.offset+tree.cluster(10)<=int(r['offset'])<tree.offset+tree.cluster(10)+tree.unit for r in output['reads']))

    def test_large_trees_and_partition_equivalence(self):
        for bits in (12,16,32):
            tree=Tree(bits,offset=12345)
            root_clusters=list(range(2,35)) if bits==32 else None
            if root_clusters:tree.chain(root_clusters)
            tree.directory(files(500),clusters=root_clusters)
            baseline=None
            for budget in ({},{'records':1,'events':1,'reads':1,'read_bytes':4096,'output_bytes':32768},{'records':17,'events':9,'reads':2}):
                events,pages,_=run(tree,budget)
                self.assertEqual('complete',pages[-1]['status']);check_metadata(tree,events)
                if baseline is not None:self.assertEqual(baseline,events)
                baseline=events
                self.assertEqual(500,sum(e['type']=='record' for e in events))

    def test_directory_chain_beyond_1024_and_record_capacity(self):
        tree=Tree(16)
        chain=list(range(3,1103));tree.chain(chain)
        raw=short(name=b'LONGDIR    ',attributes=16,cluster=3)
        key='entry:'+str(tree.root)
        tree.directory([raw]);tree.directory(files(17600),parent=key,clusters=chain,end=False)
        events,pages,_=run(tree,{'events':512,'records':512,'output_bytes':1048576})
        self.assertEqual('complete',pages[-1]['status']);check_metadata(tree,events)
        self.assertEqual(1100,sum(e['type']=='allocation' for e in events))
        self.assertEqual(17601,sum(e['type']=='record' for e in events))

    def test_names_survive_pages_sectors_and_clusters_losslessly(self):
        for bits in (12,16,32):
            tree=Tree(bits)
            cluster=10
            root_record=short(name=b'NAMES      ',attributes=16,cluster=cluster)
            parent='entry:'+str(tree.root)
            tree.directory([root_record]);tree.chain([10,12,15])
            entry=short(name=b'LONGNAMETXT',case=0x18)
            entry[13]=137;struct.pack_into('<HHH',entry,14,0x61ab,0x5041,0x5042);struct.pack_into('<HH',entry,22,0x7123,0x6043)
            original=([69,0x301,0x1b,0xd800]+[0x0041]*251)
            name,padded=slots(original,entry)
            records=files(15)+[name[i:i+32] for i in range(0,len(name),32)]+[entry]
            tree.directory(records,parent=parent,clusters=[10,12,15])
            baseline=None
            for budget in ({},{'records':1,'events':1,'reads':1,'read_bytes':4096,'output_bytes':32768}):
                events,pages,_=run(tree,budget);check_metadata(tree,events)
                self.assertEqual('complete',pages[-1]['status'])
                if baseline is not None:self.assertEqual(baseline,events)
                baseline=events
                item=next(e for e in events if e['type']=='record' and 'long_name' in e)
                self.assertEqual(name.hex(),item['long_name']['raw_slots'])
                self.assertEqual(list(map(str,padded)),item['long_name']['units'])
                self.assertEqual(escaped(original),item['long_name']['display'])
                self.assertFalse(item['long_name']['unicode_valid'])
                self.assertFalse(any(e['type']=='orphan' for e in events))

    def test_parent_identities_noncontiguous_and_deep_directories(self):
        for bits in (12,16,32):
            tree=Tree(bits);parent='root';root=short(name=b'DIR00000   ',attributes=16,cluster=10)
            tree.directory([root]);parent='entry:'+str(tree.root)
            for n in range(10,50):
                tree.chain([n])
                child=short(name=f'DIR{n:05d}'.encode()+b'   ',attributes=16,cluster=n+1)
                tree.directory([short(name=b'.          ',attributes=16,cluster=n),child],parent=parent,clusters=[n]);parent='entry:'+str(tree.cluster(n)+32)
            tree.chain([50]);tree.directory(files(3),parent=parent,clusters=[50])
            events,pages,_=run(tree,{'records':3,'events':2});check_metadata(tree,events)
            self.assertEqual('complete',pages[-1]['status'])
            self.assertEqual(42,int(pages[-1]['totals']['directories']))

    def test_cycles_reused_storage_and_damaged_chains(self):
        for bits in (12,16,32):
            for terminal,expected in ((0,'free'),(MASKS[bits]-8,'bad'),(1,'reserved'),(10,'cycle')):
                tree=Tree(bits);tree.chain([10,12],terminal)
                tree.directory([short(name=b'DIR        ',attributes=16,cluster=10)])
                tree.directory(files(32),parent='entry:'+str(tree.root),clusters=[10,12],end=False)
                events,pages,_=run(tree,{'records':1,'events':1})
                self.assertEqual('partial',pages[-1]['status'])
                self.assertIn(expected,[e['chain'] for e in events if e['type']=='directory_end'])
                check_metadata(tree,events)
            tree=Tree(bits);tree.chain([10,12]);tree.chain([11],12)
            a=short(name=b'FIRST      ',attributes=16,cluster=10);b=short(name=b'SECOND     ',attributes=16,cluster=11)
            tree.directory([a,b]);tree.directory(files(16),parent='entry:'+str(tree.root),clusters=[10],end=False)
            tree.directory(files(1),parent='entry:'+str(tree.root),clusters=[12]);tree.directory(files(16),parent='entry:'+str(tree.root+32),clusters=[11],end=False)
            events,pages,_=run(tree);self.assertEqual('partial',pages[-1]['status'])
            self.assertIn('storage_reused',[e['chain'] for e in events if e['type']=='directory_end']);check_metadata(tree,events)

    def test_orphans_deleted_invalid_and_volume_records(self):
        for bits in (12,16,32):
            tree=Tree(bits)
            record=short();name,_=slots([ord('x')]*20,record)
            deleted=short();deleted[0]=0xe5
            invalid=short(attributes=0x80)
            records=[name[:32],deleted,short(attributes=8),invalid,name[32:]]
            tree.directory(records)
            events,pages,_=run(tree,{'records':1,'events':1});check_metadata(tree,events)
            self.assertTrue(any(e['type']=='orphan' and e['reason']=='deleted_boundary' for e in events))
            self.assertTrue(any(e['type']=='orphan' and e['reason']=='end_marker' for e in events))
            self.assertEqual('complete',pages[-1]['status'])

    def test_source_epoch_and_read_failures(self):
        for bits in (12,16,32):
            tree=Tree(bits)
            if bits==32:tree.chain([2,3])
            tree.directory(files(20),clusters=None if bits!=32 else [2,3])
            for fault in (('withdraw',1),('withdraw',3),('withdraw',20),('applicable_throw',3),('reader_throw',1),('overlong',1),('short',1),('empty',1)):
                events,pages,_=run(tree,{'records':1,'events':1},fault=fault)
                self.assertEqual('partial',pages[-1]['status'])
                if fault[0] in ('withdraw','applicable_throw'):
                    self.assertFalse(pages[-1]['applicable']);self.assertEqual('fat_traversal_capture_withdrawn',pages[-1]['diagnostic'])
                check_metadata(tree,events,complete=False)
            # Read3 is directory data for fixed roots and root data after its
            # allocation cell for FAT32; preserve any complete short prefix.
            events,pages,_=run(tree,{'records':1,'events':1},fault=('short',3))
            self.assertEqual('partial',pages[-1]['status']);check_metadata(tree,events,complete=False)

    def test_explicit_resource_bounds_and_large_sector_boot_coherence(self):
        tree=Tree(16);tree.directory([short(name=f'DIR{n:05d}'.encode()+b'   ',attributes=16,cluster=10+n) for n in range(4)])
        for resource,code in ((dict(bitmap_bytes=1),'bitmap_budget'),(dict(queued_directories=1),'queue_budget')):
            events,pages,_=run(tree,resources=resource)
            self.assertEqual('partial',pages[-1]['status']);self.assertEqual('fat_traversal_'+code,pages[-1]['diagnostic'])
        tree=Tree(12);tree.directory([short(name=b'ONE        ',attributes=16,cluster=10)]);tree.chain([10]);tree.chain([11]);tree.directory([short(name=b'TWO        ',attributes=16,cluster=11)],parent='entry:'+str(tree.root),clusters=[10])
        _,pages,_=run(tree,resources=dict(depth=1));self.assertEqual('fat_traversal_depth_budget',pages[-1]['diagnostic'])
        for bits in (12,16,32):
            tree=Tree(bits,unit=4096);tree.directory(files(4))
            events,pages,_=run(tree,{'read_bytes':4096,'reads':1});check_metadata(tree,events)
            self.assertEqual('complete',pages[-1]['status'])
            _,pages,_=run(tree,fault=('boot_change',2));self.assertFalse(pages[-1]['applicable'])
            self.assertEqual('fat_traversal_boot_changed',pages[-1]['diagnostic'])


def main():
    global PROBE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();PROBE=args.probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TraversalTests))
    summary=dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECEIPTS),
        maximum_entries=max((r['entries'] for r in RECEIPTS),default=0),maximum_pages=max((r['pages'] for r in RECEIPTS),default=0),records=RECEIPTS,
        scope='Actual native runtime supplied-region traversal; held ordinary-file/worker/public extraction and other hosts not qualified.')
    args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
