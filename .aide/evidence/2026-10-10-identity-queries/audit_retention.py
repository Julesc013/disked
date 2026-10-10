"""Audit source blobs, retained evidence, decoded gzip bytes and local PE identities."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
import jsonschema

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    root=Path.cwd();e=root/'.aide/evidence/2026-10-10-identity-queries'
    def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
    def file_sha(n):return sha((root/n).read_bytes())
    inventory=json.loads((e/'inventory.json').read_bytes());source=inventory['source_revision']
    inputs=json.loads((e/('reproduction-'+source[:8])/'source-inputs.json').read_bytes())
    assert all(file_sha(n)==d for n,d in inputs.items())
    for x in inventory['evidence']+inventory['artifacts']:
        assert file_sha(x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes'],x['path']
    for x in inventory['compressed']:
        data=gzip.decompress((root/x['encoded_path']).read_bytes())
        assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256'],x['encoded_path']
    handoff_path='.aide/handoffs/DE-W030-identity-queries-2026-10-10.json'
    h=json.loads((root/handoff_path).read_bytes())
    jsonschema.Draft202012Validator(json.loads((root/'spec/schemas/handoff.schema.json').read_bytes())).validate(h)
    for x in h['artifacts']:assert file_sha(x['path'])==x['sha256'],x['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts]
    target=':' if a.index else 'HEAD:'
    requests=[(source+':'+n,d) for n,d in inputs.items()]
    requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/windows-inventory.md','docs/development-plan.md','TODO.MD'])
    blobs=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,digest in requests:
        end=blobs.index(b'\n',at);header=blobs[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;assert sha(blobs[start:start+size])==digest,name
        at=start+size;assert blobs[at:at+1]==b'\n',name;at+=1
    assert at==len(blobs)
    result=dict(status='pass',source_revision=source,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        verification_target='Git index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),
        inventoried_evidence=len(inventory['evidence']),compressed_observations=len(inventory['compressed']),
        local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(h['artifacts']),owner_accepted=False,unit_complete=False)
    raw=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(raw,encoding='utf-8',newline='\n')
    print(raw,end='')

if __name__=='__main__':main()
