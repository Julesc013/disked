"""One full current Windows native campaign for the shared acquisition routing fix."""
import argparse,hashlib,json,platform,re,subprocess,sys,time,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    root=a.root.resolve();out=a.output.resolve();out.mkdir(exist_ok=False);build=out/'build';py=Path(sys.executable)
    inputs=set(json.loads((root/'tools/build-inputs.json').read_bytes())['files'])
    inputs.update(x['path'] for x in json.loads((root/'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    inputs.update(p.relative_to(root).as_posix() for p in (root/'source').rglob('*') if p.is_file())
    before={p:sha(root/p) for p in sorted(inputs)};(out/'inputs.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8',newline='\n')
    result=dict(status='running',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_status_before=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True),host=platform.platform(),python=sys.version,stages=[],
        scope='One complete registered Windows x64 native suite plus tooling/build/source/import/context evidence for current prototype code. Not all original platforms/storage, hardware, owner or release qualification.',owner_accepted=False,full_0_1_0_complete=False,original_delay_cause_established=False)
    def save():(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    def run(name,command):
        command=list(map(str,command));print('BEGIN',name,flush=True);start=time.monotonic()
        with (out/(name+'.log')).open('wb') as log:p=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        result['stages'].append(dict(name=name,command=command,cwd=str(root),exit_code=p.returncode,seconds=time.monotonic()-start,log=name+'.log'));save();print('END',name,p.returncode,flush=True);return p.returncode
    try:
        assert run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+str(py)])==0
        assert run('build',['cmake','--build',build,'--config','Release','--parallel','4'])==0
        assert run('registered',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1'])==0
        expected={x['name'] for x in json.loads((out/'registered.log').read_bytes())['tests']}
        result['native_exit_code']=run('native',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',out/'native-junit.xml'])
        tests=ET.parse(out/'native-junit.xml').getroot().findall('.//testcase')
        assert len(tests)==len(expected) and {t.attrib['name'] for t in tests}==expected
        result['native_groups']=len(tests);result['native_failed']=[t.attrib['name'] for t in tests if t.find('failure') is not None or t.find('error') is not None]
        result['native_skipped']=[t.attrib['name'] for t in tests if t.find('skipped') is not None]
        result['native_passed']=len(tests)-len(result['native_failed'])-len(result['native_skipped'])
        identity=json.loads((build/'generated/build-identity.json').read_bytes());result['build_identity']=identity;dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');result['artifacts']=[]
        for name in ['disked','disked_image_test','acquisition_command_probe']:
            path=build/'Release'/(name+'.exe');result['artifacts'].append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
            for mode in ['headers','imports','dependents']:run(name+'-'+mode,[dumpbin,'/'+mode,path])
            header=(out/(name+'-headers.log')).read_text();assert all(s in header for s in ['8664 machine (x64)','Dynamic base','NX compatible','Control Flow Guard'])
        objects=[p for directory in build.glob('*_headers.dir') for p in (directory/'Release').glob('*.obj')]
        result['standalone_headers']=len(objects);result['header_artifacts']=[dict(path=str(p),sha256=sha(p)) for p in sorted(objects)]
        run('boundaries',[py,'tools/check-build-boundaries.py','--build',build,'--output',out/'build-boundaries.json'])
        for name,args in [('source-map',['tools/check-source-map.py']),('index',['spec/tools/specctl.py','index','--check']),('structural',['spec/tools/specctl.py','check']),('tooling',['-m','unittest','discover','-s','spec/tools/tests','-v']),('manifest',['spec/tools/specctl.py','verify-manifest'])]:run(name,[py,*args])
        run('context',[py,'spec/tools/specctl.py','context','--work','DE-W033','--output',out/'context','--byte-budget','1200000','--artifact-byte-budget','16777216'])
        run('verify-context',[py,'spec/tools/specctl.py','verify-context',out/'context'])
        result['inputs_unchanged']=all(sha(root/p)==h for p,h in before.items());result['source_status_after']=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
        result['status']='pass' if not result['native_failed'] and not result['native_skipped'] and all(s['exit_code']==0 for s in result['stages']) and result['inputs_unchanged'] and not result['source_status_before'] and not result['source_status_after'] else 'fail'
    except BaseException as error:result['status']='fail';result['error']=repr(error);save();raise
    save();print(result['status'],result.get('native_passed'),result.get('native_failed'),flush=True);return 0 if result['status']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
