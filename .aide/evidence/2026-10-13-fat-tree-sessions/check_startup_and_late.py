"""Supplemental frozen-binary startup cleanup and delayed-page observations."""
import argparse,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','exe','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();sys.path.insert(0,str(a.root/'tests/frontend'))
    from test_fat_tree_sessions import Protocol,Tree,files,write
    tree=Tree(12);tree.directory(files(3));folder=Path(tempfile.mkdtemp(prefix='disked-tree-startup-'));path=folder/'source.img';write(tree,path)
    original=path.read_bytes();records=[];scenarios=[];ports=[];passed=False
    clean={k:v for k,v in os.environ.items() if not k.startswith('DISKED_FAT_TREE_COMMAND_TEST_')}
    params=dict(phase='open',path=str(path),volume_offset='0',volume_bytes=str(tree.g['total']*tree.unit))
    def children(pid):
        command="Get-CimInstance Win32_Process -Filter 'ParentProcessId="+str(pid)+"' | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"
        r=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,timeout=15)
        assert r.returncode==0,r.stderr.decode(errors='replace')
        value=json.loads(r.stdout) if r.stdout.strip() else []
        return value if isinstance(value,list) else [value]
    try:
        for mode in ('before_spawn','after_spawn','after_spawn_alloc'):
            env=dict(clean);env['DISKED_FAT_TREE_COMMAND_TEST_STARTUP']=mode
            p=Protocol(a.exe.resolve(),records.append,env);ports.append(p)
            p.request(params,3);assert p.process.poll() is None
            assert not p.request({})['sessions']
            observed=children(p.process.pid);assert not any(x['Name'].lower()==a.exe.name.lower() for x in observed)
            p.close();assert path.read_bytes()==original
            scenarios.append(dict(mode=mode,refused=True,no_live_named_children_after_return=True,session_count=0,source_unchanged=True))
        env=dict(clean);env['DISKED_FAT_TREE_COMMAND_TEST_WORKER']='late'
        p=Protocol(a.exe.resolve(),records.append,env);ports.append(p);sid=p.request(params)['session_id'];deadline=time.monotonic()+5
        while True:
            out=p.request(dict(phase='next',session_id=sid))
            if 'page' in out:break
            assert time.monotonic()<deadline and out['worker']['status']!='unknown';time.sleep(.02)
        assert out['page']['sequence']=='1' and out['page']['status']=='complete'
        closed=p.request(dict(phase='close',session_id=sid));deadline=time.monotonic()+5
        while closed['state']!='closed':
            assert time.monotonic()<deadline;time.sleep(.01);closed=p.request(dict(phase='close',session_id=sid))
        assert closed['worker']['worker']['observation']=='exited'
        p.close();assert path.read_bytes()==original
        scenarios.append(dict(mode='late',page_sequence='1',coverage='complete',actual_exit_observed=True,source_unchanged=True))
        passed=True;print('PASS four supplemental startup/late scenarios at frozen binaries.')
    finally:
        for p in ports:p.abort()
        a.output.write_text(json.dumps(dict(passed=passed,scenarios=scenarios,records=records,exe_sha256='sha256:'+hashlib.sha256(a.exe.read_bytes()).hexdigest(),fixture=str(folder),scope='Unprivileged generated file, named owned-child absence snapshots and actual late-reader exit; no physical qualification'),indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
