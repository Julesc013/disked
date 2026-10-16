"""Closed native model histories, independently framed and hashed in Python.

Checks actual generated payloads, retained generations, selected append/crash
cuts and reader prefix controls. No file writer or hardware durability claim.
"""
import argparse,copy,json,subprocess
from pathlib import Path
from test_guarded import cases,frame_history,invariant
from test_definitions import canonical,sha,digests
from test_codec import header,record,H,P

PUB='41'*16
def projection(plan,journal):
    d=digests(plan);bindings=dict(journal='31'*16,plan=d['digest'][7:],targets=d['resources_digest'][7:],providers=d['providers_digest'][7:])
    hdr=header(bindings);parts=[];references={};sequences={};admission='';payloads=[]
    frames=journal['events']+([journal['tail_candidate']] if journal['tail'] else [])
    for frame in frames:
        kind=int(frame['kind']);data=frame['data']
        cap=lambda x:{k:copy.deepcopy(x[k]) for k in ('observer_id','capture_epoch','resources')}
        if kind<=3 or kind==4 and 'schema' in data:
            payload=copy.deepcopy(data)
            if kind==4:admission=sha(canonical(payload))
        elif kind==4:
            payload=dict(schema='org.disked.journal-checkpoint-admission-prototype/1',id='fake:checkpoint:'+frame['digest'][7:],plan_digest=d['digest'],basis_admission_digest=data['basis_admission_digest'],recovery_record_digest=references[data['recovery_frame_digest']],capture=cap(data['checkpoint']))
            payload.update({k:frame[k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')});admission=sha(canonical(payload))
        else:
            name=frame['step_id']
            if kind==5:event='intention';details=dict(capture=cap(data))
            if kind==6:event='verified_completion';details=dict(capture=cap(data),target_flush_capture_epoch=data['flush_capture_epoch'],qualified_fake_flush=data['qualified_fake_flush'])
            if kind==7:event='cancellation_request';details=dict(requested=data['requested']);name=data['pending_step']
            if kind==8:
                event='recovery_observation';details=dict(capture=cap(data),**{k:data[k] for k in ('flush_capture_epoch','qualified_fake_flush','worker_exited','exit_capture_epoch','observed')})
                if data['observed']=='terminal':name=''
            if kind==9:event='seal';name='';details=dict(capture=cap(data),**{k:data[k] for k in ('worker_exited','exit_capture_epoch','outcome','cancel_acknowledged')})
            attempt=frame['attempt_id'];sequences[attempt]=sequences.get(attempt,0)+1
            payload=dict(schema='org.disked.journal-effect-prototype/1',id='fake:event:'+frame['digest'][7:],plan_digest=d['digest'],admission_digest=admission,sequence=str(sequences[attempt]),step_id=name,event=event,details=details)
            payload.update({k:frame[k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')})
        previous=parts[-1][-32:] if parts else hdr[-32:]
        parts.append(record(hdr,len(parts)+1,previous,canonical(payload),kind,1,publisher=PUB));payloads.append(payload);references[frame['digest']]='sha256:'+parts[-1][-32:].hex()
    stable=H+sum(map(len,parts[:int(journal['stable_entries'])])) if int(journal['stable_entries']) else 0;tail=parts.pop() if journal['tail'] else b''
    return hdr+b''.join(parts)+tail[:len(tail)//2],stable,bindings,parts,payloads

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--semantic-probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();suite=[c for c in cases() if not c.root_error]
    profile=json.loads((a.root/'spec/catalog/journal-producer-prototype.json').read_bytes());assert profile['max_generations']==4 and profile['payload_bytes']==65536 and not any(profile[k] for k in ('authenticates','authorizes_effects','qualifies_durability'))
    p=subprocess.run([str(a.probe.resolve())],input=b''.join(canonical(c.request())+b'\n' for c in suite),capture_output=True,timeout=90)
    assert p.returncode==0 and not p.stderr;(outputs,observations,failed,controls)=(p.stdout.splitlines(),[],[],[]);assert len(outputs)==len(suite)
    generations=0;cuts=0;golden=None
    for c,line in zip(suite,outputs):
        out=json.loads(line);errors=[]
        try:
            assert 'error' not in out,out.get('error');frame_history(out,c.plan);assert invariant(out['final'])
            for result,check in zip(out['results'],c.checks):
                assert result['accepted']==(check['error'] is None) and result['error']==(check['error'] or ''),'action outcome disagrees with prior contract'
            assert len(out['binary_history'])==len(out['history'])
            for generation,(raw,produced) in enumerate(zip(out['history'],out['binary_history'])):
                generations+=1;expected,stable,binding,parts,payloads=projection(c.plan,raw);actual=bytes.fromhex(produced['bytes'])
                assert actual==expected,'binary differs from independent encoder';assert produced['stable_bytes']==str(stable)
                assert produced['disposition']==('torn_tail' if raw['tail'] else 'valid_prefix'),produced['semantic_diagnostic'] or produced['diagnostic']
                assert produced['records']==str(len(raw['events'])) and produced['verified_bytes']==str(H+sum(map(len,parts)))
                pr=produced['projection'];assert not any(pr[k] for k in ('authenticated','authorizes_effects','qualifies_durability','replay_authorized','retirement_authorized')) and pr['requires_live_reconciliation']
                # A copied lineage prefix must keep its exact encoded bytes.
                for old_raw,old in zip(out['history'][:generation],out['binary_history'][:generation]):
                    common=0
                    for x,y in zip(old_raw['events'],raw['events']):
                        if x!=y:break
                        common+=1
                    n=H+sum(map(len,parts[:common]));assert actual[:n]==bytes.fromhex(old['bytes'])[:n]
                # Every healthy binary record boundary plus partial prefix/body/
                # trailer cuts is independently inspected by the native reader.
                if c.name=='two-step-stable-completion' or raw['tail']:
                    ends=[H];end=H
                    for part in parts:end+=len(part);ends.append(end)
                    selected={H,*ends}
                    for start,end in zip(ends,ends[1:]):selected.update((start+1,start+P-1,start+P,end-1))
                    for n in sorted(selected):
                        prefix=max(e for e in ends if e<=n);count=ends.index(prefix)
                        controls.append(dict(request=dict(expected_plan=c.plan,bindings=binding,publisher=dict(identity=PUB,epoch='1'),bytes=actual[:n].hex()),expected=dict(disposition='valid_prefix' if n in ends else 'torn_tail',records=str(count),verified_bytes=str(prefix)),name=c.name+':'+str(generation)+':'+str(n)));cuts+=1
            if c.name=='two-step-stable-completion':golden=(c,copy.deepcopy(out['history']))
            if out['final']['operation_status'] in ('completed','cancelled'):assert out['binary_history'][-1]['projection']['declared_terminal_outcome']==out['final']['operation_status']
        except (AssertionError,KeyError,TypeError,ValueError) as error:errors.append(str(error))
        observations.append(dict(name=c.name,passed=not errors,errors=errors))
        if errors:failed.append(observations[-1])
    assert golden is not None
    c,original=golden;negative=[]
    def malformed(name,change,error):
        history=copy.deepcopy(original);change(history);request=c.request();request['history_override']=history;negative.append(dict(name=name,request=request,error=error))
    malformed('history-shape',lambda h:h[0].update(extra=True),'producer_shape')
    malformed('generation-budget',lambda h:h.extend(copy.deepcopy(h)*4),'producer_generation_limit')
    malformed('stable-prefix-budget',lambda h:h[0].update(stable_entries='513'),'producer_entry_limit')
    malformed('fake-digest',lambda h:h[0]['events'][4].update(digest='sha256:'+'f'*64),'producer_fake_chain')
    malformed('fake-order',lambda h:h[0]['events'][4].update(sequence='6'),'producer_fake_chain')
    malformed('fake-previous',lambda h:h[0]['events'][4].update(previous='sha256:'+'f'*64),'producer_fake_chain')
    malformed('fake-publisher',lambda h:h[0]['events'][4].update(publisher_identity='other'),'producer_fake_chain')
    malformed('history-digest',lambda h:h[0].update(digest='sha256:'+'f'*64),'producer_fake_history')
    malformed('frame-shape',lambda h:h[0]['events'][4].update(extra=True),'producer_shape')
    # A self-consistent but contradictory declaration is preserved as rejected
    # binary bytes, rather than repaired or blessed by the projection.
    history=copy.deepcopy(original);history[0]['events'][4]['data']['resources'][-1]['state_digest']='sha256:'+'f'*64
    previous=sha(canonical(c.plan));frames=history[0]['events']
    for frame in frames:
        frame['previous']=previous;body={k:v for k,v in frame.items() if k not in ('previous','digest')};frame['digest']=sha(b'DiskEd.fake.guard.log/1\n'+previous.encode()+canonical(body));previous=frame['digest']
    history[0]['digest']=sha(b''.join(canonical(f)+b'\n' for f in frames));request=c.request();request['history_override']=history
    negative.append(dict(name='contradictory-history-retained',request=request,semantic='semantic_capture_mismatch',history=history))
    x=subprocess.run([str(a.probe.resolve())],input=b''.join(canonical(v['request'])+b'\n' for v in negative),capture_output=True,timeout=90);assert x.returncode==0 and not x.stderr and len(x.stdout.splitlines())==len(negative)
    for case,line in zip(negative,x.stdout.splitlines()):
        out=json.loads(line);errors=[]
        try:
            if 'error' in case:assert out.get('error')==case['error'],out.get('error')
            else:
                generation=out['binary_history'][0];assert generation['semantic_diagnostic']==case['semantic'] and generation['disposition']=='invalid' and generation['records']=='4'
                expected,stable,*_=projection(c.plan,case['history'][0]);assert bytes.fromhex(generation['bytes'])==expected and int(generation['verified_bytes'])<len(expected)
        except (AssertionError,KeyError,TypeError) as error:errors.append(str(error))
        observations.append(dict(name=case['name'],passed=not errors,errors=errors))
        if errors:failed.append(observations[-1])
    q=subprocess.run([str(a.semantic_probe.resolve())],input=b''.join(canonical(x['request'])+b'\n' for x in controls),capture_output=True,timeout=90)
    assert q.returncode==0 and not q.stderr;assert len(q.stdout.splitlines())==len(controls)
    for case,line in zip(controls,q.stdout.splitlines()):
        out=json.loads(line);errors=[k for k,v in case['expected'].items() if out.get(k)!=v]
        observations.append(dict(name=case['name'],passed=not errors,errors=errors))
        if errors:failed.append(observations[-1])
    evidence=dict(passed=not failed,cases=len(suite),generations=generations,prefix_inspections=cuts,rejection_cases=len(negative),observations=observations,file_io=False,authenticated=False,authorizes_effects=False,qualifies_durability=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:15],indent=2)
    print(f'{len(suite)} native model histories / {generations} binary generations / {cuts} prefix inspections / {len(negative)} rejection cases passed; declaration fixtures only')
if __name__=='__main__':main()
