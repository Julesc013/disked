import json,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path
R=Path.cwd();C=R/'.aide-local/goal-0.1.0/clean-5293cf4e'
sys.path.insert(0,str(C/'tests/corpus'));import partition_images
rows=[];start=time.monotonic()
with tempfile.TemporaryDirectory(prefix='image-slot-',dir=C/'.aide-local') as d:
    d=Path(d);delayed=d/'test-wait-valid.img';normal=d/'gpt-valid.img'
    delayed.write_bytes(partition_images.gpt());normal.write_bytes(partition_images.gpt())
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_IMAGE_TEST_')}
    p=subprocess.Popen([str(C/'build/windows-bootstrap/Release/disked_image_test.exe'),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    q=queue.Queue()
    def reader():
        for line in p.stdout:q.put(json.loads(line))
    t=threading.Thread(target=reader,daemon=True);t.start()
    def send(id,command,params):
        began=time.monotonic();v=dict(schema='org.disked.request/1',request_id=id,command=command,parameters=params,required_features=[])
        p.stdin.write(json.dumps(v).encode()+b'\n');p.stdin.flush();reply=q.get(timeout=6)
        row=dict(id=id,sent=began-start,received=time.monotonic()-start,response=reply);rows.append(row)
        print(json.dumps(row),flush=True);return reply
    try:
        send('slow','image.inspect',dict(path=str(delayed)))
        send('essential','build.inspect',{})
        for i in range(30):
            reply=send('after:'+str(i),'table.verify',dict(path=str(normal)))
            if reply['status']=='completed':break
            time.sleep(.4)
        p.stdin.close();p.wait(timeout=5)
        print(json.dumps(dict(exit=p.returncode,stderr=p.stderr.read().decode(),rows=len(rows))),flush=True)
    finally:
        if p.poll() is None:p.kill();p.wait()
        t.join(timeout=1)
