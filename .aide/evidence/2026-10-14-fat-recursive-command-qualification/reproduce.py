"""Full exact-source DE-W057 campaign, ordinary generated files only."""
import hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd().resolve();revision=sys.argv[1]
clone=root/('.aide-local/recursive-normal-clean-'+revision[:8])
out=root/('.aide-local/recursive-normal-qualification-'+revision[:8])
assert clone.is_relative_to(root/'.aide-local') and out.is_relative_to(root/'.aide-local')
assert not clone.exists() and not out.exists()
out.mkdir();(out/'logs').mkdir();commands=[]
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(name,args,cwd=clone,input=None,timeout=900):
 args=[str(a) for a in args];start=time.monotonic()
 save(out/'current-stage.json',dict(stage=name,status='running',source_revision=revision))
 try:r=subprocess.run(args,cwd=cwd,capture_output=True,input=input,timeout=timeout)
 except subprocess.TimeoutExpired as error:
  (out/'logs'/(name+'.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
  save(out/'failure.json',dict(stage=name,status='deadline',owned_child_exit_unverified=True));raise
 (out/'logs'/(name+'.log')).write_bytes(r.stdout+r.stderr)
 commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+name+'.log'))
 save(out/'commands.json',commands);print(name+': exit '+str(r.returncode),flush=True)
 if r.returncode:save(out/'failure.json',dict(stage=name,exit_code=r.returncode));raise RuntimeError(name)
 return r.stdout
run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,clone],cwd=root)
run('checkout',['git','checkout','--detach',revision]);assert not run('source-status',['git','status','--porcelain']).strip()
host=json.loads(run('host',['powershell','-NoProfile','-Command',
 '$qualificationIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();'
 '$qualificationPrincipal=[System.Security.Principal.WindowsPrincipal]::new($qualificationIdentity);'
 '$qualificationOS=Get-CimInstance Win32_OperatingSystem;'
 '[ordered]@{identity=$qualificationIdentity.Name;elevated=$qualificationPrincipal.IsInRole('
 '[System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$qualificationOS.Caption;'
 'version=$qualificationOS.Version;architecture=$qualificationOS.OSArchitecture}|ConvertTo-Json -Compress']))
assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
catalog=json.loads((clone/'tools/build-inputs.json').read_bytes())
names=set(catalog['files'])|{p.relative_to(clone).as_posix() for folder in ('source','spec/schemas','spec/tools/tests') for p in (clone/folder).rglob('*') if p.is_file()}
names|={'AGENTS.md','spec/work/units.json','spec/catalog/input-dependencies.json','spec/tools/specctl.py','tools/check-source-map.py','tools/check-build-boundaries.py'}
inputs={p:sha((clone/p).read_bytes()) for p in sorted(names)};save(out/'source-inputs.json',inputs)
rows=run('source-tree',['git','cat-file','--batch-check'],input=('\n'.join(revision+':'+p for p in inputs)+'\n').encode()).splitlines();assert len(rows)==len(inputs)
blobs={}
for path,row in zip(inputs,rows,strict=True):
 blob,kind,size=row.split();data=(clone/path).read_bytes();assert kind==b'blob' and int(size)==len(data)
 assert hashlib.sha1(b'blob '+size+b'\0'+data).hexdigest()==blob.decode();blobs[path]=blob.decode()
save(out/'source-blob-bindings.json',blobs)
run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'])
run('cmake-version',['cmake','--version'])
build=out/'build'
run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build',build,'--config','Release','--parallel','4'],timeout=2400)
identity=json.loads((build/'generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean'
assert identity['inputs']=={p:inputs[p] for p in catalog['files']};save(out/'build-identity.json',identity)
run('boundaries',[sys.executable,'-X','utf8','tools/check-build-boundaries.py','--build',build,'--output',out/'build-boundaries.json'])
tests=json.loads(run('test-catalog',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1']))
registered={t['name'] for t in tests['tests']}
assert {'frontend.fat_recursive_product','frontend.fat_recursive_failures','image.fat_tree_commands',
 'acquisition.fat_tree_review','image.fat_tree_controller','image.fat_tree_admission','image.fat_tree_reconnect',
 'image.fat_tree_watch','image.fat_tree_extraction_worker','frontend.fat_tree_sessions','build.boundaries'}.issubset(registered)
save(out/'test-catalog.json',tests)
run('native-tests',['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure'],timeout=3600)
shutil.copyfile(build/'Testing/Temporary/LastTest.log',out/'native-details.log')
focused={}
for name in ('fat-recursive-product-cases.json','fat-recursive-failure-cases.json','fat-tree-watch-cases.json','fat-tree-command-cases.json','fat-tree-review-cases.json','fat-tree-admission-cases.json','fat-tree-controller-cases.json','fat-tree-reconnect-cases.json'):
 data=json.loads((build/name).read_bytes());assert data['passed'],name;save(out/name,data)
 focused[name]={k:data[k] for k in ('checks','methods','cases','observations') if k in data and isinstance(data[k],(int,bool,str))}
run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'],timeout=1200)
tool=(out/'logs/tooling.log').read_text(encoding='utf-8');match=re.search(r'^Ran ([0-9]+) tests ',tool,re.M);assert match and re.search(r'^OK \(skipped=2\)$',tool,re.M)
structure=json.loads(run('spec-check',[sys.executable,'-X','utf8','spec/tools/specctl.py','check']))
run('index',[sys.executable,'-X','utf8','spec/tools/specctl.py','index','--check'])
run('manifest',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W057','--output',out/'context','--byte-budget','950000'])
run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
shutil.copyfile(out/'context/manifest.json',out/'context-manifest.json')
launch=json.loads(run('product-launch',[build/'Release/disked.exe','build','inspect','--json']))['result']
assert launch['source_revision']==revision and launch['source_state']=='clean' and launch['version']=='0.1.0-dev.55'
discovery=json.loads(run('command-discovery',[build/'Release/disked.exe','command','list','--json']))['result']['commands']
assert next(c for c in discovery if c['id']=='filesystem.tree.extract')['availability']=='available'
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');artifacts=[]
for name in ('disked','disked_recursive_fault','disked_recursive_disabled','fat_tree_command_probe','fat_tree_controller_probe','fat_tree_reconnect_probe'):
 path=build/'Release'/(name+'.exe')
 for mode in ('headers','imports','dependents'):run(name+'-'+mode,[dumpbin,'/'+mode,path])
 artifacts.append(dict(kind=name,path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()),source_revision=revision))
objects=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(build.glob('*_headers.dir/Release/*.obj'))]
expected=sum(len(row.split())-1 for row in re.findall(r'^  private_header_check\(([^)]+)\)',(clone/'CMakeLists.txt').read_text(),re.M));assert len(objects)==expected
save(out/'header-objects.json',objects);shutil.copyfile(build/'private-header-usage.json',out/'private-header-usage.json')
assert not run('final-source-status',['git','status','--porcelain']).strip()
assert all(sha((clone/p).read_bytes())==digest for p,digest in inputs.items())
save(out/'summary.json',dict(source_revision=revision,source_state='clean',host=host,passed=True,
 native_test_groups=len(tests['tests']),header_compilations=len(objects),tooling_run=int(match.group(1)),tooling_skips=2,
 source_inputs=len(inputs),structural=structure,artifacts=artifacts,focused_cases=focused,
 ordinary_recursive_command_qualified=True,physical_device_access=False,owner_accepted=False,full_0_1_0_complete=False,release_ready=False))
save(out/'current-stage.json',dict(stage='complete',status='passed',source_revision=revision))
print('Full clean normal recursive campaign completed.',flush=True)
