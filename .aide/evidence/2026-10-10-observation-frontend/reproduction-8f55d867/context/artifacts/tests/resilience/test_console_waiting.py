import argparse,json,subprocess,sys,tempfile,unittest
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--delayed',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.delayed=ARGS.delayed.resolve();OBSERVATIONS=[]
class ConsoleWaiting(unittest.TestCase):
    def exercise(self,frontend):
        with tempfile.TemporaryDirectory(prefix='disked-console-wait-') as directory:
            report=Path(directory)/'report.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            p=subprocess.run([sys.executable,str(Path(__file__).with_name('console_wait_fixture.py')),str(ARGS.delayed),str(report),frontend],
                cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=35)
            value=json.loads(report.read_text(encoding='utf-8'));OBSERVATIONS.append(value)
            self.assertEqual(0,p.returncode,json.dumps(value,indent=2));self.assertNotIn('fixture_error',value)
            self.assertLess(value['cached_navigation_ms'],250);self.assertEqual('completed',value['later_operation']['status'])
    def test_shell_remains_editable_and_preserves_late_outcome(self):self.exercise('shell')
    def test_tui_retains_cached_inventory_when_late_outcome_arrives(self):self.exercise('tui')
if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
