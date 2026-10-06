"""Execute the native TUI reducer independently of terminal I/O."""
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
    def call(self,**value):
        self.p.stdin.write(json.dumps(value,ensure_ascii=False).encode()+b'\n');self.p.stdin.flush()
        result=json.loads(self.p.stdout.readline());self.assertNotIn('error',result);return result
    def key(self,key,**other):return self.call(op='key',key=key,**other)
    def stage(self,command,parameters=None):return self.call(op='stage',command=command,parameters=parameters or {})
    def execute(self):self.key('f9');return self.key('f9')

    def test_inspection_and_stable_selection_are_service_results(self):
        graph=self.call()['graph'];value=self.key('enter')['state']
        self.assertEqual(dict(target_id='fake:alpha@1',state='present'),value['selection'])
        self.assertEqual(graph['nodes'][0],value['last_outcome']['result']['target'])
        self.key('f3');self.call(op='publish',remove='fake:alpha@1')
        stale=self.key('enter')['state'];self.assertEqual('revision_conflict',stale['last_outcome']['diagnostics'][0]['code'])
        self.assertEqual(dict(target_id='fake:alpha@1',state='missing'),stale['selection'])
        self.key('f5');self.key('f3');missing=self.key('enter')['state']
        self.assertEqual('target_not_found',missing['last_outcome']['diagnostics'][0]['code'])
        self.assertEqual('fake:alpha@1',missing['selection']['target_id'])
        cleared=self.key('f4')['state'];self.assertEqual(dict(target_id=None,state='none'),cleared['selection'])

    def test_staged_review_cannot_silently_rebase(self):
        self.stage('target.inspect',dict(target_id='fake:alpha@1'));self.key('f9')
        self.call(op='publish');value=self.key('f9')['state']
        self.assertEqual('revision_conflict',value['last_outcome']['diagnostics'][0]['code'])
        self.assertEqual('1',value['requests'])

    def test_paste_enter_repeat_and_navigation_do_not_submit(self):
        self.stage('target.inspect',dict(target_id='fake:alpha@1'))
        for text in ['\n\r\n','x\0y','\x1b[31m']:
            self.assertEqual('0',self.call(op='text',text=text)['state']['requests'])
        self.assertEqual('form',self.key('enter')['state']['view'])
        self.assertEqual('review',self.key('f9')['state']['view'])
        for key in ['f9','enter','f2','f3']:
            result=self.key(key,repeat=True)['state'];self.assertEqual('0',result['requests']);self.assertEqual('review',result['view'])
        self.assertEqual('1',self.key('f9')['state']['requests'])

    def test_typed_unicode_editing_bounds_and_field_navigation(self):
        self.stage('target.inspect',dict(target_id=''))
        self.call(op='text',text='磁盘💾');value=self.key('backspace')['state']
        self.assertEqual('磁盘',value['parameters']['target_id'])
        self.call(op='text',text='x'*4097);value=self.call()['state']
        self.assertEqual('磁盘',value['parameters']['target_id']);self.assertIn('limit',value['notice'])
        self.stage('capability.explain',dict(target_id='fake:alpha@1',operation='target.inspect'))
        self.key('tab');value=self.call(op='text',text='!')['state'];self.assertTrue(value['parameters']['target_id'].endswith('!'))
        self.key('backtab');value=self.call(op='text',text='?')['state'];self.assertTrue(value['parameters']['operation'].endswith('?'))

    def test_graph_command_parity_for_both_renderers(self):
        cases=[('target.list',{}),('topology.show',{}),('target.inspect',dict(target_id='fake:denied@1')),
               ('capability.explain',dict(target_id='fake:stale@1',operation='partition.resize.plan')),
               ('target.inspect',dict(target_id='missing'))]
        for command,parameters in cases:
            self.stage(command,parameters);value=self.execute()['state']['last_outcome']
            request=dict(schema='org.disked.request/1',request_id=value['request_id'],command=command,parameters=parameters,required_features=[])
            process=subprocess.run([str(ARGS.exe),'protocol','serve','--json'],input=json.dumps(request).encode(),capture_output=True,timeout=10)
            self.assertEqual(value,json.loads(process.stdout))
            for linear in [False,True]:self.assertEqual(value,self.call(linear=linear)['state']['last_outcome'])

    def test_command_explorer_availability_and_focus_remain_visible(self):
        self.key('f2')
        for _ in range(34):
            value=self.key('down');focus=value['state']['focus']
            self.assertIn('> '+focus,'\n'.join(value['lines']))
        self.assertIn('unavailable','\n'.join(value['lines']))
        value=self.key('enter')['state'];self.assertEqual('command_unavailable',value['last_outcome']['diagnostics'][0]['code'])
        self.assertEqual('command_unavailable',self.stage('protocol.serve')['state']['last_outcome']['diagnostics'][0]['code'])

    def test_linear_output_is_complete_and_small_layout_does_not_change_outcomes(self):
        value=self.call(columns=10,rows=3);self.assertIn('linear',value['lines'][0])
        text='\n'.join(value['lines']);self.assertIn('fake:unknown@1',text);self.assertIn('Omission:',text);self.assertIn('bytes=unknown',text)
        self.stage('target.inspect',dict(target_id='fake:volume@1'));self.execute()
        small=self.call(columns=10,rows=3);self.assertTrue(all(all(32<=ord(c)<127 for c in line) for line in small['lines']))
        self.assertIn('\\u001b','\n'.join(small['lines']))
        outcome=small['state']['last_outcome']
        for columns,rows in [(60,16),(80,25),(10000,10000)]:
            other=self.call(columns=columns,rows=rows)
            self.assertEqual(outcome,other['state']['last_outcome']);self.assertLessEqual(len(other['lines']),80)
            self.assertTrue(all(len(line)<=min(columns,240) for line in other['lines']))

    def test_orderly_quit_stops_later_actions(self):
        self.key('f10');self.key('enter');value=self.call()['state']
        self.assertTrue(value['done']);self.assertEqual('0',value['requests']);self.assertIsNone(value['selection']['target_id'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--exe',type=Path,required=True);ARGS=p.parse_args()
    unittest.main(argv=[__file__],verbosity=2)
