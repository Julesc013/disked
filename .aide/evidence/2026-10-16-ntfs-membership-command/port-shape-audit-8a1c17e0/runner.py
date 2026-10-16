from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,subprocess,sys

root=Path('.aide/evidence/2026-10-16-ntfs-membership-command');qualification=Path('.aide-local/ntfs-membership-command-qualification-8a1c17e0')
campaign=json.loads((qualification/'summary.json').read_bytes())
assert campaign['native_passed']==53 and campaign['selected_native_suite_complete'] and not campaign['native_failed']
working=root/'working/third-native-evaluation';records=json.loads((working/'membership-command-cases.json').read_bytes())['records']
receipt=next(r for r in records if r['name']=='independent-owned-worker')
original=json.loads(Path(receipt['raw_output']).read_bytes())['snapshot']
obs=original['observation'];parameters=dict(path='unopened-generated.img',view='ntfs-membership',volume_offset=obs['volume_offset'],volume_bytes=obs['volume_bytes'])
out=Path('.aide-local/ntfs-membership-command-port-audit-8a1c17e0');out.mkdir()
expected=['valid','scalar-target','missing-reference','missing-inventory-flag','scalar-edge','missing-edge-corresponds']
rows=[]
for name in expected:
 full=copy.deepcopy(original);membership=full['observation']['membership']
 if name=='scalar-target':membership['targets'][0]='malformed'
 elif name=='missing-reference':del membership['targets'][0]['reference']
 elif name=='missing-inventory-flag':del membership['targets'][0]['inventory_complete']
 elif name=='scalar-edge':membership['edges'][0]='malformed'
 elif name=='missing-edge-corresponds':del membership['edges'][0]['corresponds']
 request=dict(parameters=parameters,status='captured',file=full)
 data=json.dumps(request,sort_keys=True,separators=(',',':')).encode()
 (out/(name+'-request.json')).write_bytes(data)
 command=[str((qualification/'build/Release/ntfs_inspection_probe.exe').resolve())]
 p=subprocess.run(command,input=data,capture_output=True,timeout=20);(out/(name+'-response.json')).write_bytes(p.stdout)
 value=json.loads(p.stdout);expected_exit=0 if name=='valid' else 4
 rows.append(dict(name=name,command=command,process_exit=p.returncode,expected_exit=expected_exit,observed_exit=value['exit_code'],response_status=value['response']['status'],diagnostics=value['response']['diagnostics'],expected_result=value['exit_code']==expected_exit,request_sha256='sha256:'+hashlib.sha256(data).hexdigest(),response_sha256='sha256:'+hashlib.sha256(p.stdout).hexdigest()))
(out/'summary.json').write_text(json.dumps(dict(recorded_at=datetime.now(timezone.utc).isoformat(),source_revision='8a1c17e0bef714043df2b164b1d35770f3fde207',campaign_status_at_start=campaign['status'],scope='Additional source-free public-port shape audit; exact clean-source native-built executable after53 selected groups passed. Full tooling/context campaign may still be finishing. No native source access or worker overlap.',cases=rows,all_expected=all(r['expected_result'] for r in rows),owner_accepted=False),indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps([{k:r[k] for k in ('name','expected_exit','observed_exit','expected_result')} for r in rows]))
