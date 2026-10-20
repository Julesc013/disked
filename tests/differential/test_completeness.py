"""Independent counterexamples for the predeclared differential evidence set."""
import copy
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from compare import compare,read_receipt,write_report


class CompletenessTests(unittest.TestCase):
    def sample(self):
        case=dict(name='control',common_projection=True,sha256='sha256:'+'a'*64,
                  bytes=131072,unit=512,blocks=256)
        expected=[dict(name='control',participant=p,kind=k) for p,k in
                  [('native','native'),('reference','sfdisk-json'),('reference','sfdisk-verify')]]
        rows=[dict(slot=1,start=34,end=61)]
        record=dict(name='control',sha256=case['sha256'],bytes=case['bytes'],unit=512,blocks=256,
                    outcome='exited',exit_code=0,stdout='raw',stderr='')
        native=dict(observations=[dict(record,kind='native',projection=dict(label='gpt',comparison=2,
            candidates=[dict(role='primary',rows=rows),dict(role='backup',rows=[dict(slot=1,start=35,end=61)])]))])
        external=dict(reference=dict(observations=[
            dict(record,kind='sfdisk-json',projection=dict(label='gpt',rows=rows,fields=['slot','start','end'])),
            dict(record,kind='sfdisk-verify',projection=None)]))
        return dict(cases=[case],expected_observations=expected),native,external

    def test_absent_reference_is_not_a_passing_control(self):
        manifest,native,_=self.sample()
        self.assertFalse(compare(manifest,native,{})['adapter_controls_passed'])

    def test_empty_reference_is_not_a_passing_control(self):
        manifest,native,_=self.sample()
        self.assertFalse(compare(manifest,native,dict(reference=dict(observations=[])))['adapter_controls_passed'])

    def test_duplicate_and_wrong_fixture_cannot_pass_matching_projection(self):
        for field,value in [('sha256','sha256:'+'b'*64),('bytes',131071),('unit',4096),('blocks',255)]:
            manifest,native,external=self.sample();external['reference']['observations'][0][field]=value
            with self.subTest(field=field):self.assertFalse(compare(manifest,native,external)['adapter_controls_passed'])
        manifest,native,external=self.sample();external['reference']['observations'].append(copy.deepcopy(external['reference']['observations'][0]))
        self.assertFalse(compare(manifest,native,external)['adapter_controls_passed'])

    def test_diagnostic_only_record_is_required(self):
        manifest,native,external=self.sample();external['reference']['observations'].pop()
        self.assertFalse(compare(manifest,native,external)['adapter_controls_passed'])

    def test_complete_set_does_not_invent_artifact_qualification(self):
        manifest,native,external=self.sample();before=copy.deepcopy((manifest,native,external))
        result=compare(manifest,native,external)
        self.assertEqual(result['set_status'],'complete')
        self.assertTrue(result['adapter_controls_passed'])
        self.assertFalse(result['complete_success'])
        self.assertEqual(result['evidence_status'],'unverified')
        self.assertEqual(result['comparisons'][0]['matching_candidates'],['primary'])
        self.assertEqual(result['comparisons'][0]['native']['comparison'],2)
        self.assertEqual((manifest,native,external),before)

    def test_missing_empty_or_duplicate_declaration_cannot_pass(self):
        for change in ('absent','empty','duplicate'):
            manifest,native,external=self.sample()
            if change=='absent':del manifest['expected_observations']
            elif change=='empty':manifest['expected_observations']=[]
            else:manifest['expected_observations'].append(copy.deepcopy(manifest['expected_observations'][0]))
            with self.subTest(change=change):self.assertFalse(compare(manifest,native,external)['adapter_controls_passed'])

    def test_unknown_records_are_invalid_and_retained(self):
        for field,value in [('name','unknown'),('kind','unknown')]:
            manifest,native,external=self.sample();external['reference']['observations'][0][field]=value
            before=copy.deepcopy(external);result=compare(manifest,native,external)
            with self.subTest(field=field):
                self.assertEqual(result['set_status'],'invalid')
                self.assertFalse(result['adapter_controls_passed'])
                self.assertEqual(result['unvalidated_inputs']['external'],before)
        manifest,native,external=self.sample();external['undeclared']=external.pop('reference')
        self.assertEqual(compare(manifest,native,external)['set_status'],'invalid')

    def test_native_duplicates_cannot_select_a_newer_candidate(self):
        manifest,native,external=self.sample();second=copy.deepcopy(native['observations'][0])
        second['projection']['candidates'].reverse();native['observations'].append(second)
        result=compare(manifest,native,external)
        self.assertEqual(result['set_status'],'invalid');self.assertEqual(result['comparisons'],[])
        self.assertEqual(len(result['unvalidated_inputs']['native']['observations']),2)

    def test_boolean_geometry_and_duplicate_case_are_invalid(self):
        manifest,native,external=self.sample();manifest['cases'][0]['blocks']=True
        self.assertEqual(compare(manifest,native,external)['set_status'],'invalid')
        manifest,native,external=self.sample();manifest['cases'].append(copy.deepcopy(manifest['cases'][0]))
        self.assertEqual(compare(manifest,native,external)['set_status'],'invalid')

    def cli(self,root,*extra,output=None,env=None):
        root=Path(root);manifest,native,external=self.sample()
        for name,value in [('manifest',manifest),('native',native),('reference',external['reference'])]:
            (root/(name+'.json')).write_text(json.dumps(value),encoding='utf-8')
        args=[sys.executable,'-B',str(Path(__file__).with_name('compare.py')),
              '--manifest',str(root/'manifest.json'),'--native',str(root/'native.json'),
              '--external','reference='+str(root/'reference.json'),'--output',str(output or root/'result.json'),*extra]
        return subprocess.run(args,env=env,capture_output=True,timeout=10)

    def test_cli_retains_unverified_result_without_a_success_exit(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as folder:
            result=self.cli(folder)
            self.assertNotEqual(result.returncode,0)
            value=json.loads((Path(folder)/'result.json').read_bytes())
            self.assertTrue(value['adapter_controls_passed'])
            self.assertFalse(value['complete_success'])

    def test_cli_rejects_duplicate_participant_and_preserves_prior_report(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as folder:
            root=Path(folder);report=root/'result.json';report.write_bytes(b'prior evidence')
            result=self.cli(root)
            self.assertNotEqual(result.returncode,0);self.assertEqual(report.read_bytes(),b'prior evidence')
            report.unlink()
            result=self.cli(root,'--external','reference='+str(root/'reference.json'))
            self.assertNotEqual(result.returncode,0);self.assertFalse(report.exists())

    def test_cli_refuses_missing_runner_or_output_outside_declared_root(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as folder:
            root=Path(folder);env=dict(os.environ);env.pop('DISKED_WORK_ROOT',None)
            self.assertNotEqual(self.cli(root,env=env).returncode,0)
            self.assertFalse((root/'result.json').exists())
            inner=root/'inner';inner.mkdir();env['DISKED_WORK_ROOT']=str(inner)
            outside=root/'forbidden.json';result=self.cli(root,output=outside,env=env)
            self.assertNotEqual(result.returncode,0);self.assertFalse(outside.exists())

    def test_obsolete_wsl_recipe_refuses_before_files_or_processes(self):
        path=Path(__file__).with_name('run_wsl_campaign.py')
        spec=importlib.util.spec_from_file_location('suspended_wsl_recipe',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        output=path.resolve().parents[2]/'.aide-local'/'must-not-create'
        argv=[str(path),'--output',str(output),'--mbr-probe','missing','--gpt-probe','missing','--probe-identity','missing']
        with patch.object(sys,'argv',argv),patch.object(Path,'mkdir') as mkdir,patch.object(module.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'suspended'):module.main()
            mkdir.assert_not_called();run.assert_not_called()

    def test_ambiguous_json_and_actual_file_bound_are_refused(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as folder:
            path=Path(folder)/'ambiguous.json';path.write_bytes(b'{"name":"first","name":"second"}')
            with self.assertRaisesRegex(ValueError,'Duplicate JSON'):read_receipt(path)
            path.write_bytes(b'{}')
            with self.assertRaises(ValueError):read_receipt(path,remaining=1)
            for value in (b'NaN',b'Infinity',b'1e999'):
                path.write_bytes(value)
                with self.assertRaisesRegex(ValueError,'Non-finite'):read_receipt(path)
            with path.open('wb') as stream:stream.truncate(8*1024*1024+1)
            with self.assertRaisesRegex(ValueError,'bounded ordinary'):read_receipt(path)

    def test_streamed_report_limit_refuses_before_excess_bytes_are_written(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT')) as folder:
            path=Path(folder)/'report.json'
            size=write_report(path,dict(ok=True),limit=32)
            self.assertEqual(size,path.stat().st_size);self.assertEqual(json.loads(path.read_bytes()),dict(ok=True))
            path.unlink()
            with self.assertRaisesRegex(ValueError,'exceeded'):write_report(path,dict(value='x'*64),limit=32)
            self.assertLessEqual(path.stat().st_size,32)


if __name__=='__main__':unittest.main()
