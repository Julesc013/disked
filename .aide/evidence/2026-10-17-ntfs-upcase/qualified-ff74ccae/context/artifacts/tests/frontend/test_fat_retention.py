"""Real process-lifetime FAT retention over generated ordinary files."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_auxiliary import MetadataVolume
from test_fat_capture import Volume,short,slots,code_units
from gui_fixture import Gui,U,wait
from test_image_commands import Gate


def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()


class Protocol:
    def __init__(self,exe,env,record):
        self.process=subprocess.Popen([str(exe),'protocol','serve','--format=ndjson'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        self.queue=queue.Queue();self.sequence=0;self.record=record
        def reader():
            for line in self.process.stdout:
                self.queue.put((json.loads(line),digest(line),len(line)))
        self.thread=threading.Thread(target=reader,daemon=True);self.thread.start()

    def request(self,command,parameters,expected=0,diagnostic=None,request_id=None,**extra):
        self.sequence+=1;request_id=request_id or 'retention:'+str(self.sequence)
        value=dict(schema='org.disked.request/1',request_id=request_id,command=command,
            parameters=parameters,required_features=[],**extra)
        self.process.stdin.write(json.dumps(value,ensure_ascii=False).encode('utf-8')+b'\n');self.process.stdin.flush()
        response,sha,size=self.queue.get(timeout=12)
        assert response['request_id']==request_id,(request_id,response)
        assert response['status']=={0:'completed',2:'refused',3:'refused',4:'failed',6:'unknown'}[expected],(command,response)
        assert size<=524288 and response['operation_id'] is None
        if diagnostic:assert diagnostic in [d['code'] for d in response['diagnostics']],response
        self.record(command=command,request=value,response_sha256=sha,response_bytes=size,exit_code=expected)
        return response

    def close(self,expected):
        self.process.stdin.close();assert self.process.wait(timeout=10)==expected
        self.thread.join(timeout=2);assert self.queue.empty() and not self.process.stderr.read()
        self.process.stdout.close();self.process.stderr.close()

    def abort(self):
        if self.process.poll() is None:self.process.kill();self.process.wait(timeout=5)
        self.thread.join(timeout=1)
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            if not stream.closed:stream.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('exe','fault','root'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    args.exe=args.exe.resolve();args.fault=args.fault.resolve();args.root=args.root.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_FAT_COMMAND_TEST_','DISKED_FAT_TEST_'))}
    records=[];passed=False;sessions=[];session_cleanup=ExitStack()
    def record(**fields):records.append(fields)
    def params(path,volume,**extra):return dict(path=str(path),view='fat',volume_offset=str(volume.offset),
        volume_bytes=str(volume.length),retain_capture='yes',**extra)
    def session(exe=None,settings=None):
        selected=env.copy();selected.update(settings or {})
        value=Protocol(exe or args.exe,selected,record);sessions.append(value);session_cleanup.callback(value.abort);return value
    def retrieve(port,cid,receipt,original):
        encoded=bytearray();offset=0
        while True:
            result=port.request('image.capture.inspect',dict(phase='read',capture_id=cid,
                byte_offset=str(offset),byte_count='196608'))['result']
            part=bytes.fromhex(result['data']);assert digest(part)==result['chunk_sha256']
            assert result['record_sha256']==receipt['sha256'] and result['total_bytes']==receipt['bytes']
            assert result['byte_offset']==str(offset) and result['returned_bytes']==str(len(part))
            encoded.extend(part)
            if result['next_offset'] is None:break
            offset=int(result['next_offset'])
        encoded=bytes(encoded);assert digest(encoded)==receipt['sha256'] and len(encoded)==int(receipt['bytes'])
        value=json.loads(encoded);assert value['schema']=='org.disked.retained-fat-capture/1'
        frame=value['frame'];assert frame['schema']=='org.disked.fat-region-frame/1'
        frame_bytes=json.dumps(frame,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        assert digest(frame_bytes)==value['context']['frame_sha256']
        assert not frame['result']['authorizes_effects'] and not frame['result']['product_dispatch_admitted']
        for region in frame['regions']:
            data=bytes.fromhex(region['bytes']);start=int(region['offset'])
            assert data==original[start:start+len(data)],region['offset']
        assert value['worker']['worker']['observation']=='exited'
        empty=port.request('image.capture.inspect',dict(phase='read',capture_id=cid,
            byte_offset=str(len(encoded)),byte_count='1'))['result']
        assert empty['data']=='' and empty['next_offset'] is None
        return value
    scratch=args.root/'.aide-local';scratch.mkdir(exist_ok=True)
    try:
        # ExitStack runs before TemporaryDirectory so a failing assertion closes
        # its owned sessions before cleanup attempts to unlink held source files.
        with tempfile.TemporaryDirectory(prefix='fat-retention-',dir=scratch) as folder,session_cleanup:
            folder=Path(folder);assert folder.resolve().is_relative_to(scratch.resolve())
            for bits in (12,16,32):
                volume=MetadataVolume(bits,offset=512);item=short();long,_=slots(code_units('界🙂 retained.txt'),item)
                volume.directory([long,bytes(item)]);path=folder/f'fat{bits}-界.img';volume.write(path);original=path.read_bytes()
                port=session();observed=port.request('image.inspect',params(path,volume,auxiliary_checks='yes'))
                receipt=observed['result']['capture_retention'];cid=receipt['capture_id']
                rows=port.request('image.capture.inspect',{})['result']['captures']
                assert len(rows)==1 and rows[0]['capture_id']==cid and rows[0]['request_id']=='retention:1'
                assert rows[0]['state']=='retained' and path.read_bytes()==original
                path.unlink()  # Test-owned generated file, now unavailable for any reread.
                retained=retrieve(port,cid,receipt,original)
                assert retained['frame']['result']['observation']['geometry']['bits']==str(bits)
                port.request('image.capture.inspect',dict(phase='read',capture_id=cid,byte_offset=str(int(receipt['bytes'])+1),byte_count='1'),3,'capture_retention_range')
                port.request('image.capture.release',dict(capture_id=cid))
                assert port.request('image.capture.inspect',{})['result']['captures']==[]
                port.request('image.capture.release',dict(capture_id=cid),3,'capture_retention_unknown')
                port.close(3);other=session()
                other.request('image.capture.inspect',dict(phase='read',capture_id=cid,byte_offset='0',byte_count='1'),3,'capture_retention_unknown');other.close(3)
            volume=MetadataVolume(12);path=folder/'quota.img';volume.write(path);original=path.read_bytes();port=session()
            for argv,expected in [(['image','capture','inspect'],0),
                (['image','capture','release','--capture-id','fat-capture:'+'a'*32+':1'],3),
                (['image','capture','inspect','--phase','read','--capture-id','fat-capture:'+'a'*32+':1','--byte-offset','0','--byte-count','196609'],2),
                (['image','inspect',str(path),'--view','fat','--volume-offset',str(volume.offset),'--volume-bytes',str(volume.length),'--retain-capture','yes'],0)]:
                result=subprocess.run([str(args.exe),*argv,'--json'],capture_output=True,timeout=12,env=env)
                assert result.returncode==expected and not result.stderr,(argv,result.stdout,result.stderr)
                value=json.loads(result.stdout);record(command='cli-'+argv[0]+'.'+argv[1],exit_code=result.returncode,response=value)
            no_retention=params(path,volume);no_retention.pop('retain_capture')
            first=port.request('image.inspect',no_retention);second=port.request('image.inspect',dict(no_retention,retain_capture='no'))
            assert 'capture_retention' not in first['result'] and 'capture_retention' not in second['result']
            assert port.request('image.capture.inspect',{})['result']['captures']==[]
            ids=[]
            for n in range(4):ids.append(port.request('image.inspect',params(path,volume))['result']['capture_retention']['capture_id'])
            assert len(set(ids))==4;path.unlink()
            port.request('image.inspect',params(path,volume),3,'capture_retention_resource')
            port.request('image.capture.release',dict(capture_id=ids[0]))
            path.write_bytes(original);new=port.request('image.inspect',params(path,volume))['result']['capture_retention']['capture_id']
            assert new not in ids;port.close(3)
            # Native malformed controls refuse before the guarded source port.
            port=session(args.fault,dict(DISKED_FAT_COMMAND_TEST_OPEN_GUARD='1'))
            cid='fat-capture:'+'a'*32+':1'
            invalid=[dict(phase='read',capture_id=cid,byte_offset='0',byte_count='0'),
                dict(phase='read',capture_id=cid,byte_offset=str(2**64),byte_count='1'),
                dict(phase='read',capture_id=cid,byte_offset='0',byte_count='196609'),
                dict(phase='list',capture_id=cid),dict(phase='release'),
                dict(phase='read',capture_id='fat-capture:'+'a'*32+':'+str(2**64),byte_offset='0',byte_count='1')]
            for value in invalid:port.request('image.capture.inspect',value,2,'invalid_parameter')
            port.request('image.inspect',params(path,volume),2,'unexpected_revision',expected_revision='sha256:'+'a'*64)
            port.request('image.capture.inspect',{},2,'unexpected_revision',expected_revision='sha256:'+'a'*64)
            port.request('image.inspect',dict(path=str(path),retain_capture='yes'),2,'invalid_parameter')
            assert port.request('image.capture.inspect',{})['result']['captures']==[];port.close(2)
            port=session(args.fault,dict(DISKED_FAT_COMMAND_TEST_OPEN_GUARD='1'))
            port.request('image.inspect',params(path,volume),3,'fat_source_open_forbidden')
            assert port.request('image.capture.inspect',{})['result']['captures']==[];port.close(3)
            # Failure/partial observations retain honest metadata, not successful claims.
            port=session(args.fault,dict(DISKED_FAT_COMMAND_TEST_VERIFY_CHANGED='1'))
            observed=port.request('image.inspect',params(path,volume),4,'fat_source_changed')
            receipt=observed['result']['capture_retention'];retained=retrieve(port,receipt['capture_id'],receipt,original)
            assert not retained['frame']['result']['capture']['observed_stable'];port.close(4)
            # Callback retains its reservation across timeout and completes once released.
            gate=Gate();port=session(args.fault,dict(DISKED_FAT_COMMAND_TEST_GATE='1',DISKED_IMAGE_TEST_GATE=gate.name))
            try:
                observed=port.request('image.inspect',params(path,volume),6,'request_wait_expired',request_id='late-origin')
                rows=port.request('image.capture.inspect',{})['result']['captures'];assert len(rows)==1 and rows[0]['state']=='reserved'
                cid=rows[0]['capture_id'];assert rows[0]['request_id']=='late-origin'
                port.request('image.capture.release',dict(capture_id=cid),3,'capture_retention_busy');gate.release()
                for _ in range(40):
                    rows=port.request('image.capture.inspect',{})['result']['captures']
                    if rows[0]['state']=='retained':break
                    time.sleep(.1)
                assert rows[0]['state']=='retained';retrieve(port,cid,rows[0],original);port.close(6)
            finally:gate.close()
            # Actual native GUI uses the same store across command navigation.
            detailed=Volume(32);rows=[]
            for n in range(80):
                item=short(name=f'L{n:07d}TXT'.encode());long,_=slots(code_units('界'*246+f'{n:04d}'),item)
                rows.extend([long,bytes(item)])
            detailed.chain(list(range(2,2+(len(b''.join(rows))+32+511)//512)));detailed.directory(rows)
            detail_path=folder/'gui-detail.img';detailed.write(detail_path);detail_original=detail_path.read_bytes()
            gui=Gui(args.exe,['--gui','image','inspect',str(detail_path),'--view','fat','--volume-offset',str(detailed.offset),
                '--volume-bytes',str(detailed.length),'--retain-capture','yes'],render=True)
            try:
                assert not U.IsWindowEnabled(gui.child(110));gui.click(109)
                assert gui.details().get('reviewed') is True;gui.click(110)
                value=wait(lambda:gui.details() if 'status' in gui.details() else None);cid=value['result']['capture_retention']['capture_id']
                for command,fields in [('image.capture.inspect',{}),
                    ('image.capture.inspect',dict(phase='read',capture_id=cid,byte_offset='0',byte_count='196608')),
                    ('image.capture.release',dict(capture_id=cid))]:
                    gui.click(105);ids=gui.list_ids();at=next(i for i,row in enumerate(ids) if command in row)
                    gui.choose(at);gui.click(108)
                    for key,value in fields.items():
                        try:gui.set_field(key,value)
                        except AssertionError:
                            record(command='gui-form-failure',field=key,view=gui.details(),
                                labels=[gui.text(220),gui.text(221)],page=gui.text(115),
                                editors=[gui.text(200),gui.text(201)],native=gui.observation())
                            raise
                    gui.click(109);assert gui.details().get('reviewed') is True;gui.click(110)
                    value=wait(lambda:gui.details() if 'status' in gui.details() else None)
                    assert value['status']=='completed',value
                    if not fields:assert value['result']['captures'][0]['capture_id']==cid
                    elif fields.get('phase')=='read':
                        assert value['result']['returned_bytes']=='196608' and len(value['result']['data'])==393216
                        assert digest(bytes.fromhex(value['result']['data']))==value['result']['chunk_sha256']
                    else:assert value['result']['released']
                    record(command='gui-'+command,response=value,native=gui.observation())
            finally:gui.close()
            assert gui.code==0 and gui.created_files==[] and detail_path.read_bytes()==detail_original and path.read_bytes()==original
            for frontend in ('tui','shell'):
                output=folder/(frontend+'.json');startup=subprocess.STARTUPINFO()
                startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                options=['--view','fat','--volume-offset',str(volume.offset),'--volume-bytes',str(volume.length),'--retain-capture','yes']
                cmd=[sys.executable,str(args.root/'tests/frontend/retention_console_fixture.py'),str(args.exe),
                    frontend,str(path),str(args.root),str(output),json.dumps(options)]
                result=subprocess.run(cmd,cwd=folder,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=45)
                observed=json.loads(output.read_bytes());assert result.returncode==0,observed
                assert all(observed['restored'].values()) and len(observed['retention_journey'])==2
                record(command=frontend+'-retention',observation=observed);output.unlink()
            assert path.read_bytes()==original
        passed=True
    finally:
        for port in sessions:port.abort()
        if args.output:args.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FAT retained capture '+('PASS' if passed else 'FAIL')+' '+str(len(records)),flush=True)


if __name__=='__main__':main()
