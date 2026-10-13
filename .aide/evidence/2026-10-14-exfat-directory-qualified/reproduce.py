"""Exact committed W064 decoder qualification; no claim of a fresh full suite."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd();revision='44c8b090b709a76b44ad0e349f647950629c447c'
out=root/'.aide-local/exfat-directory-exact-44c8b090';assert not out.exists();out.mkdir();commands=[]
clone=out/'source';build=out/'build'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(name,args,cwd=clone,input=None):
 args=[str(a) for a in args];start=time.monotonic();save(out/'current-stage.json',dict(stage=name,status='running',source_revision=revision))
 result=subprocess.run(args,cwd=cwd,input=input,capture_output=True)
 (out/(name+'.log')).write_bytes(result.stdout+result.stderr)
 commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),log=name+'.log'));save(out/'commands.json',commands)
 print(name+': exit '+str(result.returncode),flush=True)
 if result.returncode:save(out/'failure.json',dict(stage=name,exit_code=result.returncode));raise SystemExit(result.returncode)
 return result.stdout
run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,clone],root)
run('checkout',['git','checkout','--detach',revision]);assert not run('source-status',['git','status','--porcelain']).strip()
catalog=json.loads((clone/'tools/build-inputs.json').read_bytes());paths=set(catalog['files'])
paths|={p.relative_to(clone).as_posix() for folder in ['source','tests/property','tests/unit'] for p in (clone/folder).rglob('*') if p.is_file()}
paths|={'AGENTS.md','spec/catalog/input-dependencies.json','spec/work/units.json','spec/tools/specctl.py'}
inputs={p:sha(clone/p) for p in sorted(paths)};save(out/'source-inputs.json',inputs)
prior=json.loads((root/'.aide-local/exfat-qualification-1e938369/source-inputs.json').read_bytes())
changed={p:dict(old=prior.get(p),new=inputs[p]) for p in inputs if p not in prior or inputs[p]!=prior[p]}
save(out/'changes-from-prior-regression.json',changed)
assert all(p in {'source/portable/exfat/exfat.h','source/portable/exfat/directory.c'} for p in changed if p.startswith('source/'))
run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build',build,'--config','Release','--target','exfat_directory_probe','exfat_probe','disked_exfat_headers','fat_directory_probe','fat_probe','gpt_probe','--parallel','4'])
run('native',['ctest','--test-dir',build,'-C','Release','-R','^(portable.exfat|portable.exfat_guard|portable.exfat_directory|portable.exfat_directory_guard|portable.fat|portable.fat_guard|portable.fat_directory|portable.fat_directory_guard|portable.gpt|portable.gpt_guard|build.boundaries)$','--output-on-failure'])
gcc=json.loads((clone/'.aide/evidence/2026-10-14-fat-recursive-qualification/gcc-identity.json').read_bytes())['path']
run('c90',[gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only','source/portable/exfat/directory.c'])
run('spec-check',[sys.executable,'-X','utf8','spec/tools/specctl.py','check'])
run('index',[sys.executable,'-X','utf8','spec/tools/specctl.py','index','--check'])
run('manifest',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W064','--output',out/'context','--byte-budget','950000'])
run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
identity=json.loads((build/'generated/build-identity.json').read_bytes());dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for mode in ['headers','imports','dependents']:run(mode,[dumpbin,'/'+mode,build/'Release/exfat_directory_probe.exe'])
cases=json.loads((build/'exfat-directory-cases.json').read_bytes());assert cases['passed'] and cases['methods']==9 and cases['cases']==2316
for name in ['exfat-directory-cases.json','exfat-cases.json','private-header-usage.json']:(out/name).write_bytes((build/name).read_bytes())
shutil.copyfile(out/'context/manifest.json',out/'context-manifest.json')
header=list(build.glob('disked_exfat_headers.dir/Release/*.obj'));assert len(header)==1
artifact=build/'Release/exfat_directory_probe.exe'
save(out/'artifact-identities.json',[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in [artifact,*header]])
assert not run('final-source-status',['git','status','--porcelain']).strip()
assert all(sha(clone/p)==digest for p,digest in inputs.items())
save(out/'summary.json',dict(status='pass',source_revision=revision,source_state='clean',methods=9,cases=2316,native_groups_fresh=11,header_compilations_fresh=1,prior_full_native_revision='1e93836989ea2a9a4e163d0c9644511877455d0e',prior_full_native_groups=130,full_suite_fresh=False,owner_accepted=False,full_0_1_0_complete=False))
save(out/'current-stage.json',dict(stage='complete',status='pass',source_revision=revision))
