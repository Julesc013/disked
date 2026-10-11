"""Audit retained qualification, actual renderer receipts, exact source and staged/committed bytes; no launches."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--index',action='store_true');parser.add_argument('--output',type=Path);args=parser.parse_args()
    root=Path.cwd();e=root/'.aide/evidence/2026-10-12-inventory-frontend'
    def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
    def file_sha(name):return sha((root/name).read_bytes())
    def record(path):return json.loads(path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes()))
    def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())
    inventory=record(e/'inventory.json');source=inventory['source_revision'];repro=e/('reproduction-'+source[:8])
    inputs=record(repro/'source-inputs.json');blobs=record(repro/'source-blob-bindings.json');assert set(inputs)==set(blobs)
    for name,expected in inputs.items():
        data=(root/name).read_bytes();assert sha(data)==expected,name
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name],name
    for item in inventory['evidence']+inventory['artifacts']:
        assert file_sha(item['path'])==item['sha256'] and (root/item['path']).stat().st_size==item['bytes'],item['path']
    for item in inventory['compressed']:
        data=gzip.decompress((root/item['encoded_path']).read_bytes());assert len(data)==item['decoded_bytes'] and sha(data)==item['decoded_sha256']
    assert not any(f.suffix.lower() in ('.img','.exe','.dll','.obj','.pdb') for f in e.rglob('*') if f.is_file())
    result=record(e/'validation-summary.json');assert result['status']=='pass' and result['source_revision']==source
    assert result['private_inventory_frontend_qualified'] and not result['owner_accepted'] and not result['unit_complete'] and not result['provider_admitted']
    campaigns=result['campaigns'];assert len(campaigns)==6
    assert sum(c['controllers']+c['child_launches'] for c in campaigns)==result['native_processes']==546
    assert sum(c['assertions'] for c in campaigns)==result['native_assertions']==31208
    assert result['tooling_tests']==dict(run=215,passed=213,skipped=2) and result['structural_checks']==1073
    product=record(repro/'product-build-identity.json');assert len(product['inputs'])==404
    assert all(file_sha(n)==d for n,d in product['inputs'].items()) and product['identity']['source_revision']==source and product['identity']['source_state']=='clean'
    assert result['product_rebuilt'] and result['product_suite_rerun'] and result['native_ctest_groups']==77
    launch=record(repro/'logs/product-launch.log')['result'];assert launch['source_revision']==source and launch['version']==result['product_version']
    assert b'0 tests failed out of 77' in (repro/'logs/product-native.log').read_bytes()
    assert len(inventory['artifacts'])==8
    for artifact in inventory['artifacts']:
        data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0'
        assert struct.unpack_from('<H',data,pe+4)[0]==(0x8664 if artifact['architecture']=='x64' else 0x14c)
    for campaign in campaigns:
        retained=record(repro/(campaign['kind']+'-'+campaign['architecture'])/'results.json')
        assert retained['status']=='pass' and retained['pointer_bytes']==campaign['pointer_bytes'] and retained['assertions']==campaign['assertions']
        assert all(check['passed'] for check in retained['checks'])
    for arch,pointer in [('x64',8),('Win32',4)]:
        folder=repro/('inventory-frontend-'+arch);campaign=record(folder/'results.json')
        assert (campaign['controller_executions'],campaign['actual_child_launches'],campaign['assertions'])==(59,36,916)
        artifact=next(a for a in inventory['artifacts'] if a['kind']=='inventory-frontend' and a['architecture']==arch)
        assert campaign['probe_sha256']==artifact['sha256'];children=set()
        assert sum(x['frontend']=='launcher-rejection' for x in campaign['executions'])==44
        for mode in ('gui','tui','shell'):assert sum(x['frontend']==mode for x in campaign['executions'])==5
        for run in campaign['executions']:
            if run['frontend']=='launcher-rejection':
                assert run['exit_code'] in (2,3)
                data=(folder/(run['label']+'.stdout.log')).read_bytes()
                if run['exit_code']==2:assert not data
                else:
                    refusal=json.loads(data);assert refusal['status']=='refused' and refusal['reader_starts']==refusal['namespace_api_calls']==refusal['storage_api_calls']=='0'
                continue
            assert run['exit_code']==0;value=record(folder/(run['label']+'.receipt.json'));host=record(folder/(run['label']+'.host.json'))
            assert value['pointer_bytes']==str(pointer) and value['renderer_exit']=='0' and value['frontend_budget_ready']
            assert value['retained_after_session_and_renderer'] and int(value['callbacks'])>0
            assert value['namespace_api_calls']==value['storage_api_calls']==value['health_calls']=='0'
            assert not any(s['outstanding'] for s in value['sources'])
            graph=value['graph'];basis=dict(graph);revision=basis.pop('revision');assert revision==digest(basis)
            nodes={n['id']:n for n in graph['nodes']};workers={}
            for worker in value['workers']:
                assert worker['code_sha256']==artifact['sha256'][7:] and not worker['claims']['physical_admission'] and not worker['claims']['mutation_authority']
                identity=worker['worker'];pid,created=identity['pid'],identity['created']
                if pid is not None:
                    assert int(pid)>0 and int(created)>0;children.add((pid,created));workers[(worker['attempt_id'],pid,created)]=worker
            assert [b['node'] for b in value['bindings']]==list(nodes)
            for binding in value['bindings']:
                node=nodes[binding['node']];properties=node['properties'];b=properties['observation_binding'];context=binding['context']
                assert b['frame_digest']==digest(value['artifacts'][binding['artifact']]) and b['context_digest']==digest(context)
                assert node['id']=='observation:'+digest(dict(binding=b,kind=node['kind'],label=properties['label'],payload=properties['observation']))[7:]
                assert properties['scope']=='observation-only' and properties['identity'] is None and properties['media_generation'] is None
                assert not properties['physical_admission'] and not properties['mutation_authority']
                worker=workers[(context['attempt_id'],context['pid'],context['created'])]
                expected={k:worker[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256')}
                expected.update({k:worker['worker'][k] for k in ('pid','created')})
                if b['source']=='storage' and value['composition']!='metadata':expected['storage_profile']='identity-layout'
                assert context==expected
            for ref in value['resolved']:
                assert ref['reference']['digest']==digest(value['artifacts'][ref['artifact']])
                assert nodes[ref['node']]['properties']['observation']['references'][ref['name']]==ref['reference']
            if run['frontend']=='gui':
                assert [x['result']['node'] for x in host['inspections']]==list(nodes.values())
                assert host['health']['diagnostics'][0]['code']=='observation_not_storage_target' and host['unavailable']['diagnostics'][0]['code']=='command_unavailable'
                assert (folder/(run['label']+'.png')).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            else:
                assert host['status']=='pass' and host['exit']==0
                assert all(host['before'][k]==host['after'][k] for k in ('modes','codepages','cursor_style','attributes'))
                assert all('\x1b' not in f['text'] for f in host['frames']) and any('CACHED OBSERVATIONS' in f['text'] for f in host['frames'])
                if run['frontend']=='shell':assert host['inspected_id'] in nodes and any('observation_not_storage_target' in f['text'] for f in host['frames'])
        assert len(children)==36
        for kind,target in [('inventory-frontend','nt_inventory_frontend_probe'),('inventory-port','nt_inventory_port_probe'),('identity-frontend','nt_identity_frontend_probe')]:
            project=(repro/('build-configuration-'+arch)/(target+'.vcxproj')).read_text()
            assert 'DISKED_NT_OBSERVATION_WORKER_TESTING=1' in project
            assert ('DISKED_NT_INVENTORY_PORT_TESTING=1' in project)==(kind=='inventory-port')
            if kind=='inventory-frontend':assert 'DISKED_NT_IDENTITY_FRONTEND_TESTING=1' not in project
    handoff_path='.aide/handoffs/DE-W030-inventory-frontend-2026-10-12.json';handoff=record(root/handoff_path)
    jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(handoff)
    assert handoff['status']=='partial' and not handoff['blockers']
    for artifact in handoff['artifacts']:assert file_sha(artifact['path'])==artifact['sha256'],artifact['path']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts];target=':' if args.index else 'HEAD:'
    requests=[(source+':'+n,d) for n,d in inputs.items()]
    requests.extend((target+n,file_sha(n)) for n in retained+[handoff_path,'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/windows-inventory.md','TODO.MD'])
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,expected in requests:
        end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;data=raw[start:start+size];assert sha(data)==expected,name;at=start+size+1
    output=dict(status='pass',source_revision=source,tree='index' if args.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),native_artifacts=len(inventory['artifacts']),native_processes=result['native_processes'],native_assertions=result['native_assertions'],owner_accepted=False,unit_complete=False)
    text=json.dumps(output,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8',newline='\n')
    print(text,end='')

if __name__=='__main__':main()
