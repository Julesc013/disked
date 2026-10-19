"""Read selected upstream Git blobs; never clone or execute upstream code."""
import base64
from datetime import datetime,timezone
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
CANDIDATE='7877e05655ee33fa99583afe4855fac6a4910292'

def api(resource):
    response=subprocess.run(['gh','api','repos/Julesc013/aide/'+resource],cwd=ROOT,capture_output=True,timeout=60)
    if response.returncode:raise RuntimeError(response.stderr[-4096:].decode(errors='replace'))
    if len(response.stdout)>8*1024*1024:raise ValueError('Upstream metadata exceeds bounded review')
    return json.loads(response.stdout)

def main():
    if (HERE/'source-review.json').exists():raise ValueError('Retain/review the existing observation before fetching again')
    work=Path(os.environ['DISKED_WORK_ROOT'])
    lock=json.loads((ROOT/'spec/references/aide-lock.json').read_bytes())
    old_commit=api('git/commits/'+lock['revision'])
    new_commit=api('git/commits/'+CANDIDATE)
    assert old_commit['sha']==lock['revision'] and old_commit['tree']['sha']==lock['tree']
    assert new_commit['sha']==CANDIDATE
    old=api('git/trees/'+old_commit['tree']['sha']+'?recursive=1')
    new=api('git/trees/'+new_commit['tree']['sha']+'?recursive=1')
    assert old['sha']==old_commit['tree']['sha'] and new['sha']==new_commit['tree']['sha']
    if old.get('truncated') or new.get('truncated'):raise ValueError('Incomplete tree; no adoption')
    before={r['path']:r for r in old['tree']};after={r['path']:r for r in new['tree']}
    changed=[p for p in sorted(before.keys()|after.keys()) if before.get(p,{}).get('sha')!=after.get(p,{}).get('sha')]
    content={};files=[]
    for row in lock['files']:
        path=row['path'];entry=after[path]
        if entry['type']!='blob' or entry.get('size',0)>262144:raise ValueError('Unexpected selected blob')
        blob=api('git/blobs/'+entry['sha'])
        if blob['encoding']!='base64':raise ValueError('Unexpected blob encoding')
        data=base64.b64decode(blob['content']);assert len(data)==blob['size']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==entry['sha']==blob['sha']
        digest='sha256:'+hashlib.sha256(data).hexdigest()
        files.append(dict(path=path,git_blob=entry['sha'],sha256=digest,bytes=len(data),changed=digest!=row['sha256']))
        content[path]=data.decode('utf-8')
    release=api('releases/latest')
    retained=json.dumps(dict(selected_source=content,release={k:release.get(k) for k in ('tag_name','target_commitish','published_at','html_url','body','assets')}),indent=2).encode()
    if len(retained)>524288:raise ValueError('Review content exceeds retention bound')
    compressed=lzma.compress(retained,preset=9|lzma.PRESET_EXTREME)
    if len(compressed)>131072 or lzma.decompress(compressed)!=retained:raise ValueError('Archive bound/verification failed')
    (HERE/'selected-source.json.xz').write_bytes(compressed)
    record=dict(observed_at=datetime.now(timezone.utc).isoformat(),previous_revision=lock['revision'],revision=CANDIDATE,tree=new['sha'],
        tree_entries=len(after),changed_tree_entries=len(changed),changed_blob_paths=sum(after.get(p,before.get(p,{})).get('type')=='blob' for p in changed),protocol_changes=[p for p in changed if p.startswith('.aide/protocol/')],
        authority_page_changes=[p for p in changed if p.startswith('.aide/knowledge/okf/decisions/')],files=files,
        source_fetch_scope='Selected documentation,authority and queue schema Git blobs plus complete tree identity comparison; no clone,checkout or upstream execution',
        latest_release={k:release.get(k) for k in ('tag_name','target_commitish','published_at','html_url')},
        archive=dict(path='selected-source.json.xz',bytes=len(compressed),sha256=hashlib.sha256(compressed).hexdigest(),uncompressed_bytes=len(retained),uncompressed_sha256=hashlib.sha256(retained).hexdigest()),
        live_consumer_qualified=False,upstream_code_executed=False)
    (HERE/'source-review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record,indent=2))
    print(content['README.md'])
    if any(r['changed'] and r['path'].endswith('okf-as-knowledge-plane.md') for r in files):print(content['.aide/knowledge/okf/decisions/okf-as-knowledge-plane.md'])
    print('SELECTED_RELEASE_BODY\n'+str(release.get('body')))

if __name__=='__main__':main()
