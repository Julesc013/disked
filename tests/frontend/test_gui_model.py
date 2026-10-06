"""Native GUI-model behavior and three-frontend service parity."""
import argparse
import json
import subprocess
import unittest
from pathlib import Path


class Model(unittest.TestCase):
    def setUp(self):self.p=subprocess.Popen([str(ARGS.probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def tearDown(self):
        self.p.stdin.close()
        try:self.assertEqual(0,self.p.wait(timeout=5));self.assertEqual(b'',self.p.stderr.read())
        finally:
            if self.p.poll() is None:self.p.kill();self.p.wait()
            self.p.stdout.close();self.p.stderr.close()
    def call(self,op='',**fields):
        self.p.stdin.write(json.dumps(dict(op=op,**fields),ensure_ascii=False).encode()+b'\n');self.p.stdin.flush()
        result=json.loads(self.p.stdout.readline());self.assertNotIn('error',result);return result
    def stage(self,command,**parameters):return self.call('stage',command=command,parameters=parameters)
    def execute(self):self.call('review');return self.call('submit')['state']['last_outcome']

    def test_identity_selection_and_missing_focus_survive_refresh(self):
        self.call('open');self.call('publish',remove='fake:alpha@1')
        self.assertEqual('revision_conflict',self.call('open')['state']['last_outcome']['diagnostics'][0]['code'])
        state=self.call('refresh')['state'];self.assertEqual('missing',state['selection']['state']);self.assertEqual('fake:alpha@1',state['focus'])
        self.assertEqual('target_not_found',self.call('open')['state']['last_outcome']['diagnostics'][0]['code'])
        self.call('navigate',commands=True);state=self.call('navigate',commands=False)['state'];self.assertEqual('fake:alpha@1',state['focus'])
        self.assertEqual('none',self.call('clear')['state']['selection']['state'])

    def test_review_is_consumed_by_edit_submit_and_new_request(self):
        self.stage('target.inspect',target_id='fake:alpha@1');self.call('submit')
        self.assertEqual('0',self.call()['state']['requests'])
        self.call('review');state=self.call('edit',field='target_id',value='fake:denied@1')['state'];self.assertFalse(state['reviewed'])
        self.call('submit');self.assertEqual('0',self.call()['state']['requests'])
        self.execute();self.call('submit');self.assertEqual('1',self.call()['state']['requests'])
        self.call('review');self.stage('target.list');self.call('submit');self.assertEqual('1',self.call()['state']['requests'])

    def test_stale_review_is_not_rebased_by_refresh(self):
        self.stage('target.inspect',target_id='fake:alpha@1');self.call('review');old=self.call()['details']['expected_revision']
        self.call('publish');self.call('refresh');self.assertEqual(old,self.call()['details']['expected_revision'])
        self.assertEqual('revision_conflict',self.call('submit')['state']['last_outcome']['diagnostics'][0]['code'])

    def test_invalid_edit_cannot_authorize_old_value(self):
        self.stage('target.inspect',target_id='fake:alpha@1')
        for value in ['x'*4097,'x\ny','x\0y','x\x1by']:
            self.call('review');self.call('edit',field='target_id',value=value)
            self.assertFalse(self.call('review')['state']['reviewed']);self.call('submit')
            self.assertEqual('0',self.call()['state']['requests'])
            self.assertEqual(value,self.call()['state']['parameters']['target_id'])
        self.call('edit',field='target_id',value='磁盘💾');self.assertTrue(self.call('review')['state']['reviewed'])
        self.assertEqual('target_not_found',self.call('submit')['state']['last_outcome']['diagnostics'][0]['code'])

    def test_command_availability_and_no_invented_plan(self):
        self.assertIsNone(self.call()['details']['proposed'])
        rows=self.call('navigate',commands=True)['rows'];self.assertEqual(35,len(rows))
        self.assertEqual('transport-only',next(r for r in rows if r['id']=='protocol.serve')['state'])
        for command in ['protocol.serve','partition.resize.plan']:
            result=self.stage(command);self.assertEqual('command_unavailable',result['details']['diagnostics'][0]['code']);self.assertFalse(result['state']['form'])

    def test_gui_cli_tui_outcomes_match(self):
        cases=[('target.list',{}),('topology.show',{}),('target.inspect',dict(target_id='fake:volume@1')),
               ('target.inspect',dict(target_id='missing')),('capability.explain',dict(target_id='fake:denied@1',operation='partition.resize.plan'))]
        for command,parameters in cases:
            self.stage(command,**parameters);actual=self.execute()
            request=dict(schema='org.disked.request/1',request_id=actual['request_id'],command=command,parameters=parameters,required_features=[])
            p=subprocess.run([str(ARGS.exe),'protocol','serve','--json'],input=json.dumps(request).encode(),capture_output=True,timeout=10)
            self.assertEqual(actual,json.loads(p.stdout))
            messages=[dict(op='stage',command=command,parameters=parameters),dict(op='key',key='f9'),dict(op='key',key='f9')]
            p=subprocess.run([str(ARGS.tui)],input=b''.join(json.dumps(m).encode()+b'\n' for m in messages),capture_output=True,timeout=10)
            self.assertEqual(0,p.returncode);tui=json.loads(p.stdout.splitlines()[-1])['state']['last_outcome']
            tui['request_id']=actual['request_id'];self.assertEqual(actual,tui)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['probe','exe','tui']:p.add_argument('--'+name,type=Path,required=True)
    ARGS=p.parse_args();unittest.main(argv=[__file__],verbosity=2)
