"""Actual separately compiled domain-constructor u64 overflow; no storage API."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    probe=a.probe.absolute();out=a.output.absolute();out.mkdir();checks=[];runs=[]
    def check(label,passed):checks.append(dict(label=label,passed=bool(passed)));assert passed,label
    try:
        for label,args,exit_code in [('exhaustion',[],0),('unexpected-argument',['unexpected'],2)]:
            command=[str(probe),*args];(out/(label+'.request.json')).write_text(json.dumps(dict(command=command))+'\n',encoding='utf-8',newline='\n');r=subprocess.run(command,capture_output=True,timeout=5)
            (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);runs.append(dict(label=label,expected_exit=exit_code,exit_code=r.returncode))
            check(label+' exact exit',r.returncode==exit_code);check(label+' stderr empty',not r.stderr)
            if not exit_code:
                v=json.loads(r.stdout);check('schema',v['schema']=='org.disked.private-capture-domain-limit-probe/1');check('architecture',v['pointer_bytes']==str(a.pointer_bytes));check('exact u64 maximum',v['initial_ordinal']=='18446744073709551615')
                check('both actual constructors refuse',v['reasons']==['capture_domain_limit']*2);check('no object or grant',not v['coordinator_created'] and not v['mutation_authority'])
            else:check('invalid invocation produces no stdout',not r.stdout)
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=0,assertions=len(checks),checks=checks,executions=runs,probe_sha256='sha256:'+hashlib.sha256(probe.read_bytes()).hexdigest(),unit_complete=False)
    except BaseException as error:
        result=dict(status='fail',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),assertions=len(checks),checks=checks,executions=runs,error=str(error));raise
    finally:
        if 'result' in locals():(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','controller_executions','assertions')}))

if __name__=='__main__':main()
