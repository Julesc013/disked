"""Native bounded-channel behavior, including malformed and late callbacks."""
import argparse,json,subprocess,unittest
P=argparse.ArgumentParser();P.add_argument('--probe',required=True);ARGS,REST=P.parse_known_args()
class Channel(unittest.TestCase):
    def test_bounded_owned_callback_and_exact_completion(self):
        p=subprocess.run([ARGS.probe],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('',p.stderr)
        v=json.loads(p.stdout);self.assertTrue(v['one_call_one_completion']);self.assertTrue(v['callback_owned_lifetime'])
        self.assertEqual(5,v['invalid_completions_unknown']);self.assertLess(v['disconnected_owner_ms'],250)
        self.assertTrue(v['allocation_failure_receipt_preallocated'])
        self.assertTrue(v['explicit_finite_response_bound'])
        self.assertTrue(v['unknown_preserves_routing_and_observed_id'])
        self.assertTrue(v['timed_slot_retained_until_completion'])
        self.assertTrue(v['synthetic_joined_envelope_channel_frame_render_closure'])
        self.assertTrue(v['synthetic_joined_overflow_keeps_routing'])
        print(json.dumps(v))
if __name__=='__main__':unittest.main(argv=[__file__]+REST)
