"""Isolated Win32/WOW64 parser qualification; the product x64 gate is unchanged."""
from pathlib import Path
import argparse, hashlib, json, platform, re, subprocess, sys, time
import xml.etree.ElementTree as ET

ap=argparse.ArgumentParser()
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--codemodel',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
root=a.root.resolve();out=a.output.resolve();out.mkdir()
fixture=out/'fixture';fixture.mkdir();build=out/'build'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert revision==json.loads((a.codemodel.resolve().parent/'summary.json').read_bytes())['source_revision']
before=json.loads((a.codemodel.resolve().parent/'inputs.json').read_bytes())
assert all(sha(root/n)==h for n,h in before.items())
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
reply=a.codemodel.resolve() / '.cmake/api/v1/reply'
model=json.loads(next(reply.glob('codemodel-v2-*.json')).read_bytes())
targets={r['id']:r for r in model['configurations'][0]['targets']}
names={r['name']:r for r in targets.values()}
def data(name):return json.loads((reply/names[name]['jsonFile']).read_bytes())
def own(name):return {Path(p['path']) if Path(p['path']).is_absolute() else root/p['path'] for p in data(name).get('sources',[]) if Path(p['path']).suffix in ('.c','.cpp')}
def closure(name,seen=None):
    seen=set() if seen is None else seen
    if name in seen:return set()
    seen.add(name);result=own(name)
    for edge in data(name).get('dependencies',[]):result |= closure(targets[edge['id']]['name'],seen)
    return result
probes={n:own(n) for n in ('ntfs_capture_probe','ntfs_stream_probe')}
common=set.union(*(closure(n) for n in probes))-set.union(*probes.values())
assert all(p.is_relative_to(root/'source') for p in common)
q=lambda p:'"'+p.as_posix()+'"'
lines=['cmake_minimum_required(VERSION 3.27)','project(NtfsBlockWin32Fixture LANGUAGES C CXX)',
       'set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "Fixture profile" FORCE)',
       'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)','set(CMAKE_C_STANDARD 90)','set(CMAKE_C_STANDARD_REQUIRED YES)','set(CMAKE_C_EXTENSIONS NO)',
       'set(CMAKE_CXX_STANDARD 14)','set(CMAKE_CXX_STANDARD_REQUIRED YES)','set(CMAKE_CXX_EXTENSIONS NO)',
       'if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4 OR NOT CMAKE_VS_PLATFORM_NAME STREQUAL "Win32" OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0" OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")',
       'message(FATAL_ERROR "Pinned Win32 compiler and SDK required")','endif()',
       'find_package(Python3 REQUIRED COMPONENTS Interpreter)','enable_testing()',
       'add_library(ntfs_fixture STATIC '+' '.join(q(p) for p in sorted(common))+')']
def options(n):lines.extend(['target_include_directories('+n+' PRIVATE '+q(root/'source')+')',
                            'target_compile_options('+n+' PRIVATE /W4 /WX /GS /sdl /guard:cf "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")'])
options('ntfs_fixture')
for name,paths in probes.items():
    lines.extend(['add_executable('+name+' '+' '.join(q(p) for p in sorted(paths))+')',
                  'target_link_libraries('+name+' PRIVATE ntfs_fixture)',
                  'target_link_options('+name+' PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)']);options(name)
headers=[]
for index,header in enumerate(('runtime/capture/ntfs_capture.h','runtime/capture/ntfs_stream.h','runtime/capture/ntfs_directory.h','runtime/capture/ntfs_directory_detail.h')):
    p=fixture/('header-'+str(index)+'.cpp');p.write_text('#include "'+header+'"\n',encoding='utf-8',newline='\n');headers.append(p)
lines.append('add_library(ntfs_fixture_headers OBJECT '+' '.join(q(p) for p in headers)+')');options('ntfs_fixture_headers')
for kind in ('capture','stream','directory'):
    lines.extend(['add_test(NAME image.ntfs_'+kind+' COMMAND "${Python3_EXECUTABLE}" '+q(root/('tests/images/test_ntfs_'+kind+'.py'))+' --probe "$<TARGET_FILE:ntfs_'+('capture' if kind=='directory' else kind)+'_probe>" --output "${CMAKE_BINARY_DIR}/ntfs-'+kind+'-cases.json")',
                  'set_tests_properties(image.ntfs_'+kind+' PROPERTIES TIMEOUT 180)'])
