"""Verify retained bytes, source blobs, native artifacts and partial handoff; no launches."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-capture-domain'
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
    result=record(e/'validation-summary.json');assert result['status']=='pass' and result['source_revision']==source and not result['owner_accepted'] and not result['unit_complete']
    campaigns=result['campaigns'];assert len(campaigns)==22;assert sum(c['controllers']+c['child_launches'] for c in campaigns)==result['native_processes'];assert sum(c['assertions'] for c in campaigns)==result['native_assertions']
    product=record(repro/'product-build-identity.json');assert len(product['inputs'])==404 and all(file_sha(n)==d for n,d in product['inputs'].items()) and product['identity']['source_revision']==source and product['identity']['source_state']=='clean'
    assert result['product_rebuilt'] and result['product_suite_rerun'] and result['native_ctest_groups']==77
    launch=record(repro/'logs/product-launch.log')['result'];assert launch['source_revision']==source and launch['version']==result['product_version']
    assert b'0 tests failed out of 77' in (repro/'logs/product-native.log').read_bytes()
    assert len(inventory['artifacts'])==26
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
    handoff_path='.aide/handoffs/DE-W030-capture-domain-2026-10-12.json';h=record(root/handoff_path);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h)
    for x in h['artifacts']:assert file_sha(x['path'])==x['sha256'],x['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts];target=':' if a.index else 'HEAD:'
    requests=[(source+':'+n,d) for n,d in inputs.items()];requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/windows-inventory.md','TODO.MD'])
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,d in requests:
        end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name;size=int(header[2]);start=end+1;data=raw[start:start+size];assert sha(data)==d,name
        if name.startswith(source+':'):assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name[len(source)+1:]],name
        at=start+size;assert raw[at:at+1]==b'\n',name;at+=1
    assert at==len(raw)
    result=dict(status='pass',source_revision=source,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),verification_target='Git index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),inventoried_evidence=len(inventory['evidence']),compressed_observations=len(inventory['compressed']),local_artifacts=len(inventory['artifacts']),handoff_artifacts=len(h['artifacts']),owner_accepted=False,unit_complete=False)
    raw=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(raw,encoding='utf-8',newline='\n')
    print(raw,end='')

if __name__=='__main__':main()
