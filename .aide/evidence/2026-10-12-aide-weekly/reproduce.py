import hashlib,json,re,subprocess,sys,time
from pathlib import Path
root=Path.cwd();source='58a888c07832cbf4edfaf64dfbd165fcb00e618e';clone=root/'.aide-local/owned-layout-clean-2c731a1c/checkout';out=root/'.aide-local/aide-weekly-clean';out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8',newline='\n')
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def run(name,args,limit=300):
 args=list(map(str,args));started=time.monotonic();r=subprocess.run(args,cwd=clone,capture_output=True,timeout=limit);p=logs/(name+'.log');p.write_bytes(r.stdout+r.stderr);commands.append(dict(name=name,command=args,cwd=str(clone),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-started,3),log='logs/'+p.name));save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True);assert r.returncode==0,name;return r.stdout
assert Path(run('origin',['git','remote','get-url','origin']).decode().strip()).resolve()==root;assert not run('before-status',['git','status','--porcelain']).strip();run('fetch',['git','fetch','--no-tags','origin',source]);run('checkout',['git','checkout','--detach',source]);assert not run('source-status',['git','status','--porcelain']).strip()
lock=json.loads((clone/'spec/references/aide-lock.json').read_bytes());upstream=root/lock['checkout'];assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()==lock['revision']
for x in lock['files']:assert sha((upstream/x['path']).read_bytes())==x['sha256']
run('export',[sys.executable,'spec/tools/specctl.py','aide-export','--output',out/'export']);import jsonschema
schema=json.loads((upstream/'.aide/protocol/aide-workunit.schema.json').read_bytes());jsonschema.Draft202012Validator.check_schema(schema);validator=jsonschema.Draft202012Validator(schema);records=sorted((out/'export').glob('*.json'));assert len(records)==36
for p in records:
 v=json.loads(p.read_bytes());validator.validate(v);assert v['kind']=='WorkUnit' and v['spec']['authorizes_implementation'] is False and v['status']['phase']=='planned' and v['status']['result']=='NOT_RUN' and not v['status']['validated']
run('tooling',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);text=(logs/'tooling.log').read_text();assert re.search(r'^Ran 215 tests ',text,re.MULTILINE) and re.search(r'^OK \(skipped=2\)$',text,re.MULTILINE)
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']));run('index',[sys.executable,'spec/tools/specctl.py','index','--check']);run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']);run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W061','--output',out/'context','--byte-budget','480000']);run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context']);assert not run('final-status',['git','status','--porcelain']).strip()
product=json.loads((root/'.aide/evidence/2026-10-12-job-coexistence/reproduction-98a5b593/build-identity.json').read_bytes());assert all(sha((clone/n).read_bytes())==d for n,d in product['inputs'].items())
inputs={}
for folder in ('spec','.aide/protocol'):
 for p in (clone/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:inputs[p.relative_to(clone).as_posix()]=sha(p.read_bytes())
inputs['.aide/integration.json']=sha((clone/'.aide/integration.json').read_bytes());save(out/'source-inputs.json',inputs)
save(out/'results.json',dict(status='pass',source_revision=source,aide_revision=lock['revision'],aide_tree=lock['tree'],validated_workunits=36,tooling=dict(run=215,passed=213,skipped=2),structural_checks=check['checks'],source_inputs=len(inputs),native_product_input_comparison=dict(source_revision=product['identity']['source_revision'],inputs=len(product['inputs']),changed=[],product_rebuilt=False,product_suite_rerun=False),upstream_code_executed=False,live_import=False,selected_stable_consumer_qualified=False,owner_accepted=False,unit_complete=False));print('Weekly source/schema review passed without runtime/install claims.',flush=True)
