from pathlib import Path
import hashlib,json,subprocess
r=Path.cwd();e=r/'.aide/evidence/2026-10-10-namespace-graph'
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def git_bytes(rev,n):return subprocess.check_output(['git','show',rev+':'+n],cwd=r)
inventory=json.loads((e/'inventory.json').read_bytes());rev=inventory['source_revision']
for x in inventory['evidence']:
    n=x['path'];data=(r/n).read_bytes();assert len(data)==x['bytes'] and sha(data)==x['sha256'];assert sha(git_bytes('HEAD',n))==x['sha256'],n
for x in inventory['artifacts']:
    data=(r/x['path']).read_bytes();assert len(data)==x['bytes'] and sha(data)==x['sha256']
inputs=json.loads((e/('reproduction-'+rev[:8])/'source-inputs.json').read_bytes())
for n,d in inputs.items():assert sha((r/n).read_bytes())==d and sha(git_bytes(rev,n))==d and sha(git_bytes('HEAD',n))==d,n
handoff=json.loads((r/'.aide/handoffs/DE-W030-namespace-graph-2026-10-10.json').read_bytes())
for x in handoff['artifacts']:
    assert sha((r/x['path']).read_bytes())==x['sha256'],x['path']
    if not x['path'].startswith('.aide-local/'):assert sha(git_bytes('HEAD',x['path']))==x['sha256'],x['path']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=r).strip()
print(json.dumps(dict(status='pass',source_revision=rev,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),source_inputs=len(inputs),evidence_files=len(inventory['evidence']),local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(handoff['artifacts']),clean=True)))
