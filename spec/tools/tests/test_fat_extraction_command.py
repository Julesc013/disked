"""Logical selectors/definitions enforce cross-field identity and version separation."""
import copy,json
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from specctl import Bundle,SpecError
import test_logical_acquisition as logical_fixture

class ExtractionCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=Bundle()
    def definition(self):
        plan=logical_fixture.LogicalAcquisitionTests().value()
        return dict(schema='org.disked.acquisition-worker-definition/2',plan=plan,
            request=dict(source='source.img',destination='destination.bin',map='copy.map',resume=False,explicit_options=True,
                         logical_source=copy.deepcopy(plan['logical_source']),**{k:plan[k] for k in ('chunk_bytes','retry_limit','read_policy','substitution')}),
            store=dict(path='state',generation=dict(volume_id='1',file_id='a'*32,created='1'),access='create-owned-metadata',
                       children=['acquisition.request','acquisition.records','acquisition.cancel','acquisition.admission'],failure_domain='fixture'),
            host_id='a'*64,image_digest='b'*64,source_revision='c'*40,input_digest='sha256:'+'d'*64,target_profile='windows.nt10.x64.win32')
    def test_exact_logical_definition_and_raw_version_separation(self):
        d=self.definition();self.bundle.validate('urn:disked:schema:acquisition-worker-definition:2',d)
        with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:acquisition-worker-definition:1',d)
        for path,value in [(('request','logical_source','node_id'),'0'),(('request','chunk_bytes'),'65536'),(('plan','logical_source','expected_file_bytes'),'21')]:
            bad=copy.deepcopy(d);at=bad
            for k in path[:-1]:at=at[k]
            at[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:acquisition-worker-definition:2',bad)
    def test_selector_quantity_and_window_bounds_by_schema_identity(self):
        s=self.definition()['request']['logical_source'];self.bundle.validate('urn:disked:schema:fat-file-selector:1',s)
        for key,v in [('volume_offset','18446744073709551616'),('volume_bytes','511'),('fat_copy','16'),('node_id','128'),('expected_file_bytes','4294967296')]:
            bad={**s,key:v}
            with self.subTest(key=key),self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:fat-file-selector:1',bad)
    def test_phase_effects_and_selector_controls_cannot_mix(self):
        p=dict(phase='prepare',source='a',destination='b',map='c',state_directory='d',logical_source=self.definition()['request']['logical_source'])
        self.bundle.validate('urn:disked:schema:fat-extraction-command-parameters:1',p)
        for bad in [{**p,'allow_source_read':True},{**p,'retry_limit':'1'},{**p,'substitution':'zero-fill'}]:
            with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:fat-extraction-command-parameters:1',bad)
