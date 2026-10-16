"""Exact-source Win32/WOW64 private NTFS reader and owned-worker supplement."""
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
reply=a.codemodel.resolve()/'.cmake/api/v1/reply'
model=json.loads(next(reply.glob('codemodel-v2-*.json')).read_bytes())
targets={r['id']:r for r in model['configurations'][0]['targets']}
names={r['name']:r for r in targets.values()}
def data(n):return json.loads((reply/names[n]['jsonFile']).read_bytes())
def own(n):return {Path(p['path']) if Path(p['path']).is_absolute() else root/p['path'] for p in data(n).get('sources',[]) if Path(p['path']).suffix in ('.c','.cpp')}
def defs(n):return sorted({d['define'] for g in data(n).get('compileGroups',[]) for d in g.get('defines',[]) if d['define'] not in ('WIN32','_WINDOWS','NDEBUG')})
def closure(n,seen=None):
    seen=set() if seen is None else seen
    if n in seen:return set()
    seen.add(n);result=own(n)
    for edge in data(n).get('dependencies',[]):result|=closure(targets[edge['id']]['name'],seen)
    return result
probes={n:own(n) for n in ('ntfs_file_probe','ntfs_file_fault','ntfs_capture_probe','ntfs_names_probe','ntfs_stream_probe','ntfs_worker_probe','ntfs_worker_fault')}
variants={n:own(n) for n in ('disked_ntfs_file','disked_ntfs_file_fault','disked_ntfs_snapshot','disked_ntfs_snapshot_fault','disked_ntfs_worker','disked_ntfs_worker_fault','disked_observation_worker','disked_observation_worker_fault')}
assert all(len(v)==1 for v in variants.values())
common=set.union(*(closure(n) for n in probes))-set.union(*probes.values())-set.union(*variants.values())
assert all(p.is_relative_to(root/'source') for p in common)
q=lambda p:'"'+p.as_posix()+'"'
lines=['cmake_minimum_required(VERSION 3.27)','project(NtfsFilenameWin32Fixture LANGUAGES C CXX)',
       'set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "Fixture profile" FORCE)',
       'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)','set(CMAKE_C_STANDARD 90)','set(CMAKE_C_STANDARD_REQUIRED YES)','set(CMAKE_C_EXTENSIONS NO)',
       'set(CMAKE_CXX_STANDARD 14)','set(CMAKE_CXX_STANDARD_REQUIRED YES)','set(CMAKE_CXX_EXTENSIONS NO)',
       'if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4 OR NOT CMAKE_VS_PLATFORM_NAME STREQUAL "Win32" OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0" OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")',
       'message(FATAL_ERROR "Pinned Win32 compiler and SDK required")','endif()',
       'find_package(Python3 REQUIRED COMPONENTS Interpreter)','enable_testing()',
       'add_library(ntfs_fixture STATIC '+' '.join(q(p) for p in sorted(common))+')']
def options(n,definitions=()):
    lines.extend(['target_include_directories('+n+' PRIVATE '+q(root/'source')+')',
                  'target_compile_definitions('+n+' PRIVATE _WIN32_WINNT=0x0A00 '+' '.join(definitions)+')',
                  'target_compile_options('+n+' PRIVATE /W4 /WX /GS /sdl /guard:cf "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")'])
options('ntfs_fixture')
for n,paths in variants.items():
    definitions=defs(n)
    testing=[d for d in definitions if d.startswith('DISKED_')]
    assert bool(testing)==n.endswith('_fault'),(n,testing)
    lines.append('add_library('+n+' STATIC '+' '.join(q(p) for p in sorted(paths))+')')
    deps={targets[e['id']]['name'] for e in data(n).get('dependencies',[]) if targets[e['id']]['name'] in variants}
    lines.append('target_link_libraries('+n+' PUBLIC ntfs_fixture '+' '.join(sorted(deps))+' advapi32)')
    options(n,definitions)
for n,paths in probes.items():
    dep={'ntfs_file_probe':'disked_ntfs_file','ntfs_file_fault':'disked_ntfs_file_fault','ntfs_worker_probe':'disked_ntfs_worker','ntfs_worker_fault':'disked_ntfs_worker_fault'}.get(n,'ntfs_fixture')
    lines.extend(['add_executable('+n+' '+' '.join(q(p) for p in sorted(paths))+')','target_link_libraries('+n+' PRIVATE '+dep+' advapi32)',
                  'target_link_options('+n+' PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)']);options(n,defs(n))
headers=[]
for i,h in enumerate(('runtime/capture/ntfs_membership.h','runtime/capture/ntfs_membership_detail.h','runtime/capture/ntfs_names.h','runtime/capture/ntfs_attributes_detail.h','runtime/capture/ntfs_capture.h','providers/image/ntfs_file.h','runtime/capture/ntfs_directory.h','runtime/capture/ntfs_directory_detail.h','providers/image/ntfs_snapshot.h','platform/windows/storage/ntfs_worker.h')):
    p=fixture/('header-'+str(i)+'.cpp');p.write_text('#include "'+h+'"\n',encoding='utf-8',newline='\n');headers.append(p)
