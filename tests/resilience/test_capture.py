"""Native observation reducer, retained snapshots and bounded reader recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

P=argparse.ArgumentParser();P.add_argument('--probe',type=Path,required=True);P.add_argument('--evidence',type=Path)
ARGS,REST=P.parse_known_args();ARGS.probe=ARGS.probe.resolve();OBSERVATIONS=[]
def fragment(name='a',**changes):
    node=dict(id='fake:'+name,identity='fixture:'+name,generation='1',label=name,state='current',capacity='4096')
    node.update(changes);return dict(nodes=[node],edges=[],omissions=[])
class Probe:
    def __enter__(self):
        self.p=subprocess.Popen([str(ARGS.probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        return self
    def call(self,op,**fields):
        self.p.stdin.write(json.dumps(dict(op=op,**fields))+'\n');self.p.stdin.flush();line=self.p.stdout.readline()
        if not line:raise AssertionError('native capture probe exited: '+self.p.stderr.read())
        return json.loads(line)
    def __exit__(self,*_):
        self.p.stdin.close();self.p.stdin=None
        try:
            out,err=self.p.communicate(timeout=5)
            if self.p.returncode or out or err:raise AssertionError((self.p.returncode,out,err))
        finally:
            if self.p.poll() is None:self.p.kill();self.p.wait(timeout=3)
class Capture(unittest.TestCase):
    def test_publication_never_retires_and_duplicate_polls_do_not_churn(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');p.call('retain')
            self.assertTrue(p.call('update',key=key,graph=fragment()))
            published=p.call('view');self.assertEqual(('complete',True),(published['sources'][0]['state'],published['sources'][0]['outstanding']))
            self.assertEqual('current',published['graph']['nodes'][0]['properties']['state'])
            self.assertFalse(p.call('update',key=key,graph=fragment()));self.assertEqual(published,p.call('view'))
            self.assertEqual({'error':'capture_worker_outstanding'},p.call('start',source='one'))
            self.assertTrue(p.call('retired',key=key));retired=p.call('view')
            self.assertFalse(retired['sources'][0]['outstanding']);self.assertEqual(published['graph'],retired['graph'])
            self.assertFalse(p.call('retired',key=key));self.assertFalse(p.call('update',key=key,graph=fragment('late')))
            self.assertEqual(retired,p.call('view'));self.assertEqual([],p.call('retained',index='0')['graph']['nodes'])
            self.assertEqual({'error':'capture_attempt_already_started'},p.call('start',source='one'))
            OBSERVATIONS.append(dict(test='publication separate from adapter retirement; immutable retained view',published=published,retired=retired))

    def test_partial_publication_preserves_known_rows_and_explicit_unknown_remainder(self):
        with Probe() as p:
            p.call('init',sources=['one','peer']);key=p.call('start',source='one')
            peer=p.call('start',source='peer');p.call('finish',key=peer,graph=fragment('peer'))
            data=fragment();data['nodes']+=fragment('cached',state='stale')['nodes']
            self.assertTrue(p.call('update',key=key,graph=data,state='partial',reason='provider_partial',platform='5'))
            partial=p.call('view');self.assertEqual(['current','stale','current'],[n['properties']['state'] for n in partial['graph']['nodes']])
            self.assertIn('one:partial:provider_partial:5',partial['graph']['omissions']);self.assertTrue(partial['sources'][0]['outstanding'])
            self.assertTrue(p.call('retired',key=key));self.assertEqual(partial['graph'],p.call('view')['graph'])
            OBSERVATIONS.append(dict(test='partial current rows, explicit stale rows and unaffected peer',partial=partial))

    def test_bad_publication_and_failure_keep_worker_and_prior_content(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');p.call('update',key=key,graph=fragment())
            self.assertTrue(p.call('update',key=key,graph=fragment(identity='different')))
            bad=p.call('view');self.assertEqual(('malformed',True),(bad['sources'][0]['state'],bad['sources'][0]['outstanding']))
            self.assertEqual('fixture:a',bad['graph']['nodes'][0]['properties']['identity'])
            self.assertEqual('stale',bad['graph']['nodes'][0]['properties']['state'])
            self.assertEqual({'error':'capture_worker_outstanding'},p.call('start',source='one'))
            self.assertTrue(p.call('update_failure',key=key,state='denied',reason='access_denied',platform='5'))
            denied=p.call('view');self.assertTrue(denied['sources'][0]['outstanding'])
            self.assertFalse(p.call('update_failure',key=key,state='denied',reason='access_denied',platform='5'));self.assertEqual(denied,p.call('view'))
            self.assertTrue(p.call('update',key=key,graph=fragment(label='recovered')))
            self.assertEqual('current',p.call('view')['graph']['nodes'][0]['properties']['state'])
            p.call('retired',key=key);OBSERVATIONS.append(dict(test='invalid publication cannot retire or replace prior content',bad=bad,denied=denied))

    def test_late_old_publication_is_ignored_until_actual_retirement(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');p.call('update',key=key,graph=fragment())
            p.call('next');before=p.call('view')
            self.assertFalse(p.call('update',key=key,graph=fragment('late')))
            self.assertFalse(p.call('update_failure',key=key,state='unavailable',reason='exited',platform='23'))
            self.assertEqual(before,p.call('view'));self.assertTrue(before['sources'][0]['outstanding'])
            self.assertEqual({'error':'capture_worker_outstanding'},p.call('start',source='one'))
            self.assertTrue(p.call('retired',key=key));retired=p.call('view')
            self.assertFalse(retired['sources'][0]['outstanding']);self.assertEqual('fake:a',retired['graph']['nodes'][0]['id'])
            self.assertEqual('stale',retired['graph']['nodes'][0]['properties']['state'])
            new=p.call('start',source='one');self.assertEqual(('2','2'),(new['capture'],new['worker']))
            before=p.call('view');self.assertFalse(p.call('retired',key=key));self.assertEqual(before,p.call('view'))
            OBSERVATIONS.append(dict(test='superseded update never retires; exact old retirement required',retired=retired))

    def test_timeout_cancel_equivalents_do_not_prove_worker_exit(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');p.call('timeout',key=key)
            self.assertTrue(p.call('view')['sources'][0]['outstanding'])
            self.assertTrue(p.call('update',key=key,graph=fragment(),state='partial',reason='cancelled_at_checkpoint'))
            self.assertTrue(p.call('view')['sources'][0]['outstanding'])
            p.call('retired',key=key);self.assertEqual('partial',p.call('view')['sources'][0]['state'])
            p.call('next');key=p.call('start',source='one');p.call('timeout',key=key);p.call('retired',key=key)
            timed=p.call('view');self.assertEqual(('timed_out',False),(timed['sources'][0]['state'],timed['sources'][0]['outstanding']))
            p.call('next');key=p.call('start',source='one');p.call('retired',key=key)
            self.assertEqual('reader_exited_without_result',p.call('view')['sources'][0]['reason'])
            OBSERVATIONS.append(dict(test='timeout/cancel publication and worker lifetime independent',retired_timeout=timed))

    def test_invalid_update_policy_and_wrong_attempt_are_inert(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');before=p.call('view')
            for fields in [dict(state='pending'),dict(state='partial'),dict(state='complete',reason='unexpected'),dict(state='partial',reason='control\x1b'),dict(platform='18446744073709551616')]:
                self.assertIn('error',p.call('update',key=key,graph=fragment(),**fields));self.assertEqual(before,p.call('view'))
            wrong=dict(key,worker='18446744073709551615')
            self.assertFalse(p.call('update',key=wrong,graph=fragment()));self.assertFalse(p.call('retired',key=wrong));self.assertEqual(before,p.call('view'))

    def test_allocation_failures_during_update_failure_and_retirement_are_atomic(self):
        counts={}
        with Probe() as p:
            for op in ('update','update_failure','retired'):
                checked=0
                for index in range(0,1000,7):
                    p.call('init',sources=['one','peer']);key=p.call('start',source='one');before=p.call('view')
                    fields=dict(graph=fragment()) if op=='update' else dict(state='denied',reason='access_denied',platform='5') if op=='update_failure' else {}
                    result=p.call(op,key=key,allocation_failure=str(index),**fields)
                    if result=={'error':'allocation_failed'}:
                        self.assertEqual(before,p.call('view'));self.assertTrue(p.call(op,key=key,**fields));checked+=1
                    else:self.assertTrue(result);break
                self.assertGreater(checked,5);counts[op]=checked
        OBSERVATIONS.append(dict(test='atomic update/failure/retirement allocation sweeps',injected_failures=counts))

    def test_combined_source_outcomes_preserve_healthy_observations(self):
        with Probe() as p:
            p.call('init',sources=['healthy','denied','malformed','slow','exited'])
            keys={s:p.call('start',source=s) for s in ['healthy','denied','malformed','slow','exited']}
            p.call('finish',key=keys['healthy'],graph=fragment())
            stable=p.call('view');p.call('retain')
            p.call('fail',key=keys['denied'],state='denied',reason='access_denied',platform='5')
            p.call('finish',key=keys['malformed'],graph=fragment('bad',capacity='18446744073709551616'))
            p.call('timeout',key=keys['slow'])
            p.call('fail',key=keys['exited'],state='unavailable',reason='provider_exited',platform='3221225477')
            value=p.call('view');self.assertEqual(stable,p.call('retained',index='0'))
            self.assertEqual(['fake:a'],[n['id'] for n in value['graph']['nodes']])
            self.assertEqual(['complete','denied','malformed','timed_out','unavailable'],[s['state'] for s in value['sources']])
            self.assertTrue(value['sources'][3]['outstanding'])
            self.assertEqual({'error':'capture_worker_outstanding'},p.call('start',source='slow'))
            p.call('finish',key=keys['slow'],graph=fragment('late'))
            late=p.call('view');self.assertEqual('complete',late['sources'][3]['state'])
            self.assertEqual(['fake:a','fake:late'],[n['id'] for n in late['graph']['nodes']])
            self.assertEqual({'error':'capture_attempt_already_started'},p.call('start',source='exited'))
            OBSERVATIONS.append(dict(scope='native reducer; process campaign separate',before=stable,failed=value,late=late))

    def test_superseded_attempt_retires_without_publishing_or_replacing(self):
        with Probe() as p:
            p.call('init',sources=['one']);old=p.call('start',source='one');p.call('next')
            self.assertEqual({'error':'capture_worker_outstanding'},p.call('start',source='one'))
            before=p.call('view');self.assertFalse(p.call('timeout',key=old))
            self.assertEqual(before,p.call('view'))
            self.assertTrue(p.call('finish',key=old,graph=fragment('discarded')))
            retired=p.call('view');self.assertEqual([],retired['graph']['nodes'])
            current=p.call('start',source='one');self.assertEqual(('2','2'),(current['capture'],current['worker']))
            before=p.call('view');self.assertFalse(p.call('finish',key=old,graph=fragment('wrong')))
            self.assertEqual(before,p.call('view'))
            wrong=dict(current,worker='18446744073709551615');self.assertFalse(p.call('finish',key=wrong,graph=fragment('wrong')))
            self.assertTrue(p.call('finish',key=current,graph=fragment('new')))
            value=p.call('view');self.assertEqual('fake:new',value['graph']['nodes'][0]['id'])
            self.assertFalse(p.call('finish',key=current,graph=fragment('repeated')));self.assertEqual(value,p.call('view'))
            OBSERVATIONS.append(dict(test='superseded capture and duplicate completion',retired=retired,final=value))

    def test_failed_refresh_retains_cached_identity_and_denial(self):
        with Probe() as p:
            p.call('init',sources=['one']);key=p.call('start',source='one');data=fragment()
            data['nodes']+=fragment('denied',state='denied',capacity='')['nodes']
            p.call('finish',key=key,graph=data);p.call('next');key=p.call('start',source='one')
            stale=p.call('view');self.assertEqual(['stale','denied'],[n['properties']['state'] for n in stale['graph']['nodes']])
            p.call('finish',key=key,graph=fragment(identity='other-medium'))
            bad=p.call('view');self.assertEqual('malformed',bad['sources'][0]['state']);self.assertEqual(stale['graph']['nodes'],bad['graph']['nodes'])
            p.call('next');key=p.call('start',source='one');p.call('finish',key=key,graph=dict(nodes=[],edges=[],omissions=[]))
            self.assertEqual([],p.call('view')['graph']['nodes'])
            p.call('next');key=p.call('start',source='one');p.call('finish',key=key,graph=fragment(identity='still-other'))
            self.assertEqual('malformed',p.call('view')['sources'][0]['state'])
            OBSERVATIONS.append(dict(test='failed refresh remains stale, removal does not forget identity',failed=bad))

    def test_conflicting_source_and_dangling_edge_do_not_replace_good_data(self):
        with Probe() as p:
            p.call('init',sources=['one','two','three']);key=p.call('start',source='one');p.call('finish',key=key,graph=fragment())
            key=p.call('start',source='two');p.call('finish',key=key,graph=fragment())
            key=p.call('start',source='three');bad=fragment('other');bad['edges']=[dict(**{'from':'fake:other'},to='fake:a',kind='backs')]
            p.call('finish',key=key,graph=bad);value=p.call('view')
            self.assertEqual(['complete','malformed','malformed'],[s['state'] for s in value['sources']])
            self.assertEqual(['fake:a'],[n['id'] for n in value['graph']['nodes']])

    def test_slow_reader_gets_explicit_gap_and_current_snapshot(self):
        with Probe() as p:
            p.call('init',sources=['p'+str(i) for i in range(8)])
            for i in range(8):
                key=p.call('start',source='p'+str(i));p.call('finish',key=key,graph=fragment(str(i)))
            lost=p.call('changes',capture='1',after='0');self.assertTrue(lost['resnapshot']);self.assertEqual([],lost['notices'])
            self.assertEqual(8,len(lost['current']['graph']['nodes']));self.assertEqual('16',lost['current']['sequence'])
            retained=p.call('changes',capture='1',after='8');self.assertFalse(retained['resnapshot'])
            self.assertEqual(list(map(str,range(9,17))),[v['sequence'] for v in retained['notices']])
            self.assertEqual([],p.call('changes',capture='1',after='16')['notices'])
            self.assertEqual({'error':'capture_future_cursor'},p.call('changes',capture='1',after='17'))
            p.call('next');reset=p.call('changes',capture='1',after='16');self.assertTrue(reset['resnapshot'])
            self.assertEqual('2',reset['current']['capture']);OBSERVATIONS.append(dict(test='eight-notice ceiling',gap=lost,retained=retained,reset=reset))
            self.assertTrue(p.call('changes',capture='2',after='16')['resnapshot'])
            self.assertFalse(p.call('changes',capture='2',after='17')['resnapshot'])

    def test_source_and_aggregate_limits(self):
        with Probe() as p:
            for sources in [[],['a']*2,['x']*9,['control\x1b'],['x'*65]]:
                self.assertIn('error',p.call('init',sources=sources))
            p.call('init',sources=['one','two']);key=p.call('start',source='one')
            large=dict(nodes=[fragment(str(i))['nodes'][0] for i in range(64)],edges=[],omissions=[])
            p.call('finish',key=key,graph=large);key=p.call('start',source='two');p.call('finish',key=key,graph=fragment('overflow'))
            value=p.call('view');self.assertEqual(64,len(value['graph']['nodes']));self.assertEqual('malformed',value['sources'][1]['state'])
            p.call('init',sources=['one']);key=p.call('start',source='one');bad=fragment();bad['omissions']=['bounded']*49
            p.call('finish',key=key,graph=bad);self.assertEqual('malformed',p.call('view')['sources'][0]['state'])
            p.call('init',sources=['one']);key=p.call('start',source='one');bad=dict(nodes=[fragment(str(i),label='x'*4000)['nodes'][0] for i in range(15)])
            p.call('finish',key=key,graph=bad);self.assertEqual('malformed',p.call('view')['sources'][0]['state'])

    def test_allocation_failures_leave_publication_and_attempt_unchanged(self):
        checked=0
        with Probe() as p:
            for index in range(0,800,7):
                p.call('init',sources=['one','two']);key=p.call('start',source='one');before=p.call('view')
                result=p.call('finish',key=key,graph=fragment(),allocation_failure=str(index))
                if result=={'error':'allocation_failed'}:
                    self.assertEqual(before,p.call('view'));self.assertTrue(p.call('finish',key=key,graph=fragment()));checked+=1
                else:self.assertTrue(result);break
        self.assertGreater(checked,10);OBSERVATIONS.append(dict(test='allocation failure sweep; no replacement worker',injected_failures=checked))

    def test_session_does_not_consume_an_update_before_publication(self):
        checked=0
        with Probe() as p:
            for index in range(0,1000,7):
                result=p.call('session_atomic',initial=fragment(label='before'),updated=fragment(label='after'),allocation_failure=str(index))
                self.assertEqual('fake:1',result['old']['capture_id'])
                self.assertEqual('before',result['old']['nodes'][0]['properties']['label'])
                self.assertEqual('fake:2',result['current']['capture_id'])
                self.assertEqual('after',result['current']['nodes'][0]['properties']['label'])
                self.assertEqual(('1','0'),(result['action_polls'],result['action_exit']))
                if result['failed']:
                    self.assertFalse(result['changed']);self.assertTrue(result['retried']);checked+=1
                else:
                    self.assertTrue(result['changed']);self.assertFalse(result['retried']);break
        self.assertGreater(checked,10)
        OBSERVATIONS.append(dict(test='session publication failure retains source update and old snapshot; one poll per action',injected_failures=checked))

    def test_retired_ids_still_count_toward_the_identity_budget(self):
        with Probe() as p:
            p.call('init',sources=['one'])
            for batch in range(16):
                key=p.call('start',source='one')
                data=dict(nodes=[fragment(str(batch*64+i))['nodes'][0] for i in range(64)])
                p.call('finish',key=key,graph=data)
                self.assertEqual('complete',p.call('view')['sources'][0]['state'])
                p.call('next')
            key=p.call('start',source='one');p.call('finish',key=key,graph=fragment('overflow'))
            limited=p.call('view');self.assertEqual('malformed',limited['sources'][0]['state'])
            self.assertEqual(64,len(limited['graph']['nodes']))
            self.assertEqual('fake:960',limited['graph']['nodes'][0]['id'])
            self.assertTrue(all(n['properties']['state']=='stale' for n in limited['graph']['nodes']))
            p.call('next');key=p.call('start',source='one');p.call('finish',key=key,graph=fragment('0'))
            self.assertEqual('complete',p.call('view')['sources'][0]['state'])
            OBSERVATIONS.append(dict(test='1024 retained identity bindings; valid known identity remains admissible',limit=1024))

if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(tests=result.result.testsRun,passed=result.result.wasSuccessful(),
        probe=str(ARGS.probe),sha256=hashlib.sha256(ARGS.probe.read_bytes()).hexdigest(),observations=OBSERVATIONS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
