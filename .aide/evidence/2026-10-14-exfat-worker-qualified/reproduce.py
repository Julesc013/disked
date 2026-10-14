"""Exact full current-native campaign after the shared retirement change."""
import hashlib,json,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
root=Path.cwd();revision='cce05d172c89f0a71dba5ee1cc0698307f8c686e'
out=root/'.aide-local/exfat-worker-full-cce05d17';assert not out.exists();out.mkdir()
clone=out/'source';build=out/'build';commands=[]
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=clone):
    args=[str(a) for a in args];save(out/'current-stage.json',dict(stage=name,status='running',source_revision=revision));start=time.monotonic()
    result=subprocess.run(args,cwd=cwd,capture_output=True);(out/(name+'.log')).write_bytes(result.stdout+result.stderr)
    commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),log=name+'.log'));save(out/'commands.json',commands)
    print(name+': exit '+str(result.returncode),flush=True)
    if result.returncode:save(out/'failure.json',dict(stage=name,exit_code=result.returncode));raise SystemExit(result.returncode)
    return result.stdout
run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,clone],root)
run('checkout',['git','checkout','--detach',revision]);assert not run('initial-source-status',['git','status','--porcelain']).strip()
catalog=json.loads((clone/'tools/build-inputs.json').read_bytes());registry=json.loads((clone/'spec/catalog/input-dependencies.json').read_bytes())
paths=set(catalog['files'])|set(registry['always'])|{i['path'] for i in registry['inputs']}
paths|={p.relative_to(clone).as_posix() for folder in ['source','tests'] for p in (clone/folder).rglob('*') if p.is_file()}
inputs={p:sha(clone/p) for p in sorted(paths)};save(out/'source-inputs.json',inputs)
run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build',build,'--config','Release','--parallel','4'])
inventory=json.loads(run('native-inventory',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1']));save(out/'native-inventory.json',inventory)
run('native',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',out/'native-junit.xml'])
report=ET.parse(out/'native-junit.xml').getroot();cases=list(report.iter('testcase'));assert len(cases)==len(inventory['tests']) and not list(report.iter('failure')) and not list(report.iter('error'))
run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'])
for name,args in [('spec-check',['check']),('index',['index','--check']),('manifest',['verify-manifest'])]:run(name,[sys.executable,'-X','utf8','spec/tools/specctl.py',*args])
run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W069','--output',out/'context','--byte-budget','1200000'])
run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
identity=json.loads((build/'generated/build-identity.json').read_bytes());dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
artifacts=[]
for probe in ['disked','exfat_worker_probe','exfat_worker_fault']:
    artifact=build/'Release'/(probe+'.exe');artifacts.append(dict(path=str(artifact),bytes=artifact.stat().st_size,sha256=sha(artifact)))
    for mode in ['headers','imports','dependents']:run(probe+'-'+mode,[dumpbin,'/'+mode,artifact])
headers=list(build.glob('*_headers.dir/Release/*.obj'));assert len(headers)>=44
save(out/'artifact-identities.json',artifacts+[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in headers])
for name in ['exfat-worker-cases.json','exfat-file-cases.json','exfat-capture-cases.json','private-header-usage.json']:shutil.copyfile(build/name,out/name)
shutil.copyfile(build/'generated/build-identity.json',out/'build-identity.json');shutil.copyfile(out/'context/manifest.json',out/'context-manifest.json')
worker=json.loads((out/'exfat-worker-cases.json').read_bytes());assert worker['passed'] and worker['cases']==69 and worker['methods']==6
assert not run('final-source-status',['git','status','--porcelain']).strip();assert all(sha(clone/p)==digest for p,digest in inputs.items())
save(out/'summary.json',dict(status='pass',source_revision=revision,source_state='clean_full_checkout',native_groups_fresh=len(cases),header_compilations_fresh=len(headers),worker_cases=69,worker_methods=6,file_cases=63,file_methods=8,full_current_native_suite_fresh=True,owner_accepted=False,full_0_1_0_complete=False))
save(out/'current-stage.json',dict(stage='complete',status='pass',source_revision=revision))
