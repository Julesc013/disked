"""One fresh original two-MiB fixture; retain its state and existing deadlines."""
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
root=Path.cwd();campaign=root/'.aide-local/exfat-tree-exact-e7e3297f';source=campaign/'source';release=campaign/'build/Release'
sys.path.insert(0,str(source/'tests/images'))
from test_acquisition_worker import canonical,source_bytes,map_check,history_check
parent=Path(tempfile.mkdtemp(prefix='acq-timeout-diagnostic-',dir=source/'.aide-local'))
state=parent/'state';state.mkdir();image=parent/'source.img';data=source_bytes(2097153);image.write_bytes(data)
probe=release/'acquisition_command_probe.exe';disked=release/'disked.exe'
env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
receipts=[]
def request(command,parameters):
    return dict(schema='org.disked.request/1',request_id='timeout-diagnostic',command=command,parameters=parameters,required_features=[])
def call(label,binary,payload,delay=False):
    selected=dict(env)
    if delay:selected['DISKED_ACQ_WORKER_TEST_CHECKPOINT_DELAY']='1'
    started=time.monotonic();result=subprocess.run([str(binary)] if binary==probe else [str(binary),'protocol','serve','--format','json'],input=canonical(payload)+b'\n',capture_output=True,cwd=source,env=selected,timeout=15)
    elapsed=time.monotonic()-started;assert result.returncode in (0,5) and not result.stderr,(label,result.returncode,result.stdout,result.stderr)
    rows=[json.loads(line) for line in result.stdout.splitlines()];assert len(rows)==1
    receipts.append(dict(label=label,elapsed_seconds=round(elapsed,6),exit_code=result.returncode,response=rows[0]));return rows[0]
summary=dict(status='fail',source_revision='e7e3297f6ef707628b607597bb8f7e2d6d76659a',fixture_directory=str(parent),fixture_retained=True,deadline_seconds=30,reply_deadline_seconds=15,
    probe_sha256='sha256:'+hashlib.sha256(probe.read_bytes()).hexdigest(),disked_sha256='sha256:'+hashlib.sha256(disked.read_bytes()).hexdigest())
op=None;started=time.monotonic()
try:
    parameters=dict(phase='prepare',source=str(image),destination=str(parent/'copy.img'),map=str(parent/'copy.map'),state_directory=str(state))
    prepared=call('prepare',probe,dict(mode='request',request=request('image.acquire',parameters)))['result']
    grant=dict(phase='execute',definition=prepared['definition'],definition_digest=prepared['definition_digest'],allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
    first=call('start',probe,dict(mode='request',request=request('image.acquire',grant)),delay=True)
    op=dict(operation_id=first['operation_id'],state_directory=str(state));deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        observed=call('inspect',disked,request('operation.inspect',op));current=observed['result']['state']
        if current['phase']=='finished':
            assert current['quiescent'] and current['outcome']['status']=='completed',current
            assert (parent/'copy.img').read_bytes()==data
            map_check(parent/'copy.map',data);history_check(state/'acquisition.records')
            summary.update(status='pass',elapsed_seconds=round(time.monotonic()-started,6),final_state=current)
            break
        time.sleep(.03)
    else:
        summary.update(reason='Original thirty-second finish deadline exceeded; retain dependencies.',last_state=current)
        cancelled=call('cancel',disked,request('operation.cancel',op));summary['cancel_response']=cancelled
finally:
    summary['receipts']=receipts
    (root/'.aide-local/acquisition-timeout-e7-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('receipts','final_state','last_state','cancel_response')},indent=2))
