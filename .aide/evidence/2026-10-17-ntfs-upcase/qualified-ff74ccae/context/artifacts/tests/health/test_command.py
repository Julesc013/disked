"""Independent product/protocol/frontend checks for compiled fake health only."""
import argparse
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

OBSERVATIONS=[]
def encode(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def sha(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
def request(parameters,revision=None):
    value=dict(schema='org.disked.request/1',request_id='health-test',command='health.assess',parameters=parameters,required_features=[])
    if revision is not None:value['expected_revision']=revision
    return value
def report(value):return value['result']['support_report']
def source(value):return report(value)['sources'][0]
def flags(values):return dict(zip(('include_identifiers','include_raw','include_interpretations','include_customer_data'),values))

class HealthCommand(unittest.TestCase):
    def launch(self,argv,data=b'',code=0,guard=False):
        with tempfile.TemporaryDirectory(prefix='disked-health-') as directory:
            env={k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ}
            env.update(PATH=str(Path(os.environ['SystemRoot'])/'System32'),TEMP=directory,TMP=directory)
            run=subprocess.run([str(ARGS.guard if guard else ARGS.exe),*argv],input=data,capture_output=True,cwd=directory,env=env,timeout=15)
            self.assertEqual(code,run.returncode,run.stdout+run.stderr);self.assertEqual(b'',run.stderr);self.assertEqual([],list(Path(directory).iterdir()))
            OBSERVATIONS.append(dict(argv=argv,exit_code=run.returncode,stdout_sha256=sha(run.stdout),no_created_files=True,guard=guard))
            return run.stdout
    def cli(self,target,parameters=None,code=0):
        argv=['health','assess',target,'--json']
        for key,value in (parameters or {}).items():
            if value:argv.append('--'+key.replace('_','-'))
        value=json.loads(self.launch(argv,code=code));value['request_id']='health-test';return value
    def wire(self,parameters,revision=None,code=0,guard=False):return json.loads(self.launch(['protocol','serve','--json'],encode(request(parameters,revision)),code,guard))
    def probe(self,path,messages,argv=()):
        run=subprocess.run([str(path),*argv],input=b'\n'.join(encode(m) for m in messages)+b'\n',capture_output=True,timeout=15)
        self.assertEqual(0,run.returncode,run.stdout+run.stderr);self.assertEqual(b'',run.stderr)
        result=[json.loads(line) for line in run.stdout.splitlines()];self.assertEqual(len(messages),len(result))
        for value in result:
            if isinstance(value,dict):self.assertNotIn('error',value)
        return result
    def service(self,target,parameters=None,revision=''):
        return self.probe(ARGS.service,[dict(op='dispatch',command='health.assess',parameters=dict(target_id=target,**(parameters or {})),revision=revision)])[0]
    def normalize(self,value):value=copy.deepcopy(value);value['request_id']='health-test';return value
    def test_known_fixture_content_and_cloned_serial_binding(self):
        values=[]
        for target,temp,errors in [('fake:alpha@1',35,0),('fake:clone@1',42,3)]:
            p=flags((True,True,True,True));value=self.cli(target,p);self.assertEqual(value,self.wire(dict(target_id=target,**p)));self.assertEqual(value,self.normalize(self.service(target,p)))
            self.assertEqual('compiled-fixture',value['result']['observation_kind']);self.assertIsNone(value['result']['observed_at']);self.assertEqual('fake-only',value['result']['scope'])
            self.assertEqual('complete',report(value)['state']);self.assertFalse(source(value)['worker_outstanding']);self.assertFalse(source(value)['request_open'])
            f=source(value)['fields'];self.assertEqual(f'{temp:02x}',f[0]['raw']['hex']);self.assertEqual(f'{temp} Celsius',f[0]['interpretation']['text']);self.assertEqual('fixture.celsius@1',f[0]['interpretation']['rule_id'])
            self.assertEqual(f'{errors:02x}',f[1]['raw']['hex']);self.assertEqual(f'{errors} media errors',f[1]['interpretation']['text']);self.assertEqual('CLONED',f[2]['interpretation']['text']);values.append(value)
        self.assertNotEqual(report(values[0])['target']['identity_digest'],report(values[1])['target']['identity_digest'])
        profile=json.loads((ARGS.root/'spec/catalog/fake-health-command.json').read_bytes())
        for value in values:
            target=value['result']['target_id'];fixture=profile['fixtures'][target]
            binding=dict(id=target,identity=fixture['identity'],generation='1')
            self.assertEqual(sha(encode(binding)),report(value)['target']['identity_digest'])
            self.assertEqual(sha(b'provider.fake.health.fixture/1'),source(value)['provider_digest']);self.assertEqual(set(profile['result_fields']),set(value['result']))
    def test_default_support_payload_has_no_content_or_identifiers(self):
        value=self.cli('fake:alpha@1');r=report(value)
        self.assertEqual(dict(identifiers=False,raw_values=False,interpretations=False,customer_data=False),r['policy'])
        for absent in (b'fake:',b'sha256:',b'CLONED',b'Workshop',b'fixture-',b'"rule_id"',b'"hex"'):self.assertNotIn(absent,encode(r))
        self.assertNotIn('target',r);self.assertNotIn('id',source(value));self.assertEqual('not_established',r['claims']['reliability']);self.assertFalse(r['claims']['mutation_authority']);self.assertFalse(r['claims']['physical_admission'])
        self.assertEqual('fake:alpha@1',value['result']['target_id']) # The surrounding routing envelope is explicitly not redacted.
    def test_all_disclosure_combinations_are_independent_and_secrets_omitted(self):
        for values in itertools.product((False,True),repeat=4):
            identifiers,raw,interpretations,customer=values;p=flags(values);value=self.wire(dict(target_id='fake:alpha@1',**p));self.assertEqual(value,self.cli('fake:alpha@1',p))
            r=report(value);f=source(value)['fields'];self.assertEqual(identifiers,'target' in r)
            for i in range(5):
                allowed=i<2 or i==2 and identifiers or i==3 and customer
                self.assertEqual(bool(allowed and raw),'raw' in f[i]);self.assertEqual(bool(allowed and interpretations),'interpretation' in f[i]);self.assertEqual(bool(allowed and identifiers),'id' in f[i])
            self.assertNotIn(b'fixture-secret',encode(r));self.assertNotIn(b'"debug"',encode(r))
    def test_unknown_and_unavailable_never_substitute_zero(self):
        for target,state,source_state in [('fake:unknown@1','partial','partial'),('fake:table@1','partial','unavailable'),('fake:volume@1','partial','unavailable')]:
            value=self.wire(dict(target_id=target,**flags((True,True,True,True))));self.assertEqual('completed',value['status']);self.assertEqual(state,report(value)['state']);self.assertEqual(source_state,source(value)['state'])
            self.assertFalse(source(value)['worker_outstanding']);self.assertEqual('0' if source_state=='unavailable' else '1',source(value)['worker'])
            for f in source(value)['fields']:
                self.assertFalse(f['received']);self.assertEqual('unknown',f['raw_availability']);self.assertEqual('unknown',f['interpretation_availability'])
                if 'raw' in f:self.assertIsNone(f['raw']['hex'])
                if 'interpretation' in f:self.assertIsNone(f['interpretation']['text'])
            self.assertEqual('not_established',report(value)['claims']['reliability'])
    def test_denied_stale_alias_and_physical_path_refusals(self):
        for target,diagnostic,code in [('fake:denied@1','health_observation_denied',3),('fake:stale@1','health_observation_stale',2),('fake:serial/CLONED','target_not_found',2),('0','target_not_found',2),('\\\\.\\PhysicalDrive0','target_not_found',2),('fake:removed@1','target_not_found',2)]:
            value=self.wire(dict(target_id=target),code=code);self.assertEqual(diagnostic,value['diagnostics'][0]['code']);self.assertIsNone(value['result']);self.assertEqual(value,self.cli(target,code=code));self.assertEqual(value,self.normalize(self.service(target)))
    def test_revision_and_target_removal_reject_before_collection(self):
        graph=json.loads(self.launch(['topology','show','--json']))['result'];revision=graph['revision']
        self.assertEqual(revision,self.wire(dict(target_id='fake:alpha@1'),revision)['result']['basis_revision'])
        value=self.wire(dict(target_id='fake:alpha@1'),'sha256:'+'0'*64,2);self.assertEqual('revision_conflict',value['diagnostics'][0]['code']);self.assertIsNone(value['result'])
        changed=copy.deepcopy(graph);changed['nodes']=[n for n in graph['nodes'] if n['id']!='fake:alpha@1'];changed['edges']=[e for e in graph['edges'] if e['from']!='fake:alpha@1' and e['to']!='fake:alpha@1']
        q=dict(op='dispatch',command='health.assess',parameters=dict(target_id='fake:alpha@1'),revision=revision)
        out=self.probe(ARGS.service,[dict(op='publish',graph=changed),q,dict(q,revision='')]);self.assertEqual('revision_conflict',out[1]['diagnostics'][0]['code']);self.assertEqual('target_not_found',out[2]['diagnostics'][0]['code'])
    def test_invalid_parameters_are_static_with_poisoned_provider(self):
        for p in [{},{'target_id':''},{'target_id':3},{'target_id':'fake:alpha@1','include_raw':'yes'},{'target_id':'fake:alpha@1','force':True},{'target_id':'fake:alpha@1','self_test':True},{'target_id':'fake:alpha@1','output':'unexpected.json'}]:
            value=self.wire(p,code=2,guard=True);self.assertEqual('refused',value['status']);self.assertIsNone(value['result'])
        for argv in [['health','assess','--json'],['health','assess','fake:alpha@1','--deep','--json'],['health','assess','fake:alpha@1','--include-raw=yes','--json']]:self.launch(argv,code=2,guard=True)
    def test_unknown_fixture_or_missing_port_is_unavailable(self):
        graph=self.probe(ARGS.service,[dict(op='query')])[0];changed=copy.deepcopy(graph);node=copy.deepcopy(changed['nodes'][0]);node['id']='fake:new@1';node['properties']['identity']='fixture:new';changed['nodes'].append(node)
        q=dict(op='dispatch',command='health.assess',parameters=dict(target_id='fake:new@1'),revision='')
        self.assertEqual('health_observer_unavailable',self.probe(ARGS.service,[dict(op='publish',graph=changed),q])[-1]['diagnostics'][0]['code'])
        q['parameters']['target_id']='fake:alpha@1';self.assertEqual('health_observer_unavailable',self.probe(ARGS.service,[q],['--no-health'])[-1]['diagnostics'][0]['code'])
        graph['nodes'][0]['kind']='gpt'
        self.assertEqual('health_observer_unavailable',self.probe(ARGS.service,[dict(op='publish',graph=graph),q])[-1]['diagnostics'][0]['code'])
    def test_ndjson_refusal_does_not_stop_later_health_requests(self):
        requests=[request(dict(target_id='fake:stale@1')),request(dict(target_id='fake:unknown@1')),request(dict(target_id='fake:alpha@1'))]
        output=self.launch(['protocol','serve','--format=ndjson'],b'\n'.join(encode(r) for r in requests),2)
        values=[json.loads(line) for line in output.splitlines()];self.assertEqual(3,len(values))
        self.assertEqual('health_observation_stale',values[0]['diagnostics'][0]['code']);self.assertEqual('partial',report(values[1])['state']);self.assertEqual('complete',report(values[2])['state'])
    def test_port_presence_does_not_authorize_target_health_or_mutation(self):
        value=json.loads(self.launch(['capability','explain','fake:table@1','health.assess','--json']))['result']['assessment']
        self.assertEqual('unknown',value['checks']['provider']);self.assertEqual('unknown',value['checks']['qualification']);self.assertFalse(value['execution_eligible']);self.assertFalse(value['authorizes_execution'])
    def test_control_text_and_independent_label_byte_limits(self):
        p=flags((True,True,True,True));q=dict(op='dispatch',command='health.assess',parameters=dict(target_id='fake:alpha@1',**p),revision='')
        for label,raw_ok,text_ok in [('owned\x1b[31m\x00\n\u202e\U0001f4be',True,True),('x'*256,True,True),('x'*257,True,False),('x'*1024,True,False),('x'*1025,False,False),('\u78c1'*86,True,False)]:
            # Graph labels prohibit NUL; control presentation can still be tested losslessly via ESC/newline/bidi.
            label=label.replace('\x00','');graph=self.probe(ARGS.service,[dict(op='query')])[0];graph['nodes'][0]['properties']['label']=label
            value=self.probe(ARGS.service,[dict(op='publish',graph=graph),q])[-1];f=source(value)['fields'][3]
            self.assertEqual(label.encode().hex() if raw_ok else None,f['raw']['hex']);self.assertEqual(label if text_ok else None,f['interpretation']['text'])
            self.assertEqual('available' if raw_ok else 'error',f['raw_availability']);self.assertEqual('available' if text_ok else 'error',f['interpretation_availability'])
            ascii_value=self.probe(ARGS.service,[dict(op='display',value=value)])[0];self.assertTrue(ascii_value.isascii());self.assertNotIn('\x1b',ascii_value);self.assertEqual(value,json.loads(ascii_value))
    def test_gui_tui_shell_use_shared_results_and_revision_review(self):
        p=dict(target_id='fake:clone@1',**flags((True,True,True,False)));expected=self.wire(p)
        gui=self.probe(ARGS.gui,[dict(op='stage',command='health.assess',parameters=p),dict(op='review'),dict(op='submit')])[-1]
        tui=self.probe(ARGS.tui,[dict(op='stage',command='health.assess',parameters=p),dict(op='key',key='f9'),dict(op='key',key='f9')])[-1]
        for value in (gui,tui):self.assertEqual(expected,self.normalize(value['state']['last_outcome']))
        self.assertTrue(gui['rendered'].isascii())
        shell=self.probe(ARGS.shell,[dict(op='key',key='text',text='health assess fake:clone@1 --include-identifiers --include-raw --include-interpretations'),dict(op='key',key='f9'),dict(op='key',key='f9')])[-1]
        self.assertEqual(expected,self.normalize(shell['last_outcome']))
        for path,review,submit in [(ARGS.gui,dict(op='review'),dict(op='submit')),(ARGS.tui,dict(op='key',key='f9'),dict(op='key',key='f9'))]:
            value=self.probe(path,[dict(op='stage',command='health.assess',parameters=p),review,dict(op='publish'),submit])[-1]['state']['last_outcome']
            self.assertEqual('revision_conflict',value['diagnostics'][0]['code']);self.assertIsNone(value['result'])
    def test_discovery_and_help_are_static_and_truthful(self):
        value=json.loads(self.launch(['command','list','--json'],guard=True));command=next(c for c in value['result']['commands'] if c['id']=='health.assess')
        self.assertEqual('available',command['availability']);self.assertEqual('compiled_fake_health_fixtures_only',command['reason']);self.assertEqual('planned',command['contract_status'])
        value=json.loads(self.launch(['health','assess','--help','--json'],guard=True));self.assertEqual(['health.assess'],[c['id'] for c in value['result']['commands']])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('exe','guard','service','gui','tui','shell','root'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--evidence',type=Path);ARGS=p.parse_args();ARGS.root=ARGS.root.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HealthCommand))
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,product_launches=len(OBSERVATIONS),observations=OBSERVATIONS,physical_io=False,self_tests=False,created_support_files=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
