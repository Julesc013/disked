"""Actual held-image and owned child tree paging with independent byte oracles."""
import argparse,copy,hashlib,json,os,struct,subprocess,tempfile,unittest
from pathlib import Path
import test_fat_traversal as tree_fixture
from test_fat_traversal import Tree,files,short,slots,check_metadata

PROBE=None;FAULT=None;RECEIPTS=[]


def write(tree,path):
    request=tree.request()
    with path.open('xb') as f:
        f.truncate(int(request['source_bytes']))
        for row in request['regions']:f.seek(int(row['offset']));f.write(bytes.fromhex(row['hex']))


def run(request,fault=False,timeout=30):
    data=json.dumps(request,separators=(',',':')).encode()+b'\n'
    p=subprocess.run([str(FAULT if fault else PROBE)],input=data,capture_output=True,timeout=timeout)
    assert p.returncode==0 and not p.stderr,p.stderr.decode(errors='replace')
    rows=[json.loads(line) for line in p.stdout.splitlines()]
    RECEIPTS.append(dict(mode=request.get('mode','worker'),fault=fault,fixture=request.get('fixture',{}),
        pages=sum(r['kind']=='page' for r in rows),bytes=len(p.stdout),input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(p.stdout).hexdigest(),
        final=rows[-1]))
    return rows


def request(path,tree,**fields):return dict(path=str(path),offset=str(tree.offset),length=str(tree.length),copy=str(tree.fat_copy),**fields)


def pages(rows):return [r for r in rows if r['kind']=='page']


