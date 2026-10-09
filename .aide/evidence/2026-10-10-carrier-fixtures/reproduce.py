"""Clean native H/D/offline-carrier fixture evidence; no installation or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,default=Path.cwd())
    p.add_argument('--source-revision',required=True)
    p.add_argument('--upstream-repository',type=Path,required=True)
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--package-evidence',type=Path,required=True)
    p.add_argument('--build-info',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    root=a.repository.absolute();out=a.output.absolute()
    out.mkdir();logs=out/'logs';logs.mkdir();receipts=[]
    def run(name,cmd,cwd,expected=0,payload=None):
        args=[str(x) for x in cmd];started=time.monotonic()
        proc=subprocess.run(args,cwd=cwd,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (logs/(name+'.log')).write_bytes(proc.stdout+proc.stderr)
        if payload is not None:(logs/(name+'.request.bin')).write_bytes(payload)
        receipts.append(dict(name=name,command=args,cwd=str(cwd),exit_code=proc.returncode,expected_exit=expected,
                             status='pass' if proc.returncode==expected else 'fail',elapsed_seconds=round(time.monotonic()-started,3),log='logs/'+name+'.log'))
        save(out/'commands.json',receipts)
        if proc.returncode!=expected:raise AssertionError((name,proc.returncode,str(logs/(name+'.log'))))
        return proc.stdout
    # The exact earlier recipe performs a clean source export, base native ABI
    # campaign, 30 setup/export tests, 215 tooling tests and context checks.
    sdk=out/'sdk'
    run('source-consumer-reproduction',[sys.executable,root/'.aide/evidence/2026-10-10-setup-source-consumer/reproduce.py',
        '--repository',root,'--source-revision',a.source_revision,'--upstream-repository',a.upstream_repository.absolute(),
        '--package',a.package.absolute(),'--inventory',a.inventory.absolute(),'--package-evidence',a.package_evidence.absolute(),'--output',sdk],root)
    checkout=sdk/'checkout';source=sdk/'source';build=sdk/'build'
    local_inputs=json.loads((sdk/'source-inputs.json').read_bytes())
    for folder in ('release/carriers','tests/composition'):
        for path in sorted((checkout/folder).rglob('*')):
            if path.is_file():local_inputs[path.relative_to(checkout).as_posix()]=sha(path)
    for name in ('spec/catalog/carrier-fixture-prototype.json','spec/catalog/servicing-preview-prototype.json',
                 '.aide/evidence/2026-10-10-carrier-fixtures/reproduce.py'):
        local_inputs[name]=sha(checkout/name)
    recipe=Path(__file__).absolute()
    if sha(recipe)!=local_inputs['.aide/evidence/2026-10-10-carrier-fixtures/reproduce.py']:
        raise AssertionError('recipe differs from exact selected source')
    for name,value in local_inputs.items():
        blob=subprocess.check_output(['git','-C',str(checkout),'show',a.source_revision+':'+name])
        if 'sha256:'+hashlib.sha256(blob).hexdigest()!=value:raise AssertionError('source identity: '+name)
    save(out/'source-inputs.json',local_inputs)
    run('configure-H',['cmake','-S',checkout/'tests/setup/native','-B',build,'-G','Visual Studio 17 2022',
        '-A','x64,version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64',
        '-DUSK_SOURCE_DIR='+str(source),'-DCMAKE_SYSTEM_VERSION=10.0.19041.0','-DDISKED_BUILD_HOST_FIXTURE=ON'],checkout)
    run('build-H',['cmake','--build',build,'--config','Release','--target','disked_setup_host_fixture'],checkout)
    host=build/'Release/disked_setup_host_fixture.exe'
    observation=json.loads(run('H-product-binding',[host,'host.inspect'],checkout))
    assert observation['source_revision']==a.source_revision and observation['source_state']=='clean'
    host_input=dict(schema='org.disked.carrier-host-input/1',artifact=dict(bytes=str(host.stat().st_size),sha256=sha(host)),observation=observation)
    save(out/'host-input.json',host_input)
    shutil.copyfile(a.inventory,out/'independent-inventory.json');shutil.copyfile(a.build_info,out/'build-info.json')
    fixture=checkout/'release/carriers/fixture.py'
    common=['--inventory',a.inventory.absolute(),'--build-info',a.build_info.absolute(),'--host-input',out/'host-input.json']
    carrier=out/'carrier';duplicate=out/'repeat-carrier'
    for name,path in [('assemble',carrier),('repeat-assemble',duplicate)]:
        run(name,[sys.executable,fixture,'assemble','--package',a.package.absolute(),'--host',host,*common,'--output',path],checkout)
    assert sha(carrier/'carrier.zip')==sha(duplicate/'carrier.zip')
    verification=json.loads(run('verify',[sys.executable,fixture,'verify','--root',carrier,*common],checkout))
    assert verification['status']=='pass' and not verification['lifecycle_available']
    run('occupied-carrier-root',[sys.executable,fixture,'assemble','--package',a.package.absolute(),'--host',host,*common,'--output',carrier],checkout,1)
    owned=out/'occupied-case';owned.mkdir()
    preserved={}
    for name in ('case','evidence','recovery','foreign'):
        path=owned/(name+'.bin');path.write_bytes(('generated '+name).encode());preserved[path.name]=sha(path)
    run('occupied-data-retention',[sys.executable,fixture,'assemble','--package',a.package.absolute(),'--host',host,*common,'--output',owned],checkout,1)
    assert preserved=={name:sha(owned/name) for name in preserved}
    save(out/'retention.json',dict(generated_fixture_only=True,preserved=preserved))
    run('H-native-campaign',[sys.executable,checkout/'tests/setup/run_source_consumer.py','--probe',host,
        '--package',a.package.absolute(),'--inventory',a.inventory.absolute(),'--output',out/'host-campaign'],checkout)
    native=json.loads((out/'host-campaign/results.json').read_bytes());assert native['native_executions']==33 and native['assertions']==223
    # Read-only structural inspection of S is separate from the independent
    # decoded-byte verification already performed by the carrier checker.
    budgets=dict(max_entries=64,max_uncompressed_bytes=16777216,max_entry_bytes=16777216,max_depth=8,max_ratio=100,max_elapsed_ms=10000)
    request=dict(schema='usk.archive_inspect_request.v1',archive_path=str(carrier/'carrier.zip'),archive_format='zip',budgets=budgets)
    s_observation=json.loads(run('H-S-structure',[host,'install_local.inspect'],checkout,payload=json.dumps(request).encode()))
    assert s_observation['provider_return']==0 and s_observation['response']['payload']['source']['sha256']==sha(carrier/'carrier.zip')[7:]
    expected=json.loads((carrier/'carrier-inventory.json').read_bytes())
    assert {(x['normalized_path'],x['uncompressed_size']) for x in s_observation['response']['payload']['entries']}=={(x['path'],int(x['bytes'])) for x in expected['files']}
    # Explicitly selected known bytes into a new owned damage fixture. There is
    # no generic carrier extraction API or launch of corrupted D.
    damaged=out/'damaged-D';damaged.mkdir()
    with zipfile.ZipFile(carrier/'carrier.zip') as archive:
        hbytes=archive.read('host/disked-setup-host-fixture.exe');dbytes=archive.read('payload/disked.exe')
    assert 'sha256:'+hashlib.sha256(hbytes).hexdigest()==sha(host)
    independent_h=damaged/'disked-setup-host-fixture.exe';independent_h.write_bytes(hbytes)
    corrupt=bytearray(dbytes);corrupt[0]^=1;(damaged/'disked.exe').write_bytes(corrupt)
    assert sha(damaged/'disked.exe')!='sha256:'+hashlib.sha256(dbytes).hexdigest()
    recovered_observation=json.loads(run('independent-H-damaged-D',[independent_h,'host.inspect'],damaged))
    assert recovered_observation==observation
    damaged_inspection=json.loads(run('independent-H-source-inspect',[independent_h,'install_local.inspect'],damaged,payload=json.dumps(request).encode()))
    assert damaged_inspection['provider_return']==0
    save(out/'damage-inspection.json',dict(damaged_D_not_executed=True,independent_H_sha256=sha(independent_h),
        damaged_D_sha256=sha(damaged/'disked.exe'),inspection_route_usable=True,repair_or_recovery_success=False))
    # A damaged staged D must not pass the separate carrier verifier.
    (duplicate/'staging/payload/disked.exe').write_bytes(corrupt)
    run('changed-D-refusal',[sys.executable,fixture,'verify','--root',duplicate,*common],checkout,1)
    run('composition-tests',[sys.executable,'-m','unittest','discover','-s','tests/composition','-v'],checkout)
    dumpbin=Path('C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
    run('H-headers',[dumpbin,'/headers',host],checkout);run('H-imports',[dumpbin,'/imports',host],checkout)
    shutil.copyfile(build/'disked_setup_host_fixture.vcxproj',out/'host-build.vcxproj')
    context=out/'context'
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W062','--output',context,'--byte-budget','430000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',context],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip()
    assert all(sha(checkout/name)==value for name,value in local_inputs.items())
    artifacts=[dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path)) for path in
               (host,carrier/'carrier.zip',carrier/'staging/payload/disked.exe')]
    save(out/'results.json',dict(passed=True,source_revision=a.source_revision,upstream_revision=observation['setup_revision'],
        local_inputs=len(local_inputs),upstream_inputs=84,artifacts=artifacts,product_native_rebuilt=False,
        base_native_executions=33,base_assertions=223,host_native_executions=33,host_assertions=223,
        composition_tests=26,setup_tests=30,tooling_tests=dict(run=215,passed=213,skipped=2),
        deterministic_S=True,payload_equality=True,occupied_data_retained=True,damaged_D_inspection_route=True,
        repair_or_recovery_success=False,live_interlock_qualified=False,installed_sdk_qualified=False,
        native_setup_carrier_qualified=False,owner_accepted=False,unit_complete=False,remote_writes=False))
    print(json.dumps(dict(passed=True,source_revision=a.source_revision,commands=len(receipts),H_sha256=sha(host),S_sha256=sha(carrier/'carrier.zip'))))


if __name__=='__main__':main()
