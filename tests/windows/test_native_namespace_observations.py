import unittest
import hashlib
import json
from native_namespace_observations import frame,graph,observation,uint,validate


def name(value):return dict(original_encoding='utf16le-code-units',original_hex=value.encode('utf-16-le').hex(),display=value)


def snapshot():
    return dict(api_binding='native-win32-table',capture_epoch='9',status='complete',
        claims=dict(physical_identity='unknown',full_topology='not_observed',media_preservation='not_established',physical_admission=False,mutation_authority=False,complete_alias_proof=False),
        enumeration=dict(state='exhausted',exhausted=True),close=dict(state='closed'),
        records=[dict(volume_path=name('volume'),mounts=dict(state='observed',paths=[name('R:\\')]))])


def observed():
    return dict(schema='org.disked.nt-native-namespace-worker-observation/1',code_sha256='a'*64,
        request_digest='b'*64,worker_epoch='worker:'+32*'c',observer_epoch='observer:'+32*'d',
        worker=dict(pid='10',created='20',observation='exited',exit_code='0'),status='completed',admitted=True,
        claims=dict(live_namespace=True,physical_admission=False,mutation_authority=False,durable_reconnect=False),result=snapshot())


class NativeContainmentObservations(unittest.TestCase):
    def test_graph_label_uses_the_established_properties_object(self):
        def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        payload=dict(name=dict(display='safe'))
        binding=dict(source='namespace')
        props=dict(label='safe',physical_identity='unknown',physical_admission=False,mutation_authority=False,
            identity=None,media_generation=None,capacity_bytes=None,state='unknown',observation_binding=binding,observation=payload)
        row=dict(kind='namespace-volume-observation',properties=props)
        row['id']='observation:'+digest(dict(binding=binding,kind=row['kind'],label='safe',payload=payload))
        value=dict(nodes=[row],edges=[]);value['revision']='sha256:'+digest(value)
        graph(value)

    def test_real_name_and_mount_required(self):
        value=snapshot();frame(value,9,'volume','R:\\')
        value['records'][0]['volume_path']=dict(name('foreign'),display='volume')
        with self.assertRaisesRegex(ValueError,'known_original_volume'):frame(value,9,'volume','R:\\')

    def test_completion_cannot_substitute_for_exit_or_code(self):
        observation(observed(),'a'*64)
        for key,value in [('observation','running'),('pid','0'),('exit_code','259')]:
            bad=observed();bad['worker'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):observation(bad,'a'*64)
        with self.assertRaisesRegex(ValueError,'code_or_schema'):observation(observed(),'e'*64)

    def test_reference_refusal_cannot_be_called_admitted_success(self):
        bad=observed();bad.update(status='unknown',admitted=False,result=None);bad['worker']['exit_code']='3'
        observation(bad,'a'*64,completed=False)
        bad['admitted']=True
        with self.assertRaisesRegex(ValueError,'refused_before_admission'):observation(bad,'a'*64,completed=False)

    def test_boolean_authority_cannot_be_numeric_zero(self):
        value=snapshot();value['claims']['mutation_authority']=0
        with self.assertRaisesRegex(ValueError,'frame_authority'):frame(value,9,'volume','R:\\')

    def test_cancellation_requires_no_search_and_no_records(self):
        value=snapshot();value.update(status='cancelled',records=[],enumeration=dict(state='cancelled'),close=dict(state='not_open'))
        frame(value,9,'volume','R:\\',cancelled=True)
        value['close']['state']='closed'
        with self.assertRaisesRegex(ValueError,'cancel_before_dispatch'):frame(value,9,'volume','R:\\',cancelled=True)

    def test_case_and_integer_domains_are_not_inferred(self):
        with self.assertRaisesRegex(ValueError,'integer_bound'):uint('18446744073709551616')
        with self.assertRaisesRegex(ValueError,'case_identity'):validate(dict(schema='wrong',case='worker.normal',pointer_bytes='8'),'worker.normal',8,'a'*64,'volume','R:\\')


if __name__=='__main__':unittest.main()
