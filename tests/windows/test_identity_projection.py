"""Owned complete-evidence references and compact identity rows through cached models."""
import argparse,copy,hashlib,json,struct,subprocess,time
from collections import Counter
from pathlib import Path
from test_identity_frame import fixture,identity_disk
from test_identity_queries import identifiers,entry,layout
from test_storage_queries import packet,digest,volume
from test_observation_frontend import selected_registry

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();probe=a.probe.absolute();code=hashlib.sha256(probe.read_bytes()).hexdigest();root=Path(__file__).resolve().parents[2]
    registry=selected_registry(root);checks=[];runs=[];children=set()
    def check(name,ok):checks.append(dict(label=name,passed=bool(ok)));assert ok,name
    def stage(value=None,**kw):return dict(fixture=fixture() if value is None else value,**kw)
    def run(name,stages=None,*,expected=0,error=None,quality=None,relation=None,**kw):
        value=dict(mode='identity-projection',registry=registry,stages=stages or [stage()],**kw);request=json.dumps(value,separators=(',',':'),ensure_ascii=True).encode()
        (out/(name+'.request.json')).write_bytes(request);start=time.monotonic();r=subprocess.run([probe],input=request,capture_output=True,timeout=45)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,exit_code=r.returncode,expected_exit=expected,elapsed_seconds=round(time.monotonic()-start,3)))
        check(name+' actual exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout)
        check(name+' architecture and actual frontend job',v['pointer_bytes']==str(a.pointer_bytes) and v['frontend_budget_ready'])
        check(name+' controller does not dispatch storage API',v['api_calls']=='0')
        for index,row in enumerate(v['stages']):
            samples=list(row['worker'].values())+[row[k] for k in ('live_worker','retirement') if k in row]
            for sample in samples:
                worker=sample['worker'];check(name+' actual native code',sample['code_sha256']==code)
                check(name+' no reader mutation',not sample['claims']['mutation_authority'] and not sample['claims']['physical_admission'])
                if int(worker['pid']):check(name+' actual child identity',int(worker['created'])>0);children.add((worker['pid'],worker['created']))
            check(name+' pure immutable projection',row['capture_unchanged'] and row['api_calls']=='0')
            if 'error' in row:
                check(name+' exact refusal',row['error']==error and row['previous_preserved']);continue
            graph=row['graph'];unbound=copy.deepcopy(graph);revision=unbound.pop('revision');check(name+' independent graph digest',revision==digest(unbound))
            check(name+' native domain and bounded history',row['domains_retained'] and (row['previous_object_expired'] or row['previous_retained_for_cache']) and row['oldest_reference_pruned'])
            check(name+' exact local-only retrieval refusal',row['unknown_reference_refused'])
            check(name+' graph/allocation publication preserves originals',row['graph_refusal']=='graph_limit' and row['publication_allocation_refused'])
            current=[n for n in graph['nodes'] if n['kind']=='storage-identity-observation' and n['properties']['state']!='stale']
            check(name+' original detail nodes and edges preserved',[n for n in graph['nodes'] if n['kind']!='storage-identity-observation']==row['base_graph']['nodes'] and [x for x in graph['edges'] if x['kind']!='reports-identity']==row['base_graph']['edges'])
            check(name+' every resource has compact evidence',{n['properties']['observation']['subject_key'] for n in current}=={x['key'] for x in row['frame']['resources']})
            for node in graph['nodes']:
                props=node['properties'];payload=props['observation'];binding=props['observation_binding']
                check(name+' content-bound evidence ID',node['id']=='observation:'+digest(dict(binding=binding,kind=node['kind'],label=props['label'],payload=payload))[7:])
                check(name+' no physical identity',props['scope']=='observation-only' and props['identity'] is None and props['physical_identity']=='unknown' and not props['physical_admission'] and not props['mutation_authority'])
            for node in current:
                payload=node['properties']['observation'];summary=payload['summary'];subject=payload['subject_key'];identity=row['identity'];resource=next(x for x in identity['resources'] if x['subject']==subject)
                check(name+' exact quality/fingerprint/observation ID',all(summary[k]==resource[k] for k in ('quality','reported_fingerprint','observation_id')))
                check(name+' no selected fact duplication','facts' not in summary and 'changes' not in summary and 'lookup_hints' not in summary)
                check(name+' claims remain scoped',summary['claims']==identity['claims'] and summary['claims']['physical_association']=='unproven' and summary['claims']['current_resource_freshness']=='unknown')
                groups=Counter();occurrences=Counter()
                for group in identity['collisions']:
                    matches=sum(x['subject']==subject for x in group['occurrences'])
                    if matches:groups[group['kind']]+=1;occurrences[group['kind']]+=matches
                check(name+' all collision groups/duplicates counted',summary['collisions']==[dict(kind=k,groups=str(groups[k]),occurrences=str(occurrences[k])) for k in sorted(groups)])
                check(name+' exact complete frame/identity references',payload['references']['frame']['digest']==digest(row['frame']) and payload['references']['identity']['digest']==digest(identity))
                if quality is not None and subject=='disk' and index==len(v['stages'])-1:check(name+' specified quality',summary['quality']==quality)
                if 'comparison' in summary:
                    comparison=next(c for c in row['comparisons'] if c['current_subject']==subject)
                    check(name+' exact scoped comparison',all(summary['comparison'][k]==comparison[k] for k in ('previous_subject','current_subject','relation','reported_relation','previous_quality','current_quality','continuity')))
                    check(name+' complete changed-component summary',summary['comparison']['changed_components']==[c['component'] for c in comparison['changes']])
                    if relation is not None and index==len(v['stages'])-1:check(name+' specified comparison relation',comparison['relation']==relation)
            for resolved in row['resolved']:
                ref=resolved['reference'];content=row['artifacts'][resolved['artifact']];check(name+' full exact resolved bytes',ref['digest']==digest(content) and resolved['artifact']==ref['kind']+':'+ref['digest'])
                check(name+' retrieval scope is data',ref['retrieval']=='retained-native-projection' and ref['scope']=='complete-evidence-only' and ref['kind'] in ('frame','identity','comparison'))
                if resolved['name']=='frame' and next(n for n in graph['nodes'] if n['id']==resolved['node'])['properties']['state']!='stale':check(name+' complete current frame retrieved',content==row['frame'])
                if resolved['name']=='identity' and next(n for n in graph['nodes'] if n['id']==resolved['node'])['properties']['state']!='stale':check(name+' complete current identity retrieved',content==row['identity'])
                if resolved['name']=='previous_frame' and next(n for n in graph['nodes'] if n['id']==resolved['node'])['properties']['state']!='stale':check(name+' complete previous frame survives previous object',content==v['stages'][index-1]['frame'])
                if resolved['name']=='previous_identity' and next(n for n in graph['nodes'] if n['id']==resolved['node'])['properties']['state']!='stale':check(name+' complete previous identity survives previous object',content==v['stages'][index-1]['identity'])
                check(name+' explicit retained resolver ownership',resolved['resolver'] in ('current-projection','last-complete-projection'))
            for comparison in row['comparisons']:
                previous_row=v['stages'][index-1];before=next(x for x in previous_row['identity']['resources'] if x['subject']==comparison['previous_subject'])['facts'];after=next(x for x in row['identity']['resources'] if x['subject']==comparison['current_subject'])['facts']
                expected_changes=[dict(component=k,previous=before.get(k),current=after.get(k)) for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
                check(name+' independent complete changed evidence',comparison['changes']==expected_changes and comparison['previous_digest']==digest(previous_row['identity']) and comparison['current_digest']==digest(row['identity']))
            check(name+' every graph reference resolved',len(row['resolved'])==sum(len(n['properties']['observation']['references']) for n in graph['nodes'] if n['kind']=='storage-identity-observation'))
            check(name+' all cached model rows inspected',[x['id'] for x in row['inspections']]==[n['id'] for n in graph['nodes']])
            for inspection,node in zip(row['inspections'],graph['nodes']):
                basis=inspection['direct']['result'];check(name+' exact inspection row',basis['node']==node and basis['node_scope']=='observation-only')
                check(name+' all cached model and display outcomes agree',all(inspection[k]==digest(basis) for k in ('gui','tui','shell','cli_human','gui_display','tui_display')) and inspection['cli_background']==digest(inspection['direct']))
                check(name+' no health or storage admission',inspection['health_refused'] and inspection['capability_unqualified'])
            if index:
                focus=row['focus'];old=next((n for n in graph['nodes'] if n['id']==focus['old_id']),None)
                check(name+' prior focus never rebinds',focus['selection']==dict(target_id=None,observation_id=focus['old_id'],scope='observation-only',state='present' if old else 'missing') and focus['present']==bool(old))
                check(name+' stale action refuses',focus['stale']['diagnostics'][0]['code']=='revision_conflict')
                check(name+' prior evidence inspect remains honest',focus['inspection']['result']['node']==old if old else focus['inspection']['diagnostics'][0]['code']=='target_not_found')
            if 'live_worker' in row:check(name+' presentation preserves live reader',row['live_worker']['worker']['observation']=='running' and row['live_outstanding'] and row['retirement']['worker']['observation']=='exited')
        return v
    try:
        run('complete',quality='complete_selected_reports')
        run('unchanged',[stage(),stage()],relation='unchanged-reported-evidence')
        changed=identity_disk(serial=b'NEW');run('changed',[stage(),stage(fixture(changed,volume()))],relation='changed-reported-evidence')
        weak=identity_disk(ids=identifiers([]));run('weak',[stage(),stage(fixture(weak,volume()))],quality='insufficient',relation='incomparable')
        duplicate=identity_disk(ids=identifiers([(1,3,0,b'ID'),(1,3,0,b'ID')]));run('duplicate-occurrences',[stage(fixture(duplicate,volume()))],quality='ambiguous')
        run('cloned-hints',[stage(fixture(identity_disk(),identity_disk('other')))],quality='ambiguous')
        denied=identity_disk();denied['replies']['alignment']=[packet(ok=False,error=5)];run('partial-cache',[stage(),stage(fixture(denied,volume()))],quality='insufficient',relation='incomparable')
        run('consecutive-partial-cache',[stage(),stage(fixture(denied,volume())),stage(fixture(denied,volume()))],quality='insufficient',relation='incomparable')
        conflict=identity_disk();conflict['replies']['length']=[packet(struct.pack('<q',4096))];run('conflict',[stage(fixture(conflict))],quality='conflicting')
        name=b'\x1b\0\x00\xdc'+b'A\0'*34;large=bytearray(layout(entries=[entry(number=i+1,start=4096+i*512,length=512,guid=(i+1).to_bytes(16,'little'),name=name) for i in range(64)]));struct.pack_into('<q',large,32,1048576-4096)
        ids=identifiers([(1,3,0,bytes([i+1])*100) for i in range(32)]);wide=identity_disk(ids=ids,table=bytes(large));v=run('maximum-original-detail',[stage(fixture(wide,volume()))])
        facts=next(x for x in v['stages'][0]['identity']['resources'] if x['subject']=='disk')['facts'];check('all32 original ID bytes within4096 response retained',len(facts['identifiers'])==32 and all(len(x['original_hex'])==200 for x in facts['identifiers']))
        check('all exact36 UTF16 units retained',len(facts['layout']['partitions'])==64 and all(x['gpt_name_hex']==name.hex() for x in facts['layout']['partitions']))
        longest=identity_disk(ids=identifiers([(1,3,0,b'L'*256)]));v=run('maximum-identifier-bytes',[stage(fixture(longest))]);facts=next(x for x in v['stages'][0]['identity']['resources'] if x['subject']=='disk')['facts'];check('full256 identifier bytes retained',facts['identifiers'][0]['original_hex']==(b'L'*256).hex())
        oversized=identity_disk(ids=identifiers([(1,3,0,bytes([i+1])*256) for i in range(32)]));v=run('identifier-response-budget',[stage(fixture(oversized))]);r=next(x for x in v['stages'][0]['identity']['resources'] if x['subject']=='disk');check('oversized response explicitly refused without widening4096',r['component_states']['identifiers']=='budget_exhausted' and 'identifiers' not in r['facts'])
        subjects=[identity_disk('disk' if i==0 else 'peer'+str(i),i,ids=identifiers([(1,3,0,bytes([i+1,j+1])) for j in range(8)]),serial=('S'+str(i)).encode()) for i in range(16)]
        v=run('shared-frame-detail-budget',[stage(fixture(*subjects))]);f=v['stages'][0]['frame'];details=sum(len(c['data']['identifiers'] if k=='identifiers' else c['data']['partitions']) for row in f['resources'] for k,c in row['components'].items() if k in ('identifiers','layout') and c['state']=='observed');check('all16 subjects share128 detail limit',details<=128 and f['status']=='partial' and len(f['resources'])==16)
        declarations=[dict(previous_subject=d['key'],current_subject=d['key']) for d in subjects]
        v=run('maximum-comparisons',[stage(fixture(*subjects)),stage(fixture(*subjects),comparisons=declarations)]);check('all16 explicit disk comparisons retained',len(v['stages'][1]['comparisons'])==16)
        run('pruned-history',[stage(),stage(),stage()])
        run('foreign-comparison',[stage(),stage(new_domain=True)],expected=3,error='storage_identity_comparison_domain')
        for fault in ('source','capture','worker','frame_digest','context_digest','domain_missing','domain_foreign','identity_mismatch'):
            run('binding-'+fault,[stage(),stage()],fault=fault,expected=3,error='storage_identity_projection_binding')
        for fault in ('identity_null','frame_null'):run('null-'+fault,fault=fault,expected=3,error='storage_identity_projection_input')
        for fault in ('previous_unused','previous_absent','comparison_limit'):run(fault,[stage(),stage()],fault=fault,expected=3,error='storage_identity_projection_comparisons')
        for fault,error in [('comparison_digest','storage_identity_comparison_binding'),('comparison_subject','storage_identity_subject'),('comparison_duplicate','storage_identity_projection_duplicate_subject')]:run(fault,[stage(),stage()],fault=fault,expected=3,error=error)
        run('allocation-refusal',[stage(),stage()],fault='allocation',expected=3,error='bad allocation')
        run('live-presentation',[stage(fixture(identity_disk(),reply_fault='hold'),live=True)])
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),executions=runs,checks=checks,probe_sha256='sha256:'+code)
    except Exception:
        (out/'results.json').write_text(json.dumps(dict(status='fail',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),executions=runs,checks=checks),indent=2)+'\n');raise
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','controller_executions','actual_child_launches','assertions')}))
if __name__=='__main__':main()
