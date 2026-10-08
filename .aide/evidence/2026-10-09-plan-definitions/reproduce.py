"""Clean local reproduction. Requires the pinned compiler/SDK and spec Python deps.

Run from repository root, after committing source changes. Does not fetch remote
code, install software, elevate, access devices, run storage effects or publish.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
C=R/('.aide-local/goal-0.1.0/clean-definitions-'+revision[:8])
E=R/('.aide/evidence/2026-10-09-plan-definitions/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W040-definitions-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    argv=[str(x) for x in args];print('Running clean '+name,flush=True)
    try:p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path=E/('clean-'+name+'.log');path.write_bytes((error.stdout or b'')+(error.stderr or b''))
        commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path=E/('clean-'+name+'.log');path.write_bytes(p.stdout+p.stderr)
    commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=p.returncode,status='pass' if p.returncode==0 else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(p.returncode),flush=True)
    if p.returncode:raise RuntimeError(name+' failed; log retained')
    return p
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','plan_definition_probe','journal_codec_probe','json_codec_probe','provider_guard_probe'])
P=C/'build/windows-bootstrap/Release'
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(journal\\.|protocol.json_codec|disked.acceptance|disked.invocation|provider_guard.positive_control)'])
assert b'0 tests failed out of 6' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('definition-cases',[sys.executable,'tests/journal/test_definitions.py','--probe',P/'plan_definition_probe.exe','--root',C,'--evidence',E/'definition-cases.json'])
cases=json.loads((E/'definition-cases.json').read_bytes());assert cases['passed'] and cases['cases']==243 and all(x['passed'] for x in cases['observations'])
assert not any(cases[k] for k in ('file_io','authenticated','authorizes_effects','validates_durability'))
run('codec-cases',[sys.executable,'tests/journal/test_codec.py','--probe',P/'journal_codec_probe.exe','--root',C,'--evidence',E/'codec-cases.json'])
codec=json.loads((E/'codec-cases.json').read_bytes());assert codec['passed'] and codec['cases']==784
run('check',[sys.executable,'spec/tools/specctl.py','check']);run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W040','--output','.aide-local/context/DE-W040-definitions','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W040-definitions'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision
assert len(identity['inputs'])==235 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_journal_prototype' not in x and 'disked_plan_prototype' not in x for x in deps)
(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','plan_definition_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads((E/'clean-launch.log').read_bytes())['result']['source_revision']==revision
artifacts=[]
for name in ('disked.exe','plan_definition_probe.exe','disked_plan_prototype.lib','journal_codec_probe.exe','disked_journal_prototype.lib','disked_hash.lib','disked_json.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),sha256=sha(target),bytes=target.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups_run=6,native_ctest_groups_available=49,
    definition_cases=243,codec_cases=784,product_links_prototypes=False,spec_tests=dict(run=175,passed=173,skipped=2),artifacts=artifacts,
    limitations=['Focused native validation only; other 43 native groups were not rerun at this revision. Historical full 48-group evidence remains bound to ce9ae70f',
    'Fake definition/receipt binding only. No authenticated authority, actual target observations, guarded intention/flush/effect transitions or semantic journal scanner',
    'No target/file writer, recovery replay, physical/power-loss qualification, other-platform execution or production admission; DE-DEC-004/008 and owner acceptance remain pending']))
print('Clean DE-W040 immutable-definition component PASS at '+revision,flush=True)
