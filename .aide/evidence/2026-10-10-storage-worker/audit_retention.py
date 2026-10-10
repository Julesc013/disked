"""Verify retained fixture evidence and unchanged qualified inputs against Git."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import jsonschema
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    root=Path.cwd();e=root/'.aide/evidence/2026-10-10-storage-worker'
    def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
    def file_sha(n):return sha((root/n).read_bytes())
    inventory=json.loads((e/'inventory.json').read_bytes());source=inventory['source_revision']
    inputs=json.loads((e/('reproduction-'+source[:8])/'source-inputs.json').read_bytes())
    product=json.loads((e/('reproduction-'+source[:8])/'unchanged-product-inputs.json').read_bytes())['inputs']
    assert len(product)==401
    combined=dict(inputs)
    for n,d in product.items():
        assert n not in combined or combined[n]==d,n
        combined[n]=d
    for n,d in combined.items():assert file_sha(n)==d,n
    for x in inventory['evidence']+inventory['artifacts']:
        assert file_sha(x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes'],x['path']
    handoff_path='.aide/handoffs/DE-W030-storage-worker-2026-10-10.json'
    h=json.loads((root/handoff_path).read_bytes())
    jsonschema.Draft202012Validator(json.loads((root/'spec/schemas/handoff.schema.json').read_bytes())).validate(h)
    for x in h['artifacts']:assert file_sha(x['path'])==x['sha256'],x['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file()]
    target=':' if a.index else 'HEAD:'
    requests=[(source+':'+n,d) for n,d in combined.items()]
    requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/windows-inventory.md','docs/development-plan.md','TODO.MD'])
    # One batch avoids hundreds of Git process launches while checking raw bytes.
    v=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(x[0] for x in requests)+'\n').encode(),capture_output=True,check=True)
    at=0
    for name,digest in requests:
        end=v.stdout.index(b'\n',at);header=v.stdout[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;assert sha(v.stdout[start:start+size])==digest,name
        at=start+size;assert v.stdout[at:at+1]==b'\n',name;at+=1
    assert at==len(v.stdout)
    result=dict(status='pass',source_revision=source,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        verification_target='Git index' if a.index else 'HEAD',private_inputs=len(inputs),unchanged_product_inputs=len(product),
        combined_inputs=len(combined),retained_files=len(retained),inventoried_evidence=len(inventory['evidence']),
        local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(h['artifacts']),owner_accepted=False,unit_complete=False)
    raw=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(raw,encoding='utf-8',newline='\n')
    print(raw,end='')
if __name__=='__main__':main()
