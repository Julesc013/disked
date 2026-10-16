"""Build and test the private FAT directory traversal at an exact clean source."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-revision', required=True)
    p.add_argument('--existing-clone', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--gcc-executable', type=Path, required=True)
    a = p.parse_args(); root = Path.cwd().resolve()
    clone, out = a.existing_clone.resolve(), a.output.resolve()
    assert re.fullmatch('[0-9a-f]{40}', a.source_revision)
    assert clone.is_relative_to(root/'.aide-local') and out.is_relative_to(root/'.aide-local')
    out.mkdir(); (out/'logs').mkdir(); commands = []

    def run(name, command, timeout=300):
        command = list(map(str, command)); start = time.monotonic()
        r = subprocess.run(command, cwd=clone, capture_output=True, timeout=timeout)
        (out/'logs'/(name+'.log')).write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name, command=command, cwd=str(clone), exit_code=r.returncode,
                             elapsed_seconds=round(time.monotonic()-start, 3), log='logs/'+name+'.log'))
        save(out/'commands.json', commands)
        print(name+': exit '+str(r.returncode), flush=True)
        assert r.returncode == 0, name
        return r.stdout

    assert Path(run('origin',['git','remote','get-url','origin']).decode().strip()).resolve() == root
    assert not run('existing-status',['git','status','--porcelain']).strip()
    run('fetch',['git','fetch','--no-tags','origin',a.source_revision])
    run('checkout',['git','checkout','--detach',a.source_revision])
    assert not run('source-status',['git','status','--porcelain']).strip()
    host = json.loads(run('host',['powershell','-NoProfile','-Command',
        '$walkIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();'
        '$walkPrincipal=[System.Security.Principal.WindowsPrincipal]::new($walkIdentity);'
        '$walkOS=Get-CimInstance Win32_OperatingSystem;'
        '[ordered]@{identity=$walkIdentity.Name;elevated=$walkPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);'
        'os=$walkOS.Caption;version=$walkOS.Version;architecture=$walkOS.OSArchitecture}|ConvertTo-Json -Compress']))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    catalog=json.loads((clone/'tools/build-inputs.json').read_bytes())
    names=set(catalog['files']) | {p.relative_to(clone).as_posix() for p in (clone/'source').rglob('*') if p.is_file()}
    names |= {'AGENTS.md','spec/work/units.json','spec/catalog/input-dependencies.json','spec/tools/specctl.py','tools/check-source-map.py','tools/check-build-boundaries.py'}
    inputs={p:sha((clone/p).read_bytes()) for p in sorted(names)}
    save(out/'source-inputs.json',inputs)
    blobs={}
    for row in run('source-tree',['git','ls-tree','-r','-z',a.source_revision]).split(b'\0'):
        if row:
            header,path=row.split(b'\t',1); path=path.decode()
            if path in inputs: blobs[path]=header.split()[2].decode()
    assert set(blobs)==set(inputs)
    for path,blob in blobs.items():
        data=(clone/path).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
    save(out/'source-blob-bindings.json',blobs)
    run('source-map',[sys.executable,'-X','utf8','tools/check-source-map.py'])
    run('python-environment',[sys.executable,'-c',"import sys,importlib.metadata as m;print(sys.version);print('PyYAML='+m.version('PyYAML'));print('jsonschema='+m.version('jsonschema'))"])
    run('cmake-version',['cmake','--version'])
    gcc=a.gcc_executable.resolve(); assert gcc.is_file()
    run('gcc-version',[gcc,'--version'])
    run('gcc-c90',[gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only','source/portable/fat/allocation.c'])
    save(out/'gcc-identity.json',dict(path=str(gcc),sha256=sha(gcc.read_bytes()),scope='C90 syntax only; no GCC runtime/ABI qualification'))
    build=out/'build'
    run('configure',['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
    run('build',['cmake','--build',build,'--config','Release','--parallel','4'],1200)
    identity=json.loads((build/'generated/build-identity.json').read_bytes())
    assert identity['identity']['source_revision']==a.source_revision and identity['identity']['source_state']=='clean'
    assert identity['inputs']=={p:inputs[p] for p in catalog['files']}
    save(out/'build-identity.json',identity)
    run('boundaries',[sys.executable,'-X','utf8','tools/check-build-boundaries.py','--build',build,'--output',out/'build-boundaries.json'])
    tests=json.loads(run('test-catalog',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1']))
    assert len(tests['tests'])==110
    save(out/'test-catalog.json',tests)
    run('native-tests',['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure'],2400)
    shutil.copyfile(build/'Testing/Temporary/LastTest.log',out/'native-details.log')
    cases=json.loads((build/'fat-traversal-cases.json').read_bytes())
    assert cases['passed'] and cases['test_methods']==11 and cases['cases']==103 and cases['maximum_entries']==17601
    save(out/'fat-traversal-cases.json',cases)
    run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'],600)
    tooling=(out/'logs/tooling.log').read_text(encoding='utf-8')
    count=int(re.search(r'^Ran (\d+) tests ',tooling,re.MULTILINE).group(1))
    skipped=int(re.search(r'^OK \(skipped=(\d+)\)$',tooling,re.MULTILINE).group(1))
    structural=json.loads(run('spec-check',[sys.executable,'-X','utf8','spec/tools/specctl.py','check']))
    run('index',[sys.executable,'-X','utf8','spec/tools/specctl.py','index','--check'])
    run('manifest',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
    run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W053','--output',out/'context','--byte-budget','900000'])
    run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',out/'context'])
    launch=json.loads(run('product-launch',[build/'Release/disked.exe','build','inspect','--json']))['result']
    assert launch['source_revision']==a.source_revision and launch['version']=='0.1.0-dev.52'
    dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe'); artifacts=[]
    for name in ('disked','fat_traversal_probe'):
        path=build/'Release'/(name+'.exe')
        for mode in ('headers','imports','dependents'):run(name+'-'+mode,[dumpbin,'/'+mode,path])
        artifacts.append(dict(kind=name,path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes()),source_revision=a.source_revision))
    objects=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
             for p in build.glob('*_headers.dir/Release/*.obj')]
    assert len(objects)==21
    save(out/'header-objects.json',objects)
    config=out/'build-configuration';config.mkdir()
    for name in ('CMakeCache.txt','disked.vcxproj','disked_fat.vcxproj','disked_fat_headers.vcxproj','disked_fat_traversal.vcxproj','disked_fat_traversal_headers.vcxproj','fat_traversal_probe.vcxproj'):
        shutil.copyfile(build/name,config/name)
    shutil.copyfile(build/'private-header-usage.json',out/'private-header-usage.json')
    assert not run('final-source-status',['git','status','--porcelain']).strip()
    assert all(sha((clone/p).read_bytes())==digest for p,digest in inputs.items())
    save(out/'summary.json',dict(source_revision=a.source_revision,source_state='clean',host=host,passed=True,
         native_test_groups=110,independent_header_compilations=21,tooling_count=count,tooling_skipped=skipped,
         traversal_methods=11,traversal_cases=103,maximum_entries=17601,maximum_pages=cases['maximum_pages'],source_input_count=len(inputs),structural=structural,
         artifacts=artifacts,host_io_in_traversal=False,physical_device_access=False,owner_accepted=False,
         recursive_extraction_qualified=False,release_ready=False))
    print('Exact-source FAT directory traversal campaign completed.',flush=True)


if __name__=='__main__':main()
