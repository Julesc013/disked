"""Owned FAT child/region reconstruction tests over independently generated files."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import test_fat_capture as capture
from test_fat_capture import Volume, short, slots, code_units
from test_fat_auxiliary import MetadataVolume
from test_fat_namespace import query

PROBE=None
FAULT=None
QUOTA_OBSERVATIONS=[]


def request(path,volume,**fields):
    value=dict(op='file',path=str(path),offset=str(volume.offset),length=str(volume.length))
    value.update(fields)
    return value


def run(rows, fault=False):
    values=capture.run(rows,probe=FAULT if fault else PROBE)
    for row,value in zip(rows,values):
        if 'error' in value or 'startup_error' in value:
            print(json.dumps(dict(reader_refusal=value,request_mode=row.get('mode','worker'),fixture=row.get('fixture',{})),sort_keys=True),flush=True)
    return values


def all_false(value):
    return all(flag is False for flag in value.values())


class WorkerTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2];scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
        assert scratch.resolve().is_relative_to(root.resolve())
        self.folder=tempfile.TemporaryDirectory(prefix='fatworker-',dir=scratch)
        self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
        assert self.root.resolve().is_relative_to(scratch.resolve())

    def make(self,bits=12,unit=512,offset=512):
        volume=MetadataVolume(bits,unit=unit,offset=offset)
        item=short();long,_=slots(code_units('A long name.txt'),item)
        volume.directory([long,bytes(item)])
        path=self.root/f'{bits}-{unit}-{offset}-{len(list(self.root.iterdir()))}.img';volume.write(path)
        return path,volume

    def test_actual_children_and_independent_regions(self):
        rows=[];sources=[]
        for bits in (12,16,32):
            for unit in (512,4096):
                path,volume=self.make(bits,unit);sources.append((path,volume,hashlib.sha256(path.read_bytes()).hexdigest()))
                rows.append(request(path,volume,name_code_page='437',queries=[query('A long name.txt')],auxiliary_checks=True))
        for value,(path,volume,before) in zip(run(rows),sources):
            self.assertTrue(value['has_snapshot'],value);self.assertTrue(value['retained_unchanged'])
            result=value['result'];self.assertTrue(result['capture']['observed_stable'])
            self.assertEqual(result['observation']['geometry']['bits'],str(volume.bits))
            self.assertEqual(result['observation']['namespace']['queries'][0]['status'],'unique')
            context=value['context'];self.assertGreater(int(context['pid']),0);self.assertGreater(int(context['created']),0)
            self.assertEqual(context['image_profile'],'ordinary-file-fat')
            self.assertEqual(value['retirement']['worker']['observation'],'exited')
            self.assertEqual(value['samples'][-1]['worker']['exit_code'],'0')
            self.assertTrue(all_false(value['samples'][-1]['result']['claims']))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        path,volume=self.make(16)
        frame=run([request(path,volume,mode='frame')])[0]['frame']
        raw=path.read_bytes()
        for row,record in zip(frame['regions'],frame['result']['capture']['regions']):
            at=int(row['offset']);size=int(row['requested']);data=bytes.fromhex(row['bytes'])
            self.assertEqual(data,raw[at:at+size]);self.assertEqual(record['sha256'],'sha256:'+hashlib.sha256(data).hexdigest())
        self.assertEqual(frame['result']['capture']['capture_domain'],'sha256:'+hashlib.sha256(json.dumps(dict(
            process=frame['process_id'],process_created=frame['process_created'],sequence=frame['result']['observation']['capture_epoch'],
            source=frame['result']['capture']['source_before']),sort_keys=True,separators=(',',':')).encode()).hexdigest())

    def test_full_optional_observations_and_private_code_pages(self):
        path,volume=self.make(32)
        rows=[request(path,volume,allocation_scan=True,auxiliary_checks=True,name_code_page=str(page),
                      queries=[query('A long name.txt'),query('FILE.TXT'),query('missing')]) for page in (437,850,932)]
        for value in run(rows):
            self.assertTrue(value['has_snapshot'],value)
            obs=value['result']['observation'];self.assertTrue(obs['allocation_scan']['coverage_complete'])
            self.assertTrue(obs['auxiliary_checks']['coverage_complete'])
            self.assertEqual([q['status'] for q in obs['namespace']['queries']],['unique','unique','not_found'])

    def test_partial_media_and_selected_limits_keep_honest_facts(self):
        path,volume=self.make()
        rows=[request(path,volume,limits={name:str(value)}) for name,value in [('records',1),('read_requests',1),('nodes',1),('read_bytes',512),('output_bytes',16384)]]
        for value in run(rows):
            self.assertTrue(value['has_snapshot'],value)
            self.assertFalse(value['result']['observation']['filesystem_health_qualified'])
            self.assertFalse(value['result']['authorizes_effects'])
        empty=self.root/'zero.img';empty.write_bytes(bytes(1024))
        result=run([dict(op='file',path=str(empty),offset='0',length='1024')])[0]
        self.assertTrue(result['has_snapshot'],result);self.assertFalse(result['result']['observation']['selected_tree_complete'])
        self.assertTrue(result['result']['observation']['diagnostics'])

    def test_capture_failure_controls_and_normal_isolation(self):
        path,volume=self.make(32);before=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=[request(path,volume,name_code_page='437',queries=[query('FILE.TXT')],auxiliary_checks=True,
                      fixture={'capture_fault':fault}) for fault in ('verify_changed','verify_error','metadata_changed','read_error','short_read','overlap_changed')]
        for supplied,value in zip(rows,run(rows,True)):
            fault=supplied['fixture']['capture_fault']
            if fault=='metadata_changed':
                self.assertFalse(value['has_snapshot'],value);continue
            self.assertTrue(value['has_snapshot'],value)
            self.assertFalse(value['result']['capture']['observed_stable'])
            self.assertTrue(all(q['status']!='unique' for q in value['result']['observation']['namespace']['queries']))
        for value in run(rows):self.assertIn('error',value)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_every_publication_binding_and_result_fault(self):
        path,volume=self.make()
        faults=['capture','worker','code','request','scope','host','observer','attempt','pid','created','shape','status','claims','schema','digest']
        rows=[request(path,volume,fixture={'reply_fault':fault}) for fault in faults]
        for value in run(rows,True):
            self.assertFalse(value['has_snapshot'],value)
            self.assertEqual(value['samples'][-1]['status'],'unknown')
            self.assertEqual(value['samples'][-1]['worker']['observation'],'exited')
        faults=['payload_changed','result_changed','receipt_changed','process_changed','domain_changed','row_changed','claims']
        rows=[request(path,volume,fixture={'worker_fault':fault}) for fault in faults]
        for supplied,value in zip(rows,run(rows,True)):
            self.assertFalse(value['has_snapshot'],value);self.assertEqual(value['samples'][-1]['status'],'unknown')
            if supplied['fixture']['worker_fault']=='process_changed':self.assertEqual(value['samples'][-1]['diagnostic'],'fat_worker_capture_process')

    def test_cancel_late_hang_and_actual_retirement(self):
        path,volume=self.make();before=hashlib.sha256(path.read_bytes()).hexdigest()
        value=run([request(path,volume,cancel=True)],True)[0]
        self.assertFalse(value['has_snapshot']);self.assertTrue(value['samples'][-1]['cancellation_requested'])
        self.assertEqual(value['samples'][-1]['worker']['observation'],'exited')
        for fault in ('hang','late'):
            value=run([request(path,volume,mode='pending',fixture={'worker_fault':fault})],True)[0]
            self.assertFalse(value['has_snapshot']);self.assertEqual(value['before']['worker']['observation'],'running')
            self.assertEqual(value['retirement']['worker']['observation'],'exited');self.assertTrue(value['retirement']['retired'])
        value=run([request(path,volume,fixture={'reply_fault':'hold'})],True)[0]
        self.assertTrue(value['has_snapshot']);self.assertEqual(value['retirement']['worker']['observation'],'exited')
        value=run([request(path,volume,mode='publication',fixture={'reply_fault':'hold'})],True)[0]
        self.assertTrue(value['has_snapshot']);self.assertEqual(value['before']['status'],'completed')
        self.assertEqual(value['before']['worker']['observation'],'running')
        self.assertEqual(value['retirement']['worker']['observation'],'exited');self.assertTrue(value['retained_unchanged'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_owned_pre_and_post_spawn_failure_paths(self):
        path,volume=self.make()
        for fault,value in zip(('before_spawn','after_spawn','after_spawn_alloc'),run([
            request(path,volume,fixture={'startup_fault':f}) for f in ('before_spawn','after_spawn','after_spawn_alloc')],True)):
            self.assertIn('startup_error',value)
            if fault=='before_spawn':self.assertTrue(value['never_launched'])
            else:
                self.assertFalse(value['never_launched']);self.assertEqual(value['retirement']['worker']['observation'],'exited')

    def test_invalid_inputs_and_expected_source_mismatch(self):
        path,volume=self.make()
        source=run([request(path,volume,mode='frame')])[0]['frame']['result']['capture']['source_before']
        wrong=copy.deepcopy(source);wrong['file_id']='0'*32
        value=run([request(path,volume,expected_source=wrong)])[0]
        self.assertFalse(value['has_snapshot']);self.assertEqual(value['samples'][-1]['result']['status'],'unavailable')
        self.assertEqual(value['samples'][-1]['result']['diagnostic']['code'],'fat_file_source_changed')
        rows=[request(path,volume,capture_epoch='0'),request(path,volume,name_code_page='1252'),
              request(path,volume,offset=str(volume.offset+volume.length)),request(path,volume,length=str(volume.length+1)),
              request(path,volume,queries=[query('x')]),request(path,volume,name_code_page='437',queries=[query('x')],limits={'output_bytes':'786431'})]
        rows += [request(path,volume,limits={key:str(number)}) for key,number in [('read_requests',0),('read_bytes',2097153),('nodes',129),('records',4097),('output_bytes',1048577)]]
        for value in run(rows):self.assertIn('error',value)
        linked=self.root/'linked.img';os.link(path,linked)
        self.assertIn('error',run([request(linked,volume)])[0])

    def test_pure_frame_reconstruction_rejects_tampering(self):
        path,volume=self.make();frame=run([request(path,volume,mode='frame')])[0]['frame']
        frames=[]
        for key,value in [('schema','unknown'),('capture_epoch','2'),('process_id','0'),('process_created','0')]:
            changed=copy.deepcopy(frame);changed[key]=value;frames.append(changed)
        for key,value in [('authorizes_effects',True),('product_dispatch_admitted',True)]:
            changed=copy.deepcopy(frame);changed['result'][key]=value;frames.append(changed)
        for key,value in [('metadata_equal',False),('overlaps_equal',False),('regions_equal',False),('observed_stable',False),('whole_file_hashed',True),('atomic_snapshot',True),('reread_bytes','1'),('capture_domain','sha256:'+'0'*64)]:
            changed=copy.deepcopy(frame);changed['result']['capture'][key]=value;frames.append(changed)
        for key,value in [('offset','0'),('requested','0'),('error','1'),('bytes','00')]:
            changed=copy.deepcopy(frame);changed['regions'][0][key]=value;frames.append(changed)
        for key,value in [('source_offset','0'),('requested_bytes','1'),('captured_bytes','1'),('sha256','sha256:'+'0'*64),('reread_sha256','sha256:'+'0'*64),('reread_bytes','1'),('reread_error','1'),('matches',False)]:
            changed=copy.deepcopy(frame);changed['result']['capture']['regions'][0][key]=value;frames.append(changed)
        changed=copy.deepcopy(frame);changed['regions'].reverse();changed['result']['capture']['regions'].reverse();frames.append(changed)
        changed=copy.deepcopy(frame);changed['regions'].append(changed['regions'][0]);changed['result']['capture']['regions'].append(changed['result']['capture']['regions'][0]);frames.append(changed)
        changed=copy.deepcopy(frame);changed['regions'].pop();changed['result']['capture']['regions'].pop();frames.append(changed)
        changed=copy.deepcopy(frame);changed['result']['observation']['nodes'][1]['name_oem']='0'*22;frames.append(changed)
        for value in run([request(path,volume,mode='verify',replace=changed) for changed in frames]):self.assertIn('error',value)
        valid=run([request(path,volume,mode='verify',replace=frame)])[0]
        self.assertIn('verified',valid);self.assertNotIn('context',valid)

    def test_actual_generation_and_sharing_refusals(self):
        path,volume=self.make()
        source=run([request(path,volume,mode='frame')])[0]['frame']['result']['capture']['source_before']
        with path.open('ab') as stream:stream.write(b'changed')
        value=run([request(path,volume,expected_source=source)])[0]
        self.assertFalse(value['has_snapshot'])
        self.assertEqual(value['samples'][-1]['result']['diagnostic']['code'],'fat_file_source_changed')
        value=run([request(path,volume,hold_writer=True)])[0]
        self.assertFalse(value['has_snapshot'])
        self.assertEqual(value['samples'][-1]['result']['diagnostic'],dict(code='fat_file_open',platform_code='32'))
        directory=run([request(path.parent,volume)])[0]
        self.assertIn('error',directory)

    def test_real_shared_quota_refuses_fifth_reader(self):
        path,volume=self.make();before=hashlib.sha256(path.read_bytes()).hexdigest()
        value=run([request(path,volume,mode='quota')],True)[0]
        self.assertEqual(value['fifth_error'],'observation_spawn_failed',value)
        self.assertTrue(value['fifth_never_launched'])
        self.assertEqual(len(value['peer_retirements']),4)
        self.assertTrue(all(p['worker']['observation']=='exited' for p in value['peer_retirements']))
        QUOTA_OBSERVATIONS.append(value)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


def main():
    global PROBE,FAULT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--fault-probe',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    PROBE=args.probe.resolve();FAULT=args.fault_probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTests))
    cases=sum(r['cases'] for r in capture.RECEIPTS)
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),cases=cases,batches=capture.RECEIPTS,quota_observations=QUOTA_OBSERVATIONS),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Owned FAT reader cases executed: '+str(cases),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
