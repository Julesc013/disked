"""Controlled ordinary-file ancestor rename/replacement, with real owned workers.

--baseline observes the prior defect; it never qualifies the fixed contract.
Every rename/replacement and cleanup target stays inside generated scratch.
"""
import argparse,hashlib,json,os,queue,subprocess,tempfile,threading
from pathlib import Path
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--root',required=True,type=Path);p.add_argument('--evidence',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args()
    root=a.root.resolve();scratch=root/'.aide-local';scratch.mkdir(exist_ok=True);records=[]
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_ACQ_TEST_')};probe=a.probe.resolve()
    with tempfile.TemporaryDirectory(prefix='disked-parent-',dir=scratch) as tmp:
        owned=Path(tmp).resolve();assert owned.is_relative_to(scratch) and scratch.is_relative_to(root)
        for role in ('destination','map'):
            folder=owned/role;folder.mkdir();paths={}
            for r in ('source','destination','map'):
                parent=folder/r;parent.mkdir();paths[r]=parent/(r+'.img' if r!='map' else 'capture.map')
            data=bytes((i*37+11)%251 for i in range(9000));paths['source'].write_bytes(data);release=folder/'release'
            request=dict(mode='start',**{r:str(path) for r,path in paths.items()},options=dict(chunk_bytes='4096',retry_limit='0',read_policy='ordinary',substitution='stop'))
            parent=paths[role].parent;renamed=folder/(role+'-moved');assert parent.resolve().is_relative_to(owned) and renamed.resolve().is_relative_to(owned)
            original_id=parent.stat().st_ino;ce=dict(env,DISKED_ACQ_TEST_EVENT='before-create',DISKED_ACQ_TEST_PAUSE='1',DISKED_ACQ_TEST_RELEASE_FILE=str(release))
            child=subprocess.Popen([str(probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=ce)
            child.stdin.write(encode(request));child.stdin.close();messages=queue.Queue();threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
            renamed_ok=False;rename_error=None;stdout=b'';stderr=b''
            try:
                event=messages.get(timeout=12);v=json.loads(event);assert v['event']=='before-create' and int(v['pid'])==child.pid and child.poll() is None
                try:parent.rename(renamed);renamed_ok=True
                except PermissionError as e:rename_error=e.winerror
                if renamed_ok:
                    parent.mkdir();(parent/'owned-replacement-marker').write_bytes(b'new parent')
                    assert parent.stat().st_ino!=original_id
                release.write_bytes(b'release');child.stdin=None;stdout,stderr=child.communicate(timeout=20)
                assert child.returncode==0 and not stderr,(role,child.returncode,stdout,stderr)
                result=json.loads(stdout.splitlines()[-1]);assert result['outcome']['status']=='completed',result
                assert paths['destination'].read_bytes()==data and paths['source'].read_bytes()==data
                assert paths['map'].is_file() and paths['map'].read_bytes().endswith(b'\n')
                record=dict(role=role,pid=child.pid,alive_observed_at_pause=True,terminal_observed=True,exit_code=child.returncode,
                    renamed=renamed_ok,rename_platform_code=rename_error,original_parent_id=str(original_id),output_parent_id=str(parent.stat().st_ino),
                    old_parent_has_output=(renamed/paths[role].name).exists() if renamed_ok else None,source_sha256=sha(data),destination_sha256=sha(paths['destination'].read_bytes()),map_sha256=sha(paths['map'].read_bytes()),
                    request_sha256=sha(encode(request)),output_sha256=sha(event+stdout),outcome=result['outcome'])
                records.append(record)
                if a.baseline:
                    assert renamed_ok and record['output_parent_id']!=record['original_parent_id'] and not record['old_parent_has_output'],record
                else:
                    assert not renamed_ok and rename_error==32 and record['output_parent_id']==record['original_parent_id'],record
            finally:
                if child.poll() is None:child.kill();child.wait(timeout=10)
                child.stdout.close();child.stderr.close()
    evidence=dict(passed=True,mode='baseline-defect-observation' if a.baseline else 'strong-parent-contract',cases=len(records),
        base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),probe=dict(path=str(probe),sha256=sha(probe.read_bytes())),records=records,
        physical_io=False,power_loss_tested=False,all_namespace_fencing_qualified=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,cases=len(records),mode=evidence['mode'])))
if __name__=='__main__':main()
