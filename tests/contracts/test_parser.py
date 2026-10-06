"""Execute the canonical syntax corpus and option-placement invariants natively."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import unittest


class Parser(unittest.TestCase):
    def parse(self, words):
        result=subprocess.run([ARGS.exe],input=json.dumps(words,ensure_ascii=True).encode(),capture_output=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(b'',result.stderr)
        return json.loads(result.stdout)

    def test_shared_syntax_corpus(self):
        value=json.loads((ARGS.root/'spec/fixtures/command-syntax.json').read_text(encoding='utf-8'))
        count=0
        for group in value['groups']:
            for argv in group['equivalent_argv']:
                with self.subTest(group=group['id'],argv=argv):
                    result=self.parse(argv)
                    for key,expected in group['expected'].items():
                        self.assertEqual(expected,result.get(key),result)
                count+=1
        print('Executed canonical native syntax vectors:',count)

    def test_global_option_group_placement(self):
        words=['target','inspect','target:fixture']
        options=[['--format','json'],['--cli'],['--interactive=no']]
        baseline=self.parse([*words,*sum(options,[])])
        for slots in itertools.product(range(4),repeat=3):
            for order in itertools.permutations(range(3)):
                argv=[]
                for position in range(4):
                    for i in order:
                        if slots[i]==position:argv.extend(options[i])
                    if position<3:argv.append(words[position])
                with self.subTest(argv=argv):self.assertEqual(baseline,self.parse(argv))

    def test_quantity_boundaries_and_no_float_rounding(self):
        for quantity in ['1B','50GiB','18446744073709551615B','16777215TiB']:
            value=self.parse(['partition','resize','x','--length',quantity])
            self.assertEqual('command',value['kind'],value)
            self.assertEqual(quantity,value['parameters']['length'])
        for quantity in ['0B','-1B','01B','1.5GiB','18446744073709551616B','16777216TiB','18446744073709551615KiB','1','1GB','']:
            value=self.parse(['partition','resize','x','--length',quantity])
            self.assertEqual('error',value['kind'],value)

    def test_literal_and_consumed_values_are_not_reinterpreted(self):
        for operand in ['--help','--json','list','C:/a path/磁盘.img']:
            value=self.parse(['image','inspect','--',operand])
            self.assertEqual('command',value['kind'],value)
            self.assertEqual([operand],value['operands'])
            self.assertFalse(value['help_requested'])
            self.assertEqual({},value['controls'])
        for words in [['build inspect'],['target','--','list'],['target','list','surplus']]:
            self.assertEqual('error',self.parse(words)['kind'])

    def test_all_conflict_orders_are_refused(self):
        for flags in [['--json','--gui'],['--interactive=yes','--json'],['--tui','--interactive=no'],['--format=human','--json']]:
            for order in [flags,list(reversed(flags))]:
                value=self.parse(['build','inspect',*order])
                self.assertEqual('argument_conflict',value['code'])

    def test_bounds_and_parameter_error_location(self):
        self.assertEqual('argument_limit_exceeded',self.parse(['x']*1025)['code'])
        value=self.parse(['partition','resize','x','--length','0B'])
        self.assertEqual(3,value['diagnostics'][0]['token'])

    def test_static_completion_never_changes_execution_rules(self):
        def complete(words):
            result=subprocess.run([ARGS.exe,'--complete'],input=json.dumps(words).encode(),capture_output=True,timeout=5)
            self.assertEqual(0,result.returncode,result.stderr)
            return json.loads(result.stdout)
        self.assertIn('partition',complete(['part']))
        self.assertEqual(['resize'],complete(['partition','res']))
        self.assertEqual(['--length'],complete(['part','resize','--len']))
        self.assertNotIn('--length',complete(['target','list','--len']))
        self.assertEqual([],complete(['image','inspect','--','--j']))
        self.assertEqual(['--json'],complete(['--j']))
        self.assertEqual('error',self.parse(['partition','res','x'])['kind'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--exe',required=True);p.add_argument('--root',type=Path,required=True);ARGS=p.parse_args()
    unittest.main(argv=[__file__],verbosity=2)
