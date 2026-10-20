"""Independent counterexamples for the predeclared differential evidence set."""
import copy
import unittest

from compare import compare


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


if __name__=='__main__':unittest.main()
