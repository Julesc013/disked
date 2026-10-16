"""Native policy parity and composition-availability cases; synthetic hosts only."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest


class Policy(unittest.TestCase):
    def route(self,value):
        result=subprocess.run([ARGS.exe],input=json.dumps(value).encode(),capture_output=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        return json.loads(result.stdout)

    def test_all_canonical_fixtures(self):
        cases=json.loads((ARGS.root/'spec/fixtures/invocation.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['id']):self.assertEqual(case['expected'],self.route(case['inputs']))
        print('Native policy fixtures:',len(cases))

    def test_oracle_cross_product(self):
        sys.path.insert(0,str(ARGS.root/'spec/tools'))
        import specctl
        count=0
        for frontend,format,interactive,terminal,tui in itertools.product(
                ['auto','cli','plain','tui','gui'],['human','json','ndjson'],['auto','yes','no'],['none','limited','capable'],[False,True]):
            inputs=dict(frontend=frontend,format=format,interactive=interactive,terminal=terminal,
                        tui_available=tui,console_owner='caller',gui_available=True,display=True)
            with self.subTest(inputs=inputs):self.assertEqual(specctl.route_invocation(inputs),self.route(inputs))
            count+=1
        print('Native/oracle routing combinations:',count)

    def test_absence_is_not_redirection_and_prompt_channels_are_explicit(self):
        for stream in ['absent','invalid','unknown']:
            self.assertEqual('no-interactive-host',self.route(dict(stdin=stream,stdout=stream))['reason'])
        for stream in ['pipe','file']:
            self.assertEqual('redirected-stream',self.route(dict(stdin=stream))['reason'])
        self.assertEqual({'error':'interaction_unavailable'},self.route(dict(interactive='yes',terminal='capable',stdout='pipe')))
        self.assertTrue(self.route(dict(interactive='yes',terminal='capable',stdout='pipe',prompt_channel=True))['interactive'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--exe',required=True);parser.add_argument('--root',type=Path,required=True)
    ARGS=parser.parse_args();unittest.main(argv=[__file__],verbosity=2)
