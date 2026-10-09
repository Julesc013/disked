"""Bind retained baseline inputs to exact historical Git blobs, without checkout."""
import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
v=json.loads((E/'baseline-inputs.json').read_bytes());rows=list(v['source_inputs'].items())
requests=''.join(v['source_revision']+':'+name+'\n' for name,digest in rows).encode()
p=subprocess.run(['git','cat-file','--batch'],input=requests,capture_output=True,check=True);at=0
for name,digest in rows:
    end=p.stdout.index(b'\n',at);header=p.stdout[at:end].split();assert header[1]==b'blob'
    size=int(header[2]);at=end+1;data=p.stdout[at:at+size];at+=size
    assert p.stdout[at:at+1]==b'\n';at+=1
    assert 'sha256:'+hashlib.sha256(data).hexdigest()==digest,name
assert at==len(p.stdout)
result=dict(passed=True,base_revision=v['source_revision'],inputs=len(rows),
    scope='All baseline input hashes independently match exact Git blobs; defect observations remain separate from fixed qualification.')
(E/'baseline-git-input-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result))
