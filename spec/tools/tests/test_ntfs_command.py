"""NTFS command shape/range regressions at the canonical schema boundary."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc

class NtfsCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=sc.Bundle(Path(__file__).resolve().parents[2])

    def test_version_choices_and_signed_window(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs',volume_offset='173',volume_bytes='512')
        for selector in (None,'auto','3.0','3.1'):
            row=dict(value)
            if selector is not None:row['ntfs_version']=selector
            self.bundle.validate(schema,row)
        valid=dict(value,volume_offset=str((1<<63)-1-512))
        self.bundle.validate(schema,valid)
        for key,selected in [('ntfs_version','2.0'),('volume_bytes','511'),('volume_bytes','18446744073709551616'),('volume_offset',str((1<<63)-512)),('fat_copy','0'),('retain_capture','no'),('upcase_format','auto')]:
            row=dict(value);row[key]=selected
            with self.subTest(key=key,value=selected),self.assertRaises(sc.SpecError):self.bundle.validate(schema,row)

    def test_selector_is_confined_to_ntfs_and_old_forms_remain(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        for view in (None,'map','fat','exfat'):
            row=dict(path='generated.img')
            if view:row['view']=view
            if view in ('fat','exfat'):row.update(volume_offset='0',volume_bytes='512')
            self.bundle.validate(schema,row)
            with self.subTest(view=view),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,dict(row,ntfs_version='auto'))

if __name__=='__main__':unittest.main()
