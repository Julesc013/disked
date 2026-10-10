"""Native shell tokenizer/model probes. No real console or worker qualification."""
import argparse
import json
import subprocess
import unittest
PARSER=argparse.ArgumentParser()
PARSER.add_argument('--probe',required=True)
ARGS,REST=PARSER.parse_known_args()
def run(*actions):
    p=subprocess.run([ARGS.probe],input=''.join(json.dumps(a,ensure_ascii=True)+'\n' for a in actions),text=True,encoding='utf-8',capture_output=True,timeout=20)
    if p.returncode or p.stderr:raise AssertionError((p.returncode,p.stderr))
    return [json.loads(line) for line in p.stdout.splitlines()]
def key(name,text=None,repeat=False):
    value=dict(op='key',key=name,repeat=repeat)
    if text is not None:value['text']=text
    return value
def submit(line):return [key('text',line),key('f9'),key('f9')]

class Shell(unittest.TestCase):
    def test_literal_quoting_empty_tokens_and_windows_paths(self):
        cases=[('target inspect "fake:alpha@1"',['target','inspect','fake:alpha@1']),
               ("one '' \"\"",['one','','']),('pre"space word"post',['prespace wordpost']),
               ('"a""b"',['a"b']), ("'a''b'",["a'b"]),
               (r'plan simulate fake:complete --state-dir "C:\owned space\state"',['plan','simulate','fake:complete','--state-dir',r'C:\owned space\state']),
               ('$HOME %PATH% ~ \\',['$HOME','%PATH%','~','\\']),('"|&;<>"',['|&;<>'])]
        for line,expected in cases:
            value=run(dict(op='lex',line=line))[0]
            self.assertEqual('',value['error'],value)
            self.assertEqual(expected,[t['value'] for t in value['tokens']])
        for token in ['', 'a b', 'a"b', "a'b", '|', 'é🙂', 'C:\\Space name\\']:
            quoted=run(dict(op='quote',value=token))[0]
            self.assertEqual([token],[t['value'] for t in run(dict(op='lex',line=quoted))[0]['tokens']])

    def test_tokenizer_limits_and_operator_locations(self):
        for line,error,at in [('show | other','shell_operator_unsupported',5),('show "oops','shell_unclosed_quote',5),
                              ('a\nb','shell_control_input',1),('x'*65537,'shell_line_limit',65536),(' '.join(['a']*129),'shell_token_limit',256)]:
            result=run(dict(op='lex',line=line))[0]
            self.assertEqual((error,at),(result['error'],result['byte']))
        for size in (4097,65536):
            result=run(dict(op='lex',line='x'*size))[0]
            self.assertEqual('',result['error']);self.assertEqual('x'*size,result['tokens'][0]['value'])

    def test_review_is_consumed_and_paste_enter_repeat_do_not_dispatch(self):
        results=run(key('text','show fake:alpha@1'),key('enter'),key('text','\nexit\n'),key('f9'),key('f9',repeat=True),
                    dict(op='calls'),key('f9'),dict(op='calls'),key('f9',repeat=True))
        self.assertEqual('show fake:alpha@1',results[2]['editor'])
        self.assertEqual([],results[5])
        self.assertEqual('review',results[4]['view'])
        self.assertEqual(1,len(results[7]))
        self.assertEqual('target.inspect',results[7][0]['command'])
        self.assertEqual('1',results[8]['requests'])
        self.assertEqual('',results[6]['editor'])

    def test_unicode_cursor_editing_preserves_scalar_boundaries(self):
        results=run(key('text','aé🙂z'),key('left'),key('backspace'),key('home'),key('delete'),key('end'),key('text','X'))
        self.assertEqual('aéz',results[2]['editor'])
        self.assertEqual('3',results[2]['cursor'])
        self.assertEqual('ézX',results[-1]['editor'])
        self.assertEqual('4',results[-1]['cursor'])

    def test_syntax_error_keeps_editable_input_and_correction(self):
        results=run(key('text','show'),key('f9'),key('text',' fake:alpha@1'),key('f9'),key('f9'))
        self.assertEqual('show',results[1]['editor'])
        self.assertIn('missing_parameter',results[1]['notice'])
        self.assertEqual('completed',results[-1]['last_outcome']['status'])
        self.assertEqual('fake:alpha@1',results[-1]['last_outcome']['result']['target']['id'])

    def test_completion_is_explicit_insertion_and_cached_target_enum(self):
        result=run(key('text','target li'),key('tab'),dict(op='calls'),key('tab'),dict(op='calls'))
        self.assertEqual(['list'],result[1]['candidates'])
        self.assertEqual('target list',result[3]['editor'])
        self.assertEqual([],result[-1])
        for line,expected in [('show fake:a',['fake:alpha@1']),('plan simulate fake:c',['fake:cancel-checkpoint','fake:complete'])]:
            state=run(key('text',line),key('tab'))[-1]
            self.assertEqual(sorted(expected),state['candidates'])
        state=run(key('text','target list'),key('f9'),key('left'),key('f9'))[-1]
        self.assertEqual('review',state['view'])
        self.assertEqual('0',state['requests'])

    def test_history_opt_in_recall_draft_and_unavailable_exclusion(self):
        results=run(*submit('show fake:alpha@1'),key('up'))
        self.assertEqual([],results[-1]['history'])
        self.assertEqual('',results[-1]['editor'])
        results=run(dict(op='reset',history=True),*submit('show fake:alpha@1'),key('text','draft'),key('up'),key('down'))
        self.assertEqual(['show fake:alpha@1'],results[-1]['history'])
        self.assertEqual('show fake:alpha@1',results[-2]['editor'])
        self.assertEqual('draft',results[-1]['editor'])
        state=run(dict(op='reset',history=True),key('text','partition resize fake:alpha@1 --length 1GiB'),key('f9'))[-1]
        self.assertEqual([],state['history'])
        self.assertIn('command_unavailable',state['notice'])

    def test_history_transcript_bounds_and_linear_publication(self):
        actions=[dict(op='reset',history=True)]
        for i in range(40):actions+=submit('show '+('missing:'+str(i)))
        state=run(*actions)[-1]
        self.assertEqual(32,len(state['history']))
        self.assertLessEqual(len(state['transcript']),64)
        self.assertLessEqual(int(state['transcript_bytes']),262144)
        self.assertGreater(int(state['dropped']),0)
        outputs=run(dict(op='linear'),dict(op='linear'),key('text','sh'),dict(op='linear'))
        self.assertTrue(outputs[0]);self.assertEqual([],outputs[1]);self.assertEqual([],outputs[-1])

    def test_stale_review_and_selection_are_never_rebased(self):
        results=run(key('f3'),key('enter'),key('text','show fake:alpha@1'),key('f9'),dict(op='publish'),key('f9'))
        self.assertEqual('present',results[1]['selection']['state'])
        self.assertEqual('refused',results[-1]['last_outcome']['status'])
        self.assertEqual('revision_conflict',results[-1]['last_outcome']['diagnostics'][0]['code'])
        state=run(key('f3'),key('enter'),dict(op='publish'),key('f4'))[-1]
        self.assertIn('revision_conflict',json.dumps(state['transcript']))
        self.assertEqual('present',state['selection']['state'])

    def test_nested_sessions_and_machine_controls_refused(self):
        for line in ('shell','protocol serve --format=ndjson','show fake:alpha@1 --json','show fake:alpha@1 --gui','show fake:alpha@1 --interactive=no'):
            results=run(key('text',line),key('f9'),dict(op='calls'))
            self.assertEqual('editor',results[1]['view'])
            self.assertEqual([],results[-1])

    def test_exit_alias_and_secret_history(self):
        result=run(*submit('quit'))[-1]
        self.assertTrue(result['done'])
        results=run(dict(op='reset',history=True,secret=True),*submit('show fake:alpha@1'))
        self.assertEqual([],results[-1]['history'])
        self.assertNotIn('fake:alpha@1',json.dumps(results[-1]['transcript']))
        self.assertNotIn('fake:alpha@1',json.dumps(results[-1]))
        self.assertIn('[redacted]',json.dumps(results[-1]['transcript']))

    def test_large_result_reports_display_limit_without_retry_or_lost_session(self):
        results=run(dict(op='reset',large=True),*submit('show fake:alpha@1'),dict(op='calls'),key('text','next'))
        state=results[-1]
        self.assertIn('presentation_unavailable',json.dumps(state['transcript']))
        self.assertEqual('next',state['editor'])
        self.assertEqual('completed',state['last_outcome']['status'])
        self.assertEqual(1,len(results[-2]))
        self.assertLessEqual(int(state['transcript_bytes']),262144)

    def test_screen_focus_and_review_start_are_visible(self):
        frame=dict(op='render',columns=80,rows=25)
        results=run(key('f2'),frame,*[key('down') for _ in range(16)],frame,key('escape'),key('text','show fake:alpha@1'),key('f9'),frame)
        self.assertTrue(any(line.startswith('> build inspect') for line in results[1]))
        self.assertTrue(any(line.startswith('> ') for line in results[-5]))
        self.assertIn('REQUEST REVIEW (inert)',results[-1])
        results=run(key('f3'),key('enter'),frame)
        self.assertTrue(any('disked> [local|"fake:alpha@1"]' in line for line in results[-1]))

if __name__=='__main__':unittest.main(argv=[__file__]+REST)
