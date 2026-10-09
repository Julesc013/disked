"""Independent generated-file checks for private unprivileged acquisition workers.

Actual worker termination is a controlled owned-child test, not power-loss or
physical-storage qualification. This does not admit a public product command.
"""
import argparse
from contextlib import contextmanager
import copy
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def source_bytes(size):
    block = bytes((i * 37 + 11) % 251 for i in range(65536))
    return (block * (size // len(block) + 1))[:size]


def map_check(path, expected, sealed=True):
    raw = path.read_bytes(); assert raw.endswith(b'\n')
    previous = 'sha256:' + '0' * 64; covered = 0; rows = []
    for seq, body in enumerate(raw.splitlines()):
        row = json.loads(body)
        assert canonical(row) == body and row['sequence'] == str(seq) and row['previous'] == previous
        assert row['schema'] == 'org.disked.acquisition-record-prototype/2'
        previous = digest(body)
        if row['type'] == 'header':
            assert seq == 0 and row['payload']['plan_digest'] == digest(canonical(row['payload']['plan']))
            capture = row['payload']['capture']
            assert capture['capture_epoch'] == row['payload']['plan']['capture_epoch']
            assert capture['clock'] == 'windows-filetime-wall' and int(capture['started']) > 0
        if row['type'] == 'checkpoint':
            p = row['payload']; size = int(p['length'])
            assert int(p['offset']) == covered and p['sha256'] == digest(expected[covered:covered+size])
            covered += size
        rows.append(row)
    if sealed:
        assert rows[-1]['type'] == 'seal' and covered == len(expected)
    else:
        assert rows[-1]['type'] != 'seal'
    return rows


def history_check(path):
    raw = path.read_bytes(); assert raw.endswith(b'\n') and len(raw) <= 1048576
    previous = '0' * 64; binding = None; covered = 0; rows = []
    for seq, body in enumerate(raw.splitlines(), 1):
        row = json.loads(body); assert canonical(row) == body and len(body) <= 16384
        assert row['previous'] == previous and row['schema'] == 'org.disked.acquisition-worker-record/1'
        original = row.pop('digest'); assert hashlib.sha256(canonical(row)).hexdigest() == original
        previous = original; state = row['state']
        assert state['sequence'] == str(seq) and int(state['observed_filetime']) > 0
        if binding is None:binding = state['binding']
        assert state['binding'] == binding and int(state['checkpoint_bytes']) >= covered
        covered = int(state['checkpoint_bytes'])
        assert int(state['source_bytes']) + int(state['substituted_bytes']) == covered
        if state['phase'] == 'active':assert not state['quiescent'] and state['outcome'] is None
        else:assert state['phase'] == 'finished' and state['quiescent'] and seq == len(raw.splitlines())
        row['digest'] = original; rows.append(row)
    assert 2 <= len(rows) <= 64
    return rows


def reconnectable_start(value):
    """An admission timeout is unresolved, never successful or safe to restart.

    Allow only the specified timeout envelope. The caller must subsequently
    inspect this exact operation and prove its terminal bytes/map and exit.
    """
    assert re.fullmatch(r'image-op:[0-9a-f]{32}', value.get('operation_id') or ''), value
    if value.get('status') == 'unknown':
        assert value.get('diagnostic') == 'acquisition_admission_unresolved', value
        assert value.get('platform_code') == '0', value
        assert value.get('value') == {'admission': 'unresolved'}, value
    else:
        assert value.get('status') in ('accepted_running', 'completed'), value


K = C.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; K.OpenProcess.restype = W.HANDLE
K.CloseHandle.argtypes = [W.HANDLE]
K.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
K.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
K.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
K.OpenJobObjectW.argtypes = [W.DWORD,W.BOOL,W.LPCWSTR];K.OpenJobObjectW.restype=W.HANDLE
K.IsProcessInJob.argtypes = [W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
K.QueryInformationJobObject.argtypes = [W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)]


class JobBasic(C.Structure):
    _fields_=[('process_time',C.c_int64),('job_time',C.c_int64),('flags',W.DWORD),
        ('minimum_working',C.c_size_t),('maximum_working',C.c_size_t),('process_limit',W.DWORD),
        ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class JobIo(C.Structure):
    _fields_=[(name,C.c_uint64) for name in ('read_operations','write_operations','other_operations','read_bytes','write_bytes','other_bytes')]


class JobLimits(C.Structure):
    _fields_=[('basic',JobBasic),('io',JobIo),('process_memory',C.c_size_t),('job_memory',C.c_size_t),
        ('peak_process_memory',C.c_size_t),('peak_job_memory',C.c_size_t)]


def owned_process(state, executable, terminate=False):
    binding = state['binding']; pid = int(binding['process_id'])
    handle = K.OpenProcess(0x1000 | 0x100000 | (1 if terminate else 0), False, pid)
    if not handle:
        assert not terminate and C.get_last_error() == 87, C.get_last_error()
        return None
    stamps = [W.FILETIME() for _ in range(4)]
    assert K.GetProcessTimes(handle, *map(C.byref, stamps))
    created = stamps[0].dwHighDateTime * 2**32 + stamps[0].dwLowDateTime
    assert created == int(binding['process_created']), (pid, created, binding)
    path = C.create_unicode_buffer(1024); size = W.DWORD(1024)
    if K.QueryFullProcessImageNameW(handle, 0, path, C.byref(size)):
        assert Path(path.value).resolve() == Path(executable).resolve()
    else:
        # Windows may withdraw image-query access during teardown before the
        # process becomes signaled. Creation time is still checked; the caller
        # must wait on this retained handle. Live/termination checks require it.
        assert not terminate and state['phase']=='finished', C.get_last_error()
    return handle


@contextmanager
def fixture_directory(scratch):
    # Failure preserves the exact owned files, including any still-running
    # worker. Cleanup must never remove its recovery dependencies on timeout.
    folder=Path(tempfile.mkdtemp(prefix='disked-acq-worker-',dir=scratch)).resolve()
    assert folder.parent==scratch.resolve()
    try:yield folder
    except BaseException:
        print('Failed fixture retained:',folder,flush=True)
        raise
    else:
        deadline=time.monotonic()+5
        while True:
            try:shutil.rmtree(folder);break
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.025)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True); parser.add_argument('--fault', required=True)
    parser.add_argument('--root', default='.'); parser.add_argument('--evidence')
    args = parser.parse_args(); root = Path(args.root).resolve()
    probes = [str(Path(p).resolve()) for p in (args.probe, args.fault)]
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_', 'DISKED_TEST_'))}
    observations = []; workers = []; scratch = root/'.aide-local'; scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:

        def call(name, request, fault=False, injected=None, refusal=None):
            if request['mode'] in ('prepare','start'):print('case',name,flush=True)
            callenv = dict(env)
            if injected:
                for k in injected:
                    if k.startswith('STORE:'):callenv['DISKED_TEST_STORE_FAULT']=k[6:]
                    else:callenv['DISKED_ACQ_WORKER_TEST_'+k]='1'
            result = subprocess.run([probes[int(fault)]], input=canonical(request), capture_output=True,
                env=callenv, cwd=root, timeout=12)
            assert result.returncode == (3 if refusal else 0), (name, result.returncode, result.stdout, result.stderr)
            assert not result.stderr, (name, result.stderr)
            value = json.loads(result.stdout)
            if refusal:assert value['refusal'] == refusal, (name, value)
            observations.append(dict(name=name, input_sha256=digest(canonical(request)), output_sha256=digest(result.stdout),
                exit_code=result.returncode, status=value.get('status'), diagnostic=value.get('diagnostic'), passed=True))
            return value

        def fixture(name, size=65537):
            folder=owned/name; folder.mkdir(); state=folder/'state'; state.mkdir()
            src=folder/'source.img'; src.write_bytes(source_bytes(size))
            return dict(mode='prepare', source=str(src), destination=str(folder/'copy.img'), map=str(folder/'copy.map'), state_directory=str(state))

        def prepare(name, request, fault=False):
            before={p.name:p.read_bytes() for p in Path(request['state_directory']).iterdir() if p.is_file()}
            value=call(name,request,fault)
            assert digest(canonical(value['definition'])) == value['definition_digest']
            assert before == {p.name:p.read_bytes() for p in Path(request['state_directory']).iterdir() if p.is_file()}
            d=value['definition'];assert d['request']['explicit_options'] is True
            assert d['store']['children'] == ['acquisition.request','acquisition.records','acquisition.cancel','acquisition.admission']
            return dict(mode='start', definition=d, grant=dict(definition_digest=value['definition_digest'],
                source_read=True,destination_write=True,map_write=True,host_effects=True))

        def inspect(name, request, ident, fault=False, cancel=False):
            return call(name,dict(mode='cancel' if cancel else 'inspect', operation_id=ident,
                state_directory=request['state_directory']),fault)

        def finished(name, request, first, fault=False, timeout=30):
            ident=first['operation_id']; assert ident and ident.startswith('image-op:')
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                value=inspect(name,request,ident,fault)
                state=value['value'].get('state',{})
                if state.get('phase') == 'finished':
                    assert value['status'] == 'completed', value
                    handle=owned_process(state,probes[int(fault)])
                    if handle:
                        try:assert K.WaitForSingleObject(handle,2000)==0
                        finally:K.CloseHandle(handle)
                    return value
                assert value['value'].get('worker_observation') == 'running', value
                time.sleep(.03)
            raise AssertionError((name,'finite fixture did not finish'))

        def completed(name, request, value):
            state=value['value']['state']; out=state['outcome']; receipt=state['receipt']
            expected=Path(request['source']).read_bytes()
            assert out['status']=='completed' and out['checkpoint_bytes']==str(len(expected)) and not out['uncertain_effect'],value
            assert Path(request['destination']).read_bytes()==expected
            rows=map_check(Path(request['map']),expected)
            history=history_check(Path(request['state_directory'])/'acquisition.records')
            assert history[-1]['state']==state
            assert receipt['original_capture']==rows[0]['payload']['capture']
            assert receipt['attempt_id']==state['binding']['attempt_id']
            assert receipt['source_consistency']=='live-uncoordinated' and not receipt['physical_backing_qualified']
            assert receipt['flush_scope']=='per-file-FlushFileBuffers-API-only'
            start=int(receipt['started_filetime']); end=int(receipt['finished_filetime'])
            assert start>0 and end>0 and int(receipt['elapsed_ms'])>=0
            assert receipt['wall_clock_regressed']==(end<start)
            workers.append(dict(name=name, binding=state['binding'], outcome=out, receipt=receipt, states=len(history)))
            return rows

        for size in (0,1,65535,65536,65537,1048577,2097153):
            req=fixture('golden-'+str(size),size); reviewed=prepare('prepare-'+str(size),req)
            assert not Path(req['destination']).exists() and not Path(req['map']).exists()
            first=call('start-'+str(size),reviewed)
            reconnectable_start(first)
            end=finished('reconnect-'+str(size),req,first);completed('golden-'+str(size),req,end)
            before=(Path(req['destination']).read_bytes(),Path(req['map']).read_bytes())
            repeat=call('no-relaunch-'+str(size),reviewed)
            assert repeat['operation_id']==first['operation_id'] and repeat['value']['state']==end['value']['state']
            assert before==(Path(req['destination']).read_bytes(),Path(req['map']).read_bytes())

        req=fixture('grant-refusals'); reviewed=prepare('review-grants',req)
        for flag in ('source_read','destination_write','map_write','host_effects'):
            denied=copy.deepcopy(reviewed);denied['grant'][flag]=False
            value=call('deny-'+flag,denied);assert value['status']=='refused' and value['diagnostic']=='acquisition_worker_grant'
        denied=copy.deepcopy(reviewed);denied['grant']['definition_digest']='sha256:'+'f'*64
        value=call('deny-unbound-grant',denied);assert value['status']=='refused'
        value=call('deny-different-executable-generation',reviewed,True)
        assert value['status']=='refused' and value['diagnostic']=='acquisition_definition_changed'
        assert not list(Path(req['state_directory']).iterdir()) and not Path(req['destination']).exists()
        src=Path(req['source']); original=src.read_bytes();src.write_bytes(b'changed-generation')
        value=call('refuse-source-generation-change',reviewed)
        assert value['status']=='refused' and value['diagnostic']=='acquisition_reviewed_definition_changed',value
        assert src.read_bytes()==b'changed-generation' and not list(Path(req['state_directory']).iterdir())

        req=fixture('directory-generation-change');reviewed=prepare('review-directory-generation',req)
        directory=Path(req['state_directory']);directory.rename(directory.with_name('old-state'));directory.mkdir()
        value=call('refuse-directory-generation-change',reviewed)
        assert value['status']=='refused' and value['diagnostic']=='acquisition_definition_changed'
        assert not list(directory.iterdir()) and not Path(req['map']).exists()

        req=fixture('metadata-alias');req['destination']=str(Path(req['state_directory'])/'ACQUISITION.RECORDS')
        call('refuse-operation-metadata-alias',req,refusal='acquisition_operation_store_alias')
        assert not list(Path(req['state_directory']).iterdir())
        req=fixture('occupied-store');marker=Path(req['state_directory'])/'retained';marker.write_bytes(b'keep')
        call('refuse-occupied-store',req,refusal='operation_directory_not_empty');assert marker.read_bytes()==b'keep'

        req=fixture('cancel-resume',2097153);reviewed=prepare('review-cancel',req,True)
        first=call('start-cancel',reviewed,True,('CHECKPOINT_DELAY',));assert first['status']=='accepted_running',first
        live=inspect('live-reconnect',req,first['operation_id'],True)
        assert live['value']['worker_observation']=='running' and not live['value']['state']['quiescent']
        handle=owned_process(live['value']['state'],probes[1]);assert handle;K.CloseHandle(handle)
        repeat=call('repeat-active-does-not-relaunch',reviewed,True)
        assert repeat['status']=='accepted_running' and repeat['value']['state']['binding']==live['value']['state']['binding']
        newstate=Path(req['state_directory']).parent/'other-state';newstate.mkdir()
        candidate=dict(req,resume=True,state_directory=str(newstate))
        call('exclude-second-writer',candidate,True,refusal='acquisition_destination_open')
        cancelled=inspect('request-cancellation',req,first['operation_id'],True,True)
        assert cancelled['value']['cancellation_request']=='requested'
        end=finished('await-cancel-checkpoint',req,first,True)
        out=end['value']['state']['outcome'];assert out['status']=='paused' and not out['uncertain_effect']
        checkpoint=int(out['checkpoint_bytes']);expected=Path(req['source']).read_bytes()
        assert checkpoint<len(expected) and Path(req['destination']).read_bytes()==expected[:checkpoint]
        rows=map_check(Path(req['map']),expected,False);original_capture=rows[0]['payload']['capture']
        original_bytes=Path(req['map']).read_bytes()
        late=inspect('cancel-too-late',req,first['operation_id'],True,True)
        assert late['value']['cancellation_request']=='too_late' and Path(req['map']).read_bytes()==original_bytes
        reviewed_resume=prepare('review-resume-new-attempt',candidate,True)
        resumed=call('start-resume-new-attempt',reviewed_resume,True)
        resumed_end=finished('reconnect-resume',candidate,resumed,True);newrows=completed('resumed',candidate,resumed_end)
        assert Path(req['map']).read_bytes().startswith(original_bytes)
        assert newrows[0]['payload']['capture']==original_capture
        assert resumed['operation_id']!=first['operation_id']
        assert resumed_end['value']['state']['binding']['attempt_id']!=end['value']['state']['binding']['attempt_id']
        assert resumed_end['value']['state']['receipt']['original_capture']['attempt_id']!=resumed_end['value']['state']['receipt']['attempt_id']

        req=fixture('checkpoint-observer-error',65537);reviewed=prepare('review-checkpoint-observer-error',req,True)
        first=call('start-checkpoint-observer-error',reviewed,True,('CHECKPOINT_OBSERVER_ERROR',))
        end=finished('checkpoint-observer-error-terminal',req,first,True)
        out=end['value']['state']['outcome']
        assert out['status']=='failed' and out['diagnostic']=='acquisition_test_observer_error'
        assert out['checkpoint_bytes']=='65536' and not out['uncertain_effect']
        map_check(Path(req['map']),Path(req['source']).read_bytes(),False)
        assert Path(req['destination']).read_bytes()==Path(req['source']).read_bytes()[:65536]

        req=fixture('post-create-validation');reviewed=prepare('review-post-create-validation',req,True)
        first=call('post-create-validation-unknown',reviewed,True,('STORE:created_validation',))
        assert first['status']=='unknown' and first['operation_id'] and first['diagnostic']=='operation_directory_changed',first
        before={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()}
        assert before=={'acquisition.admission':b''}
        assert not Path(req['destination']).exists() and not Path(req['map']).exists()
        repeat=call('post-create-validation-no-restart',reviewed,True)
        assert repeat['status']=='refused' and before=={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()},repeat

        for fault in ('full','short','flush'):
            req=fixture('worker-store-fault-'+fault);reviewed=prepare('review-store-fault-'+fault,req,True)
            first=call('store-fault-retained-'+fault,reviewed,True,('STORE:acquisition_record.'+fault,))
            assert first['status']=='unknown' and first['operation_id'],first
            observed=inspect('observe-store-fault-'+fault,req,first['operation_id'],True)
            assert observed['status']=='unknown',observed
            assert not Path(req['destination']).exists() and not Path(req['map']).exists()
            before={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()}
            repeat=call('store-fault-no-restart-'+fault,reviewed,True)
            assert repeat['status']=='unknown' and repeat['operation_id']==first['operation_id']
            assert before=={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()}

        req=fixture('late-admission',65537);reviewed=prepare('review-late-admission',req,True)
        first=call('admission-timeout-is-unresolved',reviewed,True,('ADMISSION_DELAY',))
        assert first['status']=='unknown' and first['operation_id'],first
        reconnectable_start(first)
        # Use the real delayed-worker response through the same gate as golden
        # acquisitions, then reject unrelated uncertainty without any restart.
        for name,key,value in (
            ('unknown-diagnostic','diagnostic','acquisition_worker_unresolved'),
            ('unknown-shape','value',{}),
            ('unknown-platform','platform_code','5'),
            ('missing-operation','operation_id',None),
            ('malformed-operation','operation_id','image-op:wrong'),
            ('refused-start','status','refused'),
        ):
            changed=copy.deepcopy(first);changed[key]=value
            try:reconnectable_start(changed)
            except AssertionError:pass
            else:raise AssertionError(('invalid admission accepted',name))
            observations.append(dict(name='reject-reconnect-'+name,passed=True,
                scope='Synthetic contradictory envelope derived from actual delayed admission'))
        live=inspect('observe-late-admission',req,first['operation_id'],True)
        assert live['value']['worker_observation']=='running'
        repeat=call('late-admission-no-restart',reviewed,True)
        assert repeat['status']=='accepted_running' and repeat['operation_id']==first['operation_id']
        completed('late-admission',req,finished('late-admission-eventual',req,first,True))

        req=fixture('normal-ignores-fault-env',65537);reviewed=prepare('review-normal-no-fault',req)
        first=call('normal-ignores-fault-controls',reviewed,False,('ADMISSION_DELAY','CHECKPOINT_DELAY'))
        reconnectable_start(first)
        completed('normal-no-fault',req,finished('normal-no-fault-finish',req,first))

        active=[]
        for i in range(4):
            req=fixture('aggregate-'+str(i),2097153);reviewed=prepare('review-aggregate-'+str(i),req,True)
            first=call('start-aggregate-'+str(i),reviewed,True,('CHECKPOINT_DELAY',))
            assert first['status']=='accepted_running',first
            active.append((req,first))
        live=inspect('aggregate-membership',active[0][0],active[0][1]['operation_id'],True)
        state=live['value']['state'];handle=owned_process(state,probes[1]);assert handle
        host=live['value']['definition']['host_id']
        job=K.OpenJobObjectW(4,False,'Local\\DiskEd.Fake.Workers.v1.'+host);assert job
        try:
            limits=JobLimits();assert K.QueryInformationJobObject(job,9,C.byref(limits),C.sizeof(limits),None)
            member=W.BOOL();assert K.IsProcessInJob(handle,job,C.byref(member)) and member.value
            assert limits.basic.flags==0x108|0x200 and limits.basic.process_limit==4
            assert limits.process_memory==128*1024*1024 and limits.job_memory==512*1024*1024
            workers.append(dict(name='aggregate-budget',limits=dict(active_processes=4,process_bytes=limits.process_memory,job_bytes=limits.job_memory),owned_process_id=state['binding']['process_id']))
        finally:K.CloseHandle(job);K.CloseHandle(handle)
        req=fixture('aggregate-excess');reviewed=prepare('review-excess-worker',req,True)
        excess=call('excess-worker-is-not-admitted',reviewed,True)
        assert excess['status']=='unknown' and excess['diagnostic']=='acquisition_spawn_failed' and int(excess['platform_code'])>0,excess
        assert not Path(req['destination']).exists() and not Path(req['map']).exists()
        for i,(req,first) in enumerate(active):
            cancelled=inspect('cancel-aggregate-'+str(i),req,first['operation_id'],True,True)
            assert cancelled['value']['cancellation_request']=='requested'
            end=finished('finish-aggregate-'+str(i),req,first,True)
            assert end['value']['state']['outcome']['status']=='paused'

        req=fixture('terminated-worker',2097153);reviewed=prepare('review-termination',req,True)
        first=call('start-owned-termination-fixture',reviewed,True,('CHECKPOINT_DELAY',))
        live=inspect('observe-owned-worker-before-termination',req,first['operation_id'],True)
        handle=owned_process(live['value']['state'],probes[1],True);assert handle
        try:
            assert K.WaitForSingleObject(handle,0)==258
            assert K.TerminateProcess(handle,177) and K.WaitForSingleObject(handle,2000)==0
        finally:K.CloseHandle(handle)
        unresolved=inspect('unfinished-worker-is-unresolved',req,first['operation_id'],True)
        assert unresolved['status']=='unknown' and unresolved['diagnostic']=='acquisition_worker_unresolved',unresolved
        before={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()}
        outputs=[Path(req[k]).read_bytes() if Path(req[k]).exists() else None for k in ('destination','map')]
        repeat=call('unfinished-worker-never-restarted',reviewed,True)
        assert repeat['status']=='unknown' and repeat['operation_id']==first['operation_id']
        assert before=={p.name:p.read_bytes() for p in Path(req['state_directory']).iterdir()}
        assert outputs==[Path(req[k]).read_bytes() if Path(req[k]).exists() else None for k in ('destination','map')]

        req=fixture('history-corruption');reviewed=prepare('review-history',req)
        first=call('start-history-fixture',reviewed);end=finished('finish-history-fixture',req,first)
        records=Path(req['state_directory'])/'acquisition.records';original=records.read_bytes()
        rows=[json.loads(row) for row in original.splitlines()]
        for name,modify in (
            ('contradictory-completion',lambda s:s['outcome'].__setitem__('checkpoint_bytes','0')),
            ('unknown-state-field',lambda s:s.__setitem__('unreviewed',True)),
            ('invalid-sequence',lambda s:s.__setitem__('sequence','18446744073709551616')),
            ('nonquiescent-terminal',lambda s:s.__setitem__('quiescent',False)),
            ('wrong-attempt-epoch',lambda s:s['binding'].__setitem__('attempt_id','attempt:'+'f'*32)),
        ):
            modified=copy.deepcopy(rows);modify(modified[-1]['state']);row=modified[-1];row.pop('digest')
            row['digest']=hashlib.sha256(canonical(row)).hexdigest()
            records.write_bytes(b''.join(canonical(row)+b'\n' for row in modified))
            value=inspect(name,req,first['operation_id'])
            assert value['status']=='unknown',value
            assert records.read_bytes()!=original
        records.write_bytes(original+b'{"partial":')
        value=inspect('torn-history-preserved',req,first['operation_id'])
        assert value['status']=='unknown' and value['diagnostic']=='acquisition_worker_history_torn',value
        assert records.read_bytes()==original+b'{"partial":'
        records.write_bytes(original)
        assert inspect('restored-fixture-history',req,first['operation_id'])['value']['state']==end['value']['state']
        value=inspect('wrong-operation-identity',req,'image-op:'+'0'*32)
        assert value['status']=='unknown'

        for words in (['__disked_acquisition_worker'],['__disked_acquisition_worker','0','0','0','0']):
            result=subprocess.run([probes[0],*words],capture_output=True,timeout=5)
            assert result.returncode==199 and not result.stdout and not result.stderr
            observations.append(dict(name='invalid-private-role',arguments=words,exit_code=result.returncode,passed=True))
    result=dict(schema='org.disked.acquisition-worker-tests/1',checks=len(observations),all_passed=True,
        physical_access=False,elevation=False,public_command_admitted=False,power_loss_qualified=False,
        observations=observations,workers=workers)
    if args.evidence:Path(args.evidence).write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    print('PASS:',len(observations),'private acquisition worker checks;',sum('outcome' in w for w in workers),'completed byte/map verifications')


if __name__=='__main__':main()
