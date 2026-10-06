"""Injected full/partial/flush failures on owned ordinary files, never a full volume."""
import argparse
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

P=argparse.ArgumentParser();P.add_argument('--exe',type=Path,required=True);P.add_argument('--fault',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.fault=ARGS.fault.resolve();OBS=[]
K=C.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
K.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];K.CloseHandle.argtypes=[W.HANDLE]

def environment(fault=''):
    result=os.environ.copy();result.pop('DISKED_TEST_STORE_FAULT',None)
    if fault:result['DISKED_TEST_STORE_FAULT']=fault
    return result

def invoke(exe,words,fault=''):
    p=subprocess.run([str(exe),*map(str,words),'--json'],capture_output=True,env=environment(fault),timeout=8)
    if p.stderr:raise AssertionError(p.stderr)
    return p.returncode,json.loads(p.stdout)

def files(state):return {p.name:p.read_bytes() for p in state.iterdir()}
def inventory(state):
    return {name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),hex=data.hex()) for name,data in files(state).items()}

def process(state):
    try:binding=json.loads((state/'operation.records').read_bytes().split(b'\n')[0])['state']['binding']
    except (FileNotFoundError,ValueError,KeyError):return None
    handle=K.OpenProcess(0x1000|0x100000,False,int(binding['process_id']))
    if not handle:
        if C.get_last_error()==87:return None  # Process identity no longer exists.
        raise C.WinError(C.get_last_error())
    times=[W.FILETIME() for _ in range(4)]
    if not K.GetProcessTimes(handle,*map(C.byref,times)):
        error=C.get_last_error();K.CloseHandle(handle);raise C.WinError(error)
    if (times[0].dwLowDateTime|(times[0].dwHighDateTime<<32))!=int(binding['process_created']):
        K.CloseHandle(handle);raise AssertionError('PID reused; never wait on that process')
    return handle

def wait(handle):
    if not handle:return None
    if K.WaitForSingleObject(handle,6000)!=0:raise AssertionError('owned finite worker did not exit')
    code=W.DWORD()
    if not K.GetExitCodeProcess(handle,C.byref(code)):raise C.WinError(C.get_last_error())
    return code.value

@contextmanager
def store():
    with tempfile.TemporaryDirectory(prefix='disked-store-fault-') as directory:
        state=Path(directory)
        try:yield state
        finally:
            # Finite fake workers retain their directory. Wait by exact process
            # identity before deleting the owned fixture, including on assertion.
            handle=process(state)
            try:wait(handle)
            finally:
                if handle:K.CloseHandle(handle)

