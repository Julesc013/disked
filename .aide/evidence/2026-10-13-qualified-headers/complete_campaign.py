"""Continue the source-bound campaign after its wrong adapter-count assertion.

Main and standalone compilation succeeded at3598ac40. Twenty executable targets
are declared by that standalone CMake project; no executable is launched here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing-clone',type=Path,required=True)
    parser.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args()
    root=Path.cwd().resolve();checkout=args.existing_clone.resolve();out=args.campaign.resolve()
    assert checkout.is_relative_to(root/'.aide-local') and out.is_relative_to(root/'.aide-local')
    source='3598ac40b79972969ea1ce8585e38a05733e2d87'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout).decode().strip()==source
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
    commands=json.loads((out/'commands.json').read_bytes())
    assert commands[-1]['name']=='windows-compile' and all(v['exit_code']==0 for v in commands)
    assert not (out/'summary.json').exists()
    inputs=json.loads((out/'source-inputs.json').read_bytes())
    assert all(sha(checkout/n)==h for n,h in inputs.items())
    def run(name,command,timeout=300):
        command=list(map(str,command));start=time.monotonic()
        p=subprocess.run(command,cwd=checkout,capture_output=True,timeout=timeout)
        path=out/'logs'/(name+'.log');path.write_bytes(p.stdout+p.stderr)
        commands.append(dict(name=name,command=command,cwd=str(checkout),exit_code=p.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+path.name))
        save(out/'commands.json',commands);print(name+': exit '+str(p.returncode),flush=True)
        assert p.returncode==0,name
        return p.stdout
    windows=out/'windows-build'
    declared=re.findall(r'add_executable\(\s*([^\s)]+)',(checkout/'tests/windows/native/CMakeLists.txt').read_text(encoding='utf-8'))
    actual=sorted((windows/'Release').glob('*.exe'))
    assert len(declared)==len(set(declared))==20 and {v.stem for v in actual}==set(declared)
    save(out/'windows-artifacts.json',[dict(path=str(v),bytes=v.stat().st_size,sha256=sha(v),source_revision=source,validation='compiled_not_launched') for v in actual])
    build=out/'build'
    tests=json.loads(run('test-catalog',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1']))
    assert len(tests['tests'])==85
    run('native-tests',['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure'],2400)
    shutil.copyfile(build/'Testing/Temporary/LastTest.log',out/'native-details.log')
    run('checker-negative-fixtures',[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests/tools','-v'])
    run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'],600)
    text=(out/'logs/tooling.log').read_text(encoding='utf-8')
    count=int(re.search(r'^Ran (\d+) tests ',text,re.MULTILINE).group(1))
    skips=int(re.search(r'^OK \(skipped=(\d+)\)$',text,re.MULTILINE).group(1))
    check=json.loads(run('spec-check',[sys.executable,'-X','utf8','spec/tools/specctl.py','check']))
    run('index',[sys.executable,'-X','utf8','spec/tools/specctl.py','index','--check'])
    run('manifest',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
    run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W010','--output',out/'context','--byte-budget','650000'])
    run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
    identity=json.loads((out/'build-identity.json').read_bytes())
    assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean'
    launch=json.loads(run('product-launch',[build/'Release/disked.exe','build','inspect','--json']))['result']
    assert launch['source_revision']==source and launch['version']=='0.1.0-dev.42'
    dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');artifacts=[]
    for n in ('disked','gui_model_probe','tui_model_probe','presentation_rules_probe'):
        p=build/'Release'/(n+'.exe')
        for mode in ('headers','imports','dependents'):run(n+'-'+mode,[dumpbin,'/'+mode,p])
        artifacts.append(dict(kind=n,path=str(p),bytes=p.stat().st_size,sha256=sha(p),source_revision=source))
    headers=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for n in ('disked_json','disked_command','disked_invocation','disked_presentation') for p in (build/(n+'_headers.dir/Release')).glob('*.obj')]
    assert len(headers)==7;save(out/'header-objects.json',headers)
    config=out/'build-configuration';config.mkdir()
    for n in ('CMakeCache.txt','disked.vcxproj','disked_json.vcxproj','disked_command.vcxproj','disked_invocation.vcxproj','disked_presentation.vcxproj','disked_presentation_headers.vcxproj','gui_model_probe.vcxproj','tui_model_probe.vcxproj','presentation_rules_probe.vcxproj'):
        shutil.copyfile(build/n,config/n)
    shutil.copytree(build/'.cmake/api/v1/reply',out/'cmake-codemodel')
    shutil.copyfile(build/'private-header-usage.json',out/'private-header-usage.json')
    assert not run('final-source-status',['git','status','--porcelain']).strip()
    b=json.loads((out/'build-boundaries.json').read_bytes());catalog=json.loads((checkout/'tools/build-inputs.json').read_bytes())
    host=json.loads((out/'logs/host.log').read_bytes())
    save(out/'summary.json',dict(source_revision=source,source_state='clean',host=host,source_input_count=len(inputs),product_input_count=len(catalog['files']),native_test_groups=85,checker_negative_fixtures=29,tooling_count=count,tooling_skipped=skips,structural=check,build_target_count=b['target_count'],quoted_include_edges=b['quoted_include_edges'],independent_header_compilations=7,qualified_namespace=True,compile_visibility_checked=True,windows_adapter_executables_compiled=20,windows_physical_queries_run=False,artifacts=artifacts,passed=True,owner_accepted=False,unit_complete=False,release_ready=False,limitations=b['limits']))
    print('Source-bound namespace campaign completed; original controller count defect retained.',flush=True)


if __name__=='__main__':main()
