"""Native shared-service acceptance: actual mutation of private fake fixtures only."""
import argparse
import copy
import hashlib
import json
import random
import subprocess
import unittest
from pathlib import Path


def revision_bytes(value):
    # Independent implementation of DE-023's explicit private encoding;
    # Python's default short control escapes are not this encoding.
    if value is None:return b'null'
    if isinstance(value,str):
        text='"'+''.join('\\"' if c=='"' else '\\\\' if c=='\\' else f'\\u{ord(c):04x}' if ord(c)<32 else c for c in value)+'"'
        return text.encode('utf-8')
    if isinstance(value,list):return b'['+b','.join(revision_bytes(v) for v in value)+b']'
    if isinstance(value,dict):return b'{'+b','.join(revision_bytes(k)+b':'+revision_bytes(value[k]) for k in sorted(value))+b'}'
    raise AssertionError('Unexpected type in private fake graph profile')


class Service(unittest.TestCase):
    def setUp(self):
        self.process=subprocess.Popen([str(ARGS.probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.initial=self.call(op='query')

    def tearDown(self):
        self.process.stdin.close()
        try:self.assertEqual(0,self.process.wait(timeout=5));self.assertEqual(b'',self.process.stderr.read())
        finally:
            if self.process.poll() is None:self.process.kill();self.process.wait()
            self.process.stdout.close();self.process.stderr.close()

    def call(self,**value):
        self.process.stdin.write(json.dumps(value,ensure_ascii=True,separators=(',',':')).encode()+b'\n');self.process.stdin.flush()
        return json.loads(self.process.stdout.readline())

    def action(self,kind,target='',revision=None):
        return self.call(op='act',kind=kind,target=target,revision=self.initial['revision'] if revision is None else revision)

    def error(self,value,code):
        self.assertEqual('refused',value['status']);self.assertEqual(code,value['diagnostics'][0]['code'])

    def test_initial_partial_graph_cycles_clones_and_revision(self):
        graph=self.initial;self.assertEqual('fake:1',graph['capture_id'])
        self.assertEqual(7,len(graph['nodes']));self.assertEqual(3,len(graph['omissions']))
        self.assertEqual({'current','denied','stale','unknown'},{n['properties']['state'] for n in graph['nodes']})
        a,b=graph['nodes'][:2];self.assertEqual(a['properties']['label'],b['properties']['label'])
        self.assertNotEqual(a['id'],b['id']);self.assertNotEqual(a['properties']['identity'],b['properties']['identity'])
        self.assertEqual(a['properties']['aliases'][1],b['properties']['aliases'][1])
        unsigned={k:v for k,v in graph.items() if k!='revision'}
        self.assertEqual('sha256:'+hashlib.sha256(revision_bytes(unsigned)).hexdigest(),graph['revision'])
        # A three-edge cycle and a second parent remain present.
        self.assertEqual(4,len(graph['edges']))
        for label in ['quote" slash/ backslash\\','\b\f\n\r\t', '磁盘💾\x1b\x01\x7f\x9b', '']:
            changed=copy.deepcopy(graph);changed['nodes'][0]['properties']['label']=label
            newer=self.call(op='publish',graph=changed);unsigned={k:v for k,v in newer.items() if k!='revision'}
            self.assertEqual('sha256:'+hashlib.sha256(revision_bytes(unsigned)).hexdigest(),newer['revision'])

    def test_retained_snapshot_refresh_epoch_and_stale_actions(self):
        selected=self.initial['nodes'][0]['id']
        self.assertEqual('completed',self.action('select',selected)['status'])
        newer=self.call(op='publish',graph=self.initial)
        self.assertNotEqual(self.initial['revision'],newer['revision']);self.assertEqual('fake:2',newer['capture_id'])
        self.assertEqual(self.initial,self.call(op='retained',index='0'))
        for kind in ['inspect','select','clear']:
            self.error(self.action(kind,selected if kind!='clear' else ''),'revision_conflict')
        self.assertEqual(dict(target_id=selected,state='present'),self.call(op='selection'))
        self.error(self.action('inspect',selected,revision=''),'revision_conflict')
        self.assertEqual('completed',self.action('clear',revision=newer['revision'])['status'])
        self.assertEqual(dict(target_id=None,state='none'),self.call(op='selection'))

    def test_selection_survives_reorder_removal_and_replacement(self):
        selected=self.initial['nodes'][0]['id'];self.action('select',selected)
        reordered=copy.deepcopy(self.initial);reordered['nodes'].reverse()
        self.call(op='publish',graph=reordered)
        self.assertEqual(dict(target_id=selected,state='present'),self.call(op='selection'))
        removed=copy.deepcopy(self.initial);removed['nodes']=removed['nodes'][1:]
        removed['edges']=[e for e in removed['edges'] if selected not in (e['from'],e['to'])]
        current=self.call(op='publish',graph=removed)
        self.assertEqual(dict(target_id=selected,state='missing'),self.call(op='selection'))
        self.error(self.action('inspect',selected,current['revision']),'target_not_found')
        replacement=copy.deepcopy(self.initial['nodes'][0]);replacement['id']='fake:alpha@2';replacement['properties']['media_generation']='2'
        removed['nodes'].insert(0,replacement);current=self.call(op='publish',graph=removed)
        self.assertEqual(dict(target_id=selected,state='missing'),self.call(op='selection'))
        self.assertEqual('completed',self.action('select',replacement['id'],current['revision'])['status'])
        self.assertEqual(dict(target_id=replacement['id'],state='present'),self.call(op='selection'))

    def test_invalid_refresh_does_not_publish_or_lose_selection(self):
        selected=self.initial['nodes'][0]['id'];self.action('select',selected)
        cases=[]
        for field,value,error in [('identity','replacement','identity_reuse'),('media_generation','2','identity_reuse'),('media_generation','0','invalid_quantity'),('capacity_bytes','18446744073709551616','invalid_quantity'),('state','ready','invalid_state'),('label','x'*4097,'invalid_node')]:
            g=copy.deepcopy(self.initial);g['nodes'][0]['properties'][field]=value;cases.append((g,error))
        g=copy.deepcopy(self.initial);g['nodes'].append(g['nodes'][0]);cases.append((g,'duplicate_node'))
        g=copy.deepcopy(self.initial);g['edges'][0]['to']='missing';cases.append((g,'invalid_edge'))
        g=copy.deepcopy(self.initial);g['nodes'][0]['properties']['aliases']=['a']*65;cases.append((g,'alias_limit'))
        g=copy.deepcopy(self.initial);g['nodes'][0]['properties']['aliases']=['磁'*86];cases.append((g,'invalid_reference'))
        g=copy.deepcopy(self.initial);g['nodes'][0]['properties']['label']='a\0b';cases.append((g,'invalid_node'))
        for field,count,error in [('nodes',65,'graph_limit'),('edges',257,'graph_limit'),('omissions',65,'graph_limit')]:
            g=copy.deepcopy(self.initial);g[field]=[g[field][0]]*count;cases.append((g,error))
        for graph,error in cases:
            with self.subTest(error=error):
                result=self.call(op='publish',graph=graph);self.assertEqual(error,result['error'])
                self.assertEqual(self.initial,self.call(op='query'))
                self.assertEqual(dict(target_id=selected,state='present'),self.call(op='selection'))

    def test_total_graph_bytes_are_bounded_before_publication(self):
        graph=copy.deepcopy(self.initial);graph['edges']=[];graph['nodes']=[]
        # Input uses short newline escapes; private output uses six-byte
        # escapes. Input remains under 64 KiB, output exceeds that bound.
        for i in range(8):
            node=copy.deepcopy(self.initial['nodes'][0]);node['id']=f'fake:large:{i}';node['properties']['label']='\n'*1400;graph['nodes'].append(node)
        self.assertEqual('output_limit_exceeded',self.call(op='publish',graph=graph)['error'])
        self.assertEqual(self.initial,self.call(op='query'))

    def test_retired_identity_cannot_be_reused_and_history_is_bounded(self):
        selected=self.initial['nodes'][0]['id'];empty=dict(self.initial,nodes=[],edges=[],omissions=[])
        self.call(op='publish',graph=empty)
        reused=copy.deepcopy(self.initial);reused['nodes'][0]['properties']['identity']='new'
        self.assertEqual('identity_reuse',self.call(op='publish',graph=reused)['error'])
        template=self.initial['nodes'][0]
        for batch in range(16):
            nodes=[]
            for i in range(64):
                n=copy.deepcopy(template);n['id']=f'fake:other:{batch*64+i}';nodes.append(n)
            value=self.call(op='publish',graph=dict(empty,nodes=nodes))
            if batch<15:self.assertNotIn('error',value)
            else:self.assertEqual('identity_limit',value['error'])
        self.assertEqual('fake:17',self.call(op='query')['capture_id'])

    def test_cached_observations_and_capability_denials(self):
        for node in self.initial['nodes']:
            target=node['id'];result=self.action('inspect',target)
            self.assertEqual(node,result['result']['target'])
            capability=self.call(op='dispatch',command='capability.explain',parameters=dict(target_id=target,operation='partition.resize.plan'),revision='')['result']['assessment']
            self.assertFalse(capability['execution_eligible']);self.assertFalse(capability['authorizes_execution'])
            self.assertEqual('unknown',capability['checks']['qualification']);self.assertEqual('unavailable',capability['checks']['implementation'])
            if node['properties']['state']=='denied':self.assertEqual('denied',capability['checks']['permission'])
        self.error(self.call(op='dispatch',command='target.inspect',parameters={},revision=''),'missing_parameter')
        self.error(self.call(op='dispatch',command='target.list',parameters={},revision='bad'),'revision_conflict')

    def test_sha256_vectors_padding_boundaries_and_random_values(self):
        rng=random.Random(130)
        values=['','abc','abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq']
        values+=['a'*n for n in [1,55,56,57,63,64,65,119,120,127,128,129,4096,32768]]
        values+=[''.join(chr(rng.randrange(128)) for _ in range(n)) for n in range(0,512,7)]
        for value in values:
            self.assertEqual('sha256:'+hashlib.sha256(value.encode()).hexdigest(),self.call(op='hash',bytes=value))

    def test_display_escapes_without_losing_original_values(self):
        value={'label':'\x1b[31m\0\n\x7f\x85\x9b\u202e\u2028磁盘💾'}
        display=self.call(op='display',value=value)
        self.assertTrue(all(32<=ord(c)<127 for c in display));self.assertEqual(value,json.loads(display))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);ARGS=p.parse_args()
    unittest.main(argv=[__file__],verbosity=2)
