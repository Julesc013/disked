"""Actual injected reader process + common capture lifecycle; no node projection."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from test_volume_namespace import fixture


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--pointer-bytes',required=True,type=int,choices=(4,8));a=p.parse_args()
    a.output.mkdir();assertions=0;bindings=set();observations=[]
    def check(ok):
        nonlocal assertions
        assertions+=1
        if not ok:raise AssertionError('lifecycle assertion '+str(assertions))
    for mode,fault in [('published','hold'),('superseded','delay'),('late','delay'),('before',None),('crash','crash'),('retire','hang')]:
        f=fixture([])
        if fault=='hold':f['reply_fault']='hold'
        elif fault:f['worker_fault']=fault
        request=json.dumps(dict(mode=mode,fixture=f)).encode()
        (a.output/(mode+'.request.json')).write_bytes(request)
        r=subprocess.run([str(a.probe.resolve())],input=request,capture_output=True,timeout=15)
        (a.output/(mode+'.stdout')).write_bytes(r.stdout);(a.output/(mode+'.stderr')).write_bytes(r.stderr)
        check(r.returncode==0 and not r.stderr);v=json.loads(r.stdout);check(v['pointer_bytes']==str(a.pointer_bytes))
        samples=v['samples'];first=samples[0];last=samples[-1]
        check(first['capture']['state']=='pending' and first['capture']['outstanding'])
        worker=first['worker'];binding=tuple(worker[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256'))+(worker['worker']['pid'],worker['worker']['created'])
        check(binding not in bindings);bindings.add(binding)
        for sample in samples:
            w=sample['worker'];c=sample['capture']
            check(tuple(w[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256'))+(w['worker']['pid'],w['worker']['created'])==binding)
            check(w['capture_epoch']=='1' and c['attempt_capture']=='1' and c['attempt_worker']=='1')
            check(c['graph']['nodes']==[] and c['graph']['edges']==[])
            if w['worker']['observation']!='exited':check(c['outstanding'])
        check(last['worker']['worker']['observation']=='exited' and not last['capture']['outstanding'])
        if mode=='published':
            published=samples[1];check(published['worker']['status']=='completed' and published['worker']['worker']['observation']=='running')
            check(published['capture']['state']=='complete' and published['capture']['outstanding'])
            check(v['replacement_refused'] and v['duplicate_unchanged']);check(last['capture']['state']=='complete')
        elif mode=='superseded':
            check(samples[1]['capture']['capture']=='2' and samples[1]['capture']['outstanding'])
            check(last['worker']['status']=='completed' and last['capture']['state']=='not_started')
            check(last['capture']['reason']=='superseded_result_discarded' and v['next_started'])
        elif mode=='late':
            check(samples[1]['capture']['state']=='timed_out' and samples[1]['capture']['outstanding'])
            check(last['capture']['state']=='complete' and last['worker']['status']=='completed')
        elif mode=='before':
            check(last['worker']['result']['status']=='cancelled' and last['capture']['state']=='partial')
            check('namespace:partial:namespace_cancelled' in last['capture']['graph']['omissions'])
        else:check(last['worker']['status']=='unknown' and last['capture']['state']=='unavailable')
        observations.append(dict(mode=mode,worker_binding=binding,result=v))
    result=dict(status='pass',scope='common capture lifecycle with empty graphs and actual owned injected workers',pointer_bytes=a.pointer_bytes,
        controller_executions=len(observations),actual_child_launches=len(bindings),assertions=assertions,observations=observations,
        artifact_sha256='sha256:'+hashlib.sha256(a.probe.read_bytes()).hexdigest(),native_graph_projection_qualified=False,live_namespace_qualified=False)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}))


if __name__=='__main__':main()
