"""Responsiveness and stale-view isolation during an actual delayed worker admission."""
import argparse,ctypes as C,json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from gui_fixture import Gui,U,WP,wait
P=argparse.ArgumentParser();P.add_argument('--exe',type=Path,required=True);P.add_argument('--delayed',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.delayed=ARGS.delayed.resolve();OBSERVATIONS=[]
class Waiting(unittest.TestCase):
    def test_pending_admission_keeps_cached_views_and_does_not_rebase_late_result(self):
        with tempfile.TemporaryDirectory(prefix='disked-resilience-') as directory:
            state=Path(directory)/'state';state.mkdir();second=Path(directory)/'second';second.mkdir()
            g=Gui(ARGS.delayed,['--gui','plan','simulate','fake:complete','--state-dir',str(state)],render=True)
            try:
                g.click(109);g.click(110)
                self.assertEqual('gui:1',g.details()['pending_request'])
                wait(lambda:(state/'request.json').exists(),4)
                samples=[]
                for _ in range(5):
                    result=WP();started=time.monotonic();C.set_last_error(0)
                    ok=U.SendMessageTimeoutW(g.window,0,0,0,2,250,C.byref(result))
                    samples.append(dict(responsive=bool(ok),elapsed_ms=(time.monotonic()-started)*1000,error=C.get_last_error()))
                self.assertTrue(all(v['responsive'] and v['elapsed_ms']<250 for v in samples),samples)
                # A second reviewed start is refused before touching another store.
                g.set(201,str(second));g.click(109);g.click(110)
                self.assertEqual('request_resource_limit',g.details()['diagnostics'][0]['code'])
                self.assertEqual([],list(second.iterdir()))
                # Inspect a cached target while admission still has no outcome.
                g.click(104);g.choose(0);g.click(108)
                current=g.details();self.assertEqual('fake:alpha@1',current['result']['target']['id'])
                wait(lambda:'earlier_request' in g.details(),5);late=g.details()
                self.assertEqual(current['request_id'],late['request_id'])
                self.assertEqual('fake:alpha@1',late['result']['target']['id'])
                self.assertEqual('gui:1',late['earlier_request']['request_id'])
                self.assertEqual('unknown',late['earlier_request']['status'])
                operation=late['earlier_request']['operation_id'];self.assertIsNotNone(operation)
                OBSERVATIONS.append(dict(samples=samples,late=late,source='test-only five-second delayed admission'))
            finally:g.close()
            self.assertEqual(0,g.code)
            # Closing the frontend did not stop or replace the uncertain worker.
            deadline=time.monotonic()+8
            while True:
                p=subprocess.run([str(ARGS.exe),'operation','inspect',operation,'--state-dir',str(state),'--json'],capture_output=True,text=True,timeout=8)
                outcome=json.loads(p.stdout)
                if outcome['result'].get('state',{}).get('phase')=='finished':break
                self.assertLess(time.monotonic(),deadline);time.sleep(.04)
            self.assertEqual(operation,outcome['operation_id']);self.assertEqual('completed',outcome['status'])
            OBSERVATIONS[-1]['later_operation']=outcome
if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
