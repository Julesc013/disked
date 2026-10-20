"""Synthetic receipt mismatches must not qualify retained GUI evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tarfile
from types import SimpleNamespace
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_review',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/review-native.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
spec=importlib.util.spec_from_file_location('review_packet_fixture',ROOT/'tests/support/capture_transport.py')
packet_fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(packet_fixture)


class CaptureReview(unittest.TestCase):
    def setUp(self):
        self.proof=dict(source_revision='a'*40,executables=dict(disked=dict(sha256='sha256:'+'c'*64)),
            owned_window_scope_controls=dict(outside_job=True,different_image=True,
                image_write_open_refused=True,image_delete_open_refused=True),owned_window_captures=[])
        self.summary=dict(passed=True,source_dirty=False,source_revision='a'*40,executable_sha256='sha256:'+'c'*64,captures=[])
        self.inventory={}
        for index,name in enumerate(mode+'-'+str(i) for mode in ('inventory','review','minimum') for i in range(2)):
            pixel=format(index+1,'064x');png=format(index+17,'064x')
            self.proof['owned_window_captures'].append(dict(method='owned-window-dc',desktop_acl_validated=True,
                image_sha256='c'*64,image_pin_held=True,image_file_id='a'*32,image_file_volume='123',
                id=format(index+1,'032x'),nonce='d'*32,desktop='DiskEdTest-'+'e'*32,
                pid=100+index,window=1000+index,width=1000,height=720,bytes=2880000,sha256=pixel))
            self.summary['captures'].append(dict(name=name,path=name+'.png',sha256='sha256:'+png,
                geometry=dict(width=1000,height=720,pixels_sha256=pixel,capture_method='owned-window-dc')))
            self.inventory['groups/frontend.gui_capture/'+name+'.png']=dict(sha256=png)

    def verify(self):return module.validate_window_capture_receipts(self.proof,self.summary,self.inventory)

    def cooperative(self):
        proof,summary=copy.deepcopy(self.proof),copy.deepcopy(self.summary)
        for i,(row,case) in enumerate(zip(proof['owned_window_captures'],summary['captures'])):
            pair=i//2;frame=[20,30,1036,789]
            row.update(method=module.COOPERATIVE,pid=100+pair,window=1000+pair,thread=200+pair,desktop='DiskEdTest-'+format(pair+1,'032x'),
                       sequence=i%2+1,receiver_sequence=i%2+1,descendants=20,gdi_before=11,gdi_after=11,case_id=row['id'],capture_id=row['id'],
                       frame_bounds=frame,window_rect=frame,client_box=[0,0,1000,720],membership_job_query_access=4,output_section_access=2,
                       supervisor_handle_exposed=False,membership_jobs_retired=True,output_sections_retired=True)
            packet=packet_fixture.encode_request(nonce=0x0102030405060708,sequence=i%2+1,width=1000,height=720,window=row['window'],process=row['pid'],thread=row['thread'],
                job_handle=50+pair,section_handle=100+i,volume=123,file_id=bytes.fromhex(row['image_file_id']),case_id=bytes.fromhex(row['id']),window_rect=frame,desktop='WinSta0\\'+row['desktop'])
            reply=bytearray(124);reply[:8]=b'DECAPS1\0'
            for out,source,length in ((8,8,20),(32,32,16),(48,64,8),(56,72,32),(104,104,16)):reply[out:out+length]=packet[source:source+length]
            struct.pack_into('<I',reply,28,row['bytes']);struct.pack_into('<IIII',reply,88,20,11,11,1)
            struct.pack_into('<I',reply,120,4096+row['bytes'])
            row.update(request_hex=packet.hex(),request_sha256=hashlib.sha256(packet).hexdigest(),reply_header_hex=reply.hex())
            supplied=copy.deepcopy(row);supplied.pop('membership_jobs_retired');supplied.pop('output_sections_retired')
            case['geometry'].update(capture_method=module.COOPERATIVE,client_box=row['client_box'],frame_bounds=frame,capture_receipt=supplied)
        return proof,summary

    def test_cooperative_complete_bound_receipts(self):
        proof,summary=self.cooperative();result=module.review_window_captures(proof,summary,self.inventory)
        self.assertTrue(result['private_cooperative_receipts_validated']);self.assertTrue(result['client_coordinates_verified']);self.assertFalse(result['actual_images_reviewed'])
        self.assertFalse(result['text_recognition_qualified']);self.assertFalse(result['accessibility_qualified'])

    def test_cooperative_capabilities_and_retirement_cannot_be_forged(self):
        for key,value in [('membership_job_query_access',8),('output_section_access',4),('supervisor_handle_exposed',True),('membership_jobs_retired',False),('output_sections_retired',False)]:
            proof,summary=self.cooperative();proof['owned_window_captures'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)

    def test_cooperative_case_id_and_client_coordinates_are_bound(self):
        for field,value in [('client_box',[8,31,1000,720]),('frame_bounds',[21,30,1036,789])]:
            proof,summary=self.cooperative();summary['captures'][0]['geometry'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)
        proof,summary=self.cooperative();summary['captures'][1]['geometry']['capture_receipt']=copy.deepcopy(summary['captures'][0]['geometry']['capture_receipt'])
        with self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)

    def test_cooperative_rehashed_wire_scope_forgery_is_rejected(self):
        for offset in (20,32,40,44,64,72,88,104,120):
            proof,summary=self.cooperative();row=proof['owned_window_captures'][0];body=bytearray.fromhex(row['request_hex']);body[offset]^=1
            row.update(request_hex=body.hex(),request_sha256=hashlib.sha256(body).hexdigest());summary['captures'][0]['geometry']['capture_receipt'].update(request_hex=row['request_hex'],request_sha256=row['request_sha256'])
            with self.subTest(offset=offset),self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)

    def test_cooperative_reply_publication_and_gdi_are_bound(self):
        for offset in (8,16,28,32,48,56,72,88,96,100,104,120):
            proof,summary=self.cooperative();row=proof['owned_window_captures'][0];body=bytearray.fromhex(row['reply_header_hex']);body[offset]^=1
            row['reply_header_hex']=body.hex();summary['captures'][0]['geometry']['capture_receipt']['reply_header_hex']=row['reply_header_hex']
            with self.subTest(offset=offset),self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)

    def test_cooperative_boolean_integer_aliases_are_rejected(self):
        proof,summary=self.cooperative();row=proof['owned_window_captures'][0];row['sequence']=True;row['receiver_sequence']=True
        summary['captures'][0]['geometry']['capture_receipt'].update(sequence=True,receiver_sequence=True)
        with self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory)

    def test_visual_review_requires_exact_source_product_and_six_pngs(self):
        proof,summary=self.cooperative();visual=dict(status='pass',source_revision=proof['source_revision'],product_sha256=summary['executable_sha256'],pngs={c['name']:c['sha256'] for c in summary['captures']})
        self.assertTrue(module.review_window_captures(proof,summary,self.inventory,visual_review=visual)['actual_images_reviewed'])
        for key,value in [('status','fail'),('source_revision','b'*40),('product_sha256','f'*64),('pngs',{})]:
            changed=dict(visual,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):module.review_window_captures(proof,summary,self.inventory,visual_review=changed)

    def test_complete_bound_receipts(self):
        self.assertEqual(self.verify()['captures_with_consistent_receipts'],6)
        for capture in self.summary['captures']:capture['path']='R:\\work\\build\\'+capture['name']+'.png'
        self.assertEqual(self.verify()['captures_with_consistent_receipts'],6)

    def test_consistent_receipts_do_not_admit_invalidated_pixel_origin(self):
        self.verify()
        with self.assertRaisesRegex(ValueError,'pixel origin invalidated'):
            module.review_window_captures(self.proof,self.summary,self.inventory)

    def test_missing_or_duplicate_cases(self):
        self.summary['captures'][1]=copy.deepcopy(self.summary['captures'][0])
        with self.assertRaises(ValueError):self.verify()

    def test_changed_or_missing_png(self):
        self.inventory.pop(next(iter(self.inventory)))
        with self.assertRaises(ValueError):self.verify()

    def test_no_reuse_of_one_coordinator_receipt(self):
        self.summary['captures'][1]['geometry']['pixels_sha256']=self.summary['captures'][0]['geometry']['pixels_sha256']
        with self.assertRaises(ValueError):self.verify()

    def test_duplicate_coordinator_identity(self):
        self.proof['owned_window_captures'][1]['id']=self.proof['owned_window_captures'][0]['id']
        with self.assertRaises(ValueError):self.verify()

    def test_wrong_product_or_acl_or_dimensions(self):
        original=copy.deepcopy(self.proof['owned_window_captures'][0])
        for key,value in (('image_sha256','f'*64),('desktop_acl_validated',False),('bytes',1),('image_pin_held',False)):
            self.proof['owned_window_captures'][0]=dict(original,**{key:value})
            with self.assertRaises(ValueError):self.verify()

    def test_missing_scope_refusal(self):
        self.proof['owned_window_scope_controls'].pop('different_image')
        with self.assertRaises(ValueError):self.verify()

    def test_one_png_cannot_substitute_for_six_cases(self):
        shared='f'*64
        for capture in self.summary['captures']:
            capture.update(path='shared.png',sha256='sha256:'+shared)
        self.inventory={'groups/frontend.gui_capture/shared.png':dict(sha256=shared)}
        with self.assertRaises(ValueError):self.verify()


class BackgroundPixels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scope=dict(struct=struct,zlib=zlib)
        for path,names in [(ROOT/'tests/frontend/gui_fixture.py',('capture_client_content','capture_background_matches')),
                           (ROOT/'tests/frontend/test_gui_capture.py',('png',))]:
            tree=ast.parse(path.read_bytes());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
            assert len(nodes)==len(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
        cls.matches=staticmethod(scope['capture_background_matches']);cls.client=staticmethod(scope['capture_client_content']);cls.png=staticmethod(scope['png'])

    def test_solid_edges_allow_real_interior_and_ignore_alpha(self):
        body=bytearray(bytes([0x11,0x22,0x33,0])*20);body[24:28]=b'\x99\x88\x77\x00'
        self.assertTrue(self.matches(body,5,4,0x112233));body[3::4]=bytes(range(20));self.assertTrue(self.matches(body,5,4,0x112233))

    def test_every_edge_pixel_is_required(self):
        for y in range(4):
            for x in range(5):
                if x not in (0,4) and y not in (0,3):continue
                body=bytearray(bytes([0x11,0x22,0x33,0])*20);body[(y*5+x)*4]^=1
                with self.subTest(x=x,y=y):self.assertFalse(self.matches(body,5,4,0x112233))

    def test_retained_runtime_passing_png_rejects_missing_background(self):
        folder=ROOT/'.aide/evidence/2026-10-21-product-capture/attempt-004'
        with tarfile.open(folder/'retained.tar.xz','r:xz') as stream:
            member=stream.getmember('groups/frontend.gui_capture/inventory-0.png');self.assertLess(member.size,1048576);body=stream.extractfile(member).read()
        retained=json.loads((folder/'replay.json').read_bytes())
        self.assertEqual(hashlib.sha256(body).hexdigest(),retained['pngs']['inventory-0'].removeprefix('sha256:'));self.assertFalse(retained['capture_qualified'])
        width,height,pixels=self.png(SimpleNamespace(read_bytes=lambda:body))
        self.assertTrue(self.client(pixels,width,height,(0,0,width,height)))
        color=pixels[2]|pixels[1]<<8|pixels[0]<<16
        self.assertFalse(self.matches(pixels,width,height,color))

    def test_malformed_background_domains_are_rejected(self):
        for width,height,color in [(0,1,0),(True,1,0),(1,-1,0),(1,1,True),(1,1,0x1000000)]:
            with self.subTest(width=width,height=height,color=color),self.assertRaises(ValueError):self.matches(bytes(4),width,height,color)


if __name__=='__main__':unittest.main()
