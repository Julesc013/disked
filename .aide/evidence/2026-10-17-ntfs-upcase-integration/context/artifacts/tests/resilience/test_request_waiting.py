"""Native bounded waits at an injected file boundary; no real driver stall."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import unittest

P=argparse.ArgumentParser()
P.add_argument('--exe',type=Path,required=True)
P.add_argument('--fault',type=Path,required=True)
P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.fault=ARGS.fault.resolve();OBSERVATIONS=[]

def invoke(exe,*words):
    started=time.monotonic()
    p=subprocess.run([str(exe),*map(str,words),'--json'],capture_output=True,text=True,timeout=9)
    if p.stderr:raise AssertionError(p.stderr)
    return p.returncode,json.loads(p.stdout),time.monotonic()-started

class Waiting(unittest.TestCase):
    def assert_expired(self,code,value,elapsed,request,operation=None):
        self.assertEqual(6,code,value);self.assertEqual('unknown',value['status'])
        self.assertEqual(request,value['request_id']);self.assertEqual(operation,value['operation_id'])
        self.assertEqual('request_wait_expired',value['diagnostics'][0]['code'])
        self.assertGreaterEqual(elapsed,3.8);self.assertLess(elapsed,5)

    def test_cli_returns_unknown_and_retains_one_original_operation(self):
        with tempfile.TemporaryDirectory(prefix='disked-request-wait-') as directory:
            code,value,elapsed=invoke(ARGS.fault,'plan','simulate','fake:complete','--state-dir',directory)
            self.assert_expired(code,value,elapsed,'cli')
            self.assertEqual(directory,value['result']['state_directory'])
            header=json.loads((Path(directory)/'request.json').read_bytes());operation=header['operation_id']
            code,final,_=invoke(ARGS.exe,'operation','inspect',operation,'--state-dir',directory)
            self.assertEqual(0,code,final);self.assertEqual('succeeded',final['result']['state']['outcome'])
            self.assertEqual('1',final['result']['state']['synthetic_effect_count'])
            before=(Path(directory)/'operation.records').read_bytes()
            # Use the same test image so its definition digest matches the claim.
            # The next process's injected observation delay still cannot rerun it.
            code,repeated,repeat_elapsed=invoke(ARGS.fault,'plan','simulate','fake:complete','--state-dir',directory)
            self.assert_expired(code,repeated,repeat_elapsed,'cli')
            self.assertEqual(before,(Path(directory)/'operation.records').read_bytes())
            self.assertEqual(header,json.loads((Path(directory)/'request.json').read_bytes()))
            OBSERVATIONS.append(dict(test='CLI timeout and same-claim reinspection',elapsed_seconds=elapsed,response=value,
                                     repeated=repeated,repeat_elapsed_seconds=repeat_elapsed,final=final))

    def test_known_operation_identity_survives_inspection_timeout(self):
        with tempfile.TemporaryDirectory(prefix='disked-inspection-wait-') as directory:
            code,admitted,_=invoke(ARGS.exe,'plan','simulate','fake:complete','--state-dir',directory)
            self.assertEqual(5,code,admitted);operation=admitted['operation_id']
            code,value,elapsed=invoke(ARGS.fault,'operation','inspect',operation,'--state-dir',directory)
            self.assert_expired(code,value,elapsed,'cli',operation)
            code,final,_=invoke(ARGS.exe,'operation','inspect',operation,'--state-dir',directory)
            self.assertEqual(0,code,final);self.assertEqual('succeeded',final['result']['state']['outcome'])
            OBSERVATIONS.append(dict(test='Known operation identity',elapsed_seconds=elapsed,response=value,final=final))

    def test_stdio_cached_requests_continue_busy_calls_refuse_and_late_reply_is_not_reissued(self):
        with tempfile.TemporaryDirectory(prefix='disked-stdio-wait-') as directory:
            state=Path(directory)/'state';state.mkdir();second=Path(directory)/'second';second.mkdir()
            p=subprocess.Popen([str(ARGS.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            lines=queue.Queue()
            def reader():
                for line in p.stdout:lines.put(line)
                lines.put(None)
            reading=threading.Thread(target=reader,daemon=True);reading.start()
            def exchange(ident,command,parameters,timeout=6):
                request=dict(schema='org.disked.request/1',request_id=ident,command=command,parameters=parameters,required_features=[])
                started=time.monotonic();p.stdin.write(json.dumps(request)+'\n');p.stdin.flush()
                line=lines.get(timeout=timeout);self.assertIsNotNone(line)
                value=json.loads(line);self.assertEqual(ident,value['request_id']);return value,time.monotonic()-started
            try:
                value,elapsed=exchange('first','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(state)))
                self.assert_expired(6,value,elapsed,'first')
                cached,cached_time=exchange('cached','target.inspect',dict(target_id='fake:alpha@1'))
                self.assertEqual('completed',cached['status']);self.assertLess(cached_time,.5)
                busy,busy_time=exchange('second','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(second)))
                self.assertEqual('refused',busy['status']);self.assertEqual('request_resource_limit',busy['diagnostics'][0]['code'])
                self.assertLess(busy_time,.5);self.assertEqual([],list(second.iterdir()))
                with self.assertRaises(queue.Empty):lines.get(timeout=3)
                # Reconciliation is an explicit new exchange after actual channel
                # completion; it reads the exact retained admission and effect.
                final,_=exchange('reconcile','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(state)))
                self.assertEqual('completed',final['status'],final)
                self.assertEqual('existing',final['result']['admission'])
                self.assertEqual('1',final['result']['state']['synthetic_effect_count'])
                self.assertEqual(json.loads((state/'request.json').read_bytes())['operation_id'],final['operation_id'])
                with self.assertRaises(queue.Empty):lines.get(timeout=.1)
                p.stdin.close();self.assertEqual(6,p.wait(timeout=3));self.assertEqual('',p.stderr.read())
                OBSERVATIONS.append(dict(test='NDJSON after timeout',elapsed_seconds=elapsed,response=value,cached=cached,
                    cached_seconds=cached_time,busy=busy,busy_seconds=busy_time,final=final,session_exit=p.returncode))
            finally:
                if p.poll() is None:p.kill();p.wait(timeout=3)
                if not p.stdin.closed:p.stdin.close()
                reading.join(timeout=1);p.stdout.close();p.stderr.close()

if __name__=='__main__':
    run=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:
        ARGS.evidence.write_text(json.dumps(dict(scope='6.5-second injected ordinary-file observation delay',
            executable=str(ARGS.fault),sha256=hashlib.sha256(ARGS.fault.read_bytes()).hexdigest(),tests=run.result.testsRun,
            product_executable=str(ARGS.exe),product_sha256=hashlib.sha256(ARGS.exe.read_bytes()).hexdigest(),
            passed=run.result.wasSuccessful(),observations=OBSERVATIONS,
            failures=[dict(test=str(test),traceback=detail) for test,detail in run.result.failures+run.result.errors]),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not run.result.wasSuccessful())
