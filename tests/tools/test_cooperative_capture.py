"""Independent control-frame contradictions; no host native process or capture."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('cooperative_control_frames',ROOT/'tests/support/cooperative_capture.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class CooperativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.expected=[b'\x19\x29\x39'*23040,b'\x49\x59\x69'*23040]
        self.payloads=[]
        for rgb in self.expected:
            bgra=bytearray(92160);bgra[0::4]=rgb[2::3];bgra[1::4]=rgb[1::3];bgra[2::4]=rgb[0::3];self.payloads.append(bytes(bgra))
        self.header=dict(schema='org.disked.cooperative-capture-control/1',method=S.METHOD,pid='1234',thread='4321',window='1001',nonce='123456789',
            identity=dict(sid='actor',integrity_sid='S-1-16-8192',restricted=True,elevated=False,appcontainer=False),
            negative_controls=[dict(name=n,refused=True,render_called=i>=9) for i,n in enumerate(S.NEGATIVES)],
            phases=[dict(phase=str(i),width='240',height='96',bytes='92160',gdi_before='4',gdi_after='4') for i in range(2)],
            mutating_open_refusals=[dict(access=str(v),error='32') for v in (0x40000000,0x10000)],job_access_refusals=[dict(access=str(v),error='5') for v in (1,2,8)],
            display_dc_read=False,desktop_switched=False)
    def frame(self,header=None):
        body=json.dumps(self.header if header is None else header).encode();return struct.pack('<I',len(body))+body+b''.join(self.payloads)
    def parse(self,body=None):return S.parse_frame(self.frame() if body is None else body,process_id=1234,nonce=123456789,actor_sid='actor')
    def test_bound_frame_exact_rgb_and_alpha_independence(self):
        header,payloads=self.parse();self.assertEqual(header,self.header);self.assertEqual(S.verify_pixels(payloads,self.expected),self.expected)
        changed=bytearray(payloads[0]);changed[3::4]=b'\xff'*23040
        self.assertEqual(S.verify_pixels([bytes(changed),payloads[1]],self.expected),self.expected)
    def test_zero_stale_and_single_channel_changes_reject(self):
        for values in ([self.payloads[0],self.payloads[0]],[bytes(92160),self.payloads[1]]):
            with self.assertRaisesRegex(ValueError,'pixel_origin'):S.verify_pixels(values,self.expected)
        wrong=bytearray(self.payloads[0]);wrong[2]^=1
        with self.assertRaisesRegex(ValueError,'pixel_origin'):S.verify_pixels([bytes(wrong),self.payloads[1]],self.expected)
    def test_identity_phase_and_required_guard_contradictions_reject(self):
        for key,value in [('pid','5678'),('nonce','987654321'),('display_dc_read',True),('method','old-hook')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.parse(self.frame(dict(self.header,**{key:value})))
        for change in ('guard','token','geometry','gdi','write_access','job_access'):
            bad=copy.deepcopy(self.header)
            if change=='guard':bad['negative_controls'].pop()
            elif change=='token':bad['identity']['restricted']=1
            elif change=='geometry':bad['phases'][0]['width']='241'
            elif change=='gdi':bad['phases'][0]['gdi_after']='5'
            elif change=='write_access':bad['mutating_open_refusals'][0]['error']='0'
            else:bad['job_access_refusals'][0]['error']='0'
            with self.subTest(change=change),self.assertRaises(ValueError):self.parse(self.frame(bad))
    def test_missing_extra_oversized_and_duplicate_frame_fields_reject(self):
        frame=self.frame()
        for value in (b'',frame[:-1],frame+b'x',struct.pack('<I',16385)+frame[4:]):
            with self.assertRaises(ValueError):self.parse(value)
        body=json.dumps(self.header).encode();body=body[:-1]+b',"pid":"1234"}'
        with self.assertRaisesRegex(ValueError,'duplicate_field'):self.parse(struct.pack('<I',len(body))+body+b''.join(self.payloads))

    def test_tree_proof_cannot_substitute_for_parent_only_or_omit_refusals(self):
        header=dict(self.header,schema='org.disked.cooperative-tree-control/1',method=S.TREE_METHOD,descendants='2',
                    tree_controls=[dict(name=n,refused=True,render_called=i>=2) for i,n in enumerate(S.TREE_NEGATIVES)])
        args=dict(process_id=1234,nonce=123456789,actor_sid='actor',tree=True)
        self.assertEqual(S.parse_frame(self.frame(header),**args)[0],header)
        with self.assertRaises(ValueError):self.parse(self.frame(header))
        for change in ('missing','foreign_render','count','swapped'):
            wrong=copy.deepcopy(header)
            if change=='missing':wrong['tree_controls'].pop()
            elif change=='foreign_render':wrong['tree_controls'][0]['render_called']=True
            elif change=='count':wrong['descendants']='1'
            else:wrong['tree_controls'].reverse()
            with self.subTest(change=change),self.assertRaises(ValueError):S.parse_frame(self.frame(wrong),**args)


if __name__=='__main__':unittest.main()
