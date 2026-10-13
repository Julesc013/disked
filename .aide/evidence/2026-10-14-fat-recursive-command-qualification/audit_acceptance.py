"""Audit retained full campaign plus requirements, without granting acceptance."""
import hashlib,json
from pathlib import Path
root=Path.cwd().resolve();out=root/'.aide-local/recursive-normal-qualification-087f95b4'
revision='087f95b464670fa03de185d6e98a15e83eaa71dd'
data=json.loads((out/'summary.json').read_bytes());assert data['passed'] and data['source_revision']==revision
assert data['source_state']=='clean' and not data['host']['elevated'] and not data['physical_device_access']
commands=json.loads((out/'commands.json').read_bytes());assert all(c['exit_code']==0 for c in commands)
names={c['name'] for c in commands}
assert {'native-tests','tooling','boundaries','spec-check','index','manifest','context','verify-context','product-launch','command-discovery','final-source-status'}.issubset(names)
registered={t['name'] for t in json.loads((out/'test-catalog.json').read_bytes())['tests']}
tests=json.loads((out/'test-catalog.json').read_bytes())['tests']
for test in tests:
 if test['name'] in ('frontend.fat_recursive_product','frontend.fat_recursive_failures'):
  executable=Path(test['command'][test['command'].index('--exe')+1])
  assert executable.name=='disked.exe' and executable.is_relative_to(out/'build'),test
identity=json.loads((out/'build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean'
inputs=json.loads((out/'source-inputs.json').read_bytes())
blobs=json.loads((out/'source-blob-bindings.json').read_bytes())
assert set(inputs)==set(blobs) and set(identity['inputs']).issubset(inputs)
assert all(identity['inputs'][p]==inputs[p] for p in identity['inputs'])
for p,digest in inputs.items():
 assert 'sha256:'+hashlib.sha256((root/'.aide-local/recursive-normal-clean-087f95b4'/p).read_bytes()).hexdigest()==digest,p
rows=[
 dict(criterion=0,claim='Stable immutable review and explicit five-grant/resource/namespace policy',
      groups=['acquisition.fat_tree_review','image.fat_tree_commands','image.fat_tree_admission'],
      artifacts=['fat-tree-review-cases.json','fat-tree-command-cases.json','fat-tree-admission-cases.json']),
 dict(criterion=1,claim='Owned prepare/execution, exact identities, reconnect/cancel/wait, hangs/late/exit, no replay and unchanged sources',
      groups=['image.fat_tree_controller','image.fat_tree_reconnect','image.fat_tree_watch','image.fat_tree_extraction_worker','frontend.fat_recursive_failures'],
      artifacts=['fat-tree-controller-cases.json','fat-tree-reconnect-cases.json','fat-tree-watch-cases.json','fat-recursive-failure-cases.json']),
 dict(criterion=2,claim='Actual normal CLI/protocol/Win32GUI/TUI/shell exact output/source and finite response semantics',
      groups=['frontend.fat_recursive_product','frontend.fat_recursive_failures'],
      artifacts=['fat-recursive-product-cases.json','fat-recursive-failure-cases.json']),
 dict(criterion=3,claim='Full clean exact-source native/header/dependency/import/context/manifest/tooling/artifact evidence and old command regressions',
      groups=['build.boundaries','frontend.fat_tree_sessions','acquisition.fat_metadata','capture.fat_content_stream'],
      artifacts=['summary.json','build-identity.json','source-inputs.json','source-blob-bindings.json','header-objects.json','private-header-usage.json','context-manifest.json','native-details.log'])]
for row in rows:
 assert set(row['groups']).issubset(registered),row
 for path in row['artifacts']:assert (out/path).is_file(),path
for artifact in data['artifacts']:
 assert 'sha256:'+hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
assert len(json.loads((out/'header-objects.json').read_bytes()))==data['header_compilations']
for item in json.loads((out/'header-objects.json').read_bytes()):
 assert 'sha256:'+hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
failures=json.loads((out/'fat-recursive-failure-cases.json').read_bytes());assert failures['passed'] and failures['checks']>=15
product=json.loads((out/'fat-recursive-product-cases.json').read_bytes());assert product['passed']
assert {'actual-gui','actual-tui','actual-shell'}.issubset({r['name'] for r in product['records']})
audit=dict(work_id='DE-W057',source_revision=revision,status='local-development-criteria-proven',
 criteria=rows,owner_accepted=False,full_0_1_0_complete=False,
 limits=['Recorded ordinary-file Windows10x64/MSVC lane only','No physical devices/elevation/customer data','No production broker/journal ABI','Other platforms/formats/storage operations remain','No independent owner acceptance or release qualification'])
(out/'acceptance-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status='PASS',criteria=len(rows),source_revision=revision)))
