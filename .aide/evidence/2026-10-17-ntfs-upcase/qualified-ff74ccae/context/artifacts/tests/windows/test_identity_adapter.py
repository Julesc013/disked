"""Owned identity adapter publication, retained native evidence and cached presentation."""
import argparse,hashlib,json,struct,subprocess,time
from pathlib import Path
from test_identity_frame import fixture,identity_disk
from test_identity_queries import identifiers,entry,layout
from test_storage_queries import packet,digest,volume
from test_observation_frontend import selected_registry

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();probe=a.probe.absolute();code=hashlib.sha256(probe.read_bytes()).hexdigest();registry=selected_registry(Path(__file__).resolve().parents[2]);checks=[];runs=[];children=set()
    def check(name,ok):checks.append(dict(label=name,passed=bool(ok)));assert ok,name
    def stage(value=None,**kw):return dict(fixture=fixture() if value is None else value,**kw)
    declaration=dict(previous_subject='disk',current_subject='disk')
    def run(name,stages,*,states=None,start_error=None,relation=None,allocation=None,retained=False):
        request=json.dumps(dict(mode='identity-adapter',registry=registry,stages=stages),separators=(',',':'),ensure_ascii=True).encode();(out/(name+'.request.json')).write_bytes(request)
        start=time.monotonic();r=subprocess.run([probe],input=request,capture_output=True,timeout=60);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,exit_code=r.returncode,expected_exit=0,elapsed_seconds=round(time.monotonic()-start,3)));check(name+' actual exit',r.returncode==0 and not r.stderr);v=json.loads(r.stdout)
        check(name+' actual architecture/job and no controller native API',v['pointer_bytes']==str(a.pointer_bytes) and v['frontend_budget_ready'] and v['api_calls']=='0')
        check(name+' retained data after adapter destruction',v['retained_after_adapter_destruction']==retained)
        for i,row in enumerate(v['stages']):
            label=name+':'+str(i);graph=row['graph'];nodes=graph['nodes'];identity_nodes=[n for n in nodes if n['kind']=='storage-identity-observation'];owned=[n for n in nodes if n['properties']['scope']=='observation-only' and n['properties']['observation_binding']['source']=='storage']
            if states:check(label+' specified source state',row['source']['state']==states[i])
            check(label+' exited or never-launched source',not row['source']['outstanding'])
            check(label+' pure retrieval, native domains and cached presentation',row['pure_retrieval_and_presentation'] and row['domains_retained'])
            for worker in row['workers']:
                check(label+' exact child code/context',worker['code_sha256']==code and worker['claims']['physical_admission'] is False and worker['claims']['mutation_authority'] is False)
                if worker['worker']['pid'] is not None:
                    pid=worker['worker']['pid'];created=worker['worker']['created'];check(label+' actual native PID/time',int(pid)>0 and int(created)>0);children.add((pid,created))
            if row['workers']:
                check(label+' pending ownership retained',row['pending_evidence_preserved'] and row['pending_source']['outstanding'])
                check(label+' idempotent owned poll',row['duplicate_snapshot_preserved'] and row['duplicate_evidence_preserved'])
            if 'waiting_source' in row:check(label+' timeout/supersession retains reader and evidence',row['waiting_source']['outstanding'] and row['waiting_evidence_preserved'])
            if 'live_source' in row:check(label+' no replacement of actual held reader',row['replacement_refused'] and row['live_source']['outstanding'])
            if start_error and i==len(stages)-1:check(label+' typed prelaunch refusal',row['start_error']==start_error and not row['workers'] and not row['owner_changed'] and row['refused_start_key_unchanged'] and row['refused_start_capture_unchanged'])
            check(label+' every published complete reference resolved',len(row['resolved'])==sum(len(n['properties']['observation']['references']) for n in identity_nodes))
            for resolved in row['resolved']:
                ref=resolved['reference'];content=row['artifacts'][resolved['artifact']]
                check(label+' exact complete reference bytes',ref['digest']==digest(content) and resolved['artifact']==ref['kind']+':'+ref['digest'] and ref['retrieval']=='retained-native-projection')
                if ref['kind']=='frame':check(label+' actual owned frame schema',content['schema']=='org.disked.nt-storage-observation-prototype/2')
                if ref['kind']=='identity':check(label+' native identity scope retained',content['claims']['physical_association']=='unproven' and content['claims']['current_resource_freshness']=='unknown')
            for node in owned:
                q=node['properties'];payload=q['observation'];binding=q['observation_binding']
                check(label+' independent content-bound row',node['id']=='observation:'+digest(dict(binding=binding,kind=node['kind'],label=q['label'],payload=payload))[7:])
                check(label+' unchanged storage authority',q['physical_identity']=='unknown' and q['identity'] is None and not q['physical_admission'] and not q['mutation_authority'])
            if 'identity' in row:
                check(label+' exact retained capture and no unknown reference lookup',row['evidence_capture']==row['identity']['binding']['capture'] and row['unknown_reference_refused'])
                current=[n for n in identity_nodes if n['properties']['state']!='stale']
                for node in current:
                    payload=node['properties']['observation'];resource=next(x for x in row['identity']['resources'] if x['subject']==payload['subject_key'])
                    check(label+' exact compact identity evidence',all(payload['summary'][k]==resource[k] for k in ('quality','reported_fingerprint','observation_id')) and payload['references']['frame']['digest']==digest(row['frame']) and payload['references']['identity']['digest']==digest(row['identity']))
                    context=payload['worker_context'];check(label+' exact context digest',node['properties']['observation_binding']['context_digest']==digest(context) and context==row['context'] and context['code_sha256']==code)
                if row['owner_changed']:check(label+' all current resources represented',{n['properties']['observation']['subject_key'] for n in current}=={x['key'] for x in row['frame']['resources']})
                if i and row['owner_changed']:
                    prior=v['stages'][i-1]
                    for comparison in row['comparisons']:
                        before=next(x for x in prior['identity']['resources'] if x['subject']==comparison['previous_subject'])['facts'];after=next(x for x in row['identity']['resources'] if x['subject']==comparison['current_subject'])['facts']
                        expected=[dict(component=k,previous=before.get(k),current=after.get(k)) for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
                        check(label+' independent exact comparison',comparison['changes']==expected and comparison['previous_digest']==digest(prior['identity']) and comparison['current_digest']==digest(row['identity']))
                if relation and i==len(stages)-1:check(label+' explicit scoped relation',row['comparisons'][0]['relation']==relation)
                if row['owner_changed'] and row['source']['state']=='complete':check(label+' complete owner replaces both',row['complete_digest']==digest(row['identity']) and not any(n['properties']['state']=='stale' for n in owned))
                if i and row['owner_changed'] and row['source']['state']=='partial':check(label+' partial retains actual last complete digest',row['complete_digest']==v['stages'][i-1]['complete_digest'])
            check(label+' every owned row inspected by cached models',[x['id'] for x in row['inspections']]==[n['id'] for n in owned])
            for inspection,node in zip(row['inspections'],owned):
                basis=inspection['direct']['result'];check(label+' exact model/display semantics',basis['node']==node and all(inspection[k]==digest(basis) for k in ('gui','tui','shell','cli_human','gui_display','tui_display')) and inspection['cli_background']==digest(inspection['direct']) and inspection['health_refused'] and inspection['capability_unqualified'])
            if 'focus' in row and row['focus'] is not None:
                focus=row['focus'];old=next((n for n in nodes if n['id']==focus['old_id']),None)
                check(label+' exact stale/missing focus',focus['selection']['observation_id']==focus['old_id'] and focus['selection']['target_id'] is None and focus['present']==bool(old))
                check(label+' stale revision cannot act',focus['stale']['diagnostics'][0]['code']=='revision_conflict')
                check(label+' original focus inspection',focus['inspection']['result']['node']==old if old else focus['inspection']['diagnostics'][0]['code']=='target_not_found')
        if allocation:
            row=v['stages'][-1];check(name+' actual selected allocation failure',row['allocation_failed'] and v['allocation_checkpoint_hits']=='1')
            check(name+' publication/retirement boundary remains exact',row['allocation_snapshot_preserved']==(allocation!=3) and row['allocation_evidence_preserved']==(allocation!=3) and row['allocation_source']['outstanding'])
        return v
    try:
        run('complete',[stage()],states=['complete'])
        v=run('no-inferred-comparison',[stage(),stage()],states=['complete','complete']);check('same subjects do not infer comparison',v['stages'][1]['comparisons']==[])
        run('explicit-unchanged',[stage(),stage(comparisons=[declaration])],states=['complete','complete'],relation='unchanged-reported-evidence')
        changed=fixture(identity_disk(serial=b'NEW'),volume());run('explicit-changed',[stage(),stage(changed,comparisons=[declaration])],states=['complete','complete'],relation='changed-reported-evidence')
        weak=fixture(identity_disk(ids=identifiers([])),volume());run('weak',[stage(),stage(weak,comparisons=[declaration])],states=['complete','complete'],relation='incomparable')
        denied=identity_disk();denied['replies']['alignment']=[packet(ok=False,error=5)];partial=fixture(denied,volume())
        run('partial-cache',[stage(),stage(partial,comparisons=[declaration])],states=['complete','partial'],relation='incomparable')
        v=run('repeated-partial',[stage(),stage(partial),stage(partial)],states=['complete','partial','partial']);check('original complete identity survives repeated partial',v['stages'][2]['complete_digest']==digest(v['stages'][0]['identity']))
        run('recovered-complete',[stage(),stage(partial),stage()],states=['complete','partial','complete'])
        run('partial-without-complete',[stage(partial)],states=['partial'])
        duplicate=identity_disk(ids=identifiers([(1,3,0,b'ID'),(1,3,0,b'ID')]))
        for name,value in [('duplicate-occurrences',fixture(duplicate,volume())),('cloned-hints',fixture(identity_disk(),identity_disk('peer',1)))]:
            v=run(name,[stage(value)],states=['partial']);check(name+' ambiguity is evidence',next(x for x in v['stages'][0]['identity']['resources'] if x['subject']=='disk')['quality']=='ambiguous')
        run('held-reader',[stage(fixture(reply_fault='hold'))],states=['complete'])
        run('late-same-attempt',[stage(),stage(fixture(worker_fault='delay'),action='timeout')],states=['complete','complete'])
        v=run('superseded',[stage(),stage(fixture(worker_fault='delay'),action='superseded')],states=['complete','not_started']);check('late result cannot replace native owners',not v['stages'][1]['owner_changed'] and v['stages'][1]['identity']==v['stages'][0]['identity'])
        run('cancel-before',[stage(),stage(action='cancel-before')],states=['complete','partial'])
        run('cancel-during',[stage(),stage(fixture(worker_fault='delay'),action='cancel-during')],states=['complete','partial'])
        for fault in ('crash','native_table','native_error'):
            v=run('unknown-'+fault,[stage(),stage(fixture(worker_fault=fault))],states=['complete','unavailable']);check(fault+' preserves exact retained evidence',not v['stages'][1]['owner_changed'] and v['stages'][1]['identity']==v['stages'][0]['identity'])
        run('explicit-retirement',[stage(),stage(fixture(worker_fault='hang'),action='retire')],states=['complete','unavailable'])
        for point in (1,2,3):run('allocation-'+str(point),[stage(),stage(changed,allocation_checkpoint=str(point))],states=['complete','complete'],allocation=point)
        run('retained-consumer',[stage(retain=True),stage()],states=['complete','complete'],retained=True)
        run('missing-previous',[stage(comparisons=[declaration])],states=['not_started'],start_error='storage_graph_comparisons')
        bad=dict(declaration,previous_digest='sha256:'+'0'*64);run('wrong-digest',[stage(),stage(comparisons=[bad])],states=['complete','not_started'],start_error='storage_graph_comparison_selection')
        run('duplicate-selection',[stage(),stage(comparisons=[declaration,declaration])],states=['complete','not_started'],start_error='storage_graph_comparison_selection')
        run('selection-limit',[stage(),stage(comparisons=[declaration]*17)],states=['complete','not_started'],start_error='storage_graph_comparisons')
        run('missing-previous-subject',[stage(),stage(comparisons=[dict(previous_subject='absent',current_subject='disk')])],states=['complete','not_started'],start_error='storage_graph_comparison_subject')
        v=run('missing-current-subject',[stage(),stage(comparisons=[dict(previous_subject='disk',current_subject='absent')])],states=['complete','malformed']);check('post-receipt refusal retains owners',not v['stages'][1]['owner_changed'])
        subjects=[identity_disk('disk' if i==0 else 'peer'+str(i),i,serial=('S'+str(i)).encode()) for i in range(16)];declarations=[dict(previous_subject=x['key'],current_subject=x['key']) for x in subjects]
        v=run('all16-comparisons',[stage(fixture(*subjects)),stage(fixture(*subjects),comparisons=declarations)],states=['complete','complete']);check('all16 declared comparisons retained',len(v['stages'][1]['comparisons'])==16)
        name=b'\x1b\0\x00\xdc'+b'A\0'*34;table=bytearray(layout(entries=[entry(number=i+1,start=4096+i*512,length=512,guid=(i+1).to_bytes(16,'little'),name=name) for i in range(64)]));struct.pack_into('<q',table,32,1048576-4096)
        maximum=fixture(identity_disk(ids=identifiers([(1,3,0,bytes([i+1])*100) for i in range(32)]),table=bytes(table)),volume());v=run('maximum-details',[stage(maximum)],states=['complete']);check('complete original facts retained',len(v['stages'][0]['identity']['resources'][0]['facts']['layout']['partitions'])==64)
        v=run('coordinator-graph-refusal',[stage(),stage(maximum,action='graph-pressure')],states=['complete','malformed']);check('coordinator budget refusal keeps original owners',not v['stages'][1]['owner_changed'] and v['stages'][1]['identity']==v['stages'][0]['identity'])
        v=run('pruned-history',[stage(),stage(),stage(),stage()],states=['complete']*4);check('native evidence wrappers do not retain a chain',all(row['old_evidence_expired'] for row in v['stages']))
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),executions=runs,checks=checks,probe_sha256='sha256:'+code)
    except Exception:
        (out/'results.json').write_text(json.dumps(dict(status='fail',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),executions=runs,checks=checks),indent=2)+'\n');raise
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','controller_executions','actual_child_launches','assertions')}))
if __name__=='__main__':main()
