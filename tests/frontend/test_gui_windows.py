"""Actual native Win32 controls on a test-owned inactive desktop."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import unittest
from gui_fixture import Gui,U,W,caption,send,modules,wait

OBSERVATIONS=[]
class WindowsGui(unittest.TestCase):
    def launch(self,args=None):
        g=Gui(ARGS.exe,args,render=True)
        def close():
            g.close();self.assertEqual(0,g.code);self.assertEqual(b'',g.error);self.assertEqual(b'',g.output);self.assertEqual([],g.created_files)
        self.addCleanup(close);return g
    def capture(self,g,name):
        OBSERVATIONS.append(dict(case=name,observation=g.observation()))
        if ARGS.evidence:
            ARGS.evidence.parent.mkdir(parents=True,exist_ok=True)
            g.screenshot(ARGS.evidence.parent/(name+'.png'))
    def test_native_controls_cached_graph_and_actual_render(self):
        g=self.launch();value=g.details();self.assertIsNone(value['proposed']);self.assertEqual(7,len(value['current']['nodes']))
        rows=g.list_ids();self.assertIn('fake:denied@1 [denied]',rows);self.assertIn('fake:unknown@1 [unknown]',rows)
        observed=g.observation();roles={c['id']:c['role'] for c in observed['children']}
        self.assertEqual('ListBox',roles[100]);self.assertEqual('Edit',roles[101]);self.assertEqual('Button',roles[108])
        self.assertTrue(all(c['font'] for c in observed['children']));self.assertIn('High contrast:',observed['notice'])
        for module in ['user32.dll','gdi32.dll']:
            self.assertIn('\\system32\\',observed['modules'][module].lower())
        self.capture(g,'inventory')
        g.choose(6);g.click(108);result=g.details();self.assertEqual('fake:volume@1',result['result']['target']['id'])
        self.assertIn('\\u001b',g.text(101));self.assertNotIn('\x1b',g.text(101))
        self.capture(g,'inspector')
    def test_keyboard_traversal_and_explicit_navigator_enter(self):
        g=self.launch();seen=set()
        for _ in range(16):
            seen.add(U.GetDlgCtrlID(g.focus()));g.key(9)
        self.assertTrue({104,105,106,107,100,108,101}.issubset(seen),seen)
        g.choose(2);g.key(13,g.child(100));wait(lambda:'status' in g.details())
        self.assertEqual('fake:denied@1',g.details()['result']['target']['id'])
        g.click(105);rows=g.list_ids()
        catalog=json.loads((Path(__file__).resolve().parents[2]/'spec/catalog/commands.json').read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in catalog['commands']],[r.split(' ',1)[0] for r in rows])
        index=next(i for i,s in enumerate(rows) if s.startswith('partition.resize.plan '))
        g.choose(index);g.key(13,g.child(100));wait(lambda:'diagnostics' in g.details())
        self.assertEqual('command_unavailable',g.details()['diagnostics'][0]['code'])
        OBSERVATIONS.append(dict(case='keyboard',focus_ids=sorted(seen)))
    def test_forms_require_separate_review_submit_and_match_cli(self):
        g=self.launch(['--gui','target','inspect','fake:alpha@1'])
        self.assertFalse(U.IsWindowEnabled(g.child(110)))
        g.key(13,g.child(200));self.assertIn('command',g.details());self.assertNotIn('status',g.details())
        g.click(109);self.assertTrue(U.IsWindowEnabled(g.child(110)));self.assertTrue(g.details()['reviewed'])
        for target in [110,200]:
            for _ in range(24):
                if U.GetDlgCtrlID(g.focus())==target:break
                g.key(9)
            self.assertEqual(target,U.GetDlgCtrlID(g.focus()))
        g.key(13);self.assertNotIn('status',g.details())
        self.capture(g,'request-review')
        g.set(200,'fake:denied@1');self.assertFalse(U.IsWindowEnabled(g.child(110)))
        g.click(110);self.assertNotIn('status',g.details())
        g.click(109);g.click(110);actual=g.details();self.assertFalse(U.IsWindowEnabled(g.child(110)))
        request=dict(schema='org.disked.request/1',request_id=actual['request_id'],command='target.inspect',parameters=dict(target_id='fake:denied@1'),required_features=[])
        p=subprocess.run([str(ARGS.exe),'protocol','serve','--json'],input=json.dumps(request).encode(),capture_output=True,timeout=10)
        self.assertEqual(actual,json.loads(p.stdout));g.click(110);self.assertEqual(actual,g.details())
        self.capture(g,'request-result')
    def test_oversized_insert_and_control_text_cannot_authorize_old_value(self):
        g=self.launch(['--gui','target','inspect','fake:alpha@1']);g.click(109)
        buffer=C.create_unicode_buffer('x'*5000)
        send(g.child(200),0xB1,0,-1);send(g.child(200),0xC2,1,C.addressof(buffer))
        self.assertFalse(U.IsWindowEnabled(g.child(110)));g.click(109);self.assertFalse(U.IsWindowEnabled(g.child(110)))
        self.assertIn('limit',g.text(103))
        self.assertEqual('x'*4097,g.text(200))
        g.set(200,'fake:alpha@1\nnot-a-command');g.key(13,g.child(200));g.click(109)
        self.assertFalse(U.IsWindowEnabled(g.child(110)));self.assertNotIn('status',g.details())
        g.set(200,'fake:alpha@1');g.click(109);g.click(110);self.assertEqual('completed',g.details()['status'])
    def test_mode_observation_and_setting_refresh(self):
        g=self.launch(['--gui','mode','explain']);g.click(109);g.click(110);value=g.details()['result']
        self.assertEqual('gui',value['selection']['frontend']);self.assertTrue(value['policy_inputs']['gui_available']);self.assertTrue(value['policy_inputs']['display'])
        self.assertEqual('available',value['observations']['display']);self.assertEqual('win32-native',value['observations']['gui']['backend'])
        before=g.observation();send(g.window,0x1A);after=g.observation()
        self.assertEqual(before['colors'],after['colors']);self.assertEqual(value['observations']['gui']['high_contrast'],'High contrast: on' in after['notice'])
        OBSERVATIONS.append(dict(case='mode',result=value,after=after))
    def test_resize_keeps_controls_in_client_and_details_complete(self):
        g=self.launch(['--gui','capability','explain','fake:alpha@1','target.inspect'])
        class Point(C.Structure):_fields_=[('x',C.c_long),('y',C.c_long)]
        class MinMax(C.Structure):_fields_=[('reserved',Point),('size',Point),('position',Point),('minimum',Point),('maximum',Point)]
        limits=MinMax();send(g.window,0x24,0,C.addressof(limits))
        self.assertGreaterEqual(limits.minimum.x,800);self.assertGreaterEqual(limits.minimum.y,570)
        self.assertTrue(U.SetWindowPos(g.window,None,0,0,limits.minimum.x,limits.minimum.y,0x16))
        g.click(109);self.assertEqual('target.inspect',g.details()['parameters']['operation']);g.click(110)
        self.assertEqual('fake:alpha@1',g.details()['result']['assessment']['target_id'])
        # Child rectangles must remain within the parent's visible client area.
        client=W.RECT();assert U.GetClientRect(g.window,C.byref(client))
        U.MapWindowPoints.argtypes=[W.HWND,W.HWND,C.c_void_p,C.c_uint];U.MapWindowPoints.restype=C.c_int
        for id in [100,101,200,201,109,110,111]:
            rect=W.RECT();self.assertTrue(U.GetWindowRect(g.child(id),C.byref(rect)));U.MapWindowPoints(None,g.window,C.byref(rect),2)
            self.assertGreaterEqual(rect.left,0);self.assertGreaterEqual(rect.top,0);self.assertLessEqual(rect.right,client.right);self.assertLessEqual(rect.bottom,client.bottom)
        self.capture(g,'minimum-window')
    def test_unavailable_gui_dependency_is_named_and_headless_remains_static(self):
        for exe in [ARGS.exe,ARGS.guard,ARGS.unavailable]:
            for args in [['--gui','--help'],['build','inspect','--json'],['--gui','--json']]:
                p=subprocess.run([str(exe),*args],input=b'',capture_output=True,timeout=10)
                self.assertEqual(2 if args==['--gui','--json'] else 0,p.returncode)
        p=subprocess.run([str(ARGS.unavailable),'--gui'],input=b'',capture_output=True,timeout=10)
        self.assertEqual(3,p.returncode);self.assertIn(b'gui_dependency_unavailable',p.stderr);self.assertEqual(b'',p.stdout)
        # Keep a real headless server alive while observing modules. Host
        # injection may add GUI modules independently of product imports.
        p=subprocess.Popen([str(ARGS.unavailable),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            request=dict(schema='org.disked.request/1',request_id='module-check',command='build.inspect',parameters={},required_features=[])
            p.stdin.write(json.dumps(request).encode()+b'\n');p.stdin.flush();self.assertEqual('completed',json.loads(p.stdout.readline())['status'])
            OBSERVATIONS.append(dict(case='headless-module-observation',modules=modules(p.pid),application_gui_boundary='unavailable-trap-not-entered'))
            p.stdin.close();self.assertEqual(0,p.wait(timeout=5));self.assertEqual(b'',p.stderr.read())
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stdout.close();p.stderr.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['exe','guard','unavailable']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--evidence',type=Path);ARGS=p.parse_args()
    ARGS.exe=ARGS.exe.resolve();ARGS.guard=ARGS.guard.resolve();ARGS.unavailable=ARGS.unavailable.resolve()
    try:unittest.main(argv=[__file__],verbosity=2)
    finally:
        if ARGS.evidence:
            ARGS.evidence.parent.mkdir(parents=True,exist_ok=True)
            ARGS.evidence.write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8',newline='\n')
