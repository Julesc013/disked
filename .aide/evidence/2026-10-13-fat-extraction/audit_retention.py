"""Verify retained held-file FAT-content campaign evidence; this does not rerun it."""
import hashlib,json,subprocess
from pathlib import Path
def sha(data): return 'sha256:'+hashlib.sha256(data).hexdigest()
def main():
 e=Path(__file__).resolve().parent;root=e.parents[2]
 summary=json.loads((e/'summary.json').read_bytes());source=summary['source_revision']
 assert summary['passed'] and summary['source_state']=='clean'
 assert summary['native_test_groups']==104 and summary['independent_header_compilations']==20
 assert summary['fat_content_methods']==14 and summary['fat_content_cases']==209
 assert not any(summary[k] for k in ('physical_device_access','product_dispatch_admitted','owner_accepted','unit_complete','release_ready'))
 identity=json.loads((e/'build-identity.json').read_bytes())
 assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean'
 inputs=json.loads((e/'source-inputs.json').read_bytes());bindings=json.loads((e/'source-blob-bindings.json').read_bytes())
 assert set(inputs)==set(bindings) and identity['inputs']=={p:inputs[p] for p in identity['inputs']}
 raw=subprocess.check_output(['git','cat-file','--batch'],cwd=root,input=('\n'.join(source+':'+p for p in inputs)+'\n').encode());at=0
 for p,digest in inputs.items():
  end=raw.index(b'\n',at);parts=raw[at:end].split();assert parts[1]==b'blob'
  n=int(parts[2]);data=raw[end+1:end+1+n];at=end+n+2
  assert sha(data)==digest and parts[0].decode()==bindings[p],p
 extracted=json.loads((e/'fat-extraction-cases.json').read_bytes())
 assert extracted['passed'] and extracted['test_methods']==9 and extracted['cases']>=40 and len(extracted['records'])==extracted['cases']
 assert summary['fat_extraction_methods']==9 and summary['fat_extraction_cases']==extracted['cases']
 held=json.loads((e/'fat-content-file-cases.json').read_bytes())
 assert held['passed'] and held['test_methods']==11 and held['cases']==59 and len(held['records'])==59
 assert summary['fat_content_file_cases']==59 and summary['fat_content_file_methods']==11
 assert sum(r.get('has_snapshot') is True for r in held['records'])>=20
 cases=json.loads((e/'fat-content-cases.json').read_bytes())
 assert cases['passed'] and cases['test_methods']==14 and cases['cases']==209 and len(cases['records'])==209
 assert sum(r['cases'] for r in cases['batches'])==209
 boundary=json.loads((e/'build-boundaries.json').read_bytes())
 assert boundary['status']=='PASS' and not boundary['violations']
 assert {'disked_fat_content','disked_fat_content_file'} <= set(boundary['targets']['disked']['build_closure'])
 assert len(json.loads((e/'header-objects.json').read_bytes()))==20
 receipts=json.loads((e/'commands.json').read_bytes());assert all(r['exit_code']==0 for r in receipts)
 tests=json.loads((e/'test-catalog.json').read_bytes());assert len(tests['tests'])==104
 assert any(r['name']=='image.fat_content' for r in tests['tests'])
 log=(e/'logs/native-tests.log').read_text(encoding='utf-8');assert '100% tests passed' in log and 'out of 104' in log
 inventory=json.loads((e/'retention.json').read_bytes())
 actual={p.relative_to(e).as_posix() for p in e.rglob('*') if p.is_file() and '__pycache__' not in p.parts}-{'retention.json'}
 assert actual==set(inventory['files']) and inventory['source_revision']==source
 for p,digest in inventory['files'].items():assert sha((e/p).read_bytes())==digest,p
 print(json.dumps(dict(status='PASS',source_revision=source,source_blob_bindings=len(inputs),retained_files=len(actual),native_groups=104,content_cases=209,scope='complete mapped FAT file extraction through ordinary destinations; no public command admission'),indent=2))
if __name__=='__main__':main()
