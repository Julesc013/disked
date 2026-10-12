"""FAT command cross-field, numeric, encoding and bounded-query contracts."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import specctl as sc


class FatCommandContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sc.Bundle(Path(__file__).resolve().parents[2])
        cls.uri = sc.SCHEMA_PREFIX + 'command-image-inspect-parameters:1'

    def fat(self, **fields):
        return dict(path='fixture.img', view='fat', volume_offset='0', volume_bytes='1', **fields)

    def reject(self, value):
        with self.assertRaises(sc.SpecError):
            self.bundle.validate(self.uri, value)

    def test_map_defaults_preserve_existing_controls_and_forbid_fat_fields(self):
        for view in ({}, dict(view='map')):
            self.bundle.validate(self.uri, dict(path='fixture.img', logical_block_bytes='4096', **view))
            for key, value in self.fat().items():
                if key not in ('path', 'view'):
                    with self.subTest(view=view, key=key):
                        self.reject(dict(path='fixture.img', **view, **{key:value}))

    def test_fat_requires_explicit_window_and_rejects_map_control(self):
        value = self.fat()
        self.bundle.validate(self.uri, value)
        for key in ('path', 'volume_offset', 'volume_bytes'):
            bad = copy.deepcopy(value); del bad[key]
            self.reject(bad)
        self.reject(dict(value, logical_block_bytes='512'))

    def test_u64_boundaries_canonical_decimal_and_nonzero_length(self):
        value = self.fat(); value['volume_bytes'] = str(sc.U64_MAX)
        self.bundle.validate(self.uri, value)
        for key in ('volume_offset', 'volume_bytes'):
            for n in (str(sc.U64_MAX+1), '01', '-1', '1.0', 1):
                with self.subTest(key=key, n=n):
                    self.reject(dict(value, **{key:n}))
        self.reject(dict(value, volume_bytes='0'))

    def test_window_overflow_and_copy_index_bound(self):
        value = self.fat(fat_copy=str(2**32-1)); value['volume_offset'] = str(sc.U64_MAX-1)
        self.bundle.validate(self.uri, value)
        self.reject(dict(value, volume_offset=str(sc.U64_MAX)))
        self.reject(dict(value, fat_copy=str(2**32)))

    def test_explicit_model_and_capture_local_directory_bounds(self):
        for page in ('437', '850', '932'):
            value = self.fat(name_code_page=page, lookup=dict(directory='127', names=['file']))
            self.bundle.validate(self.uri, value)
        del value['name_code_page']; self.reject(value)
        for directory in ('128', '01', '-1', 0):
            self.reject(self.fat(name_code_page='437', lookup=dict(directory=directory, names=['file'])))
        self.reject(self.fat(name_code_page='1252'))

    def test_utf16_units_are_lossless_and_not_codepoint_count(self):
        for name in ('界'*255, '🙂'*127+'x', 'e\u0301', 'é'):
            self.bundle.validate(self.uri, self.fat(name_code_page='437', lookup=dict(directory='0', names=[name])))
        for name in ('🙂'*128, '\ud800', '', 'a\0b'):
            with self.subTest(name=repr(name)):
                self.reject(self.fat(name_code_page='437', lookup=dict(directory='0', names=[name])))

    def test_lookup_count_byte_budget_and_unknown_fields(self):
        value = self.fat(name_code_page='437', lookup=dict(directory='0', names=['x']*16))
        self.bundle.validate(self.uri, value)
        # UTF-16/count bounds already keep valid UTF-8 queries under the byte cap.
        self.bundle.validate(self.uri, dict(value, lookup=dict(directory='0', names=['界'*255]*16)))
        for names in ([], ['x']*17):
            self.reject(dict(value, lookup=dict(directory='0', names=names)))
        self.reject(dict(value, lookup=dict(directory='0', names=['x'], target='other')))
        self.reject(dict(value, arbitrary='x'))

    def test_flags_are_explicit_enums_and_table_verify_schema_stays_separate(self):
        self.bundle.validate(self.uri, self.fat(allocation_scan='yes', auxiliary_checks='no'))
        for key in ('allocation_scan', 'auxiliary_checks'):
            for flag in ('true', True, 'YES'):
                self.reject(self.fat(**{key:flag}))
        self.bundle.validate(sc.SCHEMA_PREFIX+'command-image-path-parameters:1', dict(path='fixture.img', logical_block_bytes='512'))
        with self.assertRaises(sc.SpecError):
            self.bundle.validate(sc.SCHEMA_PREFIX+'command-image-path-parameters:1', self.fat())
