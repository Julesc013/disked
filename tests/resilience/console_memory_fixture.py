"""Repeated real UI input and memory samples in a hidden fixture-owned console."""
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'frontend'))
from console_tui_fixture import k, configure, current_text, key, snapshot
from memory_fixture import K, MIB, checked, limits, member, memory, name

def run(exe, frontend, report):
    configure(k.GetStdHandle(-11), 80, 25)
    before = snapshot(); p = None; job = None; samples = []
    report.update(frontend=frontend, before=before, samples=samples)
    def wait(needle):
        deadline = time.monotonic()+5
        while True:
            text = current_text()
            if needle in text: return text
            if p.poll() is not None: raise AssertionError('frontend exited before '+needle)
            if time.monotonic()>deadline: raise AssertionError('missing '+needle+'\n'+text)
            time.sleep(.005)
    try:
        args = ['shell', '--history=session', '--terminal=screen'] if frontend=='shell' else ['--tui', '--terminal=screen']
        p = subprocess.Popen([exe, *args], close_fds=False)
        wait('disked>' if frontend=='shell' else 'TARGET INVENTORY')
        job = checked(K.OpenJobObjectW(4, False, name()))
        if not member(int(p._handle), job): raise AssertionError('frontend not in memory job')
        for i in range(64):
            if frontend=='shell':
                for char in 'build inspect': key(0, char)
                key(0x78); wait('REQUEST REVIEW'); key(0x78); text = wait('Request completed')
                wait('disked> [local|none] ""')
            else:
                key(0x71); wait('COMMAND EXPLORER'); key(0x72); text = wait('TARGET INVENTORY')
            value = memory(int(p._handle))
            if value['peak_commit_bytes']>256*MIB: raise AssertionError(value)
            samples.append(value)
        report.update(iterations=64, limits=limits(job), final_frame=text)
        if frontend=='shell' and 'Evicted transcript records: 0' in text:
            raise AssertionError('workload did not exercise bounded transcript eviction')
        key(0x79); report['exit'] = p.wait(timeout=5)
        if report['exit']!=0: raise AssertionError('nonzero frontend exit')
        after = snapshot(); report['after'] = after
        for field in ('modes', 'codepages', 'buffer', 'cursor_style', 'content', 'cursor'):
            if before[field]!=after[field]: raise AssertionError('caller console not restored: '+field)
    finally:
        if p is not None and p.poll() is None: p.kill(); p.wait(timeout=3)
        if job: K.CloseHandle(job)

if __name__=='__main__':
    report = {}; code = 0
    try: run(sys.argv[1], sys.argv[3], report)
    except Exception as error: report['fixture_error'] = str(error); code = 1
    Path(sys.argv[2]).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    raise SystemExit(code)
