"""Diagnostic wrapper; keeps the existing test and its process-exit waits exact."""
import argparse,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-revision',required=True);a=p.parse_args();root=a.repository.resolve();out=a.output.resolve();out.mkdir();assert len(a.source_revision)==40
source=root/'tests/frontend/test_product_export.py';data=source.read_bytes();assert data==subprocess.check_output(['git','show',a.source_revision+':tests/frontend/test_product_export.py'],cwd=root)
build=root/'build/windows-bootstrap';product=build/'Release/disked.exe';fault=build/'Release/disked_report_test.exe';probe=build/'Release/export_command_probe.exe'
assert all(x.is_file() for x in (product,fault,probe));identity=json.loads((build/'generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==a.source_revision and identity['identity']['source_state']=='clean'
sys.path.insert(0,str(source.parent));spec=importlib.util.spec_from_file_location('diagnostic_product_export',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
raw_wait=module.K.WaitForSingleObject;raw_close=module.K.CloseHandle;raw_process=module.report_process;observed={};events=[];start=time.monotonic();trace=out/'waits.ndjson'
def handle_key(handle):return int(getattr(handle,'value',handle) or 0)
def save(value):
 value['elapsed_seconds']=round(time.monotonic()-start,6);events.append(value)
 with trace.open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(value,separators=(',',':'))+'\n')
def process(state,exe):
 handle=raw_process(state,exe)
 if handle:observed[handle_key(handle)]=dict(binding=state['binding'],phase=state['phase'],sequence=state['sequence'],executable=str(exe));save(dict(kind='creation_verified_report_handle',handle=handle_key(handle),**observed[handle_key(handle)]))
 else:save(dict(kind='report_process_already_absent',binding=state['binding'],phase=state['phase']))
 return handle
def wait(handle,milliseconds):
 before=time.monotonic();result=raw_wait(handle,milliseconds);key=handle_key(handle)
 if key in observed:
  save(dict(kind='actual_wait',handle=key,milliseconds=milliseconds,result=result,duration_seconds=round(time.monotonic()-before,6),**observed[key]))
 return result
def close(handle):
 result=raw_close(handle)
 if result:observed.pop(handle_key(handle),None)
 return result
module.report_process=process;module.K.WaitForSingleObject=wait;module.K.CloseHandle=close
sys.argv=[str(source),'--product',str(product),'--fault',str(fault),'--probe',str(probe),'--root',str(root),'--joined','--evidence',str(out/'results.json')]
status='pass';error=None
try:module.main()
except BaseException as caught:status='fail';error=repr(caught);raise
finally:
 module.K.WaitForSingleObject=raw_wait;module.K.CloseHandle=raw_close;module.report_process=raw_process
 value=dict(status=status,error=error,source_revision=a.source_revision,original_test_sha256='sha256:'+hashlib.sha256(data).hexdigest(),product_sha256='sha256:'+hashlib.sha256(product.read_bytes()).hexdigest(),fault_sha256='sha256:'+hashlib.sha256(fault.read_bytes()).hexdigest(),probe_sha256='sha256:'+hashlib.sha256(probe.read_bytes()).hexdigest(),trace_events=len(events),diagnostic_only=True,existing_waits_unchanged=True,original_failure_cause_established=False)
 (out/'diagnostic-summary.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8',newline='\n')
