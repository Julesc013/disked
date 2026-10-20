"""A zero exit cannot authorize missing, stale or contradictory test evidence."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_junit',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/full-native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


class ReceiptTests(unittest.TestCase):
    def test_watch_focus_builds_every_registered_command_executable(self):
        tree=ast.parse((ROOT/'.aide/evidence/2026-10-18-ordinary-worker/campaign.py').read_bytes())
        selected=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and
                      isinstance(n.test,ast.Name) and n.test.id=='focus_fat_watch' and
                      any(isinstance(s,ast.Assign) for s in n.body))
        choices={s.targets[0].slice.value:ast.literal_eval(s.value) for s in selected.body
                 if isinstance(s,ast.Assign)}
        cmake=(ROOT/'CMakeLists.txt').read_text(encoding='utf-8')
        for group in choices['focus_groups']:
            command=re.search(r'add_test\(NAME '+re.escape(group)+r' COMMAND (.*?)\)\s*\n',cmake,re.S)
            self.assertIsNotNone(command,group)
            needed=set(re.findall(r'\$<TARGET_FILE:([^>]+)>',command.group(1)))
            self.assertTrue(needed,group)
            self.assertFalse(needed-set(choices['focus_targets']),
                             (group,'missing build targets',needed-set(choices['focus_targets'])))

    def receipt(self,body,code=0):
        with tempfile.TemporaryDirectory(prefix='disked-junit-') as name:
            path=Path(name)/'case.xml'
            if body is not None:path.write_bytes(body)
            return native.junit_result(path,'expected.case',code)

    def test_missing_receipt_cannot_pass_zero_exit(self):
        row=self.receipt(None);self.assertFalse(row['passed']);self.assertEqual('missing',row['reason']);self.assertFalse(row['retain'])

    def test_valid_matching_receipt_requires_zero_exit(self):
        xml=b'<testsuite tests="1" failures="0"><testcase name="expected.case" status="run"/></testsuite>'
        self.assertTrue(self.receipt(xml)['passed']);self.assertFalse(self.receipt(xml,8)['passed'])

    def test_stale_and_duplicate_cases_are_not_substitutes(self):
        for body in (b'<testsuite><testcase name="previous.case"/></testsuite>',
                     b'<testsuite><testcase name="expected.case"/><testcase name="expected.case"/></testsuite>'):
            with self.subTest(body=body):
                row=self.receipt(body);self.assertFalse(row['passed']);self.assertEqual('case_identity',row['reason'])

    def test_failure_error_skip_and_status_relationships(self):
        for outcome in ('failure','error','skipped'):
            xml=('<testsuite><testcase name="expected.case"><'+outcome+'/></testcase></testsuite>').encode()
            with self.subTest(outcome=outcome):self.assertFalse(self.receipt(xml)['passed'])
        self.assertFalse(self.receipt(b'<testsuite><testcase name="expected.case" status="fail"/></testsuite>')['passed'])

    def test_contradictory_suite_counters_are_refused(self):
        for field in ('failures','errors','skipped','disabled','tests'):
            xml=('<testsuite '+field+'="2"><testcase name="expected.case"/></testsuite>').encode()
            with self.subTest(field=field):self.assertFalse(self.receipt(xml)['passed'])

    def test_malformed_and_non_junit_xml_are_retained_as_failures(self):
        for xml in (b'<testsuite',b'<other><testcase name="expected.case"/></other>'):
            row=self.receipt(xml);self.assertFalse(row['passed']);self.assertTrue(row['retain'])

    def test_entity_declarations_are_not_evaluated(self):
        row=self.receipt(b'<!DOCTYPE testsuite [<!ENTITY x "data">]><testsuite><testcase name="expected.case"/></testsuite>')
        self.assertFalse(row['passed']);self.assertEqual('dtd_or_entity_refused',row['reason'])

    def test_empty_receipt_is_a_retained_failure(self):
        row=self.receipt(b'');self.assertFalse(row['passed']);self.assertTrue(row['retain']);self.assertEqual('malformed_xml',row['reason'])

    def test_receipt_byte_bound_is_enforced(self):
        row=self.receipt(b' '*1048577);self.assertFalse(row['passed']);self.assertFalse(row['retain'])


if __name__=='__main__':unittest.main()