lines.extend(['add_test(NAME image.ntfs_closure COMMAND "${Python3_EXECUTABLE}" '+q(root/'tests/images/test_ntfs_closure.py')+' --capture "$<TARGET_FILE:ntfs_capture_probe>" --join "$<TARGET_FILE:ntfs_stream_probe>" --output "${CMAKE_BINARY_DIR}/ntfs-closure-cases.json")',
              'set_tests_properties(image.ntfs_closure PROPERTIES TIMEOUT 180)'])
(fixture/'CMakeLists.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
save(out/'fixture-sources.json',{str(p):sha(p) for p in sorted(common|set.union(*probes.values()))})
save(out/'inputs.json',before)
summary=dict(status='running',source_revision=revision,host=platform.platform(),stages=[],
             scope='Four private supplied-reader/stream probes on Win32/WOW64, derived from exact x64 codemodel; not a full Win32 product or historical host qualification.',
             recipe_sha256=sha(Path(__file__).resolve()),owner_accepted=False,full_0_1_0_complete=False)
def run(name,args):
    command=list(map(str,args));start=time.monotonic()
    with (out/(name+'.log')).open('wb') as log:p=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    summary['stages'].append(dict(name=name,command=command,cwd=str(root),exit_code=p.returncode,seconds=time.monotonic()-start,log=name+'.log'))
    save(out/'summary.json',summary);print(name,p.returncode,flush=True)
    assert p.returncode==0,(name,(out/(name+'.log')).read_text(errors='replace')[-2000:])
try:
    run('configure',['cmake','-S',fixture,'-B',build,'-G','Visual Studio 17 2022','-A','Win32,version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0','-DPython3_EXECUTABLE='+sys.executable])
    run('build',['cmake','--build',build,'--config','Release','--parallel','2'])
    run('native',['ctest','--test-dir',build,'-C','Release','--parallel','1','--output-on-failure','--output-junit',out/'native-junit.xml'])
    tests=ET.parse(out/'native-junit.xml').getroot().findall('.//testcase')
    assert len(tests)==4 and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in tests)
    summary['cases']={p.name:json.loads(p.read_bytes())['count'] for p in build.glob('ntfs-*-cases.json')}
    assert summary['cases']=={'ntfs-directory-cases.json':227,'ntfs-capture-cases.json':154,'ntfs-stream-cases.json':298,'ntfs-closure-cases.json':134}
    clfile=next((build/'CMakeFiles').glob('*/CMakeCXXCompiler.cmake'))
    cl=Path(re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)',clfile.read_text())[1])
    summary['artifacts']=[]
    for name in probes:
        p=build/'Release'/(name+'.exe');summary['artifacts'].append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
        for mode in ('headers','imports','dependents'):run(name+'-'+mode,[cl.with_name('dumpbin.exe'),'/'+mode,p])
        text=(out/(name+'-headers.log')).read_text()
        assert all(v in text for v in ('14C machine (x86)','Dynamic base','NX compatible','Control Flow Guard'))
    summary['header_artifacts']=[dict(path=str(p),sha256=sha(p)) for p in sorted((build/'ntfs_fixture_headers.dir/Release').glob('*.obj'))]
    assert len(summary['header_artifacts'])==4
    summary['inputs_unchanged']=all(sha(root/n)==h for n,h in before.items())
    summary['checkout_clean']=not subprocess.check_output(['git','status','--porcelain'],cwd=root)
    assert summary['inputs_unchanged'] and summary['checkout_clean']
    summary.update(status='pass',native_groups=4)
except BaseException as e:
    summary.update(status='fail',error=repr(e));save(out/'summary.json',summary);raise
save(out/'summary.json',summary)
print('Win32/WOW64 directory/reader checks pass; product x64 gate unchanged.',flush=True)
