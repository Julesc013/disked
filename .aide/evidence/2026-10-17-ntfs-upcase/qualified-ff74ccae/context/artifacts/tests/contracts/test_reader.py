"""Native compatible-reader checks; no asynchronous runtime admission is implied."""
import argparse
import copy
import json
import subprocess
import unittest


BASE=dict(schema='org.disked.response/1',request_id='x',status='completed',operation_id=None,
          result={},diagnostics=[],evidence=[])


class Reader(unittest.TestCase):
    def read(self, value):
        result=subprocess.run([ARGS.exe],input=json.dumps(value).encode(),capture_output=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        return json.loads(result.stdout)

    def test_extensions_preserved_and_required_features_refused(self):
        value=dict(BASE,observation_extension={'nested':[1,2]},required_features=[])
        self.assertEqual(value,self.read(value)['preserved'])
        value['required_features']=['unrecognized-semantic-feature']
        self.assertEqual('unsupported_feature',self.read(value)['error'])

    def test_unknown_and_missing_known_fields(self):
        for key in BASE:
            value=dict(BASE);del value[key]
            self.assertNotEqual('',self.read(value)['error'],key)
        for key,value in [('schema','org.disked.response/2'),('status','success'),('request_id',''),
                          ('diagnostics',{}),('operation_id',''),('evidence',[7]),('result',[]),('required_features',None)]:
            with self.subTest(key=key):self.assertNotEqual('',self.read(dict(BASE,**{key:value}))['error'])

    def test_status_identity_relationship_and_exit_outcomes(self):
        for status,code in [('completed',0),('refused',2),('failed',4),('accepted_running',5),('unknown',6),('recovery_required',7)]:
            value=dict(BASE,status=status,operation_id='operation:fixture' if status=='accepted_running' else None)
            self.assertEqual(code,self.read(value)['exit'])
        self.assertEqual('invalid_response',self.read(dict(BASE,status='accepted_running'))['error'])

    def test_diagnostics_are_structural_and_not_message_parsing(self):
        diagnostic=dict(code='command_unavailable',severity='error',message_key='disked.command_unavailable',
                        parameters={},platform_code=None,remediation=[],future_observation=1)
        value=dict(BASE,status='refused',diagnostics=[diagnostic])
        self.assertEqual(3,self.read(value)['exit'])
        for key in ['code','severity','message_key','parameters','platform_code','remediation']:
            changed=copy.deepcopy(value);del changed['diagnostics'][0][key]
            self.assertEqual('invalid_response',self.read(changed)['error'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--exe',required=True);ARGS=parser.parse_args()
    unittest.main(argv=[__file__],verbosity=2)
