import json,os,subprocess
from pathlib import Path
root=Path.cwd();identity=json.loads((root/'.aide-local/exfat-qualification-1e938369/build/generated/build-identity.json').read_bytes())
compiler=Path(identity['compiler_path']);vs=compiler.parents[7]
setup=vs/'Common7/Tools/VsDevCmd.bat';assert setup.is_file(),setup
batch=root/'.aide-local/exfat-draft-environment.cmd'
batch.write_text('@echo off\ncall "'+str(setup)+'" -arch=x64 -host_arch=x64 >nul\nif errorlevel 1 exit /b 1\nset\n',encoding='utf-8')
r=subprocess.run(['cmd','/d','/c',str(batch)],capture_output=True)
assert r.returncode==0
env=os.environ.copy()
for row in r.stdout.decode('utf-8',errors='replace').splitlines():
 if '=' in row and not row.startswith('='):
  key,value=row.split('=',1);env[key]=value
draft=root/'.aide-local/exfat-directory-draft-build';draft.mkdir(exist_ok=True)
probe=(root/'.aide-local/exfat-directory-probe.cpp').read_text().replace('"portable/exfat/exfat.h"','"exfat.h"')
(root/'.aide-local/exfat-directory-probe-local.cpp').write_text(probe,encoding='utf-8')
commands=[['cl','/nologo','/TC','/W4','/WX','/MT','/GS','/sdl','/guard:cf','/I'+str(root/'source'),'/c',str(root/'.aide-local/exfat-directory.c'),'/Fo'+str(draft/'directory.obj')],
 ['cl','/nologo','/TP','/std:c++14','/EHsc','/W4','/WX','/MT','/permissive-','/utf-8','/GS','/sdl','/guard:cf','/I'+str(root/'source'),'/c',str(root/'.aide-local/exfat-directory-probe-local.cpp'),'/Fo'+str(draft/'probe.obj')],
 ['link','/nologo','/guard:cf',str(draft/'directory.obj'),str(draft/'probe.obj'),str(root/'.aide-local/exfat-qualification-1e938369/build/Release/disked_primitives.lib'),str(root/'.aide-local/exfat-qualification-1e938369/build/Release/disked_json.lib'),'kernel32.lib','/out:'+str(draft/'probe.exe')]]
with (root/'.aide-local/exfat-directory-draft-build.log').open('wb') as log:
 for command in commands:
  command[0]=str(compiler if command[0]=='cl' else compiler.with_name('link.exe'))
  result=subprocess.run(command,env=env,capture_output=True,cwd=draft);log.write(result.stdout+result.stderr);log.flush()
  if result.returncode:raise SystemExit(result.returncode)
print('Scratch-only native decoder/probe build passed; no product integration.')
