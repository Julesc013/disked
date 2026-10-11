"""Composite reported identity and epoch comparison over real owned injected readers."""
import argparse,copy,hashlib,json,struct,subprocess,time,uuid
from pathlib import Path
from test_identity_frame import identity_disk,fixture
from test_identity_queries import identifiers,alignment,entry,layout
from test_storage_queries import disk,volume,packet,digest,descriptor

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--metadata-probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();checks=[];runs=[];children=set();probe=a.probe.absolute();metadata=a.metadata_probe.absolute();codes={x:hashlib.sha256(x.read_bytes()).hexdigest() for x in (probe,metadata)}
    def check(label,ok):checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def phase(f=None,**kw):return dict(fixture=fixture(identity_disk()) if f is None else f,**kw)
    def resource(v,key='disk'):return next(x for x in v['identity']['resources'] if x['subject']==key)
    def run(name,stages=None,*,expected=0,relation=None,reported_relation=None,qualities=None,selected=probe,**kw):
        value=dict(stages=[phase()] if stages is None else stages,**kw);payload=json.dumps(value,separators=(',',':')).encode();(out/(name+'.request.json')).write_bytes(payload);start=time.monotonic()
        r=subprocess.run([selected],input=payload,capture_output=True,timeout=30);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,probe=selected.name,exit_code=r.returncode,expected_exit=expected,expected_relation=relation,expected_reported_relation=reported_relation,expected_qualities=qualities,elapsed_seconds=round(time.monotonic()-start,3)))
        check(name+' exact exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout);check(name+' architecture',v['pointer_bytes']==str(a.pointer_bytes))
        for index,row in enumerate(v.get('observations',[])):
            samples=list(row.get('samples',[]))+[row[k] for k in ('worker','retirement','live_worker') if k in row]
            for sample in samples:
                w=sample['worker'];check(name+' native code',sample['code_sha256']==codes[selected]);check(name+' no worker authority',not sample['claims']['physical_admission'] and not sample['claims']['mutation_authority'])
                if int(w['pid']):check(name+' native creation',int(w['created'])>0);children.add((w['pid'],w['created']))
            if row.get('identity_available'):
                identity=row['identity'];binding=identity['binding'];context=row['context'];frame=row['frame'];last=row['samples'][-1]
                check(name+' independent observation digest',row['identity_digest']==digest(identity))
                check(name+' exact frame/context digest',binding['frame_digest']==digest(frame) and binding['context_digest']==digest(context))
                check(name+' actual owned context',identity['worker_context']==context and context['pid']==last['worker']['pid'] and context['created']==last['worker']['created'] and context['code_sha256']==codes[selected])
                check(name+' exact epochs',binding['source']=='storage' and binding['capture']==frame['capture_epoch'] and binding['worker']==row['capture']['sources'][0]['worker'] and binding['domain']==row['capture']['domain'])
                check(name+' selected schema',identity['schema']=='org.disked.nt-composite-identity-prototype/1' and context['storage_profile']=='identity-layout')
                check(name+' conservative claims',identity['claims']==dict(owned_process_binding_verified=True,physical_identity='unknown',physical_association='unproven',current_resource_freshness='unknown',capture_consistency='sequential-not-atomic',complete_alias_proof=False,mutation_authority=False,atomic_snapshot=False))
                check(name+' original frame claim',not frame['claims']['raw_metadata_independently_verified'] and not frame['claims']['mutation_authority'])
                check(name+' pure derivation',row['derivation_api_calls']=='0')
                check(name+' actual owned graph retains typed domain',row['graph_domains_retained'])
                check(name+' every original subject',{x['subject'] for x in identity['resources']}=={x['key'] for x in frame['resources']})
                for item in identity['resources']:
                    original=next(x for x in frame['resources'] if x['key']==item['subject']);facts=item['facts']
                    check(name+' complete lookup hint',item['lookup_hints']['label']==original['label'])
                    check(name+' original conflicts retained',item['reported_conflicts']==original['conflicts'])
                    check(name+' exact selected fingerprint',item['reported_fingerprint']==digest(facts))
                    check(name+' evidence ID independently derived',item['observation_id']=='identity-observation:'+digest(dict(binding=binding,subject=item['subject'],kind=item['kind']))[7:])
                    check(name+' unavailable identity layers explicit',item['not_observed']==['controller_path','lun','namespace','exclusive_ownership','media_generation'])
                    comp=original['components']
                    if 'identifiers' in facts:
                        wanted=sorted((x['code_set'],x['type'],x['association'],x['original_hex']) for x in comp['identifiers']['data']['identifiers'])
                        check(name+' every identifier represented',sorted((x['code_set'],x['type'],x['association'],x['original_hex']) for x in facts['identifiers'])==wanted)
                    if 'layout' in facts:
                        wanted=[x for x in comp['layout']['data']['partitions'] if x['active']];actual=facts['layout']['partitions']
                        check(name+' every active partition represented',len(actual)==len(wanted))
                        for x in wanted:
                            check(name+' exact partition extent',any(y['offset_bytes']==x['offset_bytes'] and y['length_bytes']==x['length_bytes'] and (y.get('gpt_partition_guid_hex')==x.get('gpt_partition_guid_hex')) for y in actual))
                        if comp['layout']['data']['partition_style']=='1':check(name+' every GUID/name/attribute retained',sorted((x['gpt_partition_guid_hex'],x['gpt_attributes'],x['gpt_name']['original_hex']) for x in wanted)==sorted((x['gpt_partition_guid_hex'],x['gpt_attributes'],x['gpt_name_hex']) for x in actual))
                if qualities is not None:check(name+' expected selected quality '+str(index),resource(row)['quality']==qualities[index])
            if 'capture' in row:check(name+' exact retirement reconciled',not row['capture']['sources'][0]['outstanding'])
        if relation:
            c=v['comparison'];check(name+' expected relation',c['relation']==relation)
            if reported_relation:check(name+' expected selected-field relation',c['reported_relation']==reported_relation)
            check(name+' comparison exact bindings',c['previous_digest']==v['observations'][0]['identity_digest'] and c['current_digest']==v['observations'][-1]['identity_digest'])
            check(name+' no freshness or authority',c['claims']['current_resource_freshness']=='unknown' and not c['claims']['mutation_authority'] and c['claims']['physical_association']=='unproven')
        if 'api_calls' in v:check(name+' no parent API dispatch',v['api_calls']=='0')
        return v
    def pair(name,changed=None,**kw):return run(name,[phase(),phase(fixture(changed) if changed is not None else None)],**kw)
    def reply(d,component,body):
        if component=='descriptor':d['replies'][component]=[packet(body[:8]),packet(body)]
        elif component=='identifiers':d['replies'][component]=[packet(body[:8]),packet(body)]
        elif component=='layout':
            growth=[];size=192
            while len(body)>size:growth.append(packet(ok=False,error=122));size*=2
            d['replies'][component]=growth+[packet(body)]
        else:d['replies'][component]=[packet(body)]
        return d
    try:
        v=pair('unchanged',relation='unchanged-reported-evidence',qualities=['complete_selected_reports']*2)
        check('same reported facts different actual observations',v['observations'][0]['identity_digest']!=v['observations'][1]['identity_digest'] and resource(v['observations'][0])['reported_fingerprint']==resource(v['observations'][1])['reported_fingerprint'])
        changes=[]
        changes.append(('serial',identity_disk(serial=b'NEW-SERIAL'),['descriptor']))
        changes.append(('identifier',identity_disk(ids=identifiers([(1,3,0,b'NEW-ID')])),['identifiers']))
        d=identity_disk();reply(d,'geometry',struct.pack('<QIIIIQ',0,12,0,0,512,2*1048576));reply(d,'length',struct.pack('<Q',2*1048576));changes.append(('capacity',d,['geometry','length']))
        d=identity_disk();reply(d,'geometry',struct.pack('<QIIIIQ',0,12,0,0,4096,1048576));reply(d,'alignment',alignment(4096,4096,0));changes.append(('logical-unit',d,['alignment','geometry']))
        d=identity_disk();reply(d,'alignment',alignment(512,4096,512));changes.append(('alignment-offset',d,['alignment']))
        for name,offset,width,value in [('disk-guid',8,16,b'NEW-DISK'.ljust(16,b'\0')),('partition-guid',48+48,16,b'NEW-PART'.ljust(16,b'\0')),('attribute',48+64,8,struct.pack('<Q',2**64-1)),('name',48+72,72,struct.pack('<36H',*[0x41+i for i in range(32)],0,0xd800,0x1b,0xffff))]:
            d=identity_disk();body=bytearray(bytes.fromhex(d['replies']['layout'][-1]['hex']));body[offset:offset+width]=value;reply(d,'layout',bytes(body));changes.append((name,d,['layout']))
        for name,d,wanted in changes:
            v=pair('change-'+name,d,relation='changed-reported-evidence',qualities=['complete_selected_reports']*2);check(name+' exact changed components',[x['component'] for x in v['comparison']['changes']]==wanted)
        d=identity_disk();reply(d,'number',struct.pack('<III',7,7,0));d['label_hex']='strange\x1b[31m\x00\ud800'.encode('utf-16-le','surrogatepass').hex();v=pair('lookup-hints',d,relation='unchanged-reported-evidence',qualities=['complete_selected_reports']*2)
        check('hints change full frame',v['observations'][0]['identity']['binding']['frame_digest']!=v['observations'][1]['identity']['binding']['frame_digest'])
        d=identity_disk();d['key']='renamed';v=pair('explicit-lookup-continuity',d,current_subject='renamed',relation='unchanged-reported-evidence');check('subject does not become identity',resource(v['observations'][0])['reported_fingerprint']==resource(v['observations'][1],'renamed')['reported_fingerprint'])
        pair('no-automatic-subject-rebinding',d,expected=3)
        ids=[(1,3,0,b'A'),(2,2,0,b'B'),(3,8,1,b'P')];run('identifier-order',[phase(fixture(identity_disk(ids=identifiers(ids)))),phase(fixture(identity_disk(ids=identifiers(list(reversed(ids))))))],relation='unchanged-reported-evidence',qualities=['complete_selected_reports']*2)
        entries=[entry(number=i+1,start=4096+i*8192,guid=uuid.UUID(int=i+1).bytes_le) for i in range(2)];tables=[]
        for rows in (entries,list(reversed(entries))):
            body=bytearray(layout(entries=rows));struct.pack_into('<q',body,32,1048576-4096);tables.append(bytes(body))
        run('partition-order',[phase(fixture(identity_disk(table=t))) for t in tables],relation='unchanged-reported-evidence',qualities=['complete_selected_reports']*2)
        for name,ids in [('no-ids',[]),('empty-id',[(1,3,0,b'')]),('zero-id',[(1,3,0,b'\0'*8)]),('unsupported-id',[(4,999,0,b'ID')]),('port-associated-id',[(1,3,1,b'ID')]),('target-associated-id',[(1,3,2,b'ID')])]:
            d=identity_disk(ids=identifiers(ids));run(name,[phase(fixture(d)),phase(fixture(d))],relation='incomparable',reported_relation='unchanged-reported-evidence',qualities=['insufficient']*2)
        for name,serial,quality in [('absent-serial',None,'complete_selected_reports'),('empty-serial',b'','complete_selected_reports'),('non-ascii-serial',b'\xff','insufficient')]:
            d=identity_disk(serial=serial);v=run(name,[phase(fixture(d)),phase(fixture(d))],relation='unchanged-reported-evidence' if quality=='complete_selected_reports' else 'incomparable',qualities=[quality]*2);check(name+' exact serial bytes',resource(v['observations'][0])['facts']['descriptor']['serial']['original_hex']==(serial or b'').hex())
        for name in ('serial','identifier','disk-guid','partition-guid','number'):
            a0=identity_disk('disk',0,serial=b'S0');b0=identity_disk('peer',1,serial=b'S1')
            if name=='serial':a0=identity_disk('disk',0,serial=b'CLONED');b0=identity_disk('peer',1,serial=b'CLONED')
            elif name=='identifier':
                for d in (a0,b0):reply(d,'identifiers',identifiers([(1,3,0,b'CLONED')]))
            elif name=='number':reply(b0,'number',struct.pack('<III',7,0,0))
            else:
                body=bytearray(bytes.fromhex(b0['replies']['layout'][-1]['hex']));source=bytes.fromhex(a0['replies']['layout'][-1]['hex']);offset=8 if name=='disk-guid' else 96;body[offset:offset+16]=source[offset:offset+16];reply(b0,'layout',body)
            v=run('repeated-'+name,[phase(fixture(a0,b0)),phase(fixture(a0,b0))],relation='incomparable',qualities=['ambiguous']*2);groups=v['observations'][0]['identity']['collisions'];check(name+' exact duplicate group',len(groups)==1 and len(groups[0]['occurrences'])==2)
            check(name+' separate evidence records',len(v['observations'][0]['identity']['resources'])==2 and len({x['observation_id'] for x in v['observations'][0]['identity']['resources']})==2)
        d=identity_disk(ids=identifiers([(1,3,0,b'REPEAT')]*2));v=run('duplicate-in-one-reply',[phase(fixture(d))],qualities=['ambiguous']);check('both duplicate occurrences retained',len(resource(v['observations'][0])['facts']['identifiers'])==2 and [x['ordinal'] for x in v['observations'][0]['identity']['collisions'][0]['occurrences']]==['1','2'])
        a0=identity_disk('disk',0,ids=identifiers([(1,3,0,b'SAME')]),serial=b'S0');b0=identity_disk('peer',1,ids=identifiers([(1,2,0,b'SAME')]),serial=b'S1');v=run('different-identifier-type',[phase(fixture(a0,b0))]);check('different types no merge',v['observations'][0]['identity']['collisions']==[])
        for name,d in [('capacity',reply(identity_disk(),'length',struct.pack('<Q',1048577))),('alignment',reply(identity_disk(),'alignment',alignment(4096,4096,0)))] :
            run('contradiction-'+name,[phase(fixture(d)),phase(fixture(d))],relation='incomparable',reported_relation='unchanged-reported-evidence',qualities=['conflicting']*2)
        for count,length in [(10,16),(32,100),(1,256)]:
            ids=[(1,3,0,bytes([i+1])*length) for i in range(count)];d=identity_disk(ids=identifiers(ids));v=run('many-ids-'+str(count)+'-'+str(length),[phase(fixture(d))],qualities=['complete_selected_reports']);check('all exact bytes '+str(count),len(resource(v['observations'][0])['facts']['identifiers'])==count and all(len(x['original_hex'])==length*2 for x in resource(v['observations'][0])['facts']['identifiers']))
        entries=[entry(number=i+1,start=4096+i*8192,guid=uuid.UUID(int=i+1).bytes_le) for i in range(64)];body=bytearray(layout(entries=entries));struct.pack_into('<q',body,32,1048576-4096);d=identity_disk(table=bytes(body));v=run('64-partitions',[phase(fixture(d))],qualities=['complete_selected_reports']);check('all64 selected partitions',len(resource(v['observations'][0])['facts']['layout']['partitions'])==64)
        subjects=[identity_disk('disk' if i==0 else 'peer'+str(i),i,ids=identifiers([(1,3,0,bytes([i+1,j+1])) for j in range(8)]),serial=('S'+str(i)).encode()) for i in range(16)];v=run('frame-detail-boundary',[phase(fixture(*subjects))]);frame=v['observations'][0]['frame'];count=sum(len(c['data']['identifiers'] if k=='identifiers' else c['data']['partitions']) for row in frame['resources'] for k,c in row['components'].items() if k in ('identifiers','layout') and c['state']=='observed');check('bounded128 detail representation',count<=128 and frame['status']=='partial')
        run('volume-not-selected',[phase(fixture(identity_disk(),volume()))]);
        for component in ('descriptor','geometry','length','identifiers','alignment','layout'):
            d=identity_disk();d['replies'][component]=[packet(ok=False,error=5)];v=run('denied-'+component,[phase(fixture(d))],qualities=['insufficient']);check(component+' state not hidden',resource(v['observations'][0])['component_states'][component]!='observed')
        d=identity_disk();d['replies']['descriptor']=[packet(ok=False,error=997)];v=run('pending-io',[phase(fixture(d))],qualities=['insufficient']);check('pending remains unresolved',v['observations'][0]['frame']['status']=='unresolved')
        v=run('cancel-before',[phase(cancel=True)],qualities=['insufficient']);check('cancelled reported scope',v['observations'][0]['frame']['status']=='cancelled')
        v=run('superseded',[phase(fixture(identity_disk(),worker_fault='delay'),supersede=True)]);check('superseded cannot create identity',not v['observations'][0]['identity_available'])
        v=run('late-same-attempt',[phase(fixture(identity_disk(),worker_fault='delay'),timeout=True)],qualities=['complete_selected_reports']);check('late exact attempt retains evidence',v['observations'][0]['identity_available'])
        v=run('held-publication',[phase(fixture(identity_disk(),reply_fault='hold'))],qualities=['complete_selected_reports'])
        v=run('live-identity-preview',[phase(fixture(identity_disk(),reply_fault='hold'),live=True)],qualities=['complete_selected_reports']);row=v['observations'][0];check('preview is exact immutable observation',row['live_identity_digest']==row['identity_digest']);check('preview does not retire its reader',row['live_worker']['worker']['observation']=='running' and row['live_capture']['sources'][0]['outstanding'])
        v=run('hung-retirement',[phase(fixture(identity_disk(),worker_fault='hang'),retire=True)]);check('hang no manufactured identity',not v['observations'][0]['identity_available'] and v['observations'][0]['samples'][-1]['worker']['observation']=='exited')
        for fault in ('before_spawn','after_spawn','after_spawn_alloc'):
            v=run('startup-'+fault,[phase(fixture(identity_disk(),startup_fault=fault))]);check(fault+' no identity',not v['observations'][0]['identity_available'])
        for fault in ('code','request','scope','host','observer','attempt','pid','created','capture','worker','schema','digest','claims'):
            v=run('reply-'+fault,[phase(fixture(identity_disk(),reply_fault=fault))]);check(fault+' cannot manufacture identity',not v['observations'][0]['identity_available'])
        for key,value in [('source','other'),('capture','0'),('worker','0'),('frame_digest','sha256:'+'0'*64),('context_digest','sha256:'+'0'*64)]:
            v=run('construction-'+key,[phase(binding={key:value})],expected=3);check(key+' refusal retains frame',bool(v['observations'][0]['frame']) and v['observations'][0]['construction_error']=='storage_identity_binding')
        for key,value in [('previous_digest','sha256:'+'0'*64),('current_digest','sha256:'+'0'*64),('previous_subject','other'),('current_subject','other')]:
            v=pair('comparison-'+key,expected=3,comparison={key:value});check(key+' retains both originals',all(x['identity_available'] for x in v['observations']))
        for kind in ('missing','foreign'):
            v=run('construction-domain-'+kind,[phase(binding=dict(domain=kind))],expected=3);check(kind+' typed domain cannot be manufactured',v['observations'][0]['construction_error']=='storage_identity_binding')
        v=run('foreign-coordinator',[phase(),phase(new_domain=True),phase()],expected=3)
        previous=v['observations'][0]['identity']['binding'];current=v['observations'][-1]['identity']['binding']
        check('otherwise admissible counters remain foreign',previous['source']==current['source'] and int(current['capture'])>int(previous['capture']) and int(current['worker'])>int(previous['worker']) and previous['domain']!=current['domain'])
        check('actual foreign token refuses comparison',v['comparison_error']=='storage_identity_comparison_domain' and all(x['identity_available'] for x in v['observations']))
        v=run('equal-counters-foreign-coordinator',[phase(),phase(new_domain=True)],expected=3)
        check('foreign token checked before numeric ordering',v['comparison_error']=='storage_identity_comparison_domain')
        v=run('serialized-domain-not-a-token',[phase(binding=dict(domain='capture-domain-local:1'))],expected=3);check('serialized token label refused before launch','observations' not in v)
        v=pair('reversed-epochs',expected=3,reverse=True);check('reverse cannot appear current',v['comparison_error']=='storage_identity_comparison_epoch')
        v=pair('same-capture-no-replacement',same_capture=True);check('same capture cannot start replacement',v['observations'][1]['startup_error']=='capture_attempt_already_started' and not v['observations'][1]['identity_available'])
        v=run('reject-owned-metadata-profile',[dict(fixture=dict(subjects=[disk()]))],selected=metadata,expected=3);check('actual metadata profile refused',v['observations'][0]['construction_error']=='storage_identity_profile')
        v=run('invalid-later-stage',[phase(),dict(fixture=dict(profile='wrong',subjects=[disk()]))],expected=3);check('all stages validated before launch','observations' not in v)
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=runs,children=sorted(children),physical_identity='unknown',current_resource_freshness='unknown',mutation_authority=False,unit_complete=False)
    except BaseException as error:
        result=dict(status='fail',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=runs,error=str(error));raise
    finally:
        if 'result' in locals():(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],controllers=len(runs),children=len(children),assertions=len(checks))))

if __name__=='__main__':main()
