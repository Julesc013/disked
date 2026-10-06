"""Real console shell journeys; synthetic input does not qualify human usability."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
PARSER=argparse.ArgumentParser()
for name in ['exe','guard','fault','root']:PARSER.add_argument('--'+name,type=Path,required=True)
PARSER.add_argument('--evidence',type=Path)
ARGS,REST=PARSER.parse_known_args()
for name in ['exe','guard','fault','root']:setattr(ARGS,name,getattr(ARGS,name).resolve())
OBSERVATIONS=[]

class ShellConsole(unittest.TestCase):
    def console(self,case):
        with tempfile.TemporaryDirectory(prefix='disked-shell-') as directory:
            report=Path(directory)/'report.json'
            exe=ARGS.fault if case=='fault' else ARGS.guard if case=='wrong-input' else ARGS.exe
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            result=subprocess.run([sys.executable,str(ARGS.root/'tests/interaction/console_shell_fixture.py'),str(exe),str(report),case],
                cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=45)
            value=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {'fixture_error':'missing report'}
            OBSERVATIONS.append(value)
            self.assertEqual(0,result.returncode,json.dumps(value,indent=2));self.assertNotIn('fixture_error',value)
            self.assertEqual(sorted(['report.json','owned state'] if case=='worker' else ['report.json']),sorted(p.name for p in Path(directory).iterdir()))
    def test_screen_navigation_review_repeat_and_layout(self):self.console('screen')
    def test_linear_correction_completion_alias_and_inert_enter(self):self.console('journey')
    def test_history_opt_in_and_quit(self):self.console('history')
    def test_active_mode_explanation(self):self.console('mode')
    def test_native_unicode_events_and_editing(self):self.console('unicode')
    def test_shell_close_preserves_dispatched_worker(self):self.console('worker')
    def test_small_auto_linear(self):self.console('small')
    def test_resize_to_linear(self):self.console('resize')
    def test_ctrl_c_restoration(self):self.console('ctrl-c')
    def test_ctrl_key_restoration(self):self.console('ctrl-key')
    def test_unrelated_console_mode_preserved(self):self.console('external-mode')
    def test_failure_restoration(self):self.console('fault')
    def test_forced_small_refused(self):self.console('forced-small')
    def test_wrong_input_before_provider_initialization(self):self.console('wrong-input')
    def test_static_entry_help_conflicts_and_channels(self):
        with tempfile.TemporaryDirectory(prefix='disked-shell-static-') as directory:
            for exe in [ARGS.exe,ARGS.guard]:
                for words,code,needle in [(['shell'],3,'frontend_unavailable'),(['shell','--terminal=linear'],3,'frontend_unavailable'),
                        (['shell','--json'],2,'argument_conflict'),(['shell','--interactive=no'],2,'argument_conflict'),
                        (['shell','--gui'],2,'argument_conflict'),(['shell','--tui'],2,'argument_conflict'),
                        (['shell','--history=forever'],2,'invalid_option_value'),(['exit'],3,'command_requires_shell'),
                        (['shell','--help'],0,'Usage:'),(['quit','--help'],0,'shell.close')]:
                    result=subprocess.run([str(exe),*words],input=b'',capture_output=True,cwd=directory,timeout=8)
                    self.assertEqual(code,result.returncode,(words,result.stdout,result.stderr))
                    self.assertIn(needle.encode(),result.stdout+result.stderr,words)
            self.assertEqual([],list(Path(directory).iterdir()))

if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
