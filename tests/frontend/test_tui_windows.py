"""Actual isolated Windows console launches, input and restoration evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

OBSERVATIONS=[]
class WindowsTui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=None
        if ARGS.validate_schemas:
            sys.path.insert(0,str(ARGS.root/'spec/tools'));import specctl
            cls.bundle=specctl.Bundle(ARGS.root/'spec')
    def console_case(self,case):
        with tempfile.TemporaryDirectory(prefix='disked-tui-') as directory:
            report=Path(directory)/'report.json';exe=ARGS.fault if case=='fault' else ARGS.guard if case=='wrong-input' else ARGS.exe
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            p=subprocess.run([sys.executable,str(ARGS.root/'tests/frontend/console_tui_fixture.py'),str(exe),str(report),case],
                cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=45)
            value=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {'fixture_error':'missing report'}
            OBSERVATIONS.append(value);self.assertEqual(0,p.returncode,json.dumps(value,indent=2));self.assertNotIn('fixture_error',value)
            self.assertEqual(['report.json'],[p.name for p in Path(directory).iterdir()])
    def test_screen_navigation_forms_repeat_and_layout_switch(self):self.console_case('screen')
    def test_explicit_linear_inventory(self):self.console_case('linear')
    def test_small_terminal_auto_linear(self):self.console_case('small')
    def test_typed_form_paste_is_inert_until_explicit_review(self):self.console_case('form')
    def test_mode_explanation_retains_explicit_linear_preference(self):self.console_case('mode-linear')
    def test_ctrl_c_restores_caller(self):self.console_case('ctrl-c')
    def test_ctrl_c_key_event_restores_caller(self):self.console_case('ctrl-key')
    def test_resize_preserves_complete_linear_results(self):self.console_case('resize')
    def test_unrelated_mode_change_is_preserved(self):self.console_case('external-mode')
    def test_caught_failure_restores_owned_state(self):self.console_case('fault')
    def test_forced_screen_refuses_small_channel(self):self.console_case('forced-small')
    def test_active_buffer_restored_when_stdout_is_another_buffer(self):self.console_case('inactive-output')
    def test_wrong_input_role_refused_before_provider_initialization(self):self.console_case('wrong-input')
    def test_unavailable_channels_help_and_conflicts_are_static(self):
        for exe in [ARGS.exe,ARGS.guard]:
            for argv in [['--tui'],['tui'],['--tui','--terminal=linear']]:
                p=subprocess.run([str(exe),*argv],input=b'ignored',capture_output=True,timeout=10)
                self.assertEqual(3,p.returncode);self.assertIn(b'frontend_unavailable',p.stderr);self.assertEqual(b'',p.stdout)
            p=subprocess.run([str(exe),'--tui','--terminal=linear','--help'],input=b'',capture_output=True,timeout=10)
            self.assertEqual(0,p.returncode);self.assertIn(b'Usage:',p.stdout);self.assertEqual(b'',p.stderr)
            for argv in [['--terminal=linear'],['--tui','--terminal=linear','--json'],['--tui','--interactive=no']]:
                p=subprocess.run([str(exe),*argv],input=b'',capture_output=True,timeout=10)
                self.assertEqual(2,p.returncode);self.assertIn(b'argument_conflict',p.stderr+p.stdout)

    def test_startup_terminal_capabilities_are_honest_on_pipes(self):
        p=subprocess.run([str(ARGS.exe),'mode','explain','--json'],input=b'',capture_output=True,timeout=10)
        self.assertEqual(0,p.returncode);value=json.loads(p.stdout)['result']['observations']['terminal_capabilities']
        if self.bundle:self.bundle.validate('urn:disked:schema:terminal-capabilities:1',value)
        self.assertEqual('observed',value['source']);self.assertEqual('plain',value['backend'])
        for name in ['input','output','diagnostics']:self.assertEqual('pipe',value[name]['kind']);self.assertEqual('no',value[name]['interactive'])
        self.assertEqual('unknown',value['paste_detection']);self.assertEqual('unknown',value['alternate_screen'])
        self.assertEqual([],value['evidence'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['exe','guard','fault','root']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--evidence',type=Path);p.add_argument('--validate-schemas',action='store_true');ARGS=p.parse_args()
    for key in ['exe','guard','fault','root']:setattr(ARGS,key,getattr(ARGS,key).resolve())
    result=unittest.main(argv=[__file__],verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
