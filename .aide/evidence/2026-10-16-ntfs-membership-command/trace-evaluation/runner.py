from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
root=Path.cwd();out=root/'.aide/evidence/2026-10-16-ntfs-membership-command/trace-evaluation';out.mkdir();build=root/'.aide-local/ntfs-membership-command-qualification-faeeb805/build/Release';source=root/'.aide-local/ntfs-member-source'
def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=['tests/frontend/protocol_trace.py','tests/frontend/test_ntfs_directory_commands.py','tests/frontend/test_ntfs_membership_commands.py']
summary=dict(recorded_at=datetime.now(timezone.utc).isoformat(),status='running',scope='Two traced full frontend groups against exact faee native binaries, including original fault preludes. Diagnostic/working evidence, not fresh qualification.',binary_source_revision='faeeb805cdf81b1f8ab83af04a1b330d8680b375',inputs={p:sha(p) for p in paths},artifacts={p.name:sha(p) for p in build.glob('*.exe') if p.name in {'disked.exe','disked_ntfs_test.exe','ntfs_worker_probe.exe','ntfs_inspection_probe.exe'}},stages=[],original_failure_causes_established=False,owner_accepted=False)
def save():(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
try:
 for name,count in [('directory',100),('membership',126)]:
  command=[sys.executable,str(root/f'tests/frontend/test_ntfs_{name}_commands.py'),'--exe',str(build/'disked.exe'),'--fault',str(build/'disked_ntfs_test.exe'),'--worker',str(build/'ntfs_worker_probe.exe'),'--probe',str(build/'ntfs_inspection_probe.exe'),'--root',str(source),'--output',str(out/(name+'-cases.json'))];started=time.monotonic()
  with (out/(name+'.log')).open('wb') as log:p=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
  summary['stages'].append(dict(command=command,cwd=str(root),exit_code=p.returncode,seconds=time.monotonic()-started,log=name+'.log'));save();print(name,p.returncode,flush=True)
  assert p.returncode==0,name
  data=json.loads((out/(name+'-cases.json')).read_bytes());assert data['passed'] and data['cases']==count
 summary['status']='pass'
except BaseException as error:summary.update(status='failed',error=repr(error))
finally:summary['inputs_unchanged']=all(sha(p)==h for p,h in summary['inputs'].items());save()
print(summary['status'],flush=True);sys.exit(0 if summary['status']=='pass' and summary['inputs_unchanged'] else 1)