lines.append('add_library(ntfs_fixture_headers OBJECT '+' '.join(q(p) for p in headers)+')');options('ntfs_fixture_headers')
tests={
 'membership_file':['--probe','$<TARGET_FILE:ntfs_file_probe>','--fault','$<TARGET_FILE:ntfs_file_fault>','--pure','$<TARGET_FILE:ntfs_capture_probe>'],
 'membership':['--probe','$<TARGET_FILE:ntfs_capture_probe>'],
 'names':['--probe','$<TARGET_FILE:ntfs_names_probe>'],
 'capture':['--probe','$<TARGET_FILE:ntfs_capture_probe>'],
 'stream':['--probe','$<TARGET_FILE:ntfs_stream_probe>'],
 'directory':['--probe','$<TARGET_FILE:ntfs_capture_probe>'],
 'closure':['--capture','$<TARGET_FILE:ntfs_capture_probe>','--join','$<TARGET_FILE:ntfs_stream_probe>'],
 'file':['--probe','$<TARGET_FILE:ntfs_file_probe>','--fault','$<TARGET_FILE:ntfs_file_fault>'],
 'directory_file':['--probe','$<TARGET_FILE:ntfs_file_probe>','--fault','$<TARGET_FILE:ntfs_file_fault>','--pure','$<TARGET_FILE:ntfs_capture_probe>'],
 'worker':['--probe','$<TARGET_FILE:ntfs_worker_probe>','--fault','$<TARGET_FILE:ntfs_worker_fault>'],
 'directory_worker':['--probe','$<TARGET_FILE:ntfs_worker_probe>','--fault','$<TARGET_FILE:ntfs_worker_fault>']}
for kind,args in tests.items():
    lines.extend(['add_test(NAME image.ntfs_'+kind+' COMMAND "${Python3_EXECUTABLE}" '+q(root/('tests/images/test_ntfs_'+kind+'.py'))+' '+' '.join('"'+s+'"' for s in args)+' --output "${CMAKE_BINARY_DIR}/ntfs-'+kind.replace('_','-')+'-cases.json")',
                  'set_tests_properties(image.ntfs_'+kind+' PROPERTIES TIMEOUT 240 RESOURCE_LOCK disked_fake_workers)'])
(fixture/'CMakeLists.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
save(out/'fixture-sources.json',{str(p):sha(p) for p in sorted(common|set.union(*variants.values())|set.union(*probes.values()))})
save(out/'variant-definitions.json',{n:defs(n) for n in variants})
save(out/'inputs.json',before)
summary=dict(status='running',work_id='DE-W096',source_revision=revision,host=platform.platform(),stages=[],
             scope='Eleven selected native NTFS held-file membership/filename/reader/directory/owned-worker groups on Win32/WOW64, codemodel-derived with distinct normal/fault variants. Not a full Win32 product or historical-host qualification.',
             recipe_sha256=sha(Path(__file__).resolve()),owner_accepted=False,full_0_1_0_complete=False)
def run(name,args):
    command=list(map(str,args));start=time.monotonic()
    with (out/(name+'.log')).open('wb') as log:p=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    summary['stages'].append(dict(name=name,command=command,cwd=str(root),exit_code=p.returncode,seconds=time.monotonic()-start,log=name+'.log'))
    save(out/'summary.json',summary);print(name,p.returncode,flush=True)
    assert p.returncode==0,(name,(out/(name+'.log')).read_text(errors='replace')[-2000:])
try:
    run('configure',['cmake','-S',fixture,'-B',build,'-G','Visual Studio 17 2022','-A','Win32,version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0','-DPython3_EXECUTABLE='+sys.executable])
    run('build',['cmake','--build',build,'--config','Release','--parallel','4'])
    run('registered',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1'])
    assert {r['name'] for r in json.loads((out/'registered.log').read_bytes())['tests']}=={'image.ntfs_'+k for k in tests}
    run('native',['ctest','--test-dir',build,'-C','Release','--parallel','1','--output-on-failure','--stop-on-failure','--output-junit',out/'native-junit.xml'])
    actual=ET.parse(out/'native-junit.xml').getroot().findall('.//testcase')
    assert len(actual)==11 and {t.attrib['name'] for t in actual}=={'image.ntfs_'+k for k in tests}
    assert all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in actual)
    summary['cases']={p.name:json.loads(p.read_bytes()).get('count',json.loads(p.read_bytes()).get('cases')) for p in build.glob('ntfs-*-cases.json')}
    for n,v in {'membership-file':496,'membership':193,'names':247,'directory':227,'capture':155,'stream':298,'closure':134,'file':79,'directory-file':550,'directory-worker':235}.items():assert summary['cases']['ntfs-'+n+'-cases.json']==v
    clfile=next((build/'CMakeFiles').glob('*/CMakeCXXCompiler.cmake'))
    cl=Path(re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)',clfile.read_text())[1])
    summary['artifacts']=[]
    for n in probes:
        p=build/'Release'/(n+'.exe');summary['artifacts'].append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
        for mode in ('headers','imports','dependents'):run(n+'-'+mode,[cl.with_name('dumpbin.exe'),'/'+mode,p])
        text=(out/(n+'-headers.log')).read_text()
        assert all(v in text for v in ('14C machine (x86)','Dynamic base','NX compatible','Control Flow Guard'))
    summary['header_artifacts']=[dict(path=str(p),sha256=sha(p)) for p in sorted((build/'ntfs_fixture_headers.dir/Release').glob('*.obj'))]
    assert len(summary['header_artifacts'])==10
    summary['inputs_unchanged']=all(sha(root/n)==h for n,h in before.items())
    summary['checkout_clean']=not subprocess.check_output(['git','status','--porcelain'],cwd=root)
    assert summary['inputs_unchanged'] and summary['checkout_clean']
    summary.update(status='pass',native_groups=11)
except BaseException as e:
    summary.update(status='fail',error=repr(e),inputs_unchanged=all(sha(root/n)==h for n,h in before.items()),checkout_clean=not subprocess.check_output(['git','status','--porcelain'],cwd=root));save(out/'summary.json',summary);raise
save(out/'summary.json',summary)
print('Eleven Win32/WOW64 private held-file membership/filename/reader/worker groups pass; product x64 gate unchanged.',flush=True)
