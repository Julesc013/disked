"""Verify retained bytes, source blobs, native artifacts and partial handoff; no launches."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--output',type=Path);args=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-inventory-port'
    def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
    def file_sha(n):return sha((root/n).read_bytes())
    def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
    inventory=record(e/'inventory.json');source=inventory['source_revision'];repro=e/('reproduction-'+source[:8]);inputs=record(repro/'source-inputs.json');blobs=record(repro/'source-blob-bindings.json');assert set(inputs)==set(blobs)
    assert all(file_sha(n)==d for n,d in inputs.items())
    for x in inventory['evidence']+inventory['artifacts']:
        assert file_sha(x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes'],x['path']
    for x in inventory['compressed']:
        data=gzip.decompress((root/x['encoded_path']).read_bytes());assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256'],x['encoded_path']
    assert not any(f.suffix.lower() in ('.img','.exe','.dll','.obj','.pdb') for f in e.rglob('*') if f.is_file())
    result=record(e/'validation-summary.json');assert result['status']=='pass' and result['source_revision']==source and not result['owner_accepted'] and not result['unit_complete'] and result['private_identity_projection_qualified'] and result['private_identity_adapter_qualified'] and result['private_inventory_port_qualified']
    campaigns=result['campaigns'];assert len(campaigns)==28;assert sum(c['controllers']+c['child_launches'] for c in campaigns)==result['native_processes'];assert sum(c['assertions'] for c in campaigns)==result['native_assertions']
    product=record(repro/'product-build-identity.json');assert len(product['inputs'])==404 and all(file_sha(n)==d for n,d in product['inputs'].items()) and product['identity']['source_revision']==source and product['identity']['source_state']=='clean'
    assert result['product_rebuilt'] and result['product_suite_rerun'] and result['native_ctest_groups']==77
    launch=record(repro/'logs/product-launch.log')['result'];assert launch['source_revision']==source and launch['version']==result['product_version']
    assert b'0 tests failed out of 77' in (repro/'logs/product-native.log').read_bytes()
    assert len(inventory['artifacts'])==32
    for c in campaigns:
        r=record(repro/(c['kind']+'-'+c['architecture'])/'results.json');assert r['status']=='pass' and r['pointer_bytes']==c['pointer_bytes'] and r['assertions']==c['assertions'] and all(x['passed'] for x in r.get('checks',[]))
    for arch,pointer,machine in [('x64',8,0x8664),('Win32',4,0x14c)]:
        layout=record(repro/('owned-layout-'+arch)/'results.json');assert (layout['controller_executions'],layout['actual_child_launches'],layout['assertions'])==(80,106,1411)
        artifact=next(x for x in inventory['artifacts'] if x['kind']=='owned-layout' and x['architecture']==arch);data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0];assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+4)[0]==machine
        code=artifact['sha256'][7:];children=set()
        for run in layout['executions']:
            if run['expected_exit']==2:continue
            v=record(repro/('owned-layout-'+arch)/(run['label']+'.stdout'));assert v['pointer_bytes']==str(pointer)
            rows=list(v.get('image_samples',[]))+list(v.get('storage_samples',[]));rows.extend(v[k] for k in ('image_worker','before','cancelled','retirement') if k in v)
            for row in rows:
                assert row['code_sha256']==code and not row['claims']['mutation_authority'] and not row['claims']['physical_admission']
                native=row['worker']
                if int(native['pid']):assert int(native['created'])>0;children.add((native['pid'],native['created']))
            if 'comparison' in v:
                claims=v['comparison']['claims'];assert claims['owned_process_bindings_verified'] and claims['physical_association']=='unproven' and claims['current_resource_freshness']=='unknown' and not claims['mutation_authority'] and not claims['atomic_snapshot']
                assert not v['comparison']['common_fields']['claims']['owned_reader_authenticated'] and v['comparison_api_calls']=='0'
        assert len(children)==106
    def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())
    wanted_claims=dict(owned_process_binding_verified=True,physical_identity='unknown',physical_association='unproven',current_resource_freshness='unknown',capture_consistency='sequential-not-atomic',complete_alias_proof=False,mutation_authority=False,atomic_snapshot=False)
    for arch,pointer,machine in [('x64',8,0x8664),('Win32',4,0x14c)]:
        campaign=repro/('identity-observation-'+arch);identity=record(campaign/'results.json');assert (identity['controller_executions'],identity['actual_child_launches'],identity['assertions'])==(86,122,3513)
        codes={}
        for kind,name in [('identity-observation','nt_identity_observation_probe.exe'),('identity-profile','nt_identity_profile_probe.exe')]:
            artifact=next(x for x in inventory['artifacts'] if x['kind']==kind and x['architecture']==arch);data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0];assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+4)[0]==machine;codes[name]=artifact['sha256'][7:]
        children=set()
        for run in identity['executions']:
            value=record(campaign/(run['label']+'.stdout'));assert value['pointer_bytes']==str(pointer)
            if 'api_calls' in value:assert value['api_calls']=='0'
            for row in value.get('observations',[]):
                samples=list(row.get('samples',[]))+[row[k] for k in ('worker','retirement','live_worker') if k in row]
                for sample in samples:
                    assert sample['code_sha256']==codes[run['probe']] and not sample['claims']['mutation_authority'] and not sample['claims']['physical_admission']
                    native=sample['worker']
                    if int(native['pid']):assert int(native['created'])>0;children.add((native['pid'],native['created']))
                if row.get('identity_available'):
                    observed=row['identity'];binding=observed['binding'];context=row['context'];assert observed['claims']==wanted_claims and row['derivation_api_calls']=='0'
                    assert row['graph_domains_retained'] and binding['domain']==row['capture']['domain'] and binding['worker']==row['capture']['sources'][0]['worker']
                    assert row['identity_digest']==digest(observed) and binding['frame_digest']==digest(row['frame']) and binding['context_digest']==digest(context) and observed['worker_context']==context and context['code_sha256']==codes[run['probe']]
                    assert {x['subject'] for x in observed['resources']}=={x['key'] for x in row['frame']['resources']}
                    for resource in observed['resources']:
                        original=next(x for x in row['frame']['resources'] if x['key']==resource['subject']);assert resource['reported_fingerprint']==digest(resource['facts']) and resource['reported_conflicts']==original['conflicts']
                        assert resource['observation_id']=='identity-observation:'+digest(dict(binding=binding,subject=resource['subject'],kind=resource['kind']))[7:]
                if 'live_worker' in row:
                    assert row['live_worker']['worker']['observation']=='running' and row['live_capture']['sources'][0]['outstanding'] and row['live_identity_digest']==row['identity_digest']
            if value.get('comparison'):
                comparison=value['comparison'];assert comparison['claims']==wanted_claims and comparison['previous_digest']==value['observations'][0]['identity_digest'] and comparison['current_digest']==value['observations'][-1]['identity_digest']
        assert len(children)==122
    reducer=record(repro/'capture-domain-reducer-results.json');artifact=next(x for x in inventory['artifacts'] if x['kind']=='capture-reducer');assert reducer['passed'] and reducer['tests']==25 and reducer['sha256']==artifact['sha256'][7:]
    assert 'DISKED_CAPTURE_DOMAIN_EXHAUSTION_TESTING' not in (repro/'product-build-configuration/disked_presentation.vcxproj').read_text()
    for arch in ('x64','Win32'):
        campaign=repro/('capture-domain-limit-'+arch);boundary=record(campaign/'results.json');artifact=next(x for x in inventory['artifacts'] if x['kind']=='capture-domain-limit' and x['architecture']==arch)
        assert boundary['probe_sha256']==artifact['sha256'] and (boundary['controller_executions'],boundary['actual_child_launches'],boundary['assertions'])==(2,0,10)
        value=record(campaign/'exhaustion.stdout');assert value['initial_ordinal']=='18446744073709551615' and value['reasons']==['capture_domain_limit']*2 and not value['coordinator_created'] and not value['mutation_authority']
        assert not (campaign/'unexpected-argument.stdout').read_bytes() and not (campaign/'unexpected-argument.stderr').read_bytes()
        assert 'DISKED_CAPTURE_DOMAIN_EXHAUSTION_TESTING=1' in (repro/('build-configuration-'+arch)/'nt_capture_domain_limit_probe.vcxproj').read_text()
        for name in ('nt_identity_observation_probe','nt_identity_profile_probe','nt_owned_layout_probe'):
            assert 'DISKED_CAPTURE_DOMAIN_EXHAUSTION_TESTING' not in (repro/('build-configuration-'+arch)/(name+'.vcxproj')).read_text()
        identity=record(repro/('identity-observation-'+arch)/'foreign-coordinator.stdout');assert identity['comparison_error']=='storage_identity_comparison_domain'
        a=identity['observations'][0]['identity']['binding'];b=identity['observations'][-1]['identity']['binding'];assert a['domain']!=b['domain'] and a['source']==b['source'] and int(b['capture'])>int(a['capture']) and int(b['worker'])>int(a['worker'])
    for arch,pointer in [('x64',8),('Win32',4)]:
        campaign=repro/('identity-projection-'+arch);projection=record(campaign/'results.json')
        assert (projection['controller_executions'],projection['actual_child_launches'],projection['assertions'])==(34,59,7090)
        artifact=next(x for x in inventory['artifacts'] if x['kind']=='identity-projection' and x['architecture']==arch)
        assert projection['probe_sha256']==artifact['sha256'];children=set()
        for run in projection['executions']:
            value=record(campaign/(run['label']+'.stdout'));assert value['pointer_bytes']==str(pointer) and value['api_calls']=='0' and value['frontend_budget_ready']
            for row in value['stages']:
                for sample in list(row['worker'].values())+[row[k] for k in ('live_worker','retirement') if k in row]:
                    assert sample['code_sha256']==artifact['sha256'][7:] and not sample['claims']['physical_admission'] and not sample['claims']['mutation_authority']
                    native=sample['worker'];assert int(native['pid'])>0 and int(native['created'])>0;children.add((native['pid'],native['created']))
                assert row['capture_unchanged'] and row['api_calls']=='0'
                if 'error' in row:assert row['previous_preserved'];continue
                assert row['domains_retained'] and (row['previous_object_expired'] or row['previous_retained_for_cache']) and row['oldest_reference_pruned']
                assert row['unknown_reference_refused'] and row['graph_refusal']=='graph_limit' and row['publication_allocation_refused']
                for ref in row['resolved']:
                    content=row['artifacts'][ref['artifact']];assert ref['reference']['digest']==digest(content) and ref['artifact']==ref['reference']['kind']+':'+ref['reference']['digest']
                    assert ref['resolver'] in ('current-projection','last-complete-projection') and ref['reference']['retrieval']=='retained-native-projection' and ref['reference']['scope']=='complete-evidence-only'
                assert [r['id'] for r in row['inspections']]==[n['id'] for n in row['graph']['nodes']]
                for inspected in row['inspections']:
                    basis=inspected['direct']['result'];assert all(inspected[k]==digest(basis) for k in ('gui','tui','shell','cli_human','gui_display','tui_display')) and inspected['cli_background']==digest(inspected['direct'])
                    assert inspected['health_refused'] and inspected['capability_unqualified']
                if 'live_worker' in row:assert row['live_worker']['worker']['observation']=='running' and row['live_outstanding'] and row['retirement']['worker']['observation']=='exited'
        assert len(children)==59
        maximum=record(campaign/'maximum-comparisons.stdout');assert len(maximum['stages'][1]['comparisons'])==16
    for arch,pointer in [('x64',8),('Win32',4)]:
        campaign=repro/('identity-adapter-'+arch);adapter=record(campaign/'results.json')
        assert (adapter['controller_executions'],adapter['actual_child_launches'],adapter['assertions'])==(34,60,4338)
        artifact=next(x for x in inventory['artifacts'] if x['kind']=='identity-adapter' and x['architecture']==arch)
        assert adapter['probe_sha256']==artifact['sha256'];children=set()
        for run in adapter['executions']:
            value=record(campaign/(run['label']+'.stdout'));assert value['pointer_bytes']==str(pointer) and value['frontend_budget_ready'] and value['api_calls']=='0'
            for row in value['stages']:
                assert row['pure_retrieval_and_presentation'] and row['domains_retained'] and not row['source']['outstanding']
                for sample in row['workers']:
                    assert sample['code_sha256']==artifact['sha256'][7:] and not sample['claims']['physical_admission'] and not sample['claims']['mutation_authority']
                    native=sample['worker'];assert int(native['pid'])>0 and int(native['created'])>0;children.add((native['pid'],native['created']))
                if row['workers']:assert row['pending_evidence_preserved'] and row['duplicate_snapshot_preserved'] and row['duplicate_evidence_preserved']
                if 'start_error' in row:assert row['refused_start_key_unchanged'] and row['refused_start_capture_unchanged'] and not row['owner_changed'] and not row['workers']
                for ref in row['resolved']:
                    content=row['artifacts'][ref['artifact']];assert ref['reference']['digest']==digest(content) and ref['artifact']==ref['reference']['kind']+':'+ref['reference']['digest']
                owned=[n for n in row['graph']['nodes'] if n['properties']['scope']=='observation-only' and n['properties']['observation_binding']['source']=='storage']
                assert [x['id'] for x in row['inspections']]==[n['id'] for n in owned]
                for inspected,node in zip(row['inspections'],owned):
                    basis=inspected['direct']['result'];assert basis['node']==node and all(inspected[k]==digest(basis) for k in ('gui','tui','shell','cli_human','gui_display','tui_display')) and inspected['cli_background']==digest(inspected['direct'])
                    assert inspected['health_refused'] and inspected['capability_unqualified']
        assert len(children)==60
        for point in (1,2,3):
            value=record(campaign/('allocation-'+str(point)+'.stdout'));row=value['stages'][-1]
            assert value['allocation_checkpoint_hits']=='1' and row['allocation_failed'] and row['allocation_source']['outstanding']
            assert row['allocation_snapshot_preserved']==(point!=3) and row['allocation_evidence_preserved']==(point!=3)
        refusal=record(campaign/'coordinator-graph-refusal.stdout')['stages'];assert refusal[-1]['source']['state']=='malformed' and not refusal[-1]['owner_changed'] and refusal[-1]['identity']==refusal[0]['identity']
        repeated=record(campaign/'repeated-partial.stdout')['stages'];assert repeated[-1]['complete_digest']==digest(repeated[0]['identity'])
        assert len(record(campaign/'all16-comparisons.stdout')['stages'][-1]['comparisons'])==16
        assert record(campaign/'retained-consumer.stdout')['retained_after_adapter_destruction']
        for role in ('identity-adapter','storage-worker','identity-frame','identity-projection'):
            project=(repro/('build-configuration-'+arch)/(('nt_identity_adapter_probe' if role=='identity-adapter' else 'nt_storage_worker_probe' if role=='storage-worker' else 'nt_identity_frame_probe' if role=='identity-frame' else 'nt_identity_projection_probe')+'.vcxproj')).read_text()
            assert ('DISKED_NT_IDENTITY_ADAPTER_TESTING=1' in project)==(role=='identity-adapter')
    for arch,pointer,machine in [('x64',8,0x8664),('Win32',4,0x14c)]:
        campaign=repro/('inventory-port-'+arch);port=record(campaign/'results.json')
        assert (port['controller_executions'],port['actual_child_launches'],port['assertions'])==(23,88,7503)
        artifact=next(x for x in inventory['artifacts'] if x['kind']=='inventory-port' and x['architecture']==arch)
        data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        assert struct.unpack_from('<H',data,pe+4)[0]==machine;code=artifact['sha256'][7:];children=set()
        for run in port['executions']:
            value=record(campaign/(run['label']+'.stdout'))
            assert value['pointer_bytes']==str(pointer) and value['namespace_api_calls']==value['storage_api_calls']==value['health_calls']=='0'
            assert value['retained_after_session_destruction'] and value['null_owner_refused'] and value['value_construction_unowned']
            for row in value['stages']:
                assert row['pending_cached_pure'] and row['getter_no_allocation'] and row['delivered_owner'] and row['retrieval_and_presentation_pure']
                assert row['held_snapshot_retains_publication'] and row['old_publication_released'] and row['domains_retained']
                assert row['replacement_refused'] and not any(x['outstanding'] for x in row['retired']['sources'])
                for worker in row['workers']:
                    assert worker['code_sha256']==code and not worker['claims']['physical_admission'] and not worker['claims']['mutation_authority']
                    if worker['worker']['pid'] is not None:children.add((worker['worker']['pid'],worker['worker']['created']))
                nodes={x['id']:x for x in row['graph']['nodes']}
                assert [x['node'] for x in row['bindings']]==list(nodes)
                for binding in row['bindings']:
                    observation=nodes[binding['node']]['properties']['observation_binding'];frame=row['artifacts'][binding['artifact']]
                    assert observation['frame_digest']==digest(frame) and observation['context_digest']==digest(binding['context'])
                for ref in row['resolved']:assert ref['reference']['digest']==digest(row['artifacts'][ref['artifact']])
                for provider_source in ('namespace','storage'):
                    inspections=row[provider_source+'_inspections'];owned=[x for x in nodes.values() if x['properties']['observation_binding']['source']==provider_source]
                    assert [x['id'] for x in inspections]==[x['id'] for x in owned]
                    for inspection,node in zip(inspections,owned):
                        basis=inspection['direct']['result'];assert basis['node']==node and inspection['health_refused'] and inspection['capability_unqualified']
                        assert all(inspection[k]==digest(basis) for k in ('gui','tui','shell','cli_human','gui_display','tui_display')) and inspection['cli_background']==digest(inspection['direct'])
                for fault in ('provider','frontend'):
                    if row[fault+'_allocation_failed']:assert row[fault+'_failure_preserved']
        assert len(children)==88
        for role,target in [('inventory-port','nt_inventory_port_probe'),('identity-adapter','nt_identity_adapter_probe'),('identity-frontend','nt_identity_frontend_probe')]:
            project=(repro/('build-configuration-'+arch)/(target+'.vcxproj')).read_text()
            assert ('DISKED_NT_INVENTORY_PORT_TESTING=1' in project)==(role=='inventory-port')
    handoff_path='.aide/handoffs/DE-W030-inventory-port-2026-10-12.json';h=record(root/handoff_path);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h)
    for x in h['artifacts']:assert file_sha(x['path'])==x['sha256'],x['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts];target=':' if args.index else 'HEAD:'
    requests=[(source+':'+n,d) for n,d in inputs.items()];requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/windows-inventory.md','TODO.MD'])
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,d in requests:
        end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name;size=int(header[2]);start=end+1;data=raw[start:start+size];assert sha(data)==d,name
        if name.startswith(source+':'):assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name[len(source)+1:]],name
        at=start+size;assert raw[at:at+1]==b'\n',name;at+=1
    assert at==len(raw)
    result=dict(status='pass',source_revision=source,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),verification_target='Git index' if args.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),inventoried_evidence=len(inventory['evidence']),compressed_observations=len(inventory['compressed']),local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(h['artifacts']),owner_accepted=False,unit_complete=False)
    raw=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(raw,encoding='utf-8',newline='\n')
    print(raw,end='')

if __name__=='__main__':main()
