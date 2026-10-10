"""Real anonymous-pipe backpressure; only test-owned streams and fake stores."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

P=argparse.ArgumentParser();P.add_argument('--exe',type=Path,required=True);P.add_argument('--delayed',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.delayed=ARGS.delayed.resolve();OBSERVATIONS=[]

class Output(unittest.TestCase):
    def launch(self,*words,exe=None,bufsize=-1):
        p=subprocess.Popen([str(exe or ARGS.exe),*words],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=bufsize)
        self.addCleanup(self.close,p);return p
    @staticmethod
    def close(p):
        if p.poll() is None:p.kill();p.wait(timeout=3)
        for stream in (p.stdin,p.stdout,p.stderr):
            if not stream.closed:stream.close()
    def test_absent_consumer_reaches_output_deadline(self):
        p=self.launch('command','list','--json');p.stdin.close();started=time.monotonic()
        self.assertEqual(4,p.wait(timeout=5));elapsed=time.monotonic()-started
        out=p.stdout.read();err=p.stderr.read()
        self.assertGreaterEqual(elapsed,2.8);self.assertLess(elapsed,4)
        self.assertEqual(b'',err);self.assertNotIn(b'output_error',out);self.assertNotIn(b'internal_error',out)
        self.assertLessEqual(len(out),1048576)
        OBSERVATIONS.append(dict(test='undrained machine response',elapsed_seconds=elapsed,exit=p.returncode,retained_bytes=len(out)))
    def test_reader_can_resume_within_budget_without_losing_bytes(self):
        reference=subprocess.run([str(ARGS.exe),'command','list','--json'],capture_output=True,timeout=5)
        self.assertEqual(0,reference.returncode)
        p=self.launch('command','list','--json');time.sleep(.4)
        self.assertIsNone(p.poll());out,err=p.communicate(timeout=5)
        self.assertEqual(0,p.returncode);self.assertEqual(reference.stdout,out);self.assertEqual(b'',err)
        self.assertEqual('completed',json.loads(out)['status'])
        OBSERVATIONS.append(dict(test='reader resumes after 400 ms',bytes=len(out),exit=p.returncode))
    def test_partial_record_is_not_followed_by_replacement_or_diagnostic(self):
        # BufferedReader may drain more than the requested prefix and release
        # the entire pending Windows write. Consume exactly 128 kernel bytes.
        p=self.launch('command','list','--json',bufsize=0);p.stdin.close();started=time.monotonic()
        prefix=p.stdout.read(128);self.assertEqual(128,len(prefix));self.assertNotIn(b'\n',prefix)
        self.assertEqual(4,p.wait(timeout=5));elapsed=time.monotonic()-started
        retained=prefix+p.stdout.read();self.assertEqual(b'',p.stderr.read());self.assertLess(elapsed,4)
        self.assertNotIn(b'\n',retained);self.assertNotIn(b'internal_error',retained);self.assertNotIn(b'output_error',retained)
        with self.assertRaises(json.JSONDecodeError):json.loads(retained)
        OBSERVATIONS.append(dict(test='reader stops after prefix',prefix=prefix.decode(),retained_bytes=len(retained),elapsed_seconds=elapsed,exit=p.returncode))
    def test_human_output_is_also_bounded(self):
        p=self.launch('--help');p.stdin.close();started=time.monotonic()
        self.assertEqual(4,p.wait(timeout=5));elapsed=time.monotonic()-started
        out=p.stdout.read();err=p.stderr.read();self.assertLess(elapsed,4)
        self.assertEqual(b'disked: output_error\n',err)
        OBSERVATIONS.append(dict(test='undrained human help',elapsed_seconds=elapsed,exit=p.returncode,retained_bytes=len(out)))
    def test_failed_delivery_does_not_cancel_worker_or_dispatch_queued_request(self):
        with tempfile.TemporaryDirectory(prefix='disked-output-worker-') as directory:
            state=Path(directory)/'state';state.mkdir();second=Path(directory)/'second';second.mkdir()
            p=self.launch('protocol','serve','--format=ndjson',exe=ARGS.delayed)
            def request(ident,command,parameters):
                return json.dumps(dict(schema='org.disked.request/1',request_id=ident,command=command,parameters=parameters,required_features=[])).encode()+b'\n'
            p.stdin.write(request('admission','plan.simulate',dict(fixture_id='fake:cancel-checkpoint',state_directory=str(state)))+
                request('large','command.list',{})+
                request('must-not-run','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(second))))
            p.stdin.close();started=time.monotonic()
            # The first request's 3s admission bound yields unknown with its ID;
            # then the large second response stalls. The third request is queued.
            self.assertEqual(4,p.wait(timeout=8));elapsed=time.monotonic()-started;self.assertLess(elapsed,7)
            out=p.stdout.read();self.assertEqual(b'',p.stderr.read());first=json.loads(out.split(b'\n',1)[0])
            self.assertEqual('admission',first['request_id']);self.assertEqual('unknown',first['status'])
            self.assertIsNotNone(first['operation_id']);self.assertEqual([],list(second.iterdir()))
            result=subprocess.run([str(ARGS.exe),'operation','inspect',first['operation_id'],'--state-dir',str(state),'--json'],capture_output=True,timeout=5)
            active=json.loads(result.stdout);self.assertEqual('running',active['result']['worker_observation'])
            deadline=time.monotonic()+5
            while True:
                result=subprocess.run([str(ARGS.exe),'operation','inspect',first['operation_id'],'--state-dir',str(state),'--json'],capture_output=True,timeout=5)
                final=json.loads(result.stdout)
                if final['result'].get('state',{}).get('phase')=='finished':break
                self.assertLess(time.monotonic(),deadline);time.sleep(.04)
            self.assertEqual('succeeded',final['result']['state']['outcome']);self.assertEqual('1',final['result']['state']['synthetic_effect_count'])
            self.assertEqual(first['operation_id'],final['operation_id'])
            OBSERVATIONS.append(dict(test='failed transport after admission',elapsed_seconds=elapsed,exit=p.returncode,
                response=first,active_after_transport_exit=active,final=final,queued_directory_files=[]))

if __name__=='__main__':
    run=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(executable=str(ARGS.exe),sha256=hashlib.sha256(ARGS.exe.read_bytes()).hexdigest(),
        delayed_executable=str(ARGS.delayed),delayed_sha256=hashlib.sha256(ARGS.delayed.read_bytes()).hexdigest(),
        tests=run.result.testsRun,passed=run.result.wasSuccessful(),observations=OBSERVATIONS,
        failures=[dict(test=str(test),traceback=detail) for test,detail in run.result.failures+run.result.errors]),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not run.result.wasSuccessful())
