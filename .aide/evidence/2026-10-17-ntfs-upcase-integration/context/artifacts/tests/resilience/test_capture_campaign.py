"""Real native producer faults, shared service and actual Windows frontends."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from gui_fixture import Gui,U,WP

P=argparse.ArgumentParser();P.add_argument('--exe',type=Path,required=True);P.add_argument('--campaign',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.campaign=ARGS.campaign.resolve();OBSERVATIONS=[]
FAILURES=['denied:denied:access_denied:5','malformed:malformed:provider_result_invalid','exited:unavailable:provider_exited:3758150013']

class Campaign(unittest.TestCase):
    def assert_graph(self,graph,late=False):
        nodes={n['id']:n for n in graph['nodes']}
        self.assertEqual('current',nodes['fake:alpha@1']['properties']['state'])
        self.assertEqual('denied',nodes['fake:denied@1']['properties']['state'])
        for omission in FAILURES:self.assertIn(omission,graph['omissions'])
        if late:
            self.assertIn('fake:late@1',nodes);self.assertNotIn('slow:timed_out:probe_wait_expired',graph['omissions'])
        else:self.assertIn('slow:timed_out:probe_wait_expired',graph['omissions'])

    def assert_witnesses(self,report):
        self.assertEqual({'denied','malformed','slow','exited'},set(report['witnesses']))
        identities=set()
        for name,row in report['witnesses'].items():
            identities.add((row['process_id'],row['process_created']))
            self.assertTrue(row['exit_observed'] and row['private_job_member'] and row['aggregate_job_member'])
            self.assertEqual(('1','4','67108864','268435456'),(row['private_active_limit'],row['aggregate_active_limit'],row['process_memory_limit'],row['aggregate_memory_limit']))
            self.assertLessEqual(int(row['peak_process_memory']),67108864)
            self.assertEqual('3758150013' if name=='exited' else '0',row['exit_code'])
        self.assertEqual(4,len(identities))
        self.assertTrue(all(not row['outstanding'] and row['worker_epoch']=='1' for row in report['sources']))

    def test_protocol_retains_failures_freshness_and_late_success(self):
        with tempfile.TemporaryDirectory(prefix='disked-capture-protocol-') as directory:
            p=subprocess.Popen([str(ARGS.campaign),'protocol','serve','--format=ndjson'],cwd=directory,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            samples=[]
            def call(command,parameters=None,**fields):
                request=dict(schema='org.disked.request/1',request_id='campaign:'+str(len(samples)),command=command,
                             parameters=parameters or {},required_features=[],**fields)
                started=time.monotonic();p.stdin.write(json.dumps(request).encode()+b'\n');p.stdin.flush();value=json.loads(p.stdout.readline())
                samples.append(dict(elapsed_ms=(time.monotonic()-started)*1000,response=value));return value
            try:
                self.assertIsNone(call('mode.explain')['result']['test_capture_campaign'])
                first=call('target.list')['result']['graph'];time.sleep(.55)
                mixed=call('target.list')['result']['graph'];self.assert_graph(mixed)
                stale=call('target.inspect',dict(target_id='fake:alpha@1'),expected_revision=first['revision'])
                self.assertEqual('revision_conflict',stale['diagnostics'][0]['code'])
                for _ in range(8):
                    healthy=call('target.inspect',dict(target_id='fake:alpha@1'));self.assertEqual('completed',healthy['status'])
                    self.assertLess(samples[-1]['elapsed_ms'],250)
                intermediate=call('mode.explain')['result']['test_capture_campaign']
                slow=next(s for s in intermediate['sources'] if s['id']=='slow');self.assertTrue(slow['outstanding']);self.assertEqual('timed_out',slow['state'])
                time.sleep(1.5);last=call('target.list')['result']['graph'];self.assert_graph(last,late=True)
                final=call('mode.explain')['result']['test_capture_campaign'];self.assert_witnesses(final)
                p.stdin.close();p.stdin=None;out,err=p.communicate(timeout=5)
                self.assertEqual((2,b'',b''),(p.returncode,out,err));self.assertEqual([],list(Path(directory).iterdir()))
                OBSERVATIONS.append(dict(frontend='protocol',samples=samples,intermediate=intermediate,final=final))
            finally:
                if p.poll() is None:p.kill();p.wait(timeout=3)
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream:stream.close()

    def test_gui_preserves_staged_revision_and_healthy_selection(self):
        g=Gui(ARGS.campaign,['--gui','target','inspect','fake:alpha@1'],render=True)
        try:
            staged=g.details()['expected_revision'];time.sleep(.55);g.click(106)
            self.assertEqual(staged,g.details()['expected_revision'])
            g.click(109);g.click(110);self.assertEqual('revision_conflict',g.details()['diagnostics'][0]['code'])
            g.click(104);graph=g.details()['current'];self.assert_graph(graph)
            samples=[]
            for _ in range(8):
                result=WP();started=time.monotonic();ok=U.SendMessageTimeoutW(g.window,0,0,0,2,250,C.byref(result))
                samples.append((time.monotonic()-started)*1000);self.assertTrue(ok);self.assertLess(samples[-1],250)
            g.choose(0);g.click(108);self.assertEqual('fake:alpha@1',g.details()['result']['target']['id'])
            time.sleep(1.5);g.click(106);g.click(104);self.assert_graph(g.details()['current'],late=True)
            self.assertIn('fake:alpha@1',g.text(102))
            g.click(105);g.choose(g.list_ids().index('mode.explain [available]'));g.click(108);g.click(109);g.click(110)
            report=g.details()['result']['test_capture_campaign'];self.assert_witnesses(report)
            OBSERVATIONS.append(dict(frontend='gui',initial_revision=staged,mixed=graph,input_samples_ms=samples,final=report))
        finally:g.close()
        self.assertEqual(0,g.code);self.assertEqual([],g.created_files)

    def test_console_frontends_keep_cached_navigation_and_shell_input(self):
        for frontend in ('tui','shell'):
            with self.subTest(frontend=frontend),tempfile.TemporaryDirectory(prefix='disked-capture-console-') as directory:
                report=Path(directory)/'report.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
                p=subprocess.run([sys.executable,str(Path(__file__).with_name('console_capture_fixture.py')),str(ARGS.campaign),str(report),frontend],
                    cwd=directory,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=30)
                value=json.loads(report.read_text(encoding='utf-8'));OBSERVATIONS.append(value)
                self.assertEqual(0,p.returncode,json.dumps(value,indent=2));self.assertNotIn('fixture_error',value)
                self.assertLess(value['cached_navigation_ms'],250)

    def test_essential_commands_do_not_start_campaign_and_product_has_no_test_role(self):
        for args in [['build','inspect'],['help'],['commands'],['mode','explain']]:
            result=subprocess.run([str(ARGS.campaign),*args,'--json'],capture_output=True,timeout=5)
            self.assertEqual((0,b''),(result.returncode,result.stderr));value=json.loads(result.stdout)
            if args==['mode','explain']:self.assertIsNone(value['result']['test_capture_campaign'])
        result=subprocess.run([str(ARGS.exe),'__disked_capture_probe','3','1','--json'],capture_output=True,timeout=5)
        self.assertEqual(3,result.returncode);self.assertEqual('command_unavailable',json.loads(result.stdout)['diagnostics'][0]['code'])

if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(tests=result.result.testsRun,passed=result.result.wasSuccessful(),
        campaign=str(ARGS.campaign),sha256=hashlib.sha256(ARGS.campaign.read_bytes()).hexdigest(),observations=OBSERVATIONS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
