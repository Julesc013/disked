"""Shared typed acquisition contract against owned ordinary files and port spies.

This private native probe does not admit a public command or physical storage.
Expected response/exit relations come from DE-103, not probe output.
"""
import argparse
import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import time
from test_acquisition_worker import (canonical, digest, source_bytes, map_check,
    history_check, owned_process, fixture_directory, K)


def frame(parameters):
    return dict(schema='org.disked.request/1', request_id='acquisition-test',
        command='image.acquire', parameters=parameters, required_features=[])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', required=True); ap.add_argument('--root', default='.')
    ap.add_argument('--evidence')
    args = ap.parse_args(); root = Path(args.root).resolve(); probe = str(Path(args.probe).resolve())
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_', 'DISKED_TEST_'))}
    observations = []; verified = []; scratch = root/'.aide-local'; scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        def call(name, value, exits=(0,), injected=()):
            callenv = dict(env)
            for key in injected:callenv['DISKED_ACQ_WORKER_TEST_'+key] = '1'
            raw = canonical(value)
            p = subprocess.run([probe], input=raw, capture_output=True, env=callenv, cwd=root, timeout=12)
            assert p.returncode in exits and not p.stderr, (name, p.returncode, p.stdout, p.stderr)
            out = json.loads(p.stdout); response = out.get('response', out)
            assert set(response) == {'schema','request_id','status','operation_id','result','diagnostics','evidence'}, (name,out)
            assert response['schema'] == 'org.disked.response/1'
            expected = {0:'completed',2:'refused',3:'refused',4:'failed',5:'accepted_running',6:'unknown'}
            assert response['status'] == expected[p.returncode], (name,out)
            if p.returncode == 5:assert response['operation_id'] and response['operation_id'].startswith('image-op:')
            observations.append(dict(name=name, exit_code=p.returncode, status=response['status'],
                input_sha256=digest(raw), output_sha256=digest(p.stdout), passed=True))
            return out

        def fixture(name, size=65537):
            folder = owned/name; folder.mkdir(); state = folder/'state'; state.mkdir()
            src = folder/'source.img'; src.write_bytes(source_bytes(size))
            return dict(phase='prepare',source=str(src),destination=str(folder/'copy.img'),
                map=str(folder/'copy.map'),state_directory=str(state))

        def no_effects(params):
            assert not Path(params['destination']).exists() and not Path(params['map']).exists()
            assert not list(Path(params['state_directory']).iterdir())

        def prepare(name, params, mode='request'):
            if mode=='request':v=dict(mode=mode,request=frame(params))
            elif mode=='cli':v=dict(mode=mode,argv=['image','acquire','prepare',params['source'],params['destination'],
                '--map',params['map'],'--state-dir',params['state_directory']])
            else:v=dict(mode=mode,editor={k:str(v).lower() if isinstance(v,bool) else v for k,v in params.items()})
            value = call(name,v)['result']; no_effects(params)
            assert value['phase']=='prepare' and value['execution_admitted'] is False
            assert value['source_consistency']=='live-uncoordinated'
            assert value['definition_digest']==digest(canonical(value['definition']))
            assert value['definition']['request']['explicit_options'] is True
            return dict(phase='execute', definition=value['definition'],definition_digest=value['definition_digest'],
                allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)

        def finished(name, params, first):
            deadline=time.monotonic()+30; ident=first['operation_id']; assert ident
            while time.monotonic()<deadline:
                out=call(name,dict(mode='inspect',operation_id=ident,state_directory=params['state_directory']),exits=(0,5,6))
                state=(out['result'] or {}).get('state',{})
                if state.get('phase')=='finished':
                    assert out['status']=='completed' and state['quiescent']
                    handle=owned_process(state,probe)
                    if handle:
                        try:assert K.WaitForSingleObject(handle,2000)==0
                        finally:K.CloseHandle(handle)
                    return out
                assert out['status']=='completed' and out['result']['worker_observation']=='running',out
                time.sleep(.03)
            raise AssertionError((name,'finite owned operation did not finish; retain fixture'))

        def verify(name, params, out):
            state=out['result']['state']; expected=Path(params['source']).read_bytes()
            assert state['outcome']['status']=='completed' and state['outcome']['checkpoint_bytes']==str(len(expected))
            assert not state['outcome']['uncertain_effect']
            assert Path(params['destination']).read_bytes()==expected
            rows=map_check(Path(params['map']),expected);history=history_check(Path(params['state_directory'])/'acquisition.records')
            assert history[-1]['state']==state
            assert state['receipt']['original_capture']==rows[0]['payload']['capture']
            verified.append(dict(name=name,bytes=str(len(expected)),destination_sha256=digest(expected),
                capture=rows[0]['payload']['capture'],attempt=state['binding']['attempt_id']))
            return rows

        params=fixture('invalid-inputs')
        for name,bad in [('missing-phase',{}),('unknown-phase',dict(params,phase='other')),
            ('wrong-source-type',dict(params,source=1)),('unknown-field',dict(params,force=True)),
            ('mixed-phases',dict(params,allow_host_effects=True)),('prepare-definition',dict(params,definition={})),
            ('invalid-chunk',dict(params,chunk_bytes='8192')),('retry-outside-bound',dict(params,retry_limit='4')),
            ('path-too-long',dict(params,source='x'*1025)),
            ('failing-source-retry',dict(params,read_policy='failing-read-mostly',retry_limit='1'))]:
            out=call(name,dict(mode='audit',request=frame(bad),reply={}),exits=(2,))
            assert out['prepare_calls']==out['execute_calls']==0;no_effects(params)
        for key in ('source','destination','map','state_directory'):
            bad=dict(params);del bad[key]
            out=call('missing-'+key,dict(mode='audit',request=frame(bad),reply={}),exits=(2,))
            assert out['prepare_calls']==out['execute_calls']==0

        request=fixture('typed-source')
        reviewed=prepare('prepare-stdio',request)
        # Same paths and policy; each preparation deliberately gets a fresh capture.
        for mode in ('cli','form'):
            alternate=prepare('prepare-'+mode,request,mode)
            assert alternate['definition']['request']==reviewed['definition']['request']
            assert alternate['definition']['plan']['resources']==reviewed['definition']['plan']['resources']

        for flag in ('allow_source_read','allow_destination_write','allow_map_write','allow_host_effects'):
            for replacement in (False,'true',None):
                bad=copy.deepcopy(reviewed);bad[flag]=replacement
                out=call('deny-'+flag+'-'+str(replacement),dict(mode='audit',request=frame(bad),reply={}),exits=(2,))
                assert out['prepare_calls']==out['execute_calls']==0
            bad=copy.deepcopy(reviewed);del bad[flag]
            out=call('missing-'+flag,dict(mode='audit',request=frame(bad),reply={}),exits=(2,))
            assert out['execute_calls']==0
        for name,change in [('unknown-definition',lambda d:d.update(extra=True)),
            ('wrong-store-access',lambda d:d['store'].update(access='write-anywhere')),
            ('extra-store-child',lambda d:d['store']['children'].append('other')),
            ('nonresolved-options',lambda d:d['request'].update(explicit_options=False)),
            ('bad-code-generation',lambda d:d.update(image_digest='z'*64)),
            ('bad-source-revision',lambda d:d.update(source_revision='z'*40)),
            ('directory-u64-overflow',lambda d:d['store']['generation'].update(created=str(2**64))),
            ('invalid-plan-resource',lambda d:d['plan']['resources']['source'].update(access='write'))]:
            bad=copy.deepcopy(reviewed);change(bad['definition']);bad['definition_digest']=digest(canonical(bad['definition']))
            out=call(name,dict(mode='audit',request=frame(bad),reply={}),exits=(2,));assert out['execute_calls']==0
        for name,change in [('plan-size-overflow',lambda d:d['plan'].update(bytes=str(2**63))),
            ('options-disagree',lambda d:d['request'].update(retry_limit='1')),
            ('source-alias-collision',lambda d:d['plan']['resources']['destination']['aliases'].append(d['plan']['resources']['source']['aliases'][0]))]:
            bad=copy.deepcopy(reviewed);change(bad['definition']);bad['definition_digest']=digest(canonical(bad['definition']))
            out=call(name,dict(mode='audit',request=frame(bad),reply={}),exits=(3,));assert out['execute_calls']==0
        bad=copy.deepcopy(reviewed);bad['definition_digest']='sha256:'+'f'*64
        out=call('grant-not-exact',dict(mode='audit',request=frame(bad),reply={}),exits=(3,));assert out['execute_calls']==0
        no_effects(request)

        for badjson in ('{"schema":"x","schema":"y"}', '[{}]', '{', ' '*16385+'{}', '{"x":"'+'a'*1025+'"}',
            '{"x":'+'['*21+'0'+']'*21+'}'):
            editor={k:canonical(v).decode() if isinstance(v,dict) else str(v).lower() if isinstance(v,bool) else v for k,v in reviewed.items()}
            editor['definition']=badjson
            call('form-invalid-structured-json',dict(mode='form',editor=editor),exits=(2,))
            call('cli-invalid-structured-json',dict(mode='cli',argv=['image','acquire','execute','--definition-json',badjson,
                '--definition-digest',reviewed['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']),exits=(2,))
        no_effects(request)
        reserved=frame(reviewed);reserved['plan_digest']=reviewed['definition_digest']
        out=call('no-envelope-grant-substitute',dict(mode='audit',request=reserved,reply={}),exits=(2,));assert out['execute_calls']==0

        for mode in ('request','cli','form'):
            p=fixture('copy-'+mode,1048577 if mode=='request' else 65537);r=prepare('prepare-copy-'+mode,p,mode)
            if mode=='request':value=dict(mode=mode,request=frame(r))
            elif mode=='cli':value=dict(mode=mode,argv=['image','acquire','execute','--definition-json',canonical(r['definition']).decode(),
                '--definition-digest',r['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'])
            else:value=dict(mode=mode,editor={k:canonical(v).decode() if isinstance(v,dict) else str(v).lower() if isinstance(v,bool) else v for k,v in r.items()})
            first=call('execute-'+mode,value,exits=(0,5));end=finished('reconnect-'+mode,p,first);verify('copy-'+mode,p,end)
            repeat=call('repeat-never-relaunches-'+mode,dict(mode='request',request=frame(r)))
            assert repeat['operation_id']==first['operation_id'] and repeat['result']['state']==end['result']['state']
            completed_reply=dict(schema='org.disked.acquisition-admission-prototype/1',status='completed',
                operation_id=first['operation_id'],diagnostic='',platform_code='0',value=end['result'])

        # Spy an execution port with real reviewed metadata: exact invocation count
        # and conservative post-call uncertainty, no filesystem effects.
        audited=r
        for status,exitcode in [('accepted_running',5),('unknown',6),('refused',3),('completed',0)]:
            reply=copy.deepcopy(completed_reply);reply['status']=status
            if status=='accepted_running':reply['value']['state'].update(phase='active',quiescent=False,outcome=None,receipt=None)
            if status=='refused':reply.update(operation_id=None,value={})
            out=call('translate-'+status,dict(mode='audit',request=frame(audited),reply=reply),exits=(exitcode,))
            assert out['execute_calls']==1 and out['prepare_calls']==0
        for name,change in [('missing-id',lambda r:r.update(status='accepted_running',operation_id=None)),
            ('unknown-reply-field',lambda r:r.update(other=True)),('bad-platform-code',lambda r:r.update(platform_code=str(2**32))),
            ('nonquiescent-completion',lambda r:r['value']['state'].update(quiescent=False)),
            ('wrong-binding',lambda r:r['value']['state']['binding'].update(operation_id='image-op:'+'f'*32)),
            ('short-completion',lambda r:r['value']['state']['outcome'].update(checkpoint_bytes='0')),
            ('uncertain-completion',lambda r:r['value']['state']['outcome'].update(uncertain_effect=True)),
            ('wrong-definition',lambda r:r['value']['definition']['request'].update(source='C:\\other.img')),
            ('terminal-marked-running',lambda r:r.update(status='accepted_running')),
            ('admitted-marked-refused',lambda r:r.update(status='refused')),
            ('wrong-capture-epoch',lambda r:r['value']['state']['binding'].update(capture_epoch='another-capture')),
            ('state-outcome-disagreement',lambda r:r['value']['state'].update(checkpoint_bytes='0'))]:
            reply=copy.deepcopy(completed_reply);change(reply)
            out=call('unresolved-'+name,dict(mode='audit',request=frame(audited),reply=reply),exits=(6,))
            assert out['execute_calls']==1
            assert out['response']['result']['state_directory']==p['state_directory']
            assert out['response']['result']['definition_digest']==audited['definition_digest']
            if name!='missing-id':assert out['response']['operation_id']==completed_reply['operation_id']
        out=call('exception-after-invoke',dict(mode='audit',request=frame(audited),reply={},throw=True),exits=(6,))
        assert out['execute_calls']==1 and out['response']['operation_id'] is None
        for logical in ('paused','failed','refused'):
            reply=copy.deepcopy(completed_reply);reply['value']['state']['outcome']['status']=logical
            out=call('incomplete-execution-'+logical,dict(mode='audit',request=frame(audited),reply=reply),exits=(4,))
            assert out['response']['result']['state']['outcome']['status']==logical
            call('completed-observation-'+logical,dict(mode='observe-reply',reply=reply))
        no_effects(request)

        p=fixture('cancel-resume',2097153);r=prepare('prepare-cancel',p)
        first=call('execute-cancellable',dict(mode='request',request=frame(r)),exits=(5,),injected=('CHECKPOINT_DELAY',))
        cancel=call('request-checkpoint-cancel',dict(mode='cancel',operation_id=first['operation_id'],state_directory=p['state_directory']),exits=(0,5))
        assert cancel['result']['cancellation_request']=='requested'
        end=finished('await-cancellation',p,first);state=end['result']['state'];assert state['outcome']['status']=='paused'
        expected=Path(p['source']).read_bytes();prefix=int(state['outcome']['checkpoint_bytes']);assert prefix<len(expected)
        assert Path(p['destination']).read_bytes()==expected[:prefix]
        rows=map_check(Path(p['map']),expected,False);capture=rows[0]['payload']['capture']
        repeat=call('paused-execution-remains-incomplete',dict(mode='request',request=frame(r)),exits=(4,))
        assert repeat['operation_id']==first['operation_id']
        nextstate=Path(p['state_directory']).parent/'resume-state';nextstate.mkdir();resume=dict(p,resume=True,state_directory=str(nextstate))
        rv=call('prepare-resume',dict(mode='request',request=frame(resume)))['result']
        rr=dict(r,definition=rv['definition'],definition_digest=rv['definition_digest'])
        resumed=call('execute-resume',dict(mode='request',request=frame(rr)),exits=(0,5))
        assert resumed['operation_id']!=first['operation_id']
        end=finished('await-resume',resume,resumed);rows=verify('cancel-resume',resume,end)
        assert rows[0]['payload']['capture']==capture

        p=fixture('late-start',1);r=prepare('prepare-delayed',p)
        first=call('admission-timeout-is-unknown',dict(mode='request',request=frame(r)),exits=(6,),injected=('ADMISSION_DELAY',))
        assert first['operation_id']
        end=finished('observe-late-start',p,first);verify('late-start',p,end)
        repeat=call('late-attempt-not-restarted',dict(mode='request',request=frame(r)))
        assert repeat['operation_id']==first['operation_id']

        # Positive separate code/state-directory layout; this does not test every
        # possible concurrent directory substitution or backing-store alias.
        original_probe=probe;code=owned/'separate-code';code.mkdir()
        executable=code/'acquisition_command_probe.exe';shutil.copy2(probe,executable);probe=str(executable)
        p=fixture('separate-state-layout',65537);r=prepare('prepare-separate-code-state',p)
        first=call('execute-separate-code-state',dict(mode='request',request=frame(r)),exits=(0,5))
        end=finished('observe-separate-code-state',p,first);verify('separate-code-state',p,end)
        probe=original_probe

    report=dict(scope='private-shared-acquisition-command-contract',physical_storage_qualified=False,
        public_command_admitted=False,checks=len(observations),verified_copies=verified,observations=observations)
    if args.evidence:Path(args.evidence).write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print('PASS shared acquisition commands:',len(observations),'checks;',len(verified),'verified copies')


if __name__=='__main__':main()
