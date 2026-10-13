"""Actual caller exit, detached ownership and independently observed effects."""
import argparse
import copy
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import time
import unittest
import test_fat_tree_admission as admission
from test_fat_tree_review import canonical, rebind

NORMAL = FAULT = RECONNECT = None
RESULTS = []


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def call(value, fault=False):
    run = subprocess.run([str(FAULT if fault else NORMAL)], input=canonical(value), capture_output=True, timeout=20)
    assert run.returncode == 0 and not run.stderr, (run.returncode, run.stderr)
    rows = [json.loads(line) for line in run.stdout.splitlines()]
    assert len(rows) == 1, rows
    RESULTS.append(dict(kind='caller', input_sha256=sha(canonical(value)), caller_pid_exit='observed-by-subprocess-wait',
                        exit_code=run.returncode, rows=rows))
    return rows[0]


def inspect(root, cancel=False):
    header = json.loads((root/'store/recursive-request.json').read_bytes())
    run = subprocess.run([str(RECONNECT)], input=canonical(dict(operation_id=header['operation_id'],
                            store=str(root/'store'), cancel=cancel)), capture_output=True, timeout=20)
    assert run.returncode == 0 and not run.stderr, (run.returncode, run.stderr)
    out = json.loads(run.stdout)
    RESULTS.append(dict(kind='inspect', cancel=cancel, result=out))
    return out


def wait_history(root, terminal=True, timeout=90):
    until = time.monotonic()+timeout
    last = None
    while time.monotonic() < until:
        if (root/'store/recursive-request.json').exists():
            try:
                last = inspect(root)
            except (json.JSONDecodeError, AssertionError):
                # Opening during initial exclusive reservation is not admission.
                time.sleep(.02)
                continue
            history = last.get('history') or {}
            state = history.get('state')
            if terminal and state in ('recorded_complete','recorded_partial','recorded_exit_unresolved','recorded_uncertain'):
                worker = history.get('last_worker') or {}
                if (worker.get('worker') or {}).get('observation') == 'exited':
                    return last
            if not terminal and state == 'recorded_active':
                return last
        time.sleep(.02)
    raise AssertionError(('existing controller not replaced', root, last))


def actual_exit(identity, timeout=15):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000|0x1000, False, int(identity['pid']))
    if not handle:
        assert ctypes.get_last_error() == 87, ctypes.get_last_error()
        RESULTS.append(dict(kind='controller_current_fact', identity=identity, observation='not_present'))
        return
    class FT(ctypes.Structure):
        _fields_ = [('lo',ctypes.c_ulong),('hi',ctypes.c_ulong)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p,*([ctypes.POINTER(FT)]*4)]
    try:
        fields = [FT() for _ in range(4)]
        assert kernel.GetProcessTimes(handle,*[ctypes.byref(f) for f in fields]),ctypes.get_last_error()
        assert str((fields[0].hi<<32)|fields[0].lo) == identity['created'], ('PID reused',identity)
        assert kernel.WaitForSingleObject(handle,int(timeout*1000)) == 0, ('controller remains live',identity)
        RESULTS.append(dict(kind='controller_current_fact', identity=identity, observation='exited-handle'))
    finally:
        kernel.CloseHandle(handle)


def prepared(count=3, fault=False):
    root,inputs,expected = admission.fixture(count=count)
    row = admission.prepare(root,inputs,fault=fault)
    return root,inputs,expected,row['review']


