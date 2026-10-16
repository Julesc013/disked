"""Qualify the preparation-timeout phase correction; not the original stall cause."""
import argparse,hashlib,json,platform,re,subprocess,sys,time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    root=a.root.resolve();out=a.output.resolve();out.mkdir(exist_ok=False);build=out/'build';py=Path(sys.executable)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    paths=set(json.loads((root/'tools/build-inputs.json').read_bytes())['files'])
    paths.update(x['path'] for x in json.loads((root/'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    paths.update(p.relative_to(root).as_posix() for p in (root/'source').rglob('*') if p.is_file())
    before={p:sha(root/p) for p in sorted(paths)}
    summary=dict(status='running',source_revision=revision,source_status_before=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True),host=platform.platform(),python=sys.version,
        scope='Four selected x64 export/frontend/watch groups and tooling/source/import/context checks. No full native, original-stall resolution, other-platform, owner or release qualification.',stages=[],original_timeout_cause_established=False,full_native_suite_run=False,owner_accepted=False,full_0_1_0_complete=False)
    def save():
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    def run(name,command):
        command=list(map(str,command));start=time.monotonic();print('BEGIN',name,flush=True)
        with (out/(name+'.log')).open('wb') as log:r=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        summary['stages'].append(dict(name=name,command=command,cwd=str(root),exit_code=r.returncode,seconds=time.monotonic()-start,log=name+'.log'));save();print('END',name,r.returncode,flush=True)
        if r.returncode:raise RuntimeError(name+' failed; retained original result')
    (out/'inputs.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8',newline='\n')
    try:
        run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+str(py)])
        run('build',['cmake','--build',build,'--config','Release','--target','bootstrap_registry','disked','disked_report_test','export_command_probe','export_command_fault','--parallel','4'])
        run('native',['ctest','--test-dir',build,'-C','Release','--verbose','--output-on-failure','--output-junit',out/'native-junit.xml','-R',r'^(frontend\.(product_export|joined_report)|evidence\.(export_commands|report_watch))$'])
        tests=ET.parse(out/'native-junit.xml').getroot().findall('.//testcase')
        expected={'frontend.product_export','frontend.joined_report','evidence.export_commands','evidence.report_watch'}
        assert len(tests)==4 and {test.attrib['name'] for test in tests}==expected
        assert all(test.find('failure') is None and test.find('error') is None for test in tests)
        summary['native_groups']=sorted(expected)
        identity=json.loads((build/'generated/build-identity.json').read_bytes());summary['build_identity']=identity
        dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');summary['artifacts']=[]
        for name in ['disked','disked_report_test','export_command_probe','export_command_fault']:
            path=build/'Release'/(name+'.exe');summary['artifacts'].append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
            for mode in ['headers','imports','dependents']:run(name+'-'+mode,[dumpbin,'/'+mode,path])
            headers=(out/(name+'-headers.log')).read_text()
            assert all(s in headers for s in ['8664 machine (x64)','Dynamic base','NX compatible','Control Flow Guard'])
        run('boundaries',[py,'tools/check-build-boundaries.py','--build',build,'--output',out/'build-boundaries.json'])
        for name,options in [('source-map',['tools/check-source-map.py']),('index',['spec/tools/specctl.py','index','--check']),('structural',['spec/tools/specctl.py','check']),('tooling',['-m','unittest','discover','-s','spec/tools/tests','-v']),('manifest',['spec/tools/specctl.py','verify-manifest'])]:run(name,[py,*options])
        run('context',[py,'spec/tools/specctl.py','context','--work','DE-W034','--output',out/'context','--byte-budget','700000','--artifact-byte-budget','16777216'])
        run('verify-context',[py,'spec/tools/specctl.py','verify-context',out/'context'])
        summary['inputs_unchanged']=all(sha(root/p)==h for p,h in before.items())
        summary['source_status_after']=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
        assert summary['inputs_unchanged'] and not summary['source_status_before'] and not summary['source_status_after']
        assert 'Ran 242 tests' in (out/'tooling.log').read_text() and 'OK (skipped=2)' in (out/'tooling.log').read_text()
        summary['status']='pass'
    except BaseException as error:
        summary['status']='fail';summary['error']=repr(error);save();raise
    save();print('PASS selected export preparation correction; original main gate remains.',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
