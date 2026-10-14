"""Exact W067 input closure in a clean sparse Git checkout; archived logs excluded."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd();revision='bba3d600001109ad4dd370d5320f9bcda2d06e6e'
out=root/'.aide-local/exfat-capture-exact-bba3d600';assert not out.exists();out.mkdir()
clone=out/'source';build=out/'build';commands=[]
def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,args,cwd=clone,input=None):
    args=[str(a) for a in args];save(out/'current-stage.json',dict(stage=name,status='running',source_revision=revision));start=time.monotonic()
    result=subprocess.run(args,cwd=cwd,input=input,capture_output=True)
    (out/(name+'.log')).write_bytes(result.stdout+result.stderr)
    commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),log=name+'.log'));save(out/'commands.json',commands)
    print(name+': exit '+str(result.returncode),flush=True)
    if result.returncode:save(out/'failure.json',dict(stage=name,exit_code=result.returncode));raise SystemExit(result.returncode)
    return result.stdout
run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,clone],root)
tracked=run('tracked-files',['git','ls-tree','-r','--name-only',revision]).decode('utf-8').splitlines()
registry=json.loads(run('input-registry',['git','show',revision+':spec/catalog/input-dependencies.json']))
catalog=json.loads(run('build-input-catalog',['git','show',revision+':tools/build-inputs.json']))
selected={p for p in tracked if not p.startswith('.aide/') or p.startswith('.aide/programmes/')}
selected|={i['path'] for i in registry['inputs']}|set(catalog['files'])|set(registry['always'])
assert selected<=set(tracked)
save(out/'checkout-selection.json',dict(kind='clean-sparse-git-checkout',selected_files=sorted(selected),excluded_files=len(set(tracked)-selected),scope='All current implementation/tests/spec/docs/tools/external roots and every registered/build input are present. Unused historical evidence is excluded; no claim of a full archive checkout.'))
run('sparse-init',['git','sparse-checkout','init','--no-cone'])
patterns=('\n'.join('/'+p for p in sorted(selected))+'\n').encode()
(out/'sparse-patterns.txt').write_bytes(patterns)
run('sparse-selection',['git','sparse-checkout','set','--no-cone','--stdin'],input=patterns)
run('checkout',['git','checkout','--detach',revision]);assert not run('initial-source-status',['git','status','--porcelain']).strip()
assert all((clone/p).is_file() for p in selected)
inputs={p:sha(clone/p) for p in sorted(selected)};save(out/'source-inputs.json',inputs)
run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build',build,'--config','Release','--target','bootstrap_registry','exfat_capture_probe','disked_exfat_capture_headers','exfat_probe','exfat_directory_probe','exfat_allocation_probe','exfat_upcase_probe','fat_capture_probe','fat_capture_fault','fat_content_probe','fat_probe','fat_directory_probe','gpt_probe','--parallel','4'])
pattern='^(portable.exfat|portable.exfat_guard|portable.exfat_directory|portable.exfat_directory_guard|portable.exfat_allocation|portable.exfat_allocation_guard|portable.exfat_upcase|portable.exfat_upcase_guard|portable.fat|portable.fat_guard|portable.fat_directory|portable.fat_directory_guard|portable.gpt|portable.gpt_guard|build.boundaries|image.exfat_capture|image.fat_capture|image.fat_content|portable.fat_cell_guard)$'
run('native',['ctest','--test-dir',build,'-C','Release','-R',pattern,'--output-on-failure'])
run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'])
for name,args in [('spec-check',['check']),('index',['index','--check']),('manifest',['verify-manifest'])]:run(name,[sys.executable,'-X','utf8','spec/tools/specctl.py',*args])
run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W067','--output',out/'context','--byte-budget','1050000'])
run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
identity=json.loads((build/'generated/build-identity.json').read_bytes());dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');artifact=build/'Release/exfat_capture_probe.exe'
for mode in ['headers','imports','dependents']:run(mode,[dumpbin,'/'+mode,artifact])
for name in ['exfat-capture-cases.json','exfat-cases.json','exfat-directory-cases.json','exfat-allocation-cases.json','exfat-upcase-cases.json','private-header-usage.json']:shutil.copyfile(build/name,out/name)
shutil.copyfile(build/'generated/build-identity.json',out/'build-identity.json')
shutil.copyfile(out/'context/manifest.json',out/'context-manifest.json')
cases=json.loads((out/'exfat-capture-cases.json').read_bytes());assert cases['passed'] and cases['cases']==121 and cases['methods']==9
headers=list(build.glob('disked_exfat_capture_headers.dir/Release/*.obj'));assert len(headers)==1
save(out/'artifact-identities.json',[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in [artifact,*headers]])
assert not run('final-source-status',['git','status','--porcelain']).strip()
assert all(sha(clone/p)==digest for p,digest in inputs.items())
save(out/'summary.json',dict(status='pass',source_revision=revision,source_state='clean_sparse',native_groups_fresh=19,header_compilations_fresh=1,cases=121,methods=9,full_native_suite_fresh=False,owner_accepted=False,full_0_1_0_complete=False))
save(out/'current-stage.json',dict(stage='complete',status='pass',source_revision=revision))