class ControllerTests(unittest.TestCase):
    def test_actual_caller_exit_does_not_end_completion(self):
        for bits in (12,16,32):
            root,inputs,expected = admission.fixture(bits,count=150)
            review = admission.prepare(root,inputs)['review']
            source = (root/'source.img').read_bytes()
            row = call(dict(review=review,controller_mode='dispatch',wait_ms='0'))
            self.assertEqual('controller_handoff',row['kind'],row)
            identity = row['observation']['controller']
            final = wait_history(root)
            self.assertEqual('recorded_complete',final['history']['state'],final)
            header = json.loads((root/'store/recursive-request.json').read_bytes())
            self.assertEqual(row['observation']['operation_id'],header['operation_id'])
            self.assertEqual({k:identity[k] for k in ('pid','created')},header['controller'])
            self.assertEqual(source,(root/'source.img').read_bytes())
            for name,(data,attributes) in expected.items():
                self.assertEqual(data,(root/'output'/name).read_bytes())
            actual_exit(identity)

    def test_abandoned_closed_gate_has_no_resource_effects(self):
        root,inputs,expected,review = prepared()
        row = call(dict(review=review,controller_mode='abandon'))
        self.assertEqual('controller_abandoned',row['kind'])
        identity = row['observation']['controller']
        actual_exit(identity)
        self.assertEqual([],list((root/'store').iterdir()))
        self.assertFalse((root/'output').exists())
        self.assertFalse((root/'metadata.ndjson').exists())

    def test_each_missing_grant_and_wrong_digest_refuse_before_spawn(self):
        root,inputs,expected,review = prepared()
        for missing in ('source','destination','ledger','operation','host'):
            row = call(dict(review=review,controller_mode='dispatch',missing_grant=missing))
            self.assertEqual('error',row['kind'],row)
            self.assertEqual('fat_tree_review_grant',row['code'],row)
        row = call(dict(review=review,controller_mode='dispatch',review_digest='sha256:'+'0'*64))
        self.assertEqual('error',row['kind'],row)
        self.assertEqual('fat_tree_review_grant',row['code'],row)
        self.assertEqual([],list((root/'store').iterdir()))
        self.assertFalse((root/'output').exists())

    def test_stale_source_and_code_do_not_create_outputs(self):
        root,inputs,expected,review = prepared()
        source=root/'source.img';raw=source.read_bytes();source.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        row=call(dict(review=review,controller_mode='dispatch'))
        self.assertEqual('controller_handoff',row['kind'],row)
        self.assertEqual('refused',row['observation']['status'],row)
        self.assertEqual([],list((root/'store').iterdir()))
        self.assertFalse((root/'output').exists())
        actual_exit(row['observation']['controller'])
        root,inputs,expected,review=prepared()
        changed=copy.deepcopy(review)
        changed['backend']['resources']['executable']['observed']['sha256']='sha256:'+'0'*64
        rebind(changed['backend']['resources']['executable'])
        row=call(dict(review=changed,controller_mode='dispatch'))
        self.assertEqual('fat_tree_review_code',row.get('code'),row)
        changed['backend']['resources']['provider']['observed']['code_sha256']='sha256:'+'0'*64
        rebind(changed['backend']['resources']['provider'])
        row=call(dict(review=changed,controller_mode='dispatch'))
        self.assertEqual('fat_tree_controller_code_changed',row.get('code'),row)
        self.assertEqual([],list((root/'store').iterdir()))
        self.assertFalse((root/'output').exists())

    def test_detached_cooperative_cancellation_by_another_process(self):
        root,inputs,expected,review=prepared(fault=True)
        original=(root/'source.img').read_bytes()
        row=call(dict(review=review,controller_mode='dispatch',fixture=dict(worker_fault='execute_wait_cancel')),fault=True)
        self.assertEqual('accepted_running',row['observation']['status'],row)
        self.assertIsInstance(row['observation']['operation_id'],str)
        active=wait_history(root,terminal=False)
        self.assertEqual('running',active['controller']['observation'],active)
        self.assertEqual('running',active['writer']['observation'],active)
        cancelled=inspect(root,cancel=True)
        self.assertEqual('requested',cancelled['cancellation_request'],cancelled)
        final=wait_history(root)
        self.assertEqual('recorded_partial',final['history']['state'],final)
        self.assertTrue(final['history']['last_worker']['outcome']['cancellation_observed'])
        self.assertEqual(original,(root/'source.img').read_bytes())
        actual_exit(row['observation']['controller'])

    def test_owned_hang_budget_preserves_unresolved_history_without_replacement(self):
        root,inputs,expected,review=prepared(fault=True)
        source=(root/'source.img').read_bytes()
        row=call(dict(review=review,controller_mode='dispatch',fixture=dict(worker_fault='execute_hang',controller_stall_ms='200')),fault=True)
        self.assertEqual('accepted_running',row['observation']['status'],row)
        final=wait_history(root)
        self.assertEqual('recorded_exit_unresolved',final['history']['state'],final)
        self.assertEqual('31',final['history']['last_worker']['worker']['exit_code'])
        self.assertTrue((root/'output').exists())
        self.assertEqual(source,(root/'source.img').read_bytes())
        actual_exit(row['observation']['controller'])

    def test_role_and_normal_fixture_invocation_are_not_authority(self):
        for args in (['__disked_fat_tree_controller'],['__disked_fat_tree_controller']+['1']*7):
            run=subprocess.run([str(NORMAL),*args],capture_output=True,timeout=10)
            self.assertIn(run.returncode,(2,3));self.assertFalse(run.stdout);self.assertFalse(run.stderr)
            RESULTS.append(dict(kind='role_refusal',arguments=args,exit_code=run.returncode))
        root,inputs,expected,review=prepared()
        row=call(dict(review=review,controller_mode='dispatch',fixture=dict(controller_stall_ms='100')))
        self.assertEqual('fat_tree_controller_fixture_not_compiled',row.get('code'),row)
        self.assertEqual([],list((root/'store').iterdir()))

    def test_launch_cannot_be_reused_and_dispatch_cannot_be_replayed(self):
        root,inputs,expected,review=prepared()
        row=call(dict(review=review,controller_mode='launch_reused'))
        self.assertEqual('fat_tree_controller_launch_reused',row.get('code'),row)
        time.sleep(.1)
        self.assertEqual([],list((root/'store').iterdir()))
        self.assertFalse((root/'output').exists())
        root,inputs,expected,review=prepared()
        row=call(dict(review=review,controller_mode='dispatch_reused'))
        self.assertEqual('fat_tree_controller_dispatch_reused',row.get('code'),row)
        final=wait_history(root)
        self.assertEqual('recorded_complete',final['history']['state'],final)
        header=json.loads((root/'store/recursive-request.json').read_bytes())
        actual_exit(header['controller'])

    def test_published_outcome_does_not_prove_exit(self):
        root,inputs,expected,review=prepared(fault=True)
        row=call(dict(review=review,controller_mode='dispatch',fixture=dict(worker_fault='outcome_hold')),fault=True)
        self.assertEqual('accepted_running',row['observation']['status'],row)
        until=time.monotonic()+10;pending=None
        while time.monotonic()<until:
            out=inspect(root)
            if (out.get('history') or {}).get('state')=='recorded_outcome_pending_exit':
                pending=out;break
            time.sleep(.01)
        self.assertIsNotNone(pending)
        self.assertEqual('running',pending['writer']['observation'])
        self.assertEqual('running',pending['controller']['observation'])
        final=wait_history(root)
        self.assertEqual('recorded_complete',final['history']['state'],final)
        actual_exit(row['observation']['controller'])

    def test_controller_exit_after_admission_stays_unresolved(self):
        root,inputs,expected,review=prepared(fault=True)
        source=(root/'source.img').read_bytes()
        row=call(dict(review=review,controller_mode='observe_exit',fixture=dict(
            worker_fault='execute_wait_cancel',controller_fault='exit_after_admitted')),fault=True)
        out=row['observation']
        self.assertEqual('exited',out['controller']['observation'],out)
        self.assertEqual('unknown',out['status'],out)
        self.assertEqual('fat_tree_controller_exit_unresolved',out['diagnostic'],out)
        self.assertIsInstance(out['operation_id'],str)
        view=inspect(root)
        self.assertEqual('recorded_active',view['history']['state'],view)
        self.assertEqual(source,(root/'source.img').read_bytes())
        actual_exit(out['controller'])


def main():
    global NORMAL,FAULT,RECONNECT
    parser=argparse.ArgumentParser();parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--fault',type=Path,required=True);parser.add_argument('--reconnect',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    NORMAL,FAULT,RECONNECT=args.probe.resolve(),args.fault.resolve(),args.reconnect.resolve()
    admission.PROBE,admission.FAULT=NORMAL,FAULT
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ControllerTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,cases=len(RESULTS),
        records=RESULTS,native_preparations=admission.RESULTS),indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
