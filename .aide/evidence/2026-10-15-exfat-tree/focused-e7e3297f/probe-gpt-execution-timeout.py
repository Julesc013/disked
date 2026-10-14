import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
root=Path.cwd();campaign=root/'.aide-local/exfat-tree-exact-e7e3297f';source=campaign/'source';exe=campaign/'build/Release/gpt_execution_probe.exe'
sys.path.insert(0,str(source/'tests/recovery'))
from test_gpt_restoration import fixture,change_array,expected,request,receipts,send,Replies,close
parent=Path(tempfile.mkdtemp(prefix='gpt-execution-diagnostic-',dir=source/'.aide-local'))
value=fixture();change_array(value,lambda b:b.__setitem__(0,b[0]^1),'backup',False);header=bytearray.fromhex(value['backup']);header[16]^=1;value['backup']=header.hex();case=expected(value,'primary')
env=os.environ.copy();env['DISKED_GPT_FIXTURE_TRACE']='1';start=time.monotonic()
process=subprocess.Popen([str(exe),'--fixture-parent',str(parent)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
rows=Replies(process);observations=[];summary=dict(status='fail',source_revision='e7e3297f6ef707628b607597bb8f7e2d6d76659a',fixture_directory=str(parent),fault=dict(stage='image.write.2',action='crash_after'),reply_deadline_seconds=15,trace_enabled=True,artifact_sha256='sha256:'+hashlib.sha256(exe.read_bytes()).hexdigest())
try:
    send(process,request(case,fault=summary['fault']));prepared=rows.get(timeout=15,phase='preparation');assert prepared['phase']=='prepared' and prepared['definition']==case['definition']
    review,grant=receipts(prepared);send(process,dict(phase='execute',review=review,grant=grant,cancel_at='none'));process.stdin.close();finish=rows.get(timeout=15,phase='execution');code=rows.wait(timeout=15);rows.assert_drained(trace=True)
    assert finish is None and code==112,(finish,code)
    summary.update(status='pass',expected_crash_observed=True,preparation=prepared,exit_code=code)
finally:
    close(process,rows,observations);summary.update(elapsed_seconds=round(time.monotonic()-start,6),process_observations=observations,fixture_retained=True)
    output=root/'.aide-local/gpt-execution-timeout-e7-summary.json';output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({key:summary[key] for key in ['status','elapsed_seconds','exit_code','fixture_directory','artifact_sha256']},indent=2))