class Failures(unittest.TestCase):
    def unknown(self,code,response,operation=None):
        self.assertEqual(6,code,response);self.assertEqual('unknown',response['status'])
        if operation:self.assertEqual(operation,response['operation_id'])

    def test_created_claim_write_failure_remains_unknown_and_is_not_retried(self):
        for mode in ('full','short','flush'):
            with self.subTest(mode=mode),store() as state:
                code,value=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state],'claim.'+mode)
                before=files(state)
                again,repeated=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state])
                OBS.append(dict(test='claim',mode=mode,exit=code,response=value,repeated=repeated,files=inventory(state)))
                self.unknown(code,value);self.assertIsNotNone(value['operation_id'])
                self.assertEqual('unresolved',value['result']['admission']);self.assertEqual('112',value['diagnostics'][0]['platform_code'])
                self.unknown(again,repeated);self.assertEqual(before,files(state));self.assertEqual(['request.json'],list(before))
                if mode=='full':self.assertEqual(b'',before['request.json'])
                elif mode=='short':
                    with self.assertRaises(ValueError):json.loads(before['request.json'])
                else:self.assertEqual(value['operation_id'],json.loads(before['request.json'])['operation_id'])

    def test_initial_flag_failure_retains_claim_without_spawning_worker(self):
        for mode in ('full','short','flush'):
            with self.subTest(mode=mode),store() as state:
                code,value=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state],'cancel_initial.'+mode)
                before=files(state);again,repeated=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state])
                OBS.append(dict(test='initial cancellation flag',mode=mode,exit=code,response=value,repeated=repeated,files=inventory(state)))
                self.unknown(code,value);self.assertEqual('112',value['diagnostics'][0]['platform_code'])
                self.assertEqual(value['operation_id'],json.loads(before['request.json'])['operation_id'])
                self.assertEqual(b'',before['operation.records']);self.unknown(again,repeated,value['operation_id'])
                self.assertEqual(before,files(state))

    def test_cancel_write_failure_preserves_identity_and_possible_observation(self):
        for mode in ('full','short','flush'):
            with self.subTest(mode=mode),store() as state:
                admitted,start=invoke(ARGS.fault,['plan','simulate','fake:cancel-checkpoint','--state-dir',state])
                self.assertEqual(5,admitted,start);operation=start['operation_id'];handle=process(state);self.assertTrue(handle)
                try:
                    code,value=invoke(ARGS.fault,['operation','cancel',operation,'--state-dir',state],'cancel_request.'+mode)
                    worker_exit=wait(handle)
                finally:K.CloseHandle(handle)
                end,final=invoke(ARGS.exe,['operation','inspect',operation,'--state-dir',state])
                OBS.append(dict(test='cancellation',mode=mode,exit=code,response=value,worker_exit=worker_exit,final=final,files=inventory(state)))
                self.unknown(code,value,operation);self.assertEqual('unresolved',value['result']['cancellation_request'])
                self.assertEqual('112',value['diagnostics'][0]['platform_code']);self.assertEqual(0,worker_exit)
                self.assertEqual(0,end,final)
                outcome='cancelled' if mode=='flush' else 'succeeded'
                self.assertEqual(outcome,final['result']['state']['outcome'])
                self.assertEqual('0' if mode=='flush' else '1',final['result']['state']['synthetic_effect_count'])

    def test_record_failure_stops_transitions_without_replaying_effects(self):
        for point in ('initialized','prepared','effect_dispatched','effect_observed','verified'):
            for mode in ('full','short','flush'):
                with self.subTest(point=point,mode=mode),store() as state:
                    code,admitted=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state],point+'.'+mode)
                    self.assertIn(code,(5,6),admitted);operation=admitted['operation_id'];self.assertIsNotNone(operation)
                    handle=process(state)
                    try:worker_exit=wait(handle) if handle else int(admitted['result']['worker_exit'])
                    finally:
                        if handle:K.CloseHandle(handle)
                    end,final=invoke(ARGS.exe,['operation','inspect',operation,'--state-dir',state])
                    before=files(state);again,repeated=invoke(ARGS.fault,['plan','simulate','fake:complete','--state-dir',state])
                    OBS.append(dict(test='record',point=point,mode=mode,admission=admitted,worker_exit=worker_exit,exit=end,final=final,repeated=repeated,files=inventory(state)))
                    self.assertEqual(119 if mode=='flush' else 118,worker_exit)
                    expected=0 if (point,mode)==('verified','flush') else 6
                    self.assertEqual(expected,end,final);self.assertEqual(expected,again,repeated);self.assertEqual(before,files(state))
                    if expected==0:
                        # Readable terminal truth is not evidence that its flush
                        # succeeded. The independent actual worker exit is 119.
                        self.assertEqual('succeeded',final['result']['state']['outcome'])
                    if mode=='short':self.assertFalse(before['operation.records'].endswith(b'\n'))

    def test_cached_observations_continue_after_failed_claim_in_same_stream(self):
        with store() as state:
            requests=[('claim','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(state))),
                      ('healthy','target.inspect',dict(target_id='fake:alpha@1')),
                      ('denied','target.inspect',dict(target_id='fake:denied@1')),
                      ('again','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(state)))]
            data=b''.join(json.dumps(dict(schema='org.disked.request/1',request_id=i,command=c,parameters=p,required_features=[])).encode()+b'\n' for i,c,p in requests)
            p=subprocess.run([str(ARGS.fault),'protocol','serve','--format=ndjson'],input=data,capture_output=True,env=environment('claim.short'),timeout=8)
            responses=[json.loads(line) for line in p.stdout.splitlines()]
            OBS.append(dict(test='same-stream partial store and retained graph',exit=p.returncode,responses=responses,files=inventory(state)))
            self.assertEqual(b'',p.stderr);self.assertEqual(6,p.returncode)
            self.assertEqual([r[0] for r in requests],[v['request_id'] for v in responses])
            self.assertEqual(['unknown','completed','completed','unknown'],[v['status'] for v in responses])
            self.assertEqual('current',responses[1]['result']['target']['properties']['state'])
            self.assertEqual('denied',responses[2]['result']['target']['properties']['state'])

    def test_product_does_not_read_test_injection_control(self):
        with store() as state:
            code,admitted=invoke(ARGS.exe,['plan','simulate','fake:complete','--state-dir',state],'claim.full')
            self.assertEqual(5,code,admitted);handle=process(state);self.assertTrue(handle)
            try:self.assertEqual(0,wait(handle))
            finally:K.CloseHandle(handle)
            end,final=invoke(ARGS.exe,['operation','inspect',admitted['operation_id'],'--state-dir',state])
            self.assertEqual(0,end,final);self.assertEqual('succeeded',final['result']['state']['outcome'])
            OBS.append(dict(test='product ignores fault control',final=final))

if __name__=='__main__':
    run=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(scope='Injected ordinary-file write/flush boundaries, not a full filesystem or driver failure',
        executable=str(ARGS.exe),sha256=hashlib.sha256(ARGS.exe.read_bytes()).hexdigest(),fault_executable=str(ARGS.fault),fault_sha256=hashlib.sha256(ARGS.fault.read_bytes()).hexdigest(),
        tests=run.result.testsRun,passed=run.result.wasSuccessful(),observations=OBS,
        failures=[dict(test=str(test),traceback=detail) for test,detail in run.result.failures+run.result.errors]),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not run.result.wasSuccessful())
