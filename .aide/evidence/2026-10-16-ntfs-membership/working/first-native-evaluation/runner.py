from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time

root=Path.cwd()
label=sys.argv[1]
out=root/'.aide/evidence/2026-10-16-ntfs-membership/working'/label
out.mkdir(parents=True,exist_ok=False)
context=root/'.aide-local/context/ntfs-membership-first-evaluation'
(out/'context-manifest.json').write_bytes((context/'manifest.json').read_bytes())
paths=[p for base in ('source','tests') for p in Path(base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [Path(p) for p in ('CMakeLists.txt','CMakePresets.json','tools/build-inputs.json','spec/catalog/native-bootstrap.json','spec/catalog/ntfs-membership-prototype.json','spec/catalog/source-maintenance-prototype.json')]
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
summary=dict(base_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),status='running',qualification=False,recorded_at=datetime.now(timezone.utc).isoformat(),stages=[],inputs={p.as_posix():sha(p) for p in paths})
for p in paths:
 if p.as_posix() in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() or 'membership' in p.name:
  dest=out/'input-snapshots'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
def save():
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(name,args):
 print('BEGIN',name,flush=True);start=time.monotonic()
 with (out/(name+'.log')).open('wb') as stream:
  result=subprocess.run(list(map(str,args)),stdout=stream,stderr=subprocess.STDOUT)
 summary['stages'].append(dict(name=name,command=list(map(str,args)),cwd=str(root),exit_code=result.returncode,seconds=time.monotonic()-start,log=name+'.log'));save()
 print('END',name,result.returncode,flush=True)
 assert result.returncode==0,name
build=root/'.aide-local/report-phases-build'
try:
 run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
 run('build',['cmake','--build',build,'--config','Release','--parallel','4','--target','ntfs_capture_probe','disked_ntfs_capture_headers'])
 run('membership',[sys.executable,'tests/images/test_ntfs_membership.py','--probe',build/'Release/ntfs_capture_probe.exe','--output',out/'membership-cases.json'])
 run('old-pure',['ctest','--test-dir',build,'-C','Release','--parallel','1','--output-on-failure','--stop-on-failure','-R','^image.ntfs_(capture|closure|directory)$','--output-junit',out/'old-pure.xml'])
 summary['status']='pass'
except Exception as error:
 summary['status']='failed';summary['error']=str(error)
finally:
 summary['inputs_unchanged']=all(sha(root/p)==v for p,v in summary['inputs'].items());save()
print(json.dumps(dict(output=str(out),status=summary['status'],inputs_unchanged=summary['inputs_unchanged'])),flush=True)
sys.exit(0 if summary['status']=='pass' and summary['inputs_unchanged'] else 1)
