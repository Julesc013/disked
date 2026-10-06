"""Delayed fake admission in a hidden, test-owned console; never the user's console."""
import ctypes as C,json,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from console_tui_fixture import k,w,checked,configure,key,current_text,snapshot

def run(exe,frontend,report):
    out=k.GetStdHandle(-11);configure(out,80,25)
    before=snapshot();state=Path.cwd()/'state';state.mkdir();p=None;observations=[]
    report.update(frontend=frontend,before=before,observations=observations)
    def wait_text(needle,seconds=8,after=None):
        started=time.monotonic()
        while time.monotonic()-started<seconds:
            text=current_text()
            observed=text.rsplit(after,1)[-1] if after and after in text else '' if after else text
            if needle in observed:
                elapsed=(time.monotonic()-started)*1000
                observations.append(dict(contains=needle,text=text,elapsed_ms=elapsed));return elapsed
            if p.poll() is not None:raise AssertionError('Exited before '+needle+' '+str(p.returncode))
            time.sleep(.01)
        raise AssertionError('Missing '+needle+'\n'+text)
    def type_text(value):
        for char in value:key(0,char)
    if frontend=='shell':args=['shell','--terminal=linear']
    else:args=['--tui','plan','simulate','fake:complete','--state-dir',str(state),'--terminal=linear']
    began=time.monotonic()
    try:
        p=subprocess.Popen([exe,*args],close_fds=False)
        wait_text('disked>' if frontend=='shell' else 'TYPED FORM')
        if frontend=='shell':type_text('plan simulate fake:complete --state-dir "'+str(state)+'"')
        key(0x78);wait_text('F9 submits:' if frontend=='shell' else 'REQUEST REVIEW')
        key(0x78);wait_text('pending request' if frontend=='shell' else 'Pending request:')
        deadline=time.monotonic()+4
        while not (state/'request.json').exists():
            if time.monotonic()>deadline:raise AssertionError('No admission claim')
            time.sleep(.01)
        key(0x72)
        elapsed=wait_text('targets (cached)' if frontend=='shell' else 'TARGET INVENTORY',.25)
        report['cached_navigation_ms']=elapsed
        if frontend=='shell':
            key(13,'\r');wait_text('disked>');type_text('inert draft');wait_text('inert draft')
            wait_text('earlier request outcome',5)
            # Console writes expose intermediate frames. Wait for the editable
            # row after the new outcome, not a snapshot between clearing the old
            # prompt and writing the new one. Missing/replaced input still fails.
            wait_text('inert draft',1,after='earlier request outcome')
        else:
            wait_text('EARLIER REQUEST RESULT',5)
            if 'TARGET INVENTORY' not in current_text():raise AssertionError('Late completion replaced inventory')
        wait_text('"status": "unknown"')
        header=json.loads((state/'request.json').read_text());report['operation_id']=header['operation_id']
        key(0x79);report['exit']=p.wait(timeout=5);assert report['exit']==0
        after=snapshot();report['after']=after
        for field in ['modes','codepages','buffer','cursor_style']:
            if before[field]!=after[field]:raise AssertionError('Caller changed '+field)
        deadline=time.monotonic()+8
        while True:
            result=subprocess.run([exe,'operation','inspect',header['operation_id'],'--state-dir',str(state),'--json'],capture_output=True,text=True,timeout=8)
            value=json.loads(result.stdout)
            if value['result'].get('state',{}).get('phase')=='finished':break
            if time.monotonic()>deadline:raise AssertionError('Delayed worker did not finish')
            time.sleep(.04)
        report['later_operation']=value
        if value['status']!='completed':raise AssertionError('Closing changed uncertain operation outcome')
    finally:
        if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)
        # On fixture failure, allow this compiled finite delayed worker to exit
        # before the parent test cleans its owned directory. No product claim is
        # inferred from elapsed time; failed cleanup still fails the test.
        if sys.exc_info()[0] is not None:time.sleep(max(0,8-(time.monotonic()-began)))

if __name__=='__main__':
    report={};status=0
    try:run(sys.argv[1],sys.argv[3],report)
    except Exception as error:report['fixture_error']=str(error);status=1
    Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(status)
