"""Finish source-bound checks after a manifest-only repair; do not rerun native tests."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing-clone',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--specification-revision',required=True)
    args=parser.parse_args();root=Path.cwd().resolve();checkout=args.existing_clone.resolve();out=args.output.resolve()
    assert checkout.is_relative_to(root/'.aide-local') and out.is_relative_to(root/'.aide-local')
    assert re.fullmatch('[0-9a-f]{40}',args.specification_revision)
    receipts=json.loads((out/'commands.json').read_bytes())
    assert receipts[-1]['name']=='manifest' and receipts[-1]['exit_code']==2
    assert all(r['exit_code']==0 for r in receipts[:-1])
    identity=json.loads((out/'build-identity.json').read_bytes());source=identity['identity']['source_revision']
    assert identity['identity']['source_state']=='clean'
    inputs=json.loads((out/'source-inputs.json').read_bytes())
    def run(name,command):
        command=list(map(str,command));start=time.monotonic()
        result=subprocess.run(command,cwd=checkout,capture_output=True,timeout=300)
        log=out/'logs'/(name+'.log');log.write_bytes(result.stdout+result.stderr)
        receipts.append(dict(name=name,command=command,cwd=str(checkout),exit_code=result.returncode,
                             elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name))
        save(out/'commands.json',receipts);print(name+': exit '+str(result.returncode),flush=True)
        assert result.returncode==0,name
        return result.stdout
    assert not run('repair-initial-status',['git','status','--porcelain']).strip()
    run('repair-fetch',['git','fetch','--no-tags','origin',args.specification_revision])
    changed=run('repair-diff',['git','diff','--name-only',source,args.specification_revision]).decode().splitlines()
    assert changed==['spec/manifest.json'],changed
    run('repair-checkout',['git','checkout','--detach',args.specification_revision])
    assert not run('repair-source-status',['git','status','--porcelain']).strip()
    assert all(sha(checkout/name)==digest for name,digest in inputs.items())
    save(out/'metadata-bridge.json',dict(native_source_revision=source,specification_revision=args.specification_revision,
        changed_paths=changed,unchanged_inputs=inputs,
        scope='Manifest-only repair; every bound source/build input unchanged. Native tests/artifacts remain at the original source.'))
    run('manifest-repaired',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
    run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W028','--output',out/'context','--byte-budget','650000'])
    run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
    build=out/'build'
    launch=json.loads(run('product-launch',[build/'Release/disked.exe','build','inspect','--json']))['result']
    assert launch['source_revision']==source and launch['version']=='0.1.0-dev.42'
    dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');artifacts=[]
    for name in ('disked','fat_probe','fat_directory_probe','fat_capture_probe','fat_capture_fault'):
        p=build/'Release'/(name+'.exe')
        for mode in ('headers','imports','dependents'):run(name+'-'+mode,[dumpbin,'/'+mode,p])
        artifacts.append(dict(kind=name,path=str(p),bytes=p.stat().st_size,sha256=sha(p),source_revision=source))
    for name in ('disked_fat','disked_fat_headers','disked_fat_capture','disked_fat_file','disked_fat_file_fault'):
        p=build/(name+'.dir/Release')/(name+'.lib') if name.endswith('_headers') else build/'Release'/(name+'.lib')
        artifacts.append(dict(kind=name,path=str(p),bytes=p.stat().st_size,sha256=sha(p),source_revision=source))
    objects=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
        for name in ('disked_json','disked_command','disked_invocation','disked_presentation','disked_fat','disked_region_reader','disked_fat_capture')
        for p in (build/(name+'_headers.dir/Release')).glob('*.obj')]
    assert len(objects)==10;save(out/'header-objects.json',objects)
    config=out/'build-configuration';config.mkdir()
    for name in ('CMakeCache.txt','disked.vcxproj','disked_fat.vcxproj','disked_fat_headers.vcxproj','fat_probe.vcxproj','fat_directory_probe.vcxproj',
                 'fat_capture_probe.vcxproj','fat_capture_fault.vcxproj','disked_fat_capture.vcxproj','disked_fat_file.vcxproj','disked_fat_file_fault.vcxproj'):
        shutil.copyfile(build/name,config/name)
    shutil.copytree(build/'.cmake/api/v1/reply',out/'cmake-codemodel')
    shutil.copyfile(build/'private-header-usage.json',out/'private-header-usage.json')
    assert not run('final-source-status',['git','status','--porcelain']).strip()
    assert all(sha(checkout/name)==digest for name,digest in inputs.items())
    text=(out/'logs/tooling.log').read_text(encoding='utf-8')
    count=int(re.search(r'^Ran (\d+) tests ',text,re.MULTILINE).group(1));skipped=int(re.search(r'^OK \(skipped=(\d+)\)$',text,re.MULTILINE).group(1))
    boundary=json.loads((out/'build-boundaries.json').read_bytes());check=json.loads((out/'logs/spec-check.log').read_bytes())
    host=json.loads((out/'logs/host.log').read_bytes())
    save(out/'summary.json',dict(source_revision=source,source_state='clean',specification_revision=args.specification_revision,
        initial_manifest_failed=True,metadata_bridge='metadata-bridge.json',host=host,source_input_count=len(inputs),product_input_count=len(identity['inputs']),
        native_test_groups=92,fat_test_methods=19,fat_cases=1335,directory_test_methods=19,directory_cases=6790,
        capture_test_methods=20,capture_cases=149,scan_test_methods=13,scan_cases=86,tooling_count=count,tooling_skipped=skipped,
        structural=check,build_target_count=boundary['target_count'],quoted_include_edges=boundary['quoted_include_edges'],
        independent_header_compilations=10,gcc_scope='strict C90 syntax only; no GCC runtime qualification',artifacts=artifacts,passed=True,
        physical_device_access=False,product_dispatch_admitted=False,filesystem_health_qualified=False,owner_accepted=False,unit_complete=False,release_ready=False,
        qualification_scope='Native source and artifacts at '+source+'; manifest/context at '+args.specification_revision+' with all bound source/build inputs unchanged.'))
    print('Manifest-only continuation completed; native source identity preserved.',flush=True)

if __name__=='__main__':main()
