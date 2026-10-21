import unittest
from native_volume_observations import original,validate


def named(value):return dict(original_encoding='utf16le-code-units',original_hex=value.encode('utf-16-le').hex())


def observation():
    return dict(mode='--observe',native_table_bound=True,identity=dict(sid='owned',pid='42',restricted=True,elevated=False,appcontainer=False,in_job=True),
        reuse_refused=True,repeat_close='closed',snapshot=dict(api_binding='native-win32-table',capture_epoch='7',scope='volume-namespace-only',
        claims=dict(physical_identity='unknown',full_topology='not_observed',media_preservation='not_established',physical_admission=False,mutation_authority=False,complete_alias_proof=False),
        status='complete',enumeration=dict(state='exhausted',exhausted=True),close=dict(state='closed'),
        records=[dict(state='present',volume_path=named('known-volume'),mounts=dict(state='observed',paths=[named('R:\\')]))]))


class NativeVolumeObservations(unittest.TestCase):
    def check(self,value):return validate(value,'--observe','owned',42,'known-volume','R:\\')

    def test_exact_known_volume_and_mount(self):
        self.assertTrue(self.check(observation())['known_mount_observed'])

    def test_display_text_cannot_replace_original(self):
        value=observation();value['snapshot']['records'][0]['volume_path']=dict(named('foreign'),display='known-volume')
        with self.assertRaisesRegex(ValueError,'known_volume'):self.check(value)

    def test_wrong_actor_pid_or_unconfined_token(self):
        for key,value in [('sid','other'),('pid','43'),('restricted',False),('elevated',True),('appcontainer',True),('in_job',False)]:
            bad=observation();bad['identity'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'actor'):self.check(bad)

    def test_missing_mount_duplicate_target_and_uncertain_close_refused(self):
        for choice in range(3):
            value=observation()
            if choice==0:value['snapshot']['records'][0]['mounts']['paths']=[]
            if choice==1:value['snapshot']['records']*=2
            if choice==2:value['snapshot']['close']['state']='uncertain'
            with self.subTest(choice=choice),self.assertRaises(ValueError):self.check(value)

    def test_partial_other_mounts_are_not_called_complete(self):
        value=observation();value['snapshot']['status']='partial'
        self.assertFalse(self.check(value)['namespace_complete'])

    def test_lossless_non_display_units(self):
        value='a\x00\ud800\u202e';self.assertEqual(original(dict(original_encoding='utf16le-code-units',original_hex=value.encode('utf-16-le',errors='surrogatepass').hex())),value)


if __name__=='__main__':unittest.main()
