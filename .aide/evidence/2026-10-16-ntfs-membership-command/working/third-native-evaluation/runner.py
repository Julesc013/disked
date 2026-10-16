from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time

root=Path.cwd();label=sys.argv[1];context=root/('.aide-local/context/ntfs-membership-command-'+sys.argv[2]);out=root/'.aide/evidence/2026-10-16-ntfs-membership-command/working'/label;out.mkdir(parents=True,exist_ok=False)
(out/'context-manifest.json').write_bytes((context/'manifest.json').read_bytes())
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save():(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
paths=[p for base in ('source','tests') for p in Path(base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [Path(p) for p in ('CMakeLists.txt','CMakePresets.json','tools/build-inputs.json','spec/catalog/native-bootstrap.json','spec/catalog/ntfs-membership-command-prototype.json','spec/catalog/commands.json','spec/schemas/command-image-inspect-parameters.schema.json')]
summary=dict(base_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),status='running',qualification=False,recorded_at=datetime.now(timezone.utc).isoformat(),stages=[],inputs={p.as_posix():sha(p) for p in paths})
changed=set(subprocess.check_output(['git','diff','--name-only'],text=True).splitlines())
for p in paths:
 if p.as_posix() in changed or 'membership_commands' in p.name:
  dest=out/'input-snapshots'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
build=root/'.aide-local/report-phases-build'
def run(name,args):
 print('BEGIN',name,flush=True);start=time.monotonic()
 with (out/(name+'.log')).open('wb') as log:p=subprocess.run(list(map(str,args)),stdout=log,stderr=subprocess.STDOUT)
 summary['stages'].append(dict(name=name,command=list(map(str,args)),cwd=str(root),exit_code=p.returncode,seconds=time.monotonic()-start,log=name+'.log'));save();print('END',name,p.returncode,flush=True);assert p.returncode==0,name
try:
 run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
 run('build',['cmake','--build',build,'--config','Release','--parallel','4','--target','disked','disked_ntfs_test','ntfs_worker_probe','ntfs_inspection_probe','disked_ntfs_inspection_headers'])
 run('membership-command',[sys.executable,'tests/frontend/test_ntfs_membership_commands.py','--exe',build/'Release/disked.exe','--fault',build/'Release/disked_ntfs_test.exe','--worker',build/'Release/ntfs_worker_probe.exe','--probe',build/'Release/ntfs_inspection_probe.exe','--root',root,'--output',out/'membership-command-cases.json'])
 run('old-commands',['ctest','--test-dir',build,'-C','Release','--parallel','1','--stop-on-failure','--output-on-failure','-R','^image.ntfs_(commands|directory_commands)$','--output-junit',out/'old-commands.xml'])
 summary['status']='pass'
except Exception as error:summary.update(status='failed',error=str(error))
finally:
 summary['inputs_unchanged']=all(sha(root/p)==h for p,h in summary['inputs'].items());save()
print(json.dumps(dict(output=str(out),status=summary['status'],inputs_unchanged=summary['inputs_unchanged'])),flush=True)
sys.exit(0 if summary['status']=='pass' and summary['inputs_unchanged'] else 1)
