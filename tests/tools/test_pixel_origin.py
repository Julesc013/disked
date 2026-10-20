"""Independent fixed vectors and adversarial pixels for the bounded GUI preflight."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'.aide/evidence/2026-10-18-ordinary-worker'
spec=importlib.util.spec_from_file_location('pixel_origin_verifier',HERE/'pixel-origin.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PixelOriginTests(unittest.TestCase):
    def setUp(self):self.seed=bytes(range(16))

    def test_fixed_recipe_vectors_and_tile_edges(self):
        rgb=module.expected_rgb(self.seed,0);self.assertEqual(len(rgb),69120)
        for x,y,color in [(0,0,'99d67a'),(59,23,'99d67a'),(60,0,'ee636f'),
                          (0,24,'ed876e'),(239,95,'b6c2aa')]:
            at=(y*240+x)*3;self.assertEqual(rgb[at:at+3].hex(),color)
        other=module.expected_rgb(self.seed,1)
        self.assertEqual(other[:3].hex(),'a32254');self.assertEqual(other[-3:].hex(),'ccf598')

    def test_all_rgb_pixels_and_only_unused_alpha_are_compared(self):
        rgb=module.expected_rgb(self.seed,0);bgra=bytearray(92160)
        bgra[0::4]=rgb[2::3];bgra[1::4]=rgb[1::3];bgra[2::4]=rgb[0::3]
        for alpha in (0,1,255):
            bgra[3::4]=bytes([alpha])*23040
            self.assertEqual(module.rgb_pixels(bytes(bgra)),rgb)
        bgra[-2]^=1
        self.assertNotEqual(module.rgb_pixels(bytes(bgra)),rgb)

    def test_stale_and_wrong_surface_do_not_match_expected_phase(self):
        first=module.expected_rgb(self.seed,0);second=module.expected_rgb(self.seed,1)
        self.assertNotEqual(first,second)
        self.assertNotEqual(module.rgb_pixels(bytes(92160)),first)
        self.assertNotEqual(module.rgb_pixels(bytes(92160)),second)

    def test_strict_geometry_challenge_and_phase_domains(self):
        for value in (b'',bytes(15),bytes(17),'a'*32,None):
            with self.subTest(value=value),self.assertRaises(ValueError):module.expected_rgb(value,0)
        for value in (True,False,-1,2,'0',None):
            with self.subTest(value=value),self.assertRaises(ValueError):module.expected_rgb(self.seed,value)
        for value in (b'',bytes(92159),bytes(92161),bytearray(92160),None):
            with self.assertRaises(ValueError):module.rgb_pixels(value)

    def test_print_producer_has_no_display_read_or_desktop_switch_path(self):
        # Accidental regression guard,not an OS isolation or pixel-origin proof.
        tree=ast.parse((HERE/'pixel-print.py').read_bytes())
        forbidden={'GetDC','GetDCEx','GetWindowDC','BitBlt','StretchBlt','GetDesktopWindow','SwitchDesktop'}
        names={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
        names|={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
        self.assertFalse(names&forbidden)

    def test_broker_rejects_stale_pixels_despite_correct_transport_hash(self):
        first=module.expected_rgb(self.seed,0);body=bytearray(92160)
        body[0::4]=first[2::3];body[1::4]=first[1::3];body[2::4]=first[0::3];body=bytes(body)
        header=dict(method=module.METHOD,sha256=hashlib.sha256(body).hexdigest(),api_succeeded=True,
                    renderer_pid=456,renderer_thread=777,fixture_hook_scope='exact-owned-ui-thread',fixture_dll_sha256='fixture-hash',
                    producer_identity=dict(pid=999,user_sid='actor',integrity_sid='S-1-16-8192',
                        restricted=True,administrator=False,elevated=0,appcontainer=0))
        response=SimpleNamespace(returncode=0,stdout=json.dumps(header).encode()+b'\n'+body,stderr=b'')
        records={};archive=SimpleNamespace(writestr=lambda name,value:records.update({name:value}))
        broker=module.Broker.__new__(module.Broker);broker.expected=[first,module.expected_rgb(self.seed,1)]
        broker.observations=[];broker.archive=archive;broker.last_producer_pid=999
        broker.worker=SimpleNamespace(user_sid='actor')
        broker.render_sha256='fixture-hash'
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as directory:
            broker.temp=Path(directory)
            request=dict(window=123,pid=456,desktop='DiskEdTest-'+'a'*32)
            self.assertNotIn('DISKED_PIXEL_CHALLENGE',module.producer_environment(dict(DISKED_PIXEL_CHALLENGE='not-for-the-producer')))
            with patch.object(broker,'_producer',return_value=response.stdout):
                    self.assertEqual(broker._read_pixels(request),response.stdout)
                    with self.assertRaisesRegex(ValueError,'phase1'):broker._read_pixels(request)
            self.assertIn('pixel-origin/phase-1.png',records)
            self.assertTrue(broker.observations[0]['exact_all_pixels'])
            self.assertFalse(broker.observations[1]['exact_all_pixels'])

    def test_control_refuses_host_before_any_windows_api(self):
        definition=importlib.util.spec_from_file_location('owned_pixel_control',HERE/'pixel-window.py')
        control=importlib.util.module_from_spec(definition);definition.loader.exec_module(control)
        with patch.object(control.socket,'gethostname',return_value='physical-host'):
            with patch.object(control.C,'WinDLL',create=True) as api:
                with self.assertRaisesRegex(ValueError,'guest-only'):control.main()
                api.assert_not_called()

    def test_unknown_surface_is_rejected_without_retaining_pixels_or_binary_log(self):
        body=bytes([1,2,3,255])*23040
        header=dict(method=module.METHOD,sha256=hashlib.sha256(body).hexdigest(),api_succeeded=True,
                    renderer_pid=456,renderer_thread=777,fixture_hook_scope='exact-owned-ui-thread',fixture_dll_sha256='fixture-hash',
                    producer_identity=dict(pid=999,user_sid='actor',integrity_sid='S-1-16-8192',
                        restricted=True,administrator=False,elevated=0,appcontainer=0))
        raw=json.dumps(header).encode()+b'\n'+body;records={}
        broker=module.Broker.__new__(module.Broker);broker.expected=[module.expected_rgb(self.seed,p) for p in (0,1)]
        broker.observations=[];broker.archive=SimpleNamespace(writestr=lambda name,value:records.update({name:value}))
        broker.worker=SimpleNamespace(user_sid='actor');broker.last_producer_pid=999;broker.last_producer_log=raw
        broker.render_sha256='fixture-hash'
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as directory:
            broker.temp=Path(directory)
            with patch.object(broker,'_producer',return_value=raw):
                with self.assertRaisesRegex(ValueError,'pixel-origin comparison'):
                    broker._read_pixels(dict(window=123,pid=456,desktop='DiskEdTest-'+'a'*32))
        self.assertEqual(set(records),{'pixel-origin/phase-0.json'})
        self.assertFalse(broker.observations[0]['pixels_retained'])

    def test_expected_pixels_cannot_authorize_a_different_renderer(self):
        broker=module.Broker.__new__(module.Broker);broker.observations=[];broker.render_sha256='fixture-hash'
        for changed in ({'renderer_pid':457},{'renderer_thread':0},{'fixture_dll_sha256':'other'},
                        {'fixture_hook_scope':'global'}):
            header=dict(renderer_pid=456,renderer_thread=777,fixture_dll_sha256='fixture-hash',
                        fixture_hook_scope='exact-owned-ui-thread');header.update(changed)
            with self.subTest(changed=changed),patch.object(broker,'_producer',return_value=json.dumps(header).encode()+b'\n'+bytes(92160)):
                with self.assertRaisesRegex(ValueError,'renderer identity'):
                    broker._read_pixels(dict(pid=456))


if __name__=='__main__':unittest.main()
