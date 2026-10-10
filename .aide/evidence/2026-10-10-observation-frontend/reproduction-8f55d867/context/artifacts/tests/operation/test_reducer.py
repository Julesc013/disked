"""Independent transition/history probes for private, fake-only operation evidence."""
import argparse
import copy
import hashlib
import json
import subprocess
import unittest

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--probe', required=True)
ARGS, REST = PARSER.parse_known_args()

def binding(fixture='fake:complete'):
    ident = 'fake-op:' + '1' * 32
    return dict(operation_id=ident, attempt_id=ident + ':attempt:1',
                worker_epoch='worker:' + '2' * 32, fixture_id=fixture,
                host_id='3' * 64, source_revision='4' * 40, input_digest='sha256:' + '5' * 64,
                image_digest='6' * 64, process_id='123', process_created='456',
                provider_id='provider.fake.bootstrap/1', target_profile='windows.nt10.x64.win32')

def native_bytes(value):
    # These records contain only ASCII strings/null/object. Keep an independent
    # encoder and hash implementation so a writer/reader shared bug is visible.
    if value is None:
        return 'null'
    if isinstance(value, str):
        return '"' + ''.join('\\u%04x' % ord(c) if ord(c) < 32 else
                            '\\' + c if c in '\\"' else c for c in value) + '"'
    return '{' + ','.join(native_bytes(k) + ':' + native_bytes(value[k]) for k in sorted(value)) + '}'

def chain(states):
    previous = '0' * 64
    lines = []
    for state in states:
        record = dict(schema='org.disked.fake-operation-record/1', state=state, previous=previous)
        previous = hashlib.sha256(native_bytes(record).encode()).hexdigest()
        record['digest'] = previous
        lines.append(native_bytes(record))
    return '\n'.join(lines) + '\n'

def run(*actions):
    process = subprocess.run([ARGS.probe], input=''.join(json.dumps(a) + '\n' for a in actions),
                             text=True, capture_output=True, timeout=10)
    if process.returncode or process.stderr:
        raise AssertionError((process.returncode, process.stderr))
    return [json.loads(s) for s in process.stdout.splitlines()]

START = dict(action='start', binding=binding())
NORMAL = [START, dict(action='prepare'), dict(action='dispatch'),
          dict(action='observe', count='1'), dict(action='verify')]

class Reducer(unittest.TestCase):
    def test_success_and_independent_hashes(self):
        results = run(*NORMAL, dict(action='history'))
        self.assertEqual(chain(results[:-1]), results[-1])
        final = results[-2]
        self.assertEqual(('finished', 'completed', 'observed', 'succeeded', '1', '5'),
                         tuple(final[k] for k in ('phase', 'logical_state', 'effect_certainty',
                                                 'outcome', 'synthetic_effect_count', 'sequence')))
        self.assertEqual(final, run(dict(action='read', bytes=results[-1]))[0])

    def test_wrong_epoch_cannot_advance_or_cancel(self):
        for key in ('operation_id', 'attempt_id', 'worker_epoch'):
            for action in ('prepare', 'cancel', 'checkpoint'):
                origin = {k: binding()[k] for k in ('operation_id', 'attempt_id', 'worker_epoch')}
                origin[key] += ':late'
                initial, rejected = run(START, dict(action=action, origin=origin))
                self.assertEqual('operation_epoch_mismatch', rejected['error'])
                self.assertEqual(initial, rejected['retained'])

    def test_guards_and_observed_counter(self):
        initial, refused = run(START, dict(action='verify'))
        self.assertEqual('operation_transition_refused', refused['error'])
        self.assertEqual(initial, refused['retained'])
        results = run(*NORMAL[:3], dict(action='observe', count='0'), dict(action='observe', count='2'))
        for result in results[-2:]:
            self.assertEqual('operation_observation_refused', result['error'])
            self.assertEqual(results[2], result['retained'])

    def test_cancel_before_dispatch_is_checkpointed(self):
        results = run(START, dict(action='prepare'), dict(action='cancel'), dict(action='cancel'),
                      dict(action='dispatch'), dict(action='checkpoint'), dict(action='cancel'))
        self.assertEqual(results[2], results[3])
        self.assertEqual('operation_checkpoint_required', results[4]['error'])
        self.assertEqual(('acknowledged', 'cancelled', 'not_started', '0'),
                         tuple(results[-1][k] for k in ('cancellation', 'outcome', 'effect_certainty', 'synthetic_effect_count')))
        self.assertEqual(results[-1], results[-2])

    def test_cancel_after_dispatch_does_not_erase_effect(self):
        results = run(*NORMAL[:3], dict(action='cancel'), dict(action='checkpoint'), *NORMAL[3:])
        self.assertEqual(results[3], results[4])
        self.assertEqual(('requested', 'succeeded', 'observed', '1'),
                         tuple(results[-1][k] for k in ('cancellation', 'outcome', 'effect_certainty', 'synthetic_effect_count')))

    def test_verification_failure_is_separate_from_effect(self):
        actions = copy.deepcopy(NORMAL)
        actions[0]['binding']['fixture_id'] = 'fake:verification-failure'
        final = run(*actions)[-1]
        self.assertEqual(('unresolved', 'required', 'verification_failed', 'observed'),
                         tuple(final[k] for k in ('logical_state', 'recovery', 'outcome', 'effect_certainty')))

    def test_corruption_partial_tail_and_forged_consistency(self):
        states = run(*NORMAL)
        encoded = chain(states)
        for invalid, error in ((encoded[:-1], 'operation_history_partial'),
                               (encoded.replace('fake-only', 'fake-mess', 1), 'operation_digest_mismatch'),
                               ('', 'operation_history_empty')):
            self.assertEqual(error, run(dict(action='read', bytes=invalid))[0]['error'])
        for key, value in (('sequence', '18446744073709551616'), ('cancellation', 'acknowledged'),
                           ('effect_certainty', 'not_started'), ('outcome', 'cancelled')):
            forged = copy.deepcopy(states)
            forged[-1][key] = value
            self.assertEqual('operation_state_mismatch', run(dict(action='read', bytes=chain(forged)))[0]['error'])

    def test_forged_late_binding_duplicate_and_skipped_transition(self):
        states = run(*NORMAL)
        forged = copy.deepcopy(states)
        forged[-1]['binding']['worker_epoch'] = 'worker:' + 'f' * 32
        self.assertEqual('operation_state_mismatch', run(dict(action='read', bytes=chain(forged)))[0]['error'])
        self.assertIn('error', run(dict(action='read', bytes=chain([states[0], states[-1]])))[0])
        self.assertIn('error', run(dict(action='read', bytes=chain(states + [states[-1]])))[0])

    def test_binding_rejects_unsupported_fixture_and_process(self):
        for key, value in (('fixture_id', 'physical:0'), ('process_id', '4294967296'),
                           ('process_created', '18446744073709551616'), ('operation_id', 'fake-op:../escape')):
            invalid = binding()
            invalid[key] = value
            self.assertIn('error', run(dict(action='start', binding=invalid))[0])

if __name__ == '__main__':
    unittest.main(argv=[__file__] + REST)
