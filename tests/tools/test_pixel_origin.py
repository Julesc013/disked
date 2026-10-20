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
        header=dict(method=module.METHOD,sha256=hashlib.sha256(body).hexdigest(),api_succeeded=True)
        response=SimpleNamespace(returncode=0,stdout=json.dumps(header).encode()+b'\n'+body,stderr=b'')
        records={};archive=SimpleNamespace(writestr=lambda name,value:records.update({name:value}))
        broker=module.Broker.__new__(module.Broker);broker.expected=[first,module.expected_rgb(self.seed,1)]
        broker.observations=[];broker.archive=archive
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as directory:
            broker.temp=Path(directory)
            request=dict(window=123,pid=456,desktop='DiskEdTest-'+'a'*32)
            with patch.dict(os.environ,DISKED_PIXEL_CHALLENGE='not-for-the-producer'):
                with patch.object(module.subprocess,'run',return_value=response) as run:
                    self.assertEqual(broker._read_pixels(request),response.stdout)
                    self.assertNotIn('DISKED_PIXEL_CHALLENGE',run.call_args.kwargs['env'])
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


if __name__=='__main__':unittest.main()