def verify_pages(tree,path,rows,complete=True):
    source=path.read_bytes();events=[];previous=None;producer=None
    for n,row in enumerate(pages(rows),1):
        frame=row['frame'];page=frame['page'];context=frame['context']
        assert frame['source_before']==frame['input']['expected_source']
        if producer is None:producer=context
        assert context==producer and int(context['process_id'])>0 and int(context['process_created'])>0 and int(context['capture_sequence'])>0
        body=dict(page);digest=body.pop('page_digest')
        assert digest=='sha256:'+hashlib.sha256(b'disked:fat-traversal-page:1\n'+json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert page['previous_page_digest']==previous and page['sequence']==str(n);previous=digest
        expected_capture='sha256:'+hashlib.sha256(json.dumps(dict(process=context,source=frame['source_before'],capture_epoch=frame['input']['capture_epoch']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert page['binding']['capture_id']==expected_capture
        for region in frame['regions']:
            offset=int(region['offset']);size=int(region['requested']);raw=source[offset:offset+size]
            if region['matches']:
                assert region['read_error']=='0' and region['reread_error']=='0'
                assert bytes.fromhex(region['bytes'])==bytes.fromhex(region['reread_bytes'])==raw
            else:assert region['bytes']!=region['reread_bytes'] or region['read_error']!='0' or region['reread_error']!='0' or len(bytes.fromhex(region['bytes']))!=size
        for check in frame['checks']:
            expected=not check['cancelled'] and check['read_consistent'] and check['code'] is None and check['metadata']==frame['input']['expected_source']
            assert check['applicable']==expected
        if 'context' in row:
            owned=row['context'];assert owned['pid']==context['process_id'] and owned['created']==context['process_created']
            assert owned['image_profile']=='ordinary-file-fat-tree' and owned['capture_epoch']==frame['input']['capture_epoch']
            assert owned['worker_epoch'] and owned['observer_epoch'] and owned['attempt_id'] and owned['code_sha256'] and owned['request_digest']
        events.extend(page['events'])
    check_metadata(tree,events,complete=complete)
    return events


class TreeFileTests(unittest.TestCase):
    def test_source_generation_alias_and_parameter_refusal(self):
        tree,path=self.make()
        source=run(request(path,tree,mode='metadata'))[0]['source']
        stale=dict(source);stale['bytes']=str(int(stale['bytes'])+1)
        rows=run(request(path,tree,expected_source=stale));self.assertFalse(pages(rows));self.assertEqual('unavailable',rows[-1]['retirement']['result']['status'])
        self.assertEqual('fat_tree_source_changed',rows[-1]['retirement']['result']['diagnostic']['code'])
        for fields in (dict(page=dict(reads='4294967297')),dict(resources=dict(depth='4294967297')),dict(capture_epoch='0')):
            rows=run(request(path,tree,**fields));self.assertEqual('error',rows[-1]['kind'])
        alias=self.folder/'alias.img';os.link(path,alias)
        rows=run(request(alias,tree,expected_source=source));self.assertFalse(pages(rows));self.assertEqual('image_file_aliases',rows[-1]['retirement']['result']['diagnostic']['code'])
        alias.unlink()

    def test_reply_binding_and_claim_mutations_remain_unknown(self):
        tree,path=self.make()
        for mode in ('capture','worker','code','request','scope','host','observer','attempt','pid','created','shape','status','claims','schema','digest'):
            rows=run(request(path,tree,fixture=dict(reply_fault=mode)),fault=True)
            self.assertEqual('unknown',rows[-1]['retirement']['status'],mode)
            self.assertEqual('exited',rows[-1]['retirement']['worker']['observation'])
            self.assertTrue(rows[-1]['retained_unchanged'])

    def test_nonzero_copy_and_name_pages_on_native_sources(self):
        for bits in (12,16,32):
            tree=Tree(bits,offset=512);tree.fat_copy=1;tree.chain([10,12,15]);raw=short(name=b'LONGDIR    ',attributes=16,cluster=10)
            tree.directory([raw]);entry=short();name,_=slots([ord('x')]*255,entry)
            records=files(15)+[name[i:i+32] for i in range(0,len(name),32)]+[entry]
            tree.directory(records,parent='entry:'+str(tree.offset+tree.root),clusters=[10,12,15])
            path=self.folder/f'copy{bits}.img';write(tree,path)
            with path.open('r+b') as f:f.seek(tree.offset+tree.g['reserved']*tree.unit);f.write(bytes(tree.table))
            rows=run(request(path,tree,page=dict(records='1',events='1')));events=verify_pages(tree,path,rows)
            self.assertEqual('complete',pages(rows)[-1]['frame']['page']['status'])
            self.assertTrue(any(e['type']=='record' and e.get('long_name',{}).get('name_length')=='255' for e in events))
            selected=tree.offset+(tree.g['reserved']+tree.g['fat_sectors'])*tree.unit
            self.assertTrue(all(selected<=int(e['source_offset'])<selected+tree.table for e in events if e['type']=='allocation'))

    def setUp(self):
        root=Path(__file__).resolve().parents[2];scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='fattree-',dir=scratch);self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        assert self.folder.resolve().is_relative_to(scratch.resolve())

    def make(self,bits=12,large=False):
        tree=Tree(bits,offset=512)
        if large:
            chain=list(range(10,1110));tree.chain(chain);tree.directory([short(name=b'LARGETREE  ',attributes=16,cluster=10)])
            tree.directory(files(17600),parent='entry:'+str(tree.offset+tree.root),clusters=chain,end=False)
        else:
            if bits==32:tree.chain(list(range(2,35)))
            tree.directory(files(500),clusters=list(range(2,35)) if bits==32 else None)
        path=self.folder/f'{bits}-{len(list(self.folder.iterdir()))}.img';write(tree,path);return tree,path

    def test_native_files_and_children_agree_with_source_bytes(self):
        for bits in (12,16,32):
            tree,path=self.make(bits);before=hashlib.sha256(path.read_bytes()).hexdigest()
            baseline=None
            for mode in ('file','worker'):
                rows=run(request(path,tree,mode=mode,sharing=True));events=verify_pages(tree,path,rows)
                self.assertEqual('complete',pages(rows)[-1]['frame']['page']['status'])
                if baseline is not None:self.assertEqual(baseline,events)
                baseline=events
                sharing=next(r for r in rows if r['kind']=='sharing');self.assertFalse(sharing['write_open']);self.assertEqual('32',sharing['platform_code'])
                self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
                if mode=='worker':
                    final=rows[-1];self.assertTrue(final['retained_unchanged']);self.assertEqual('exited',final['retirement']['worker']['observation']);self.assertEqual('0',final['retirement']['worker']['exit_code'])
                    self.assertEqual('completed',final['last']['status']);self.assertEqual(final['pages'],final['last']['result']['page_count'])

    def test_large_complete_tree_exceeds_single_frame_budget(self):
        tree,path=self.make(16,large=True);before=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=run(request(path,tree),timeout=90);events=verify_pages(tree,path,rows)
        self.assertEqual(17601,sum(e['type']=='record' for e in events));self.assertGreater(sum(len(json.dumps(p,separators=(',',':')).encode()) for p in pages(rows)),8*1024*1024)
        self.assertTrue(all(len(json.dumps(p['frame'],separators=(',',':')).encode())<=2*1024*1024 for p in pages(rows)))
        self.assertEqual('complete',pages(rows)[-1]['frame']['page']['status']);self.assertEqual('exited',rows[-1]['retirement']['worker']['observation'])
        self.assertTrue(rows[-1]['retained_unchanged']);self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_parent_replay_rejects_altered_frame_coordinates_and_checks(self):
        tree,path=self.make();original=run(request(path,tree,mode='file'));frames=[p['frame'] for p in pages(original)]
        accepted=run(request(path,tree,mode='replay',frames=frames))
        self.assertEqual(len(frames),len(accepted));self.assertTrue(all(r['kind']=='replayed' for r in accepted))
        for change in ('region','receipt','check','page','source','context','binding'):
            forged=copy.deepcopy(frames)
            first=forged[0]
            if change=='region':first['regions'][0]['offset']=str(int(first['regions'][0]['offset'])+1)
            if change=='receipt':first['regions'][0]['matches']=False
            if change=='check':first['checks'][0]['read_consistent']=False
            if change=='page':first['page']['page_digest']='sha256:'+'0'*64
            if change=='source':first['source_before']['file_id']='0'*32
            if change=='context':forged[1]['context']['capture_sequence']='2'
            if change=='binding':first['page']['binding']['capture_epoch']='2'
            rows=run(request(path,tree,mode='replay',frames=forged));self.assertEqual('error',rows[-1]['kind'],change)

    def test_fault_child_cannot_construct_changed_owned_pages(self):
        tree,path=self.make()
        for fault in ('frame_changed','region_changed','checks_changed','process_changed','page_digest','page_context'):
            rows=run(request(path,tree,fixture=dict(worker_fault=fault)),fault=True)
            self.assertFalse(pages(rows),fault);self.assertEqual('unknown',rows[-1]['retirement']['status']);self.assertEqual('exited',rows[-1]['retirement']['worker']['observation'])

    def test_reread_generation_and_cancel_preserve_partial_history(self):
        tree,path=self.make();before=hashlib.sha256(path.read_bytes()).hexdigest()
        for fault in ('read_error','short_read','verify_changed','metadata_changed'):
            rows=run(request(path,tree,fixture=dict(file_fault=fault)),fault=True)
            self.assertTrue(pages(rows),rows[-1]);verify_pages(tree,path,rows,complete=False)
            self.assertFalse(pages(rows)[-1]['frame']['page']['applicable']);self.assertEqual('partial',pages(rows)[-1]['frame']['page']['status'])
            self.assertEqual('exited',rows[-1]['retirement']['worker']['observation']);self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
        rows=run(request(path,tree,cancel_after='1',page=dict(records='4',events='4')))
        self.assertTrue(pages(rows));self.assertTrue(rows[-1]['retained_unchanged']);self.assertTrue(rows[-1]['retirement']['cancellation_requested'])
        self.assertEqual('exited',rows[-1]['retirement']['worker']['observation']);verify_pages(tree,path,rows,complete=False)

    def test_startup_hang_late_and_normal_fixture_refusal(self):
        tree,path=self.make()
        for mode in ('before_spawn','after_spawn','after_spawn_alloc'):
            rows=run(request(path,tree,fixture=dict(startup_fault=mode)),fault=True)
            final=rows[-1];self.assertIsNotNone(final['startup_error']);self.assertEqual(final['never_launched'],mode=='before_spawn')
            self.assertEqual('not_started' if mode=='before_spawn' else 'exited',final['retirement']['worker']['observation'])
        rows=run(request(path,tree,fixture=dict(worker_fault='late')),fault=True);self.assertTrue(pages(rows));self.assertEqual('exited',rows[-1]['retirement']['worker']['observation'])
        rows=run(request(path,tree,fixture=dict(worker_fault='hang')),fault=True)
        self.assertFalse(pages(rows));self.assertEqual('exited',rows[-1]['retirement']['worker']['observation']);self.assertTrue(rows[-1]['retirement']['retired'])
        rows=run(request(path,tree,fixture=dict(worker_fault='hang')));self.assertEqual('fat_tree_fixture_not_compiled',rows[-1]['code'])


def main():
    global PROBE,FAULT
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--fault',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();PROBE=args.probe.resolve();FAULT=args.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TreeFileTests))
    summary=dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECEIPTS),maximum_pages=max((r['pages'] for r in RECEIPTS),default=0),maximum_publication_bytes=max((r['bytes'] for r in RECEIPTS),default=0),records=RECEIPTS,
        scope='Actual generated ordinary files/owned unprivileged children; no mount, physical writes, public extraction, owner or full-release admission.')
    args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n');raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
