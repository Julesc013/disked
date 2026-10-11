"""Read-only audit of retained source, native observations and Git evidence."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',action='store_true');p.add_argument('--historical',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    root=Path.cwd();e=root/'.aide/evidence/2026-10-12-inventory-host'
    def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
    def record(path):return json.loads(path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes()))
    def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())
    inv=record(e/'inventory.json');source=inv['source_revision'];r=e/('reproduction-'+source[:8]);v=record(e/'validation-summary.json')
    inputs=record(r/'source-inputs.json');blobs=record(r/'source-blob-bindings.json');assert inputs.keys()==blobs.keys()
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
    for name,d in inputs.items():
        end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;data=raw[start:start+size];assert sha(data)==d,name;at=start+size+1
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name],name
        if not a.historical:assert sha((root/name).read_bytes())==d,name
    for item in inv['evidence']+inv['artifacts']:
        data=(root/item['path']).read_bytes();assert len(data)==item['bytes'] and sha(data)==item['sha256'],item['path']
    for item in inv['compressed']:
        data=gzip.decompress((root/item['encoded_path']).read_bytes());assert len(data)==item['decoded_bytes'] and sha(data)==item['decoded_sha256']
    assert not any(f.suffix.lower() in ('.exe','.dll','.img','.obj','.pdb') for f in e.rglob('*') if f.is_file())
    assert v['status']=='pass' and v['source_revision']==source and v['private_inventory_advance_qualified']
    assert not v['owner_accepted'] and not v['unit_complete'] and not v['provider_admitted'] and not v['public_protocol_admitted']
    assert len(v['campaigns'])==2 and len(inv['artifacts'])==4
    assert v['native_processes']==sum(c['controllers']+c['child_launches'] for c in v['campaigns'])
    assert v['native_assertions']==sum(c['assertions'] for c in v['campaigns'])
    assert v['tooling_tests']==dict(run=215,passed=213,skipped=2) and v['structural_checks']==1075
    product=record(r/'product-build-identity.json');assert product['identity']['source_revision']==source and product['identity']['source_state']=='clean'
    assert len(product['inputs'])==404 and all(inputs[n]==d for n,d in product['inputs'].items())
    assert v['product_rebuilt'] and v['product_suite_rerun'] and v['native_ctest_groups']==77
    assert record(r/'logs/product-launch.log')['result']['source_revision']==source
    assert b'0 tests failed out of 77' in (r/'logs/product-native.log').read_bytes()
    assert record(r/'capture-domain-reducer-results.json')['tests']==25
    for artifact in inv['artifacts']:
        assert artifact['source_revision']==source
        data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0'
        assert struct.unpack_from('<H',data,pe+4)[0]==(0x8664 if artifact['architecture']=='x64' else 0x14c)
    for c in v['campaigns']:
        assert c['kind']=='inventory-host'
        retained=record(r/c.get('retained_folder',c['kind']+'-'+c['architecture'])/'results.json')
        assert retained['status']=='pass' and retained['pointer_bytes']==c['pointer_bytes'] and retained['assertions']==c['assertions']
        assert all(x['passed'] for x in retained['checks'])
    for arch,pointer in [('x64',8),('Win32',4)]:
        folder=r/('inventory-host-'+arch);campaign=record(folder/'results.json');children=set()
        assert campaign['controller_executions']==62 and campaign['actual_child_launches']==113
        artifact=next(x for x in inv['artifacts'] if x['kind']=='inventory-host' and x['architecture']==arch)
        assert sum(x['frontend']=='launcher-rejection' for x in campaign['executions'])==34
        for run in campaign['executions']:
            if run['frontend']=='launcher-rejection':
                data=(folder/(run['label']+'.stdout.log')).read_bytes();assert run['exit_code'] in (2,3)
                if run['exit_code']==2:assert not data
                else:
                    refusal=json.loads(data);assert refusal['status']=='refused' and refusal['reader_starts']=='0'
                continue
            value=record(folder/(run['label']+'.receipt.json'));host=record(folder/(run['label']+'.host.json'))
            failed=run['label'].endswith('callback-fault')
            assert run['exit_code']==(4 if run['label']=='gui-callback-fault' else 0) and value['renderer_exit']==('4' if failed else '0') and value['pointer_bytes']==str(pointer) and value['frontend_budget_ready']
            assert value['namespace_api_calls']==value['storage_api_calls']==value['health_calls']=='0'
            assert not value['retirement']['outstanding'] and not any(s['outstanding'] for s in value['trace'][-1]['sources'])
            workers={}
            for w in value['workers']:
                assert w['code_sha256']==artifact['sha256'][7:] and not any(w['claims'].values())
                pid,created=w['worker']['pid'],w['worker']['created']
                if pid is not None:
                    assert int(pid)>0 and int(created)>0;children.add((pid,created));workers[(w['attempt_id'],pid,created)]=w
            assert all(w['worker']['observation']=='exited' for w in workers.values())
            held=value['retained_after_session_and_renderer'];assert len(held)==len(value['trace']) and all(x['same_snapshot'] for x in held)
            for index,sample in enumerate(value['trace']):
                assert all(held[index][k]==sample[k] for k in ('graph','sources','bindings','artifacts','resolved'))
                graph=sample['graph'];basis=dict(graph);revision=basis.pop('revision');assert revision==digest(basis)
                nodes={n['id']:n for n in graph['nodes']};assert [b['node'] for b in sample['bindings']]==list(nodes)
                for b in sample['bindings']:
                    n=nodes[b['node']];q=n['properties'];binding=q['observation_binding'];context=b['context']
                    assert n['id']=='observation:'+digest(dict(binding=binding,kind=n['kind'],label=q['label'],payload=q['observation']))[7:]
                    assert binding['frame_digest']==digest(sample['artifacts'][b['artifact']]) and binding['context_digest']==digest(context)
                    assert q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None and q['aliases']==[]
                    assert q['scope']=='observation-only' and not q['physical_admission'] and not q['mutation_authority']
                    w=workers[(context['attempt_id'],context['pid'],context['created'])]
                    expected={k:w[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256')}
                    expected.update({k:w['worker'][k] for k in ('pid','created')})
                    if binding['source']=='storage' and value['composition']!='metadata':expected['storage_profile']='identity-layout'
                    assert context==expected
                for ref in sample['resolved']:
                    assert ref['reference']['digest']==digest(sample['artifacts'][ref['artifact']])
                    assert nodes[ref['node']]['properties']['observation']['references'][ref['name']]==ref['reference']
            if failed:
                assert value['callback_threw'] and value['callback_sources_before_throw']==[True,True]
                assert value['retirement']['before']==[True,True] and value['final_model_state'] is None and not value['dispatches']
            else:
                assert not value['callback_threw'] and not value['callback_sources_before_throw']
                assert value['final_model_state']['view_revision'] in {s['graph']['revision'] for s in value['trace']}
            kinds=[x['kind'] for x in value['events']]
            assert bool(value['errors'])==(run['label']=='gui-startup-recover')
            if run['label']=='gui-refuse-pending':assert 'advance_refused_outstanding' in kinds
            if run['label'] in ('gui-late-timeout','gui-hang-deadline','gui-startup-recover'):assert kinds.count('timeout')==1
            if run['label']=='gui-close-pending':assert any(value['retirement']['before']) and not value['dispatches']
            if run['frontend']=='gui':
                assert (folder/(run['label']+'.png')).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
                if failed:assert host['exit']==4 and host['stderr']=='disked: gui_event_error\r\n'
                if value['dispatches']:
                    request=value['dispatches'][0];assert request['expected_revision']==value['trace'][0]['graph']['revision']
                    assert request['parameters']['target_id']==value['selection']['observation_id']
                    assert request['outcome']['diagnostics'][0]['code']=='revision_conflict'
            else:
                assert host['status']=='pass' and host['exit']==(4 if failed else 0) and all(host['before'][k]==host['after'][k] for k in ('modes','codepages','cursor_style','attributes'))
                assert all('\x1b' not in f['text'] for f in host['frames'])
                if failed:assert host['stderr']=='disked: frontend_event_error\r\n'
                elif run['label'] in ('shell-chooser','shell-completion'):
                    before=value['model_samples'][1];final=value['final_model_state']
                    assert final['editor']==before['editor']=='target ins' and final['cursor']==before['cursor'] and final['candidates']==before['candidates']
                    assert final['view']==('editor' if run['label']=='shell-chooser' else 'completion') and not value['dispatches']
                else:assert value['dispatches'][-1]['outcome']['diagnostics'][0]['code']=='revision_conflict'
                if value['terminal_style']=='screen':
                    assert all(host['before'][k]==host['after'][k] for k in ('handles','buffer','viewport','cursor','content'))
                    assert host['active_after']==host['before']['content']
                    assert any('CACHED OBSERVATIONS | screen' in f['text'] for f in host['frames'])
        assert len(children)==113
    commands=record(r/'commands.json');assert all(c['exit_code']==0 for c in commands)
    assert v['private_screen_delivery_qualified'] and v['private_callback_teardown_qualified']
    prior=record(r/'prior-product-build-identity.json');auxiliary=record(r/'auxiliary-inputs.json')
    assert len(auxiliary)==v['auxiliary_inputs']==1 and prior['identity']['source_revision']=='6e4c20591afb31389b95afe91dfc4037cde2a4e4'
    assert prior['inputs'].keys()==product['inputs'].keys()
    assert [n for n in product['inputs'] if product['inputs'][n]!=prior['inputs'][n]]==record(r/'prior-product-input-comparison.json')['changed_inputs']==['spec/interaction/presentation.md']
    prior_data=(r/'prior-product-build-identity.json').read_bytes()
    assert sha(prior_data)==auxiliary[0]['sha256'] and hashlib.sha1(b'blob '+str(len(prior_data)).encode()+b'\0'+prior_data).hexdigest()==auxiliary[0]['git_blob']
    name='.aide/handoffs/DE-W030-inventory-host-2026-10-12.json';handoff=record(root/name)
    jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(handoff)
    assert handoff['status']=='partial' and not handoff['blockers']
    for artifact in handoff['artifacts']:assert sha((root/artifact['path']).read_bytes())==artifact['sha256']
    retained=[f.relative_to(root).as_posix() for f in sorted(e.rglob('*')) if f.is_file() and '__pycache__' not in f.parts]
    target=':' if a.index else 'HEAD:';requests=[(source+':'+n,d) for n,d in inputs.items()]
    requests.extend((item['source_revision']+':'+item['path'],item['sha256']) for item in auxiliary)
    requests.extend((target+n,sha((root/n).read_bytes())) for n in retained+[name,'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/windows-inventory.md','TODO.MD'])
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
    for name,expected in requests:
        end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]);start=end+1;data=raw[start:start+size];assert sha(data)==expected,name;at=start+size+1
    result=dict(status='pass',source_revision=source,historical_source_only=a.historical,tree='index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(retained),native_artifacts=len(inv['artifacts']),native_processes=v['native_processes'],native_assertions=v['native_assertions'],owner_accepted=False,unit_complete=False)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(text,encoding='utf8',newline='\n')
    print(text,end='')


if __name__=='__main__':main()
