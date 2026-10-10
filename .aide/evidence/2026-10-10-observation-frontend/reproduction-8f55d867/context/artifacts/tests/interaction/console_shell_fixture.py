"""Synthetic keyboard journeys in a new, hidden, test-owned Windows console."""
import ctypes as c
import json
from pathlib import Path
import re
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from console_tui_fixture import (k,w,Callback,checked,configure,snapshot,current_text,
                                 key,active,mode)

def run(exe,case,report):
    started_at=time.monotonic()
    small=case=='small'
    out=k.GetStdHandle(-11);configure(out,40 if small else 80,8 if small else 25)
    marker='CALLER SHELL BUFFER\r\n';written=w.DWORD()
    checked(k.WriteConsoleW(out,marker,len(marker),c.byref(written),None))
    before=snapshot();frames=[];trace=[];p=None
    report.update(case=case,before=before,frames=frames,synthetic_trace=trace)
    handler=Callback(lambda event:True);checked(k.SetConsoleCtrlHandler(handler,True))
    style='linear' if case in ['linear','journey','history','mode','worker','unicode'] else 'auto'
    flags=['shell','--terminal='+style]
    if case=='history':flags+=['--history=session']
    if case=='forced-small':configure(out,40,8);before=snapshot();flags=['shell','--terminal=screen']
    def wait_for(needle,absent=False):
        started=time.monotonic();deadline=started+8
        while time.monotonic()<deadline:
            text=current_text()
            if (needle in text)!=absent:
                frames.append(dict(contains=needle,absent=absent,text=text))
                trace.append(dict(observation=needle,absent=absent,elapsed_ms=round((time.monotonic()-started)*1000,3),
                                  session_offset_ms=round((time.monotonic()-started_at)*1000,3)))
                return text
            if p.poll() is not None:raise AssertionError('Exited before '+needle+': '+str(p.returncode)+'\n'+text)
            time.sleep(.02)
        raise AssertionError('Console did not show '+needle+'\n'+text)
    def type_text(text):
        trace.append(dict(action='type',text=text,session_offset_ms=round((time.monotonic()-started_at)*1000,3)))
        for char in text:
            # Supplementary Unicode uses the two UTF-16 events supplied by Win32.
            units=char.encode('utf-16-le')
            for at in range(0,len(units),2):key(0,chr(int.from_bytes(units[at:at+2],'little')))
    def tap(vk):trace.append(dict(action='key',vk=vk,session_offset_ms=round((time.monotonic()-started_at)*1000,3)));key(vk)
    def submit(line):
        type_text(line);tap(0x78);wait_for('F9 submits:');tap(0x78)
        return wait_for('"request_id": "shell:')
    try:
        startup=None
        if case=='wrong-input':
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESTDHANDLES
            startup.hStdInput=out;startup.hStdOutput=out;startup.hStdError=k.GetStdHandle(-12)
        p=subprocess.Popen([exe,*flags],close_fds=False,startupinfo=startup)
        if case in ['fault','forced-small','wrong-input']:
            code=p.wait(timeout=8)
        else:
            wait_for('disked>')
            if case=='screen':
                type_text('show fake:alpha@1');tap(13);tap(0x78);wait_for('REQUEST REVIEW')
                key(0x78,up=False);wait_for('Request completed')
                key(0x78,up=False);time.sleep(.08)
                if 'REQUEST REVIEW' in current_text():raise AssertionError('Held F9 began another request')
                key(0x78,down=False)
                tap(0x71);wait_for('Enter inserts:');wait_for('> build inspect')
                tap(0x1b);tap(0x72);wait_for('Enter selects:');tap(13);wait_for('fake:alpha@1')
                tap(0x75);wait_for('linear');tap(0x75);wait_for('screen')
            elif case=='journey':
                type_text('show');tap(0x78);wait_for('missing_parameter')
                type_text(' fake:a');tap(9);wait_for('Tab inserts: "fake:alpha@1"');tap(9)
                wait_for('disked> [local|none] "show fake:alpha@1"')
                tap(13);tap(13);time.sleep(.08)
                if '"request_id": "shell:' in current_text():raise AssertionError('Enter submitted input')
                key(0x78,up=False);wait_for('F9 submits: target.inspect')
                key(0x78,up=False);time.sleep(.08)
                if '"request_id": "shell:' in current_text():raise AssertionError('Held F9 submitted review')
                key(0x78,down=False);tap(0x78);wait_for('"request_id": "shell:1"')
                wait_for('"id": "fake:alpha@1"')
                # No per-keystroke duplication of complete result records.
                type_text('inert draft');text=wait_for('inert draft')
                if text.count('"request_id": "shell:1"')!=1:raise AssertionError('Linear outcome duplicated')
                report['correction_count']=1
            elif case=='history':
                submit('show fake:alpha@1');wait_for('disked> [local|none] ""')
                tap(0x26);wait_for('disked> [local|none] "show fake:alpha@1"')
                tap(0x28);wait_for('disked> [local|none] ""')
                type_text('quit');tap(0x78);wait_for('F9 submits: shell.close');tap(0x78)
            elif case=='mode':
                submit('mode explain');wait_for('"interactive": true');wait_for('"terminal_presentation": "linear"')
            elif case=='unicode':
                type_text('show "é🙂z"');wait_for('\\u00e9\\ud83d\\ude42z')
                tap(0x25);tap(0x25);tap(8);wait_for('\\ud83d',absent=True)
                tap(0x23);tap(0x78);wait_for('F9 submits: target.inspect');tap(0x78);wait_for('target_not_found')
            elif case=='worker':
                state=Path.cwd()/'owned state';state.mkdir()
                submit('plan simulate fake:cancel-checkpoint --state-dir "'+str(state)+'"')
                text=wait_for('"status": "accepted_running"')
                ids=re.findall(r'fake-op:[0-9a-f]{32}',text)
                if not ids:raise AssertionError('No operation ID displayed')
                report['operation_id']=ids[-1];report['state_dir']=str(state)
                tap(0x79);code=p.wait(timeout=8)
                # Reconnect from a separate one-shot client after shell exit.
                deadline=time.monotonic()+8
                while True:
                    result=subprocess.run([exe,'operation','inspect',ids[-1],'--state-dir',str(state),'--json'],capture_output=True,text=True,timeout=8)
                    value=json.loads(result.stdout)
                    report.setdefault('reconnect',[]).append(dict(exit=result.returncode,response=value))
                    if value['result'].get('state',{}).get('phase')=='finished':break
                    if time.monotonic()>=deadline:raise AssertionError('Disconnected worker did not finish')
                    time.sleep(.04)
                if value['status']!='completed':raise AssertionError('Shell close cancelled worker')
            elif case=='resize':
                handle=active()
                try:configure(handle,40,8)
                finally:k.CloseHandle(handle)
                wait_for('linear');type_text('show fake:alpha@1');tap(0x78);wait_for('F9 submits:');tap(0x78);wait_for('"status": "completed"')
            elif case=='external-mode':checked(k.SetConsoleMode(k.GetStdHandle(-10),mode(k.GetStdHandle(-10))^0x20))
            if case=='ctrl-c':checked(k.GenerateConsoleCtrlEvent(0,0))
            elif case=='ctrl-key':key(ord('C'),'\x03',control=8)
            elif case not in ['history','worker']:tap(0x79)
            code=p.wait(timeout=8)
        after=snapshot();report.update(after=after,child_exit=code,active_after=current_text(),
            synthetic_session_ms=round((time.monotonic()-started_at)*1000,3),
            timing_scope='Injected Win32 input and polling observations; includes deliberate waits, not human entry time or keyboard qualification')
        expected=4 if case=='fault' else 3 if case in ['forced-small','wrong-input'] else 0
        if code!=expected:raise AssertionError('Wrong exit '+str(code))
        for field in ['handles','codepages','buffer','attributes','cursor_style']:
            if before[field]!=after[field]:raise AssertionError('Caller changed: '+field)
        expected_modes=before['modes'][:]
        if case=='external-mode':expected_modes[0]^=0x20
        if after['modes']!=expected_modes:raise AssertionError('Mode restoration mismatch')
        if case in ['ctrl-c','ctrl-key','external-mode','resize']:
            if before['content']!=after['content'] or before['cursor']!=after['cursor']:raise AssertionError('Caller screen changed')
        if marker.strip() not in report['active_after']:raise AssertionError('Caller active buffer not restored')
    finally:
        if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)
        k.SetConsoleActiveScreenBuffer(out);k.SetConsoleMode(k.GetStdHandle(-10),before['modes'][0]);k.SetConsoleCtrlHandler(handler,False)

if __name__=='__main__':
    report={};code=0
    try:run(sys.argv[1],sys.argv[3],report)
    except Exception as error:report['fixture_error']=str(error);code=1
    Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
