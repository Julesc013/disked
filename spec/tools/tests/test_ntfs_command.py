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

    def test_name_order_profile_reference_and_signed_window(self):
        schema = 'urn:disked:schema:command-image-inspect-parameters:1'
        value = dict(path='generated.img', view='ntfs-name-order', volume_offset='0', volume_bytes='512')
        for reference in (None, '0', str(1 << 48), str((1 << 64) - 1)):
            row = dict(value)
            if reference is not None:
                row['directory_reference'] = reference
            for version in ('auto', '3.0', '3.1'):
                self.bundle.validate(schema, dict(row, ntfs_version=version))
        self.bundle.validate(schema, dict(value, volume_offset=str((1 << 63) - 1 - 512)))
        for key, invalid in [('volume_bytes', '511'), ('volume_offset', str((1 << 63) - 512)),
                             ('volume_bytes', str(1 << 64)), ('directory_reference', '1'),
                             ('directory_reference', str(1 << 64)), ('directory_reference', '00'),
                             ('directory_reference', True), ('ntfs_version', '2.0')]:
            with self.subTest(key=key, value=invalid), self.assertRaises(sc.SpecError):
                self.bundle.validate(schema, dict(value, **{key: invalid}))

    def test_name_order_rejects_other_views_default_controls(self):
        schema = 'urn:disked:schema:command-image-inspect-parameters:1'
        value = dict(path='generated.img', view='ntfs-name-order', volume_offset='0', volume_bytes='512')
        for key, invalid in [('ntfs_target_limit', '64'), ('upcase_format', 'auto'),
                             ('logical_block_bytes', '512'), ('fat_copy', '0'),
                             ('allocation_scan', 'no'), ('retain_capture', 'no'),
                             ('lookup', {}), ('allocation_window', {}), ('name_code_page', '437')]:
            with self.subTest(key=key), self.assertRaises(sc.SpecError):
                self.bundle.validate(schema, dict(value, **{key: invalid}))

    def test_upcase_profile_and_signed_window(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs-upcase',volume_offset='0',volume_bytes='512')
        for version in (None,'auto','3.0','3.1'):
            row=dict(value)
            if version is not None:row['ntfs_version']=version
            self.bundle.validate(schema,row)
        self.bundle.validate(schema,dict(value,volume_offset=str((1<<63)-1-512)))
        for key,invalid in [('volume_bytes','511'),('volume_offset',str((1<<63)-512)),('volume_bytes',str(1<<64)),('volume_offset','00'),('ntfs_version',True),('ntfs_version','2.0')]:
            with self.subTest(key=key,value=invalid),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,dict(value,**{key:invalid}))

    def test_upcase_rejects_graph_and_other_view_controls(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs-upcase',volume_offset='0',volume_bytes='512')
        for key,invalid in [('directory_reference','0'),('directory_reference',str(1<<48)),('ntfs_target_limit','64'),('upcase_format','auto'),('logical_block_bytes','512'),('fat_copy','0'),('allocation_scan','no'),('retain_capture','no'),('lookup',{}),('allocation_window',{})]:
            with self.subTest(key=key),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,dict(value,**{key:invalid}))

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

    def test_directory_reference_is_root_or_complete_u64(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs-directory',volume_offset='173',volume_bytes='512')
        for reference in (None,'0',str(1<<48),str((1<<64)-1)):
            row=dict(value)
            if reference is not None:row['directory_reference']=reference
            for version in ('auto','3.0','3.1'):self.bundle.validate(schema,dict(row,ntfs_version=version))
        for reference in ('1',str((1<<48)-1),str(1<<64),'01','-1',True,None):
            with self.subTest(reference=reference),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,dict(value,directory_reference=reference))

    def test_directory_controls_do_not_expand_other_views(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        for view in (None,'map','fat','exfat','ntfs'):
            row=dict(path='generated.img',directory_reference='0')
            if view:row['view']=view
            if view in ('fat','exfat','ntfs'):row.update(volume_offset='0',volume_bytes='512')
            with self.subTest(view=view),self.assertRaises(sc.SpecError):self.bundle.validate(schema,row)

    def test_directory_window_and_unrelated_options(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs-directory',volume_offset='0',volume_bytes='512')
        self.bundle.validate(schema,dict(value,volume_offset=str((1<<63)-1-512)))
        for key,selected in [('volume_offset',str((1<<63)-512)),('volume_bytes','511'),('fat_copy','0'),('retain_capture','no'),('upcase_format','auto'),('logical_block_bytes','512')]:
            with self.subTest(key=key),self.assertRaises(sc.SpecError):self.bundle.validate(schema,dict(value,**{key:selected}))

    def test_membership_target_limits_and_window(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        value=dict(path='generated.img',view='ntfs-membership',volume_offset='0',volume_bytes='512')
        for limit in (None,'1','64','256'):
            row=dict(value)
            if limit is not None:row['ntfs_target_limit']=limit
            for version in ('auto','3.0','3.1'):
                self.bundle.validate(schema,dict(row,ntfs_version=version,directory_reference=str(1<<48)))
        for key,invalid in [('ntfs_target_limit','0'),('ntfs_target_limit','257'),('ntfs_target_limit','01'),('ntfs_target_limit',True),('ntfs_target_limit',None),('ntfs_target_limit',str(1<<64)),('directory_reference','1'),('volume_bytes','511'),('volume_offset',str((1<<63)-512)),('fat_copy','0'),('retain_capture','no')]:
            with self.subTest(key=key,value=invalid),self.assertRaises(sc.SpecError):
                self.bundle.validate(schema,dict(value,**{key:invalid}))

    def test_membership_limit_does_not_expand_old_views(self):
        schema='urn:disked:schema:command-image-inspect-parameters:1'
        for view in (None,'map','fat','exfat','ntfs','ntfs-directory'):
            value=dict(path='generated.img',ntfs_target_limit='64')
            if view is not None:value['view']=view
            if view not in (None,'map'):value.update(volume_offset='0',volume_bytes='512')
            with self.subTest(view=view),self.assertRaises(sc.SpecError):self.bundle.validate(schema,value)

if __name__=='__main__':unittest.main()
