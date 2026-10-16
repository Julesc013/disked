"""Actual product process-lifetime tree sessions and independent frame bytes."""
import argparse,contextlib,hashlib,json,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_traversal import Tree,files,short,check_metadata
from test_fat_tree_file import write
from gui_fixture import Gui,U,wait

def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()

class Protocol:
    def __init__(self,exe,record,env=None):
        self.process=subprocess.Popen([str(exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        self.queue=queue.Queue();self.sequence=0;self.record=record;self.expected=0
        def reader():
            for line in self.process.stdout:self.queue.put((json.loads(line),line))
        self.thread=threading.Thread(target=reader,daemon=True);self.thread.start()
    def request(self,p,expected=0,diagnostic=None,**extra):
        self.sequence+=1;rid='tree-session:'+str(self.sequence)
        wire=dict(schema='org.disked.request/1',request_id=rid,command='filesystem.tree.inspect',parameters=p,required_features=[],**extra)
        self.process.stdin.write(json.dumps(wire).encode()+b'\n');self.process.stdin.flush()
        response,data=self.queue.get(timeout=12)
        assert response['request_id']==rid and response['operation_id'] is None and len(data)<=524288,response
        allowed=expected if isinstance(expected,tuple) else (expected,)
        actual=next((code for code in allowed if response['status']=={0:'completed',2:'refused',3:'refused',4:'failed',6:'unknown'}[code]),None)
        assert actual is not None,response
        if diagnostic:assert diagnostic in [d['code'] for d in response['diagnostics']],response
        self.expected=max(self.expected,actual)
        self.record(dict(request=wire,response_sha256=digest(data),response_bytes=len(data),expected_exit=expected))
        return response['result']
    def close(self):
        self.process.stdin.close();assert self.process.wait(timeout=15)==self.expected
        self.thread.join(timeout=2);assert self.queue.empty() and not self.process.stderr.read()
        self.process.stdout.close();self.process.stderr.close()
    def stream(self,p,original):
        self.sequence+=1;rid='tree-session:'+str(self.sequence)
        wire=dict(schema='org.disked.request/1',request_id=rid,command='filesystem.tree.inspect',parameters=p,required_features=['org.disked.fat-tree-events/1'])
        self.process.stdin.write(json.dumps(wire).encode()+b'\n');self.process.stdin.flush()
        events=[];page=None;record=bytearray();offset=0;frames=0;pages=0;total=0;previous=None;sequence=0
        while True:
            response,data=self.queue.get(timeout=35);frames+=1
            assert response['request_id']==rid and response['status']=='completed' and response['operation_id'] is None and len(data)<=524288,response
            body=response['result'];self.record(dict(kind='stream-envelope',response_sha256=digest(data),response_bytes=len(data),request_id=rid))
            if body['final']:
                assert body['request_kind']=='tree-stream-outcome' and int(body['pages'])==pages and body['coverage']=='complete'
                assert body['closure']['state']=='closed' and body['closure']['worker']['worker']['observation']=='exited'
                assert not body['closure']['cancellation_requested']
                assert int(body['events_emitted'])==sequence and not record
                return events,pages,total,frames
            assert body['request_kind']=='tree-stream-event';sequence+=1;assert int(body['stream_sequence'])==sequence
            if body['event_kind']=='page':
                page=body['page'];pages+=1;assert int(page['sequence'])==pages and page['previous_page_digest']==previous and not record
                unhashed=dict(page);previous=unhashed.pop('page_digest');assert digest(b'disked:fat-traversal-page:1\n'+json.dumps(unhashed,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==previous
                events.extend(page['events']);offset=0
            elif body['event_kind']=='record-chunk':
                assert body['page_sequence']==page['sequence'] and int(body['byte_offset'])==offset
                chunk=bytes.fromhex(body['data']);assert digest(chunk)==body['chunk_sha256'] and len(chunk)==int(body['returned_bytes'])
                record.extend(chunk);offset+=len(chunk)
                if body['next_offset'] is None:
                    assert len(record)==int(body['total_bytes']) and digest(record)==body['record_sha256']
                    value=json.loads(record);assert value['frame']['page']==page
                    for region in value['frame']['regions']:
                        start=int(region['offset']);count=int(region['requested']);expected=original[start:start+count]
                        assert bytes.fromhex(region['bytes'])==expected and bytes.fromhex(region['reread_bytes'])==expected and region['matches']
                    total+=len(record);record.clear()
                else:assert int(body['next_offset'])==offset
            else:assert body['event_kind']=='opened'
    def abort(self):
        if self.process.poll() is None:self.process.kill();self.process.wait(timeout=5)
        self.thread.join(timeout=2)
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            if not stream.closed:stream.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--fault',type=Path,required=True);parser.add_argument('--output',type=Path);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();args.exe=args.exe.resolve();records=[];sessions=[];passed=False;journeys=[]
    def port():
        p=Protocol(args.exe,records.append);sessions.append(p);return p
    def opening(path,tree,**extra):
        return dict(phase='open',path=str(path),volume_offset=str(tree.offset),volume_bytes=str(tree.g['total']*tree.unit),fat_copy=str(tree.fat_copy),**extra)
    def call(phase,sid,**extra):return dict(phase=phase,session_id=sid,**extra)
    def close_session(p,sid):
        deadline=time.monotonic()+5
        while True:
            out=p.request(call('close',sid))
            if out['state']=='closed':assert out['worker']['worker']['observation']=='exited';break
            assert out['state']=='closing' and time.monotonic()<deadline;time.sleep(.005)
    def retrieve(p,sid,receipt):
        data=bytearray();offset=0
        while True:
            out=p.request(call('read',sid,page_sequence=receipt['page_sequence'],byte_offset=str(offset),byte_count='196608'))
            part=bytes.fromhex(out['data']);assert digest(part)==out['chunk_sha256'] and out['record_sha256']==receipt['sha256']
            assert out['total_bytes']==receipt['bytes'] and out['byte_offset']==str(offset) and out['returned_bytes']==str(len(part))
            data.extend(part)
            if out['next_offset'] is None:break
            offset=int(out['next_offset'])
        assert len(data)==int(receipt['bytes']) and digest(data)==receipt['sha256']
        return json.loads(data),len(data)
    try:
        # Retain owned generated fixtures on failure; automatic directory cleanup
        # must not race a reader whose retirement has not yet been established.
        with contextlib.nullcontext(tempfile.mkdtemp(prefix='disked-tree-session-')) as directory:
            root=Path(directory)
            for bits in (12,16,32):
                tree=Tree(bits,offset=12345);chain=list(range(2,35)) if bits==32 else None
                if chain:tree.chain(chain)
                tree.directory(files(500),clusters=chain)
                path=root/f'fat{bits}.img';write(tree,path);original=path.read_bytes();p=port()
                opened=p.request(opening(path,tree,page_records='128',page_events='128'));sid=opened['session_id']
                assert opened['process_lifetime_only'] and opened['state']=='owned'
                # The child can publish and wait while the actual UI/consumer is idle.
                if bits==12:time.sleep(1.2)
                events=[];pages=0;previous=None;total=0;last=None;deadline=time.monotonic()+60
                while True:
                    out=p.request(call('next',sid));assert not out['authorizes_effects'] and not out['current_source_authority']
                    if 'page' in out:
                        page=out['page'];pages+=1;assert int(page['sequence'])==pages and page['previous_page_digest']==previous
                        unhashed=dict(page);previous=unhashed.pop('page_digest');assert digest(b'disked:fat-traversal-page:1\n'+json.dumps(unhashed,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==previous
                        value,n=retrieve(p,sid,out['record']);total+=n;last=out['record']
                        assert value['schema']=='org.disked.fat-tree-page-record/1' and value['frame']['page']==page and value['context']==out['context']
                        frame=value['frame'];assert frame['source_before']==opened['source']
                        assert out['context']['pid']==frame['context']['process_id'] and out['context']['created']==frame['context']['process_created']
                        assert out['context']['image_profile']=='ordinary-file-fat-tree'
                        for r in frame['regions']:
                            start=int(r['offset']);size=int(r['requested']);expected=original[start:start+size]
                            assert bytes.fromhex(r['bytes'])==expected and bytes.fromhex(r['reread_bytes'])==expected and r['matches']
                        events.extend(page['events'])
                        if page['status']=='complete':break
                    else:
                        assert out['worker']['status']!='unknown',out
                        time.sleep(.002)
                    assert time.monotonic()<deadline
                check_metadata(tree,events);assert sum(e['type']=='record' for e in events)==500
                p.request(call('read',sid,page_sequence='1',byte_offset='0',byte_count='1'),3,'tree_session_stale_page')
                # EOF is a valid empty chunk, and range/byte limits refuse.
                eof=p.request(call('read',sid,page_sequence=last['page_sequence'],byte_offset=last['bytes'],byte_count='1'));assert not eof['data'] and eof['next_offset'] is None
                p.request(call('read',sid,page_sequence=last['page_sequence'],byte_offset=str(int(last['bytes'])+1),byte_count='1'),3,'tree_session_range')
                p.request(call('read',sid,page_sequence=last['page_sequence'],byte_offset='0',byte_count='196609'),2,'invalid_parameter')
                deadline=time.monotonic()+5
                while True:
                    status=p.request(call('status',sid));worker=status['worker']
                    if worker['status']=='completed' and worker['worker']['observation']=='exited':break
                    assert time.monotonic()<deadline;time.sleep(.002)
                assert worker['result']['status']=='completed' and int(worker['result']['page_count'])==pages and worker['result']['sha256']==previous
                assert retrieve(p,sid,last)[0]['frame']['page']['sequence']==last['page_sequence']
                close_session(p,sid);p.request(call('status',sid),3,'tree_session_unknown');p.close()
                assert path.read_bytes()==original
                journeys.append(dict(kind='complete',bits=bits,pages=pages,records=500,record_bytes=total,source_sha256=digest(original)))
            # More than8MiB of independent actual frame reconstruction is not a whole-tree cap.
            tree=Tree(16);chain=list(range(3,1103));tree.chain(chain)
            tree.directory([short(name=b'LONGDIR    ',attributes=16,cluster=3)])
            tree.directory(files(17600),parent='entry:'+str(tree.root),clusters=chain,end=False)
            path=root/'large.img';write(tree,path);original=path.read_bytes();p=port();scan=opening(path,tree);scan['phase']='scan'
            events,pages,total,frames=p.stream(scan,original)
            check_metadata(tree,events);assert sum(e['type']=='record' for e in events)==17601 and total>8388608 and frames>256
            p.close();assert path.read_bytes()==original
            journeys.append(dict(kind='large-stream',pages=pages,records=17601,record_bytes=total,event_envelopes=frames,input_requests=1,source_sha256=digest(original)))
            # Invalid parameters and foreign session selectors cannot open a source.
            p=port()
            for value in [dict(phase='open',path=str(root/'missing'),volume_offset='0',volume_bytes='0'),dict(phase='open',path=str(root/'missing'),volume_offset=str(2**64-1),volume_bytes='512'),dict(phase='next',session_id='fat-tree:'+'a'*32+':18446744073709551616')]:p.request(value,2,'invalid_parameter')
            p.request(dict(phase='status',session_id='fat-tree:'+'a'*32+':1'),3,'tree_session_unknown');p.close()
            p=port();unnegotiated=opening(root/'missing',tree);unnegotiated['phase']='scan'
            p.request(unnegotiated,3,'tree_stream_requires_ndjson');p.close()
            # Four real children retain capacity until actual close/exit, including cancellation.
            p=port();ids=[p.request(opening(path,tree))['session_id'] for _ in range(4)]
            p.request(opening(path,tree),3,'tree_session_capacity')
            listed=p.request({});assert len(listed['sessions'])==4
            cancelled=p.request(call('cancel',ids[0]));assert cancelled['cancellation_requested']
            for sid in ids:close_session(p,sid)
            assert not p.request({})['sessions'];p.close();assert path.read_bytes()==original
            # Individual CLI phases identify their limited process lifetime and close owned readers on exit.
            for mode in ('--json','--format=human'):
                result=subprocess.run([str(args.exe),'filesystem','tree','--phase=open','--path',str(path),'--volume-offset','0','--volume-bytes',str(tree.g['total']*tree.unit),mode],capture_output=True,timeout=15)
                assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
                if mode=='--json':assert json.loads(result.stdout)['result']['process_lifetime_only']
                else:assert b'process_lifetime_only' in result.stdout
                records.append(dict(kind='individual-cli',mode=mode,stdout_sha256=digest(result.stdout),exit_code=0))
            streamed=subprocess.run([str(args.exe),'filesystem','tree','--phase=scan','--path',str(path),'--volume-offset','0','--volume-bytes',str(tree.g['total']*tree.unit),'--format=ndjson'],capture_output=True,timeout=90)
            assert streamed.returncode==0 and not streamed.stderr,streamed.stderr
            lines=streamed.stdout.splitlines();final=json.loads(lines[-1]);assert final['result']['final'] and final['result']['coverage']=='complete' and int(final['result']['pages'])==pages and len(lines)>256
            records.append(dict(kind='complete-cli-stream',envelopes=len(lines),stdout_sha256=digest(streamed.stdout),pages=pages,exit_code=0))
            # Actual GUI retains the same owned session across command navigation.
            ui_tree=Tree(12);ui_tree.directory(files(3));ui_path=root/'ui.img';write(ui_tree,ui_path);ui_original=ui_path.read_bytes()
            command=['filesystem','tree','--phase=open','--path',str(ui_path),'--volume-offset','0','--volume-bytes',str(ui_tree.g['total']*ui_tree.unit)]
            gui=Gui(args.exe,['--gui',*command],render=True)
            try:
                assert not U.IsWindowEnabled(gui.child(110));gui.click(109);assert gui.details().get('reviewed') is True;gui.click(110)
                opened=wait(lambda:gui.details() if 'status' in gui.details() else None);assert opened['status']=='completed';sid=opened['result']['session_id']
                def execute(phase,**fields):
                    gui.click(105);ids=gui.list_ids();gui.choose(next(i for i,row in enumerate(ids) if 'filesystem.tree.inspect' in row));gui.click(108)
                    gui.set_field('phase',phase)
                    for key,value in dict(fields,session_id=sid).items():gui.set_field(key,value)
                    gui.click(109);assert gui.details().get('reviewed') is True;gui.click(110)
                    value=wait(lambda:gui.details() if 'status' in gui.details() else None);assert value['status']=='completed',value
                    records.append(dict(kind='native-gui',phase=phase,response=value,native=gui.observation()))
                    return value['result']
                for _ in range(5):
                    page=execute('next')
                    if 'page' in page:break
                assert 'page' in page
                chunk=execute('read',page_sequence='1',byte_offset='0',byte_count='64');assert chunk['returned_bytes']=='64' and digest(bytes.fromhex(chunk['data']))==chunk['chunk_sha256']
                assert execute('cancel')['cancellation_requested']
                for _ in range(5):
                    closed=execute('close')
                    if closed['state']=='closed':break
                assert closed['state']=='closed' and closed['worker']['worker']['observation']=='exited'
            finally:gui.close()
            assert gui.code==0 and gui.created_files==[] and ui_path.read_bytes()==ui_original
            request_path=root/'console-request.json';request_path.write_text(json.dumps(dict(parameters=opening(ui_path,ui_tree),command=command)),encoding='utf-8',newline='\n')
            for frontend in ('tui','shell'):
                output=root/(frontend+'.json');startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                result=subprocess.run([sys.executable,str(args.root/'tests/frontend/tree_console_fixture.py'),str(args.exe),str(request_path),str(output),frontend,str(args.root)],cwd=root,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=60)
                observed=json.loads(output.read_bytes());assert result.returncode==0,observed
                assert all(observed['restored'].values()) and len(observed['tree_journey'])>=4
                records.append(dict(kind='native-'+frontend,observation=observed))
            assert ui_path.read_bytes()==ui_original
            clean_env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_FAT_TREE_COMMAND_TEST_')}
            for field,mode in [('WORKER','hang'),('WORKER','page_digest'),('REPLY','claims')]:
                env=dict(clean_env);env['DISKED_FAT_TREE_COMMAND_TEST_'+field]=mode
                p=Protocol(args.fault.resolve(),records.append,env);sessions.append(p)
                sid=p.request(opening(ui_path,ui_tree))['session_id']
                if mode=='hang':
                    cancelled=p.request(call('cancel',sid));assert cancelled['cancellation_requested']
                else:
                    deadline=time.monotonic()+5;historical=None
                    while True:
                        value=p.request(call('next',sid),expected=(0,6))
                        if value and 'record' in value:historical=value['record']
                        if value['worker']['status']=='unknown':break
                        if time.monotonic()>deadline:raise AssertionError('fault did not become unresolved')
                        time.sleep(.02)
                    if historical:assert retrieve(p,sid,historical)[0]['frame']['page']['sequence']==historical['page_sequence']
                close_session(p,sid);p.close();assert ui_path.read_bytes()==ui_original
        passed=True
        print('PASS',len(records),'actual tree-session observations;',len(journeys),'complete tree journeys')
        return 0
    finally:
        for p in sessions:p.abort()
        if args.output:args.output.write_text(json.dumps(dict(passed=passed,observations=len(records),journeys=journeys,records=records),indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':raise SystemExit(main())
