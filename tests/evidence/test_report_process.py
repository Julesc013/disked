"""Real owned process exit/identity observations with scoped lookup API faults.

Ordinary Python children only. Injected image-lookup failure is a harness fault,
not an observed Windows API outage or execution evidence for report effects.
"""
import argparse,ctypes as C,json,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
from test_report_worker import report_process,K

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path);args=parser.parse_args();checks=[]
    def check(name,passed):assert passed,name;checks.append(dict(name=name,passed=True))
    for mode in ('normal','reused-identity','lookup-unavailable-exiting','lookup-unavailable-live'):
        child=subprocess.Popen([sys.executable,'-c',r'import sys;sys.stdout.buffer.write(b"ready\n");sys.stdout.buffer.flush();sys.stdin.buffer.readline()'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        result=None;query=K.QueryFullProcessImageNameW;released=False
        def release():
            nonlocal released
            if not released and child.poll() is None:
                released=True;child.stdin.write(b'quit\n');child.stdin.flush()
        try:
            inbox=queue.Queue();thread=threading.Thread(target=lambda:inbox.put(child.stdout.readline()),daemon=True);thread.start()
            assert inbox.get(timeout=5)==b'ready\n';thread.join(timeout=1)
            stamps=[W.FILETIME() for _ in range(4)];assert K.GetProcessTimes(child._handle,*map(C.byref,stamps))
            created=stamps[0].dwHighDateTime*2**32+stamps[0].dwLowDateTime
            state=dict(binding=dict(process_id=str(child.pid),process_created=str(created)))
            if mode=='reused-identity':state['binding']['process_created']=str(created+1)
            if mode.startswith('lookup-unavailable'):
                def unavailable(*unused):
                    if mode=='lookup-unavailable-exiting':release()
                    C.set_last_error(31);return 0
                K.QueryFullProcessImageNameW=unavailable
            started=time.monotonic()
            if mode in ('reused-identity','lookup-unavailable-live'):
                try:report_process(state,Path(sys.executable));raise RuntimeError('unverified process accepted')
                except AssertionError:pass
                check(mode+'-still-live-not-owned-by-observation',K.WaitForSingleObject(child._handle,0)==258)
                if mode=='lookup-unavailable-live':check('unavailable-live-bounded-wait',2.8<=time.monotonic()-started<5)
            else:
                result=report_process(state,Path(sys.executable));check(mode+'-exact-handle-returned',bool(result))
                check(mode+'-actual-lifetime',K.WaitForSingleObject(result,0)==(0 if mode.endswith('exiting') else 258))
        finally:
            K.QueryFullProcessImageNameW=query
            if result:K.CloseHandle(result)
            release();assert child.wait(timeout=5)==0 and not child.stderr.read()
            for stream in (child.stdin,child.stdout,child.stderr):stream.close()
    result=dict(passed=True,checks=len(checks),observations=checks,
        scope='Four real owned Python children, exact creation identity, actual exit and scoped image-lookup API faults; no report effect, physical or privilege qualification')
    if args.evidence:args.evidence.parent.mkdir(parents=True,exist_ok=True);args.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}))
if __name__=='__main__':main()
