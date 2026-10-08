"""Generated ordinary files and independent byte/map expectations.

Owned-child termination and injected API faults are not power-loss or physical
storage qualification. The probes are private; no product command is admitted.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def source_bytes(size):
    return bytes((i * 37 + 11) % 251 for i in range(size))


def options(chunk=4096, policy='ordinary', substitution='stop', retry=0):
    return dict(chunk_bytes=str(chunk), retry_limit=str(retry), read_policy=policy, substitution=substitution)


def inspect_map(path, expected, sealed=True):
    raw = path.read_bytes()
    assert raw.endswith(b'\n')
    previous = 'sha256:' + '0' * 64
    position = 0
    rows = []
    for sequence, body in enumerate(raw.splitlines()):
        row = json.loads(body)
        assert canonical(row) == body and row['sequence'] == str(sequence) and row['previous'] == previous
        previous = digest(body)
        if row['type'] == 'header':
            assert sequence == 0 and row['payload']['plan_digest'] == digest(canonical(row['payload']['plan']))
        if row['type'] == 'checkpoint':
            c = row['payload']; size = int(c['length'])
            assert int(c['offset']) == position and c['sha256'] == digest(expected[position:position+size])
            position += size
        rows.append(row)
    if sealed:
        assert rows[-1]['type'] == 'seal' and position == len(expected)
        assert rows[-1]['payload']['bytes'] == str(position)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True); parser.add_argument('--fault', required=True)
    parser.add_argument('--root', default='.'); parser.add_argument('--evidence')
    args = parser.parse_args(); root = Path(args.root).resolve()
    probes = [str(Path(p).resolve()) for p in (args.probe, args.fault)]
    env = {k:v for k,v in os.environ.items() if not k.startswith('DISKED_ACQ_TEST_')}
    records = []; process_observations = []
    scratch = root / '.aide-local'; scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='disked-acquire-', dir=scratch) as tmp:
        owned = Path(tmp)

        def fixture(name, size=9000):
            folder = owned / name; folder.mkdir()
            src = folder / 'source.img'; src.write_bytes(source_bytes(size))
            return dict(mode='start', source=str(src), destination=str(folder/'copy.img'), map=str(folder/'copy.map'), options=options())

        def paths(request):
            return [Path(request[k]) for k in ('destination', 'map')]

        def snapshot(request):
            return [p.read_bytes() if p.exists() and p.is_file() else None for p in paths(request)]

        def run(name, request, fault=False, injected=None, refusal=None, status=None, diagnostic=None):
            print('case', name, flush=True)
            callenv = dict(env)
            if injected:callenv.update({'DISKED_ACQ_TEST_'+k:str(v) for k,v in injected.items()})
            result = subprocess.run([probes[int(fault)]], input=canonical(request), capture_output=True, env=callenv, cwd=root, timeout=20)
            assert result.returncode == (3 if refusal else 0), (name, result.returncode, result.stdout, result.stderr)
            value = json.loads(result.stdout.splitlines()[-1])
            if refusal:assert value['refusal'] == refusal, (name, value)
            else:
                assert value['plan_digest'] == digest(canonical(value['plan']))
                if status:assert value['outcome']['status'] == status, (name, value)
                if diagnostic:assert value['outcome']['diagnostic'] == diagnostic, (name, value)
                if 'receipt' in value:
                    assert value['receipt']['source_consistency'] == 'live-uncoordinated'
                    assert not value['receipt']['physical_backing_qualified']
                    assert value['receipt']['flush_scope'] == 'per-file-FlushFileBuffers-API-only'
                    receipt=value['receipt'];assert not receipt['size_observation_errors']
                    if receipt['map_bytes'] is not None:assert receipt['map_bytes']==str(Path(request['map']).stat().st_size)
                    if receipt['destination_bytes'] is not None:assert receipt['destination_bytes']==str(Path(request['destination']).stat().st_size)
            records.append(dict(name=name, exit_code=result.returncode, output_sha256=digest(result.stdout),
                refusal=value.get('refusal'), outcome=value.get('outcome'), passed=True))
            return value

        def resume(request):
            return dict(request, mode='resume')

        for size in (0,1,4095,4096,4097,65535,65536,65537,131073):
            req = fixture('golden-'+str(size),size); expected=source_bytes(size)
            prepared=run('inert-prepare-'+str(size),dict(req,mode='prepare'))
            assert snapshot(req)==[None,None] and Path(req['source']).read_bytes()==expected
            value=run('golden-'+str(size),req,status='completed')
            assert Path(req['destination']).read_bytes()==Path(req['source']).read_bytes()==expected
            assert value['outcome']['checkpoint_bytes']==value['outcome']['source_bytes']==str(size)
            assert value['outcome']['substituted_bytes']=='0' and not value['outcome']['uncertain_effect']
            inspect_map(Path(req['map']),expected)
            before=snapshot(req);v=run('sealed-resume-'+str(size),resume(req),status='completed')
            assert snapshot(req)==before and v['outcome']['attempt_written_bytes']=='0'
        for chunk,size in ((65536,131073),(1048576,131073),(1048576,1048576),(1048576,1048577)):
            name='chunk-'+str(chunk)+'-'+str(size);req=fixture(name,size);req['options']=options(chunk)
            run(name,req,status='completed');assert Path(req['destination']).read_bytes()==source_bytes(size)
            inspect_map(Path(req['map']),source_bytes(size))
        req=fixture('unicode');folder=Path(req['source']).parent
        Path(req['source']).rename(folder/'--help-é-漢.img');req['source']=str(folder/'--help-é-漢.img')
        req['destination']=str(folder/'image-é-漢.img');req['map']=str(folder/'map-é-漢.jsonl')
        run('lossless-unicode-paths',req,status='completed');inspect_map(Path(req['map']),source_bytes(9000))

        for key in ('destination','map'):
            req=fixture('exists-'+key);Path(req[key]).write_bytes(b'prior-owner');before=snapshot(req)
            run('no-clobber-'+key,req,refusal='acquisition_output_exists');assert snapshot(req)==before
        for variant in ('source','same','case'):
            req=fixture('alias-'+variant)
            if variant=='source':req['destination']=req['source']
            else:req['map']=req['destination'].upper() if variant=='case' else req['destination']
            before=snapshot(req);run('alias-'+variant,req,refusal='acquisition_output_exists' if variant=='source' else 'acquisition_file_alias')
            assert snapshot(req)==before
        for role in ('source_read','destination_write','map_write','host_effects','digest'):
            req=fixture('grant-'+role)
            req['grant']=dict(plan_digest='$prepared', source_read=True,destination_write=True,map_write=True,host_effects=True)
            if role=='digest':req['grant']['plan_digest']='sha256:'+'0'*64
            else:req['grant'][role]=False
            run('grant-'+role,req,status='refused',diagnostic='acquisition_grant');assert snapshot(req)==[None,None]
        for changed in ({'chunk_bytes':'0'},{'retry_limit':'4'},{'read_policy':'other'},{'substitution':'silent'},{'read_policy':'failing-read-mostly','retry_limit':'1'}):
            req=fixture('options-'+str(len(records)));req['source']=str(owned/'missing.img');req['options'].update(changed)
            run('policy-before-source-'+str(changed),req,refusal='acquisition_file_options');assert snapshot(req)==[None,None]
        for name in ('NUL','CON.txt','bad:stream','bad\x1bname','trailing.','trailing ','C:relative.img','\\\\.\\PhysicalDrive0','\\\\?\\C:\\no.img','//absent/share.img','x'*241):
            req=fixture('path-'+str(len(records)));req['source']=name
            run('path-refusal-'+repr(name),req,refusal='image_path_profile');assert snapshot(req)==[None,None]
        req=fixture('missing');Path(req['source']).unlink();run('missing-source',req,refusal='image_source_open')
        req=fixture('directory');req['source']=str(Path(req['source']).parent);run('directory-source',req,refusal='image_file_type')
        req=fixture('missing-parent');req['destination']=str(owned/'absent'/'out.img');run('missing-parent',req,refusal='image_parent_open')
        req=fixture('hardlink');alias=Path(req['source']).with_name('alias.img');os.link(req['source'],alias)
        try:run('hardlink-source',req,refusal='image_file_aliases')
        finally:alias.unlink()

        # Actual normal-file sharing conflicts on owned source only.
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];kernel.CreateFileW.restype=W.HANDLE
        kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
        for label,access,sharing in (('writer',0x40000000,7),('exclusive-reader',0x80000000,0)):
            req=fixture('sharing-'+label);h=kernel.CreateFileW(req['source'],access,sharing,None,3,0,None)
            assert h not in (None,C.c_void_p(-1).value),C.get_last_error()
            try:v=run('sharing-'+label,req,refusal='image_source_open');assert v['platform_code']=='32'
            finally:assert kernel.CloseHandle(h)
        # Empty DACL on our generated source, restoring the exact descriptor.
        advapi=C.WinDLL('advapi32',use_last_error=True)
        advapi.GetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)];advapi.GetFileSecurityW.restype=W.BOOL
        advapi.SetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p];advapi.SetFileSecurityW.restype=W.BOOL
        advapi.InitializeSecurityDescriptor.argtypes=[C.c_void_p,W.DWORD];advapi.InitializeSecurityDescriptor.restype=W.BOOL
        advapi.InitializeAcl.argtypes=[C.c_void_p,W.DWORD,W.DWORD];advapi.InitializeAcl.restype=W.BOOL
        advapi.SetSecurityDescriptorDacl.argtypes=[C.c_void_p,W.BOOL,C.c_void_p,W.BOOL];advapi.SetSecurityDescriptorDacl.restype=W.BOOL
        req=fixture('DACL');needed=W.DWORD()
        advapi.GetFileSecurityW(req['source'],4,None,0,C.byref(needed));assert needed.value
        old=C.create_string_buffer(needed.value);assert advapi.GetFileSecurityW(req['source'],4,old,len(old),C.byref(needed))
        sd=C.create_string_buffer(64);acl=C.create_string_buffer(8)
        assert advapi.InitializeSecurityDescriptor(sd,1) and advapi.InitializeAcl(acl,8,2) and advapi.SetSecurityDescriptorDacl(sd,True,acl,False)
        assert advapi.SetFileSecurityW(req['source'],4,sd)
        try:
            v=run('actual-source-access-denied',req,refusal='image_source_open');assert v['platform_code']=='5' and snapshot(req)==[None,None]
        finally:assert advapi.SetFileSecurityW(req['source'],4,old)
        assert Path(req['source']).read_bytes()==source_bytes(9000)
        req=fixture('junction');junction=owned/'reparse'
        made=subprocess.run([os.environ['COMSPEC'],'/d','/c','mklink','/J',str(junction),str(Path(req['source']).parent)],capture_output=True,timeout=10)
        assert made.returncode==0,(made.stdout,made.stderr)
        try:
            req['source']=str(junction/'source.img');run('reparse-parent',req,refusal='image_reparse_source')
        finally:junction.rmdir()

        req=fixture('capacity');run('capacity-before-create',req,True,{'NO_CAPACITY':1},status='refused',diagnostic='acquisition_capacity');assert snapshot(req)==[None,None]
        for stop in (0,4096):
            req=fixture('stop-'+str(stop));v=run('stop-'+str(stop),req,True,{'STOP_AFTER':stop},status='paused')
            assert v['outcome']['checkpoint_bytes']==str(stop)
            if stop==0:assert snapshot(req)==[None,None]
            else:
                run('resume-stop-'+str(stop),resume(req),True,status='completed');inspect_map(Path(req['map']),source_bytes(9000))
        for fault in ('READ_ERROR','SHORT_READ'):
            req=fixture('read-'+fault);v=run('read-'+fault,req,True,{fault:1},status='failed',diagnostic='acquisition_source_read')
            assert Path(req['destination']).read_bytes()==b'' and Path(req['source']).read_bytes()==source_bytes(9000)
            assert inspect_map(Path(req['map']),b'',False)[-1]['type']=='read_failure'
            run('read-retry-attempt-'+fault,resume(req),True,status='completed');inspect_map(Path(req['map']),source_bytes(9000))
        for policy in ('ordinary','failing-read-mostly'):
            req=fixture('zero-'+policy);req['options']=options(policy=policy,substitution='zero-fill')
            v=run('explicit-zero-'+policy,req,True,{'READ_ERROR':1},status='completed_with_substitution')
            assert v['outcome']['source_bytes']=='0' and v['outcome']['substituted_bytes']=='9000'
            assert Path(req['destination']).read_bytes()==b'\0'*9000;inspect_map(Path(req['map']),b'\0'*9000)
        for fault in ('WRITE_ERROR','PARTIAL_WRITE'):
            req=fixture('write-'+fault);v=run('write-'+fault,req,True,{fault:1},status='failed')
            assert v['outcome']['uncertain_effect'] and v['outcome']['checkpoint_bytes']=='0'
            if fault=='WRITE_ERROR':assert v['receipt']['platform_code']=='112'
            run('resume-'+fault,resume(req),True,status='completed');inspect_map(Path(req['map']),source_bytes(9000))
            assert Path(req['destination']).read_bytes()==source_bytes(9000)
        for fault in ('MAP_FLUSH_ERROR','DESTINATION_FLUSH_ERROR'):
            req=fixture('flush-'+fault);v=run('flush-'+fault,req,True,{fault:1},status='failed')
            assert v['outcome']['checkpoint_bytes']=='0' and v['receipt']['platform_code']=='29'
            run('resume-flush-'+fault,resume(req),True,status='completed');inspect_map(Path(req['map']),source_bytes(9000))
        req=fixture('torn-checkpoint');v=run('torn-checkpoint',req,True,{'TORN_MAP_TYPE':'checkpoint'},status='failed')
        assert v['outcome']['checkpoint_bytes']=='0' and v['outcome']['uncertain_effect']
        v=run('resume-torn-checkpoint',resume(req),True,status='completed');assert v['outcome']['attempt_written_bytes']=='4904'
        inspect_map(Path(req['map']),source_bytes(9000))
        req=fixture('failing-resume');req['options']=options(policy='failing-read-mostly')
        run('failing-pause',req,True,{'STOP_AFTER':4096},status='paused')
        v=run('failing-resume-no-prefix-reread',resume(req),True,status='completed');assert v['outcome']['attempt_read_bytes']=='4904'
        req=fixture('hooks-absent');run('hooks-absent',req,False,{k:1 for k in ('READ_ERROR','SHORT_READ','WRITE_ERROR','PARTIAL_WRITE','TORN_MAP','NO_CAPACITY','PAUSE','STOP_AFTER')},status='completed')
        assert Path(req['destination']).read_bytes()==source_bytes(9000)

        for corruption in ('complete-json','incomplete','unexplained-suffix','checkpoint-data','source-change','output-generation','map-generation','options','code-generation','sealed-tail'):
            req=fixture('corrupt-'+corruption)
            if corruption in ('code-generation','sealed-tail'):run('setup-'+corruption,req,True,status='completed')
            else:run('setup-'+corruption,req,True,{'STOP_AFTER':4096},status='paused')
            if corruption=='complete-json':
                with Path(req['map']).open('ab') as f:f.write(b'{}\n')
            elif corruption in ('incomplete','unexplained-suffix','sealed-tail'):
                with Path(req['map']).open('ab') as f:f.write(b'{torn')
                if corruption=='unexplained-suffix':
                    with Path(req['destination']).open('ab') as f:f.write(b'unexplained')
            elif corruption=='source-change':
                with Path(req['source']).open('r+b') as f:f.write(b'changed')
            elif corruption=='checkpoint-data':
                with Path(req['destination']).open('r+b') as f:f.write(b'changed')
            elif corruption in ('output-generation','map-generation'):
                path=Path(req['destination' if corruption=='output-generation' else 'map']);data=path.read_bytes()
                # Retain old inode while creating replacement to prevent immediate ID reuse.
                path.rename(path.with_suffix('.old'));path.write_bytes(data)
            elif corruption=='options':req['options']=options(65536)
            before=snapshot(req)
            if corruption=='incomplete':
                run('repair-incomplete-tail',resume(req),True,status='completed');inspect_map(Path(req['map']),source_bytes(9000))
            elif corruption in ('source-change','output-generation','map-generation','options','code-generation'):
                run('refuse-'+corruption,resume(req),corruption!='code-generation',refusal='acquisition_resume_options' if corruption=='options' else 'acquisition_resume_binding')
                assert snapshot(req)==before
            else:
                run('refuse-'+corruption,resume(req),True,status='failed',diagnostic='acquisition_unexplained_output' if corruption=='unexplained-suffix' else 'acquisition_destination_verification' if corruption=='checkpoint-data' else 'acquisition_map_after_seal' if corruption=='sealed-tail' else None)
                assert snapshot(req)==before

        # Read the observed event with a finite timeout; never guess whether a
        # worker is alive. Terminate only our Popen child and wait before resume.
        def paused(request,event,release=None):
            callenv=dict(env,DISKED_ACQ_TEST_EVENT=event,DISKED_ACQ_TEST_PAUSE='1')
            if release:callenv['DISKED_ACQ_TEST_RELEASE_FILE']=str(release)
            child=subprocess.Popen([probes[1]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=callenv,cwd=root)
            child.stdin.write(canonical(request));child.stdin.close();messages=queue.Queue()
            threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
            try:
                message=json.loads(messages.get(timeout=12));assert message['event']==event and int(message['pid'])==child.pid and child.poll() is None
                process_observations.append(dict(event=event,pid=child.pid,alive_observed=True,terminal_observed=False,exit_code=None))
            except BaseException:
                child.kill();child.wait(timeout=10);raise
            return child

        def terminate(child):
            assert child.poll() is None
            child.kill();child.wait(timeout=10);assert child.poll() is not None
            observation=next(p for p in process_observations if p['pid']==child.pid)
            observation.update(terminal_observed=True,exit_code=child.returncode,method='owned-child-kill-and-wait')
            child.stdout.close();child.stderr.close()

        for event in ('append-header','append-pending','destination-written','destination-flushed','append-checkpoint','append-seal'):
            req=fixture('terminate-'+event);child=paused(req,event)
            try:
                v=run('live-worker-sharing-'+event,resume(req),True,refusal='acquisition_destination_open');assert v['platform_code']=='32'
            finally:terminate(child)
            v=run('after-process-termination-'+event,resume(req),True,status='completed')
            assert Path(req['destination']).read_bytes()==Path(req['source']).read_bytes()==source_bytes(9000)
            inspect_map(Path(req['map']),source_bytes(9000))
            if event=='append-seal':assert v['outcome']['attempt_written_bytes']=='0'
        for raced in ('map','destination'):
            req=fixture('race-'+raced);release=Path(req['source']).parent/'release'
            child=paused(req,'before-create',release)
            try:
                Path(req[raced]).write_bytes(b'other-owner');release.write_bytes(b'release')
                # Drain while waiting: the complete receipt can exceed a pipe's
                # buffer. A blocked writer is not evidence of worker failure.
                child.stdin=None
                stdout,stderr=child.communicate(timeout=15);assert child.returncode==0,(stdout,stderr)
                observation=next(p for p in process_observations if p['pid']==child.pid)
                observation.update(terminal_observed=True,exit_code=child.returncode,method='test-release-file-and-communicate')
                result=json.loads(stdout.splitlines()[-1]);out=result['outcome']
                assert out['status']==('refused' if raced=='map' else 'failed'),result
                assert out['diagnostic']=='acquisition_'+raced+'_create'
                assert Path(req[raced]).read_bytes()==b'other-owner'
                if raced=='map':assert not Path(req['destination']).exists()
                else:assert Path(req['map']).read_bytes()==b''
                assert result['receipt']['map_bytes']==(None if raced=='map' else '0')
                records.append(dict(name='CREATE_NEW-race-'+raced,exit_code=child.returncode,outcome=out,passed=True))
            finally:
                if child.poll() is None:terminate(child)
                else:child.stdout.close();child.stderr.close()
        req=fixture('partial-bootstrap');child=paused(req,'map-created')
        try:assert Path(req['map']).exists() and not Path(req['destination']).exists()
        finally:terminate(child)
        before=snapshot(req);run('partial-bootstrap-retained',req,True,refusal='acquisition_output_exists');assert snapshot(req)==before
        req=fixture('torn-header');run('torn-header',req,True,{'TORN_MAP':1},status='failed')
        before=snapshot(req);run('torn-header-resume',resume(req),True,refusal='acquisition_file_header');assert snapshot(req)==before

    evidence=dict(schema='org.disked.file-acquisition-tests/1',passed=True,cases=len(records),
        scope='generated Windows ordinary files, controlled API faults and observed owned-child termination; no physical/power-loss qualification',
        probes=[dict(path=p,sha256=digest(Path(p).read_bytes())) for p in probes],process_observations=process_observations,records=records)
    if args.evidence:Path(args.evidence).write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,cases=len(records))))


if __name__=='__main__':main()
