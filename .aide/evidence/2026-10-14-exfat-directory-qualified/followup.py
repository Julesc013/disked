"""Continue terminal selective-build failure after producing missing registry."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd();base=root/'.aide-local/exfat-directory-exact-44c8b090';clone=base/'source';build=base/'build';out=base/'followup';assert not out.exists();out.mkdir();commands=[]
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(name,args):
 args=[str(a) for a in args];start=time.monotonic();r=subprocess.run(args,cwd=clone,capture_output=True);(out/(name+'.log')).write_bytes(r.stdout+r.stderr)
 commands.append(dict(name=name,command=args,cwd=str(clone),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log=name+'.log'));save(out/'commands.json',commands);print(name+': exit '+str(r.returncode),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
 return r.stdout
run('boundaries',['ctest','--test-dir',build,'-C','Release','-R','^build.boundaries$','--output-on-failure'])
gcc=json.loads((clone/'.aide/evidence/2026-10-14-fat-recursive-qualification/gcc-identity.json').read_bytes())['path']
run('c90',[gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only','source/portable/exfat/directory.c'])
for name,args in [('spec-check',['check']),('index',['index','--check']),('manifest',['verify-manifest'])]:run(name,[sys.executable,'-X','utf8','spec/tools/specctl.py',*args])
run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W064','--output',out/'context','--byte-budget','950000'])
run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
identity=json.loads((build/'generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']=='44c8b090b709a76b44ad0e349f647950629c447c' and identity['identity']['source_state']=='clean'
save(out/'build-identity.json',identity);dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for mode in ['headers','imports','dependents']:run(mode,[dumpbin,'/'+mode,build/'Release/exfat_directory_probe.exe'])
cases=json.loads((build/'exfat-directory-cases.json').read_bytes());assert cases['passed'] and cases['methods']==9 and cases['cases']==2316
for name in ['exfat-directory-cases.json','exfat-cases.json','private-header-usage.json']:(out/name).write_bytes((build/name).read_bytes())
shutil.copyfile(out/'context/manifest.json',out/'context-manifest.json')
headers=list(build.glob('disked_exfat_headers.dir/Release/*.obj'));assert len(headers)==1
save(out/'artifact-identities.json',[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in [build/'Release/exfat_directory_probe.exe',*headers]])
assert not run('final-source-status',['git','status','--porcelain']).strip()
inputs=json.loads((base/'source-inputs.json').read_bytes());assert all(sha(clone/p)==digest for p,digest in inputs.items())
save(out/'summary.json',dict(status='pass',source_revision='44c8b090b709a76b44ad0e349f647950629c447c',source_state='clean',methods=9,cases=2316,parser_guard_groups_fresh=10,boundary_group_followup=1,header_compilations_fresh=1,original_native_exit=8,original_failure='Unbuilt generated bootstrap registry in selective build',prior_full_native_revision='1e93836989ea2a9a4e163d0c9644511877455d0e',prior_full_native_groups=130,full_suite_fresh=False,owner_accepted=False,full_0_1_0_complete=False))
