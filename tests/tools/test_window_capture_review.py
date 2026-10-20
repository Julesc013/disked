"""Synthetic receipt mismatches must not qualify retained GUI evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_review',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/review-native.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


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

    def verify(self):return module.review_window_captures(self.proof,self.summary,self.inventory)

    def test_complete_bound_receipts(self):
        self.assertEqual(self.verify()['qualified_captures'],6)
        for capture in self.summary['captures']:capture['path']='R:\\work\\build\\'+capture['name']+'.png'
        self.assertEqual(self.verify()['qualified_captures'],6)

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


if __name__=='__main__':unittest.main()
