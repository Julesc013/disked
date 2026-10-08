"""Public acquisition observations against generated files and actual workers.

Copy admission remains in a private probe; disked.exe owns the observation
paths tested here. Expectations derive from DE-103's observation contract.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from test_acquisition_worker import (canonical, digest, source_bytes, map_check,
    history_check, owned_process, fixture_directory, K)

FEATURE = 'org.disked.acquisition-operation-events/1'


def main():
    ap = argparse.ArgumentParser()
    for flag in ('probe','disked','reader'):ap.add_argument('--'+flag,required=True)
    ap.add_argument('--root',default='.');ap.add_argument('--evidence')
    a = ap.parse_args();root=Path(a.root).resolve()
    probe,disked,reader=(str(Path(p).resolve()) for p in (a.probe,a.disked,a.reader))
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
    observations=[];verified=[];producer=[]

    def run(name,argv,value=None,exits=(0,),inject=False):
        callenv=dict(env)
        if inject:callenv['DISKED_ACQ_WORKER_TEST_CHECKPOINT_DELAY']='1'
        raw=b'' if value is None else canonical(value)+b'\n'
        p=subprocess.run(argv,input=raw,capture_output=True,cwd=root,env=callenv,timeout=15)
        assert p.returncode in exits and not p.stderr,(name,p.returncode,p.stdout,p.stderr)
        rows=[json.loads(row) for row in p.stdout.splitlines()]
        assert rows,(name,p.stdout)
        observations.append(dict(name=name,exit_code=p.returncode,input_sha256=digest(raw),
            output_sha256=digest(p.stdout),passed=True))
        return rows

    def request(command,params,features=()):
        return dict(schema='org.disked.request/1',request_id='acquisition-observer',
            command=command,parameters=params,required_features=list(features))

    def public(name,command,params,features=(),ndjson=False,exits=(0,)):
        rows=run(name,[disked,'protocol','serve','--format','ndjson' if ndjson else 'json'],
            request(command,params,features),exits)
        response=rows[-1]
        assert response['schema']=='org.disked.response/1' and response['request_id']=='acquisition-observer'
        assert response['status'] in {'completed','accepted_running','refused','unknown','failed'}
        return response,rows[:-1]

    def rehash(event):
        row=event['payload']['record'];row.pop('digest',None)
        row['digest']=hashlib.sha256(canonical(row)).hexdigest()
        return event

    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        def prepare(name,size):
            folder=owned/name;folder.mkdir();state=folder/'state';state.mkdir()
            source=folder/'source.img';source.write_bytes(source_bytes(size))
            params=dict(phase='prepare',source=str(source),destination=str(folder/'copy.img'),
                map=str(folder/'copy.map'),state_directory=str(state))
            value=run('prepare-'+name,[probe],dict(mode='request',request=request('image.acquire',params)))[0]['result']
            return params,dict(phase='execute',definition=value['definition'],definition_digest=value['definition_digest'],
                allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)

        def start(name,params,grant,delay=False):
            first=run('start-'+name,[probe],dict(mode='request',request=request('image.acquire',grant)),(0,5),delay)[0]
            return dict(operation_id=first['operation_id'],state_directory=params['state_directory'])

        def finish(name,params):
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                value,_=public('inspect-'+name,'operation.inspect',params)
                state=value['result']['state']
                if state['phase']=='finished':
                    h=owned_process(state,probe)
                    if h:
                        try:assert K.WaitForSingleObject(h,2000)==0
                        finally:K.CloseHandle(h)
                    return value
                assert value['result']['worker_observation']=='running'
                time.sleep(.03)
            raise AssertionError('owned worker did not finish; retain fixtures')

        def events_check(events,definition):
            previous='0'*64;binding=None;covered=0
            for seq,event in enumerate(events,1):
                row=event['payload']['record'];state=row['state']
                assert event['type']=='acquisition.operation.record' and event['sequence']==str(seq)==state['sequence']
                assert event['operation_id']==state['binding']['operation_id']
                assert row['previous']==previous
                assert row['digest']==hashlib.sha256(canonical({k:v for k,v in row.items() if k!='digest'})).hexdigest()
                previous=row['digest'];binding=binding or state['binding'];assert binding==state['binding']
                assert binding['definition_digest']==digest(canonical(definition))
                assert binding['capture_epoch']==definition['plan']['capture_epoch']
                assert int(state['checkpoint_bytes'])>=covered;covered=int(state['checkpoint_bytes'])
                assert int(state['source_bytes'])+int(state['substituted_bytes'])==covered
                assert covered<=int(definition['plan']['bytes'])
            native=run('reader-actual-history',[reader],dict(op='read',definition=definition,
                operation_id=events[0]['operation_id'],events=events))[0]['results']
            assert all(row['accepted'] for row in native)
            producer.extend(events)

        # Active watch is a bounded observation; closing it does not request cancellation.
        params,grant=prepare('complete',2097153);op=start('complete',params,grant,True)
        active,_=public('active-inspect','operation.inspect',op)
        assert active['status']=='completed' and not active['result']['state']['quiescent']
        watch,events=public('active-stream','operation.watch',dict(op,follow_ms='0'),(FEATURE,),True,(5,))
        assert watch['status']=='accepted_running' and watch['operation_id']==op['operation_id'] and events
        assert watch['result']['events']==[]
        end=finish('complete',op);assert end['result']['state']['outcome']['status']=='completed'
        expected=Path(params['source']).read_bytes();assert Path(params['destination']).read_bytes()==expected
        map_check(Path(params['map']),expected);records=history_check(Path(params['state_directory'])/'acquisition.records')
        batch,_=public('complete-batch','operation.watch',op)
        events=batch['result']['events'];events_check(events,grant['definition'])
        assert [e['payload']['record'] for e in events]==records
        verified.append(dict(name='completed-public-observation',bytes=str(len(expected)),sha256=digest(expected)))
        run('cli-complete-watch',[disked,'operation','watch',op['operation_id'],'--state-dir',op['state_directory'],'--format','json'])
        run('human-complete-watch',[disked,'operation','watch',op['operation_id'],'--state-dir',op['state_directory']])
        stream,streamed=public('complete-stream','operation.watch',op,(FEATURE,),True)
        events_check(streamed,grant['definition']);assert stream['result']['events']==[]
        assert stream['result']['last_sequence']==str(len(records)) and stream['result']['last_digest']==records[-1]['digest']
        cursor=dict(op,after_sequence='1',after_digest=records[0]['digest'],worker_epoch=records[0]['state']['binding']['worker_epoch'])
        resumed,_=public('cursor-replay','operation.watch',cursor)
        assert [e['payload']['record'] for e in resumed['result']['events']]==records[1:]
        for name,change in [('wrong-digest',dict(after_digest='f'*64)),('future-cursor',dict(after_sequence='64')),
            ('changed-worker',dict(worker_epoch='worker:'+'f'*32)),('snapshot-cursor-conflict',dict(snapshot=True))]:
            public(name,'operation.watch',dict(cursor,**change),exits=(2,))
        snap,_=public('explicit-snapshot','operation.watch',dict(op,snapshot=True))
        assert len(snap['result']['events'])==1 and snap['result']['events'][0]['type']=='acquisition.operation.snapshot'

        def read_case(name,values,**extra):
            return run(name,[reader],dict(op='read',definition=grant['definition'],operation_id=op['operation_id'],events=values,**extra))[0]['results']
        duplicate=read_case('reader-duplicate-gap',[events[0],events[0],events[2],events[1]])
        assert [r.get('accepted') for r in duplicate]==[True,False,None,True]
        assert duplicate[2]['sequence']=='1' and duplicate[2]['digest']==records[0]['digest']
        for key,value in [('worker_epoch','worker:'+'f'*32),('attempt_id','attempt:'+'f'*32),
            ('process_id','123'),('definition_digest','sha256:'+'f'*64),('capture_epoch','changed')]:
            bad=copy.deepcopy(events[1]);bad['payload']['record']['state']['binding'][key]=value;rehash(bad)
            result=read_case('reader-binding-'+key,[events[0],bad,events[1]])
            assert result[1]['error'] and result[1]['sequence']=='1' and result[2]['accepted']
        # A validly hashed record still cannot claim contradictory coverage or regress it.
        bad=copy.deepcopy(events[2]);bad['payload']['record']['state'].update(checkpoint_bytes='0',source_bytes='0',substituted_bytes='0');rehash(bad)
        result=read_case('reader-coverage-regression',[events[0],events[1],bad,events[2]])
        assert result[2]['error']=='acquisition_worker_history_order' and result[2]['sequence']=='2' and result[3]['accepted']
        for name,change in [('counter-overflow',lambda s:s.update(checkpoint_bytes=str(2**64))),
            ('coverage-disagrees',lambda s:s.update(source_bytes='1')),
            ('nonquiescent-terminal',lambda s:s.update(quiescent=False)),
            ('incomplete-completed',lambda s:s.update(checkpoint_bytes='0',source_bytes='0',substituted_bytes='0'))]:
            bad=copy.deepcopy(events[-1]);change(bad['payload']['record']['state']);rehash(bad)
            result=run(name,[reader],dict(op='validate',definition=grant['definition'],event=bad))[0]
            assert result['error']
        assert read_case('reader-snapshot-unrequested',snap['result']['events'])[0]['error']=='watch_snapshot_unrequested'
        assert read_case('reader-snapshot-requested',snap['result']['events'],snapshot=True)[0]['accepted']
        for features,ndjson in [((FEATURE,),False),(('org.disked.fake-operation-events/1',),True),(('unknown',),True)]:
            refused,_=public('feature-gated','operation.watch',op,features,ndjson,(3,));assert refused['diagnostics'][0]['code']=='unsupported_feature'
        public('malformed-namespace','operation.inspect',dict(op,operation_id='other:'+ 'a'*32),exits=(2,))
        before={p.name:p.read_bytes() for p in Path(op['state_directory']).iterdir()}
        refused,_=public('wrong-namespace-no-fallback','operation.inspect',dict(op,operation_id='fake-op:'+'a'*32),exits=(2,))
        assert refused['diagnostics'][0]['code']=='operation_request_unavailable'
        assert before=={p.name:p.read_bytes() for p in Path(op['state_directory']).iterdir()}
        public('wrong-image-identity','operation.inspect',dict(op,operation_id='image-op:'+'f'*32),exits=(6,))
        unavailable,_=public('copy-still-unavailable','image.acquire',grant,exits=(3,))
        assert unavailable['diagnostics'][0]['code']=='command_unavailable'

        # Existing complete evidence is never repaired by an observation.
        path=Path(op['state_directory'])/'acquisition.records';original=path.read_bytes()
        path.write_bytes(original+b'{"partial":')
        torn,_=public('torn-watch','operation.watch',op,exits=(6,))
        assert torn['status']=='unknown' and torn['result']['last_sequence']==str(len(records))
        assert path.read_bytes()==original+b'{"partial":'
        corrupt=copy.deepcopy(records);corrupt[-1]['state']['source_bytes']='0'
        row=corrupt[-1];row.pop('digest');row['digest']=hashlib.sha256(canonical(row)).hexdigest()
        raw=b''.join(canonical(r)+b'\n' for r in corrupt);path.write_bytes(raw)
        public('corrupt-inspect','operation.inspect',op,exits=(6,));public('corrupt-watch','operation.watch',op,exits=(6,))
        assert path.read_bytes()==raw;path.write_bytes(original)

        params,grant=prepare('cancel',2097153);op=start('cancel',params,grant,True)
        cancelled,_=public('persist-cancel','operation.cancel.request',op)
        assert cancelled['result']['cancellation_request']=='requested'
        end=finish('cancel',op);state=end['result']['state']
        assert state['quiescent'] and state['outcome']['status']=='paused'
        assert Path(params['destination']).read_bytes()==Path(params['source']).read_bytes()[:int(state['checkpoint_bytes'])]
        watched,_=public('paused-watch-is-completed-observation','operation.watch',op)
        assert watched['status']=='completed' and watched['result']['state']['outcome']['status']=='paused'
        late,_=public('late-cancel','operation.cancel.request',op);assert late['result']['cancellation_request']=='too_late'
        events_check(watched['result']['events'],grant['definition'])
        verified.append(dict(name='paused-public-observation',bytes=state['checkpoint_bytes'],quiescent=True))

    report=dict(scope='public-acquisition-observation-private-copy-admission',checks=len(observations),
        verified=verified,physical_storage_qualified=False,public_copy_admitted=False,
        observations=observations,producer_events=producer)
    if a.evidence:Path(a.evidence).write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print('PASS public acquisition observations:',len(observations),'checks;',len(producer),'producer events')


if __name__=='__main__':main()
