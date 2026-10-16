"""Offline schema ownership, pointer binding and missing-dependency checks."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
MODULE=importlib.util.spec_from_file_location('disked_bootstrap_generator',ROOT/'tools/build-bootstrap.py')
generator=importlib.util.module_from_spec(MODULE);MODULE.loader.exec_module(generator)

class ClosureTests(unittest.TestCase):
    def closure(self,schemas,selected,inputs=('a.json','b.json')):
        return generator.parameter_schema_closure({key:(value,ROOT/path) for key,(value,path) in schemas.items()},selected,inputs,ROOT)
    def test_local_pointers_keep_their_owners_across_external_refs(self):
        a={'$ref':'#/$defs/item','$defs':{'item':{'type':'object','properties':{'other':{'$ref':'urn:b'}}}}}
        b={'$ref':'#/$defs/item','$defs':{'item':{'const':'different owner'}}}
        result=self.closure({'urn:a':(a,'a.json'),'urn:b':(b,'b.json')},['urn:a'])
        self.assertEqual(result['urn:a']['$ref'],'urn:a#/$defs/item')
        self.assertEqual(result['urn:b']['$ref'],'urn:b#/$defs/item')
        self.assertEqual(result['urn:b#/$defs/item'],{'const':'different owner'})
        self.assertEqual(a['$ref'],'#/$defs/item')
    def test_escaped_pointer_and_closed_cycle(self):
        a={'$defs':{'x/y~z':{'$ref':'urn:a#/$defs/x~1y~0z'}}}
        result=self.closure({'urn:a':(a,'a.json')},['urn:a#/$defs/x~1y~0z'])
        self.assertEqual(list(result),['urn:a#/$defs/x~1y~0z'])
    def test_missing_artifact_pointer_and_unsupported_anchor_fail_closed(self):
        a={'$ref':'urn:b'};b={'type':'string'}
        with self.assertRaisesRegex(ValueError,'build input closure'):
            self.closure({'urn:a':(a,'a.json'),'urn:b':(b,'b.json')},['urn:a'],('a.json',))
        for reference in ('urn:missing','urn:a#/$defs/no','urn:a#anchor','urn:a#/~2'):
            with self.subTest(reference=reference),self.assertRaises(ValueError):self.closure({'urn:a':(a,'a.json')},[reference])
