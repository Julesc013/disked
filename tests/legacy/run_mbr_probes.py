"""Explicit installed compiler controls for the same private read-only C core."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--compiler',required=True);p.add_argument('--family',choices=['gcc','msvc'],required=True)
    p.add_argument('--include',action='append',default=[]);p.add_argument('--lib',action='append',default=[])
    p.add_argument('--dumpbin',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[2];out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    compiler=Path(a.compiler).resolve();env=os.environ.copy()
    env['PATH']=str(compiler.parent)+os.pathsep+env.get('PATH','')
    if a.family=='msvc':env['INCLUDE']=os.pathsep.join(a.include);env['LIB']=os.pathsep.join(a.lib)
    commands=[]
    def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
    def write(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    def run(name,args):
        r=subprocess.run([str(x) for x in args],cwd=out,env=env,capture_output=True,timeout=90)
        (out/(name+'.log')).write_bytes(r.stdout+r.stderr)
        commands.append(dict(command=[str(x) for x in args],cwd=str(out),exit_code=r.returncode,log=name+'.log'))
        write('commands.json',commands)
        if r.returncode:raise RuntimeError(name+' failed; retained output')
        return r
    c=['source/portable/primitives/checked.c','source/portable/primitives/view.c','source/portable/primitives/extent.c','source/portable/mbr/mbr.c','source/portable/ebr/ebr.c']
    cpp=['source/runtime/command/json.cpp','tests/unit/mbr_probe.cpp']
    includes=[root/'source/portable/primitives',root/'source/portable/mbr',root/'source/portable/ebr',root/'source/runtime/command']
    sources=c+cpp+['source/portable/primitives/checked.h','source/portable/primitives/view.h','source/portable/primitives/extent.h','source/portable/mbr/mbr.h','source/portable/ebr/ebr.h','source/runtime/command/json.h','tests/property/test_mbr.py','tests/legacy/run_mbr_probes.py']
    identity=dict(source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                  source_state='dirty' if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True) else 'clean',
                  compiler=dict(path=str(compiler),sha256=sha(compiler)),include=a.include,lib=a.lib,host=platform.platform(),
                  inputs=[dict(path=x,sha256=sha(root/x)) for x in sources],c_language='C90',cpp_harness='C++14')
    objects=[]
    for i,path in enumerate(c+cpp):
        obj=out/(str(i)+('.o' if a.family=='gcc' else '.obj'));objects.append(obj)
        if a.family=='gcc':
            driver=compiler if path in c else compiler.with_name('g++.exe')
            args=[driver,'-std=c90' if path in c else '-std=c++14','-pedantic-errors','-Wall','-Wextra','-Werror','-O2']
            args += ['-I'+str(d) for d in includes]+['-c',root/path,'-o',obj]
        else:
            args=[compiler,'/nologo','/TC' if path in c else '/TP','/W4','/WX','/O2','/MT','/GS','/sdl']
            if path in cpp:args+=['/std:c++14','/EHsc']
            args+=['/I'+str(d) for d in includes]+['/c',root/path,'/Fo'+str(obj)]
        run('compile-'+str(i),args)
    exe=out/'mbr-probe.exe'
    if a.family=='gcc':
        driver=compiler.with_name('g++.exe');args=[driver,*objects,'-static','-o',exe]
        identity['cpp_compiler']=dict(path=str(driver),sha256=sha(driver))
        run('compiler-version',[compiler,'--version']);run('cpp-version',[driver,'--version'])
    else:
        args=[compiler,'/nologo',*objects,'/Fe'+str(exe),'/link','kernel32.lib']
        # /Bv with a compile records actual tool versions without relying on banner-only exits.
        run('compiler-version',[compiler,'/Bv','/nologo','/TC','/c',root/c[0],'/I'+str(includes[0]),'/Fo'+str(out/'version.obj')])
    run('link',args)
    for kind in ['HEADERS','IMPORTS','DEPENDENTS']:run(kind.lower(),[a.dumpbin,'/'+kind,exe])
    run('guard',[exe,'--guard'])
    run('cases',[sys.executable,root/'tests/property/test_mbr.py','--probe',exe,'--evidence',out/'observations.json'])
    write('identity.json',identity)
    observations=json.loads((out/'observations.json').read_text(encoding='utf-8'))
    write('results.json',dict(status='pass',cases=observations['cases'],source=identity,executable=dict(path=str(exe),sha256=sha(exe)),
                              limitations=['Modern host only; no historical-loader qualification','Private synthetic-image probe; no admitted storage provider','No independent external parser differential run']))
    print(a.family,'PASS',observations['cases'],sha(exe))


if __name__=='__main__':main()
