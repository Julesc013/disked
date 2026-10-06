"""Build harmless C90 controls and compare exact results with independent integers."""
import argparse, hashlib, json, os, platform, random, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

P = argparse.ArgumentParser()
P.add_argument('--compiler', type=Path, required=True)
P.add_argument('--family', choices=['gcc', 'msvc'], required=True)
P.add_argument('--include', action='append', default=[])
P.add_argument('--lib', action='append', default=[])
P.add_argument('--dumpbin', type=Path, required=True)
P.add_argument('--output', type=Path, required=True)
ARGS = P.parse_args()
ROOT = Path(__file__).resolve().parents[2]
OUT = ARGS.output.resolve()
OUT.mkdir(parents=True, exist_ok=False)
compiler, dumpbin = ARGS.compiler.resolve(), ARGS.dumpbin.resolve()
env = dict(os.environ)
env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
if ARGS.include: env['INCLUDE'] = os.pathsep.join(ARGS.include)
if ARGS.lib: env['LIB'] = os.pathsep.join(ARGS.lib)
commands = []

def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')
def run(name, args, success=True):
    result = subprocess.run([str(x) for x in args], cwd=OUT, env=env, capture_output=True, timeout=30)
    (OUT / (name + '.log')).write_bytes(result.stdout + result.stderr)
    commands.append(dict(command=[str(x) for x in args], cwd=str(OUT), exit_code=result.returncode, log=name+'.log'))
    write('commands.json', commands)
    if success and result.returncode: raise RuntimeError(name + ' failed; log retained')
    return result

sources = ['source/portable/primitives/checked.h', 'source/portable/primitives/checked.c',
           'tests/legacy/primitive_probe.c', 'tests/legacy/run_probes.py', 'tests/legacy/README.md']
identity = dict(observed_at=datetime.now(timezone.utc).isoformat(),
    source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    source_state='dirty' if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT) else 'clean',
    inputs={p:sha(ROOT/p) for p in sources},compiler=dict(path=str(compiler),sha256=sha(compiler)),
    include=ARGS.include,lib=ARGS.lib,host=dict(platform=platform.platform(),machine=platform.machine()),
    scope='Modern control launch of private C90 primitive probes; no historical target or product parser qualification')
write('identity.json', identity)
exe = OUT / 'primitive-probe.exe'
inputs = [ROOT/'source/portable/primitives/checked.c', ROOT/'tests/legacy/primitive_probe.c']
include = ROOT/'source/portable/primitives'
if ARGS.family == 'gcc':
    run('compiler-version', [compiler, '-v'])
    for name in ['cc1','ld']:
        r=run('locate-'+name,[compiler,'-print-prog-name='+name]);p=Path(r.stdout.decode().strip()).resolve()
        identity[name]=dict(path=str(p),sha256=sha(p))
    command=[compiler,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-O2','-I'+str(include),*inputs,'-o',exe]
else:
    run('compiler-version',[compiler],success=False)
    identity['linker']=dict(path=str(compiler.with_name('link.exe')),sha256=sha(compiler.with_name('link.exe')))
    command=[compiler,'/nologo','/TC','/W4','/WX','/O2','/MT','/I'+str(include),*inputs,'/Fe:'+str(exe)]
write('identity.json',identity)
run('build',command)
for kind in ['HEADERS','IMPORTS','DEPENDENTS']: run(kind.lower(),[dumpbin,'/'+kind,exe])

observations=[]
def expect(args, code, output):
    p=subprocess.run([str(exe),*args],cwd=OUT,env=env,capture_output=True,timeout=5)
    actual=p.stdout.decode('ascii').replace('\r\n','\n')
    row=dict(arguments=args,exit_code=p.returncode,stdout=actual,stderr=p.stderr.decode('ascii'),expected_exit=code,expected_stdout=output+'\n')
    row['passed']=(code==p.returncode and actual==output+'\n' and not p.stderr)
    observations.append(row)
    if not row['passed']:
        write('observations.json',observations);raise AssertionError(row)
def value(n): return 'ok '+str(n)+' '+n.to_bytes(8,'little').hex()
expect(['selftest'],0,'ok unchanged_outputs_and_bounds')
profile=run('profile',[exe,'profile']).stdout.decode('ascii').strip()
assert profile.startswith('ok char=8 short=16 ') and profile.endswith('intermediate=32'),profile
maximum=(1<<64)-1
boundary=sorted({0,1,2,*(max(0,(1<<bit)+offset) for bit in [8,16,32,48,63,64] for offset in [-1,0,1])})
rng=random.Random(0xD15CED)
numbers=[n for n in boundary if n<=maximum]+[rng.getrandbits(64) for _ in range(64)]
for n in numbers:
    expect(['roundtrip',str(n)],0,value(n))
    expect(['wire',n.to_bytes(8,'little').hex()],0,value(n))
    expect(['narrow',str(n)],0 if n<=0xffffffff else 2,'ok '+str(n) if n<=0xffffffff else 'refused width')
for a,b in [(maximum,0),(maximum,1),(65535,1),(0xffffffff,1),(maximum,maximum)]+[(rng.getrandbits(64),rng.getrandbits(64)) for _ in range(96)]:
    total=a+b;expect(['add',str(a),str(b)],0 if total<=maximum else 2,value(total) if total<=maximum else 'refused overflow')
for text in ['', '00','01','-1','+1',' 1','1 ','1.0','1e3','0x10','1\t','9x','\u001b[31m']:
    expect(['roundtrip',text],2,'refused invalid')
for n in [1<<64,(1<<64)+1,10**20,10**30]:expect(['roundtrip',str(n)],2,'refused overflow')
for text in ['','00','0'*15,'0'*17,'0'*18,'g'*16]:expect(['wire',text],2,'refused invalid')
for data in [b'',bytes(range(256)),b'\x1b[31m\r\n\t\x00\\',b'A'*256]+[bytes(rng.randrange(256) for _ in range(rng.randrange(257))) for _ in range(32)]:
    display=''.join('\\\\' if b==92 else chr(b) if 32<=b<=126 else '\\x%02X'%b for b in data)
    expect(['escape',data.hex()],0,'ok '+display)
expect(['escape','00'*257],2,'refused invalid')
write('observations.json',observations)
write('results.json',dict(status='pass',cases=len(observations),profile=profile,source=identity,
    executable=dict(path=str(exe),sha256=sha(exe),bytes=exe.stat().st_size),
    historical_lanes={name:'not_run' for name in ['8086','Win16','Win9x','OS2']},
    product_parser='not_run',storage_access='none',limitations=['One modern Windows host','No 16-bit compiler or historical loader/terminal launch','Private primitive probe, not admitted product ABI']))
print(json.dumps(dict(status='pass',cases=len(observations),profile=profile,artifact=sha(exe))))
