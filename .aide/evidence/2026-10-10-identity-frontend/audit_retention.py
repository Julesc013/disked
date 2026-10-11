"""Audit exact source, retained native frontend receipts and local PE bytes."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
import jsonschema

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    root=Path.cwd();e=root/'.aide/evidence/2026-10-10-identity-frontend'
    def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
    def file_sha(n):return sha((root/n).read_bytes())
    def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
    inventory=record(e/'inventory.json');source=inventory['source_revision'];reproduction=e/('reproduction-'+source[:8])
    inputs=record(reproduction/'source-inputs.json');assert all(file_sha(n)==d for n,d in inputs.items())
    for x in inventory['evidence']+inventory['artifacts']:
        assert file_sha(x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes'],x['path']
    for x in inventory['compressed']:
        data=gzip.decompress((root/x['encoded_path']).read_bytes());assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256'],x['encoded_path']
    assert not any(f.suffix.lower() in ('.img','.exe','.dll','.obj','.pdb') for f in e.rglob('*') if f.is_file())
    cases=(('observation-frontend',16,26,1339),('identity-frontend',21,46,7185),('identity-frame',54,41,6980),('storage-worker',43,35,671))
    for arch,pointer in (('x64',8),('Win32',4)):
        for name,controllers,children,assertions in cases:
            result=record(reproduction/(name+'-'+arch)/'results.json')
            assert result['status']=='pass' and result['pointer_bytes']==pointer
            assert result['controller_executions']==controllers and result['actual_child_launches']==children and result['assertions']==assertions
            assert all(x['passed'] for x in result['checks'])
    product=record(reproduction/'product-build-identity.json');assert product['identity']['source_revision']==source and product['identity']['source_state']=='clean'
    assert all(file_sha(n)==d for n,d in product['inputs'].items())
    result=record(e/'validation-summary.json');assert result['status']=='pass' and result['native_ctest_groups']==77 and result['product_version']=='0.1.0-dev.41'
    assert result['product_rebuilt'] and result['product_suite_rerun'] and result['native_processes']==564 and result['native_assertions']==32350
    handoff_path='.aide/handoffs/DE-W030-identity-frontend-2026-10-12.json';h=record(root/handoff_path)
    jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h)
    for x in h['artifacts']:assert file_sha(x['path'])==x['sha256'],x['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts]
    target=':' if a.index else 'HEAD:';requests=[(source+':'+n,d) for n,d in inputs.items()]
    requests.extend((source+':'+n,d) for n,d in product['inputs'].items())
    requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/windows-inventory.md','TODO.MD'])
    blobs=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,digest in requests:
        end=blobs.index(b'\n',at);header=blobs[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;assert sha(blobs[start:start+size])==digest,name;at=start+size
        assert blobs[at:at+1]==b'\n',name;at+=1
    assert at==len(blobs)
    result=dict(status='pass',source_revision=source,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),verification_target='Git index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),inventoried_evidence=len(inventory['evidence']),compressed_observations=len(inventory['compressed']),local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(h['artifacts']),owner_accepted=False,unit_complete=False)
    raw=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(raw,encoding='utf-8',newline='\n')
    print(raw,end='')
if __name__=='__main__':main()
