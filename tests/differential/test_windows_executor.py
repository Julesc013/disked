"""Executor state/byte-budget tests with a fake launcher;no OS admission."""
import json
import hashlib
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from windows_executor import WindowsFileExecutor


class Child:
    pid=1234 # Synthetic launcher identity, not a native process.
    def __init__(self, code):self.code=code
    def poll(self):return self.code
    def wait(self, timeout=1):return self.code
    def close(self):pass


class Worker:
    def __init__(self, root):
        self.work=root;self.base=SimpleNamespace(plain_directory=lambda p:Path(p).resolve())
        self.last_launch=None;self.counter=0;self.child=None
    def file_identity(self,path):
        info=path.stat();return dict(volume=str(info.st_dev),identity=str(info.st_ino))
    def launch(self,argv,environment,job,*,variant,raw_input,cwd,before_resume=None):
        assert variant=='basic-raw-stdio';assert cwd==self.work
        self.counter+=1
        self.raw_paths=dict(stdin=raw_input,stdout=self.work/('out-'+str(self.counter)),stderr=self.work/('err-'+str(self.counter)))
        self.child=Child(None if argv[-1]=='wait' else 7 if argv[-1]=='refuse' else 0)
        self.last_launch=dict(stdio_identities=dict(stdin=self.file_identity(raw_input)))
        if before_resume:
            before_resume(SimpleNamespace(process='synthetic-suspended-handle',pid=self.child.pid))
            self.last_launch['pre_resume_hook_completed']=True
        self.raw_paths['stdout'].write_bytes(raw_input.read_bytes() if argv[-1]=='echo' else b'A'*8192 if argv[-1]=='overrun' else b'OUT')
        self.raw_paths['stderr'].write_bytes(b'\0ERR\xff')
        self.last_launch['stdio_identities'].update({k:self.file_identity(v) for k,v in self.raw_paths.items()})
        return self.child


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ['DISKED_WORK_ROOT']);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.worker=Worker(self.root);self.retirements=[]
        def retire(job):
            self.retirements.append(job);self.worker.child.code=78 if self.worker.child.code is None else self.worker.child.code
            return dict(active_processes=0,total_processes=1)
        self.executor=WindowsFileExecutor(self.worker,{},lambda:object(),retire)
    def call(self,mode='echo',payload=b'\0\xff\r\n\x1a',limit=1048576,timeout=1):
        return self.executor(argv=['synthetic',mode],cwd=self.root,payload=payload,timeout=timeout,output_limit=limit)
    def test_bytes_eof_streams_exit_and_cleanup(self):
        result=self.call();self.assertEqual(result['stdout'],b'\0\xff\r\n\x1a');self.assertEqual(result['stderr'],b'\0ERR\xff')
        self.assertTrue(result['terminal']);self.assertEqual(len(self.retirements),1);self.assertEqual(list(self.root.iterdir()),[])
        self.assertEqual(self.executor.observations[0]['process_id'],1234)
        result=self.call(payload=b'');self.assertEqual(result['stdout'],b'')
        result=self.call('refuse');self.assertEqual(result['exit_code'],7);self.assertEqual(result['outcome'],'exited')
    def test_deadline_and_output_failure_are_terminal_but_never_completed(self):
        result=self.call('wait',timeout=.02);self.assertEqual(result['outcome'],'timeout');self.assertEqual(result['exit_code'],78)
        result=self.call('overrun',limit=32);self.assertEqual(result['outcome'],'output_limit');self.assertEqual(result['stdout'],b'A'*32)
        self.assertEqual(result['stderr'],b'');self.assertEqual(result['exit_code'],0)
        self.assertEqual(self.executor.observations[-1]['produced_bytes']['stdout'],8192)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_unknown_retirement_preserves_files_and_blocks_reuse(self):
        def failed(job):raise RuntimeError('synthetic unresolved retirement')
        self.executor.retire_job=failed
        with self.assertRaises(RuntimeError):self.call()
        self.assertTrue(self.executor.poisoned);self.assertTrue(self.executor.observations[-1]['quiescence_unknown'])
        count=self.worker.counter
        with self.assertRaises(RuntimeError):self.call()
        self.assertEqual(self.worker.counter,count);self.assertTrue(list(self.root.iterdir()))
    def test_invalid_budgets_or_outside_cwd_refuse_before_launch(self):
        for value in (True,0,1048577):
            with self.subTest(limit=value),self.assertRaises(ValueError):self.call(limit=value)
        for value in (True,0,float('inf')):
            with self.subTest(timeout=value),self.assertRaises(ValueError):self.call(timeout=value)
        with self.assertRaises(ValueError):self.executor(argv=['synthetic'],cwd=self.root.parent,payload=b'',timeout=1,output_limit=1)
        self.assertEqual(self.worker.counter,0);self.assertEqual(list(self.root.iterdir()),[])

    def test_suspended_child_payload_binds_actual_identity_before_read(self):
        seen=[]
        def build(process,job):
            self.assertIs(job,self.executor.active_job)
            self.assertEqual(process.process,'synthetic-suspended-handle')
            self.assertFalse(self.worker.raw_paths['stdout'].exists())
            seen.append(process.pid)
            return b'actual-pid:'+str(process.pid).encode()+b'\0\xff'
        self.executor.payload_builder=build
        value=self.call(payload=b'placeholder-longer-than-final-result')
        expected=b'actual-pid:1234\0\xff'
        self.assertEqual(value['stdout'],expected);self.assertEqual(seen,[1234])
        row=self.executor.observations[-1]
        self.assertEqual(row['stdin_bytes'],len(expected))
        self.assertEqual(row['stdin_sha256'],hashlib.sha256(expected).hexdigest())
        self.assertTrue(row['launch']['pre_resume_hook_completed'])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_suspended_child_setup_failure_retires_and_prohibits_reuse(self):
        def build(process,job):raise RuntimeError('synthetic capability handoff refused')
        self.executor.payload_builder=build
        with self.assertRaisesRegex(RuntimeError,'handoff refused'):self.call()
        self.assertTrue(self.executor.poisoned);self.assertEqual(len(self.retirements),1)
        self.assertTrue(self.executor.observations[-1]['terminal'])
        self.assertFalse(self.worker.raw_paths['stdout'].exists())
        with self.assertRaises(RuntimeError):self.call()

    def test_native_proof_refuses_mixed_modes_before_staging_or_processes(self):
        path=Path(__file__).resolve().parents[2]/'.aide/evidence/2026-10-18-ordinary-worker/campaign.py'
        spec=importlib.util.spec_from_file_location('raw_port_campaign_controls',path)
        campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)
        for mode in ('--native-port-proof','--native-probe-proof','--cooperative-capture-proof'):
            for option in ('--native-journey','--native-x64','--crypto-full','--interactive-ui','--size-mib=512','--unknown-mode',
                           '--native-probe-proof' if mode=='--native-port-proof' else '--native-port-proof'):
                with self.subTest(mode=mode,option=option),mock.patch.dict(os.environ,DISKED_WORK_ROOT=str(self.root)), \
                        mock.patch.object(campaign.sys,'argv',[str(path),mode,'--prepare-only',option]), \
                        mock.patch.object(campaign.subprocess,'run',side_effect=AssertionError('No process may start')):
                    with self.assertRaisesRegex(ValueError,'Native (port|probe) proof accepts only|Cooperative capture accepts only'):
                        campaign.main()
                    self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main()
