import hashlib,json,subprocess,time
from pathlib import Path
root=Path.cwd();out=root/'.aide-local/parser-timeout-e7';out.mkdir(exist_ok=False)
campaign=root/'.aide-local/exfat-tree-exact-e7e3297f';exe=campaign/'build/Release/command_parser_probe.exe';source=campaign/'source'
words=['image','inspect','--','list'];payload=json.dumps(words,ensure_ascii=True).encode()
data=dict(source_revision='e7e3297f6ef707628b607597bb8f7e2d6d76659a',argv=words,deadline_seconds=5,artifact_sha256='sha256:'+hashlib.sha256(exe.read_bytes()).hexdigest())
start=time.monotonic();process=subprocess.Popen([str(exe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=source)
data.update(pid=process.pid,spawn_seconds=round(time.monotonic()-start,6))
try:
    stdout,stderr=process.communicate(payload,timeout=5)
    data.update(status='pass',exit_code=process.returncode,elapsed_seconds=round(time.monotonic()-start,6))
    assert process.returncode==0 and not stderr
    result=json.loads(stdout);fixture=json.loads((source/'spec/fixtures/command-syntax.json').read_bytes());group=next(g for g in fixture['groups'] if g['id']=='literal-command-looking-filename')
    assert all(result.get(k)==v for k,v in group['expected'].items()),result
    (out/'stdout.json').write_bytes(stdout);(out/'stderr.log').write_bytes(stderr)
except subprocess.TimeoutExpired as error:
    data.update(status='fail',reason=repr(error),elapsed_seconds=round(time.monotonic()-start,6))
    (out/'stdout.partial').write_bytes(error.stdout or b'');(out/'stderr.partial').write_bytes(error.stderr or b'')
finally:
    if process.poll() is None:
        process.kill();data['kill_requested']=True
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:data['exit_unconfirmed']=True
    data.update(exit_confirmed=process.poll() is not None,final_exit_code=process.poll(),artifact_unchanged=data['artifact_sha256']=='sha256:'+hashlib.sha256(exe.read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps(data,indent=2))
