"""Clean local reproduction of the private repeated-crash journal proof audit.

Requires the recorded Windows compiler/SDK and existing spec Python dependencies.
No remote fetch, install, elevation, media access, storage writer or publication.
Run at the matching source revision from the repository root. Destinations must
not already exist; later evidence-only commits produce a different source stamp.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
C=R/('.aide-local/goal-0.1.0/clean-crash-audit-'+revision[:8])
E=R/('.aide/evidence/2026-10-09-journal-crash-audit/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W040-crash-audit-'+revision[:8])
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
host_command="""$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"""
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout)
assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','model_journal_producer_probe','journal_semantic_probe','guarded_journal_probe','plan_definition_probe','journal_codec_probe','json_codec_probe','provider_guard_probe'])
P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==53
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(journal\\.|protocol.json_codec|disked.acceptance|disked.invocation|provider_guard.positive_control)'])
assert b'0 tests failed out of 10' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('semantic-cases',[sys.executable,'tests/journal/test_semantics.py','--probe',P/'journal_semantic_probe.exe','--root',C,'--evidence',E/'semantic-cases.json'])
semantic=json.loads((E/'semantic-cases.json').read_bytes());assert semantic['passed'] and semantic['cases']==191 and semantic['native_inspections']==382 and all(x['passed'] for x in semantic['observations'])
assert not any(semantic[k] for k in ('authorizes_effects','authenticates','qualifies_durability'))
run('guarded-cases',[sys.executable,'tests/journal/test_guarded.py','--probe',P/'guarded_journal_probe.exe','--root',C,'--evidence',E/'guarded-cases.json'])
guarded=json.loads((E/'guarded-cases.json').read_bytes());assert guarded['passed'] and guarded['cases']==172 and guarded['actions']==4320 and all(x['passed'] for x in guarded['observations'])
assert not any(guarded[k] for k in ('file_io','authenticated','authorizes_effects','physical_durability_qualified'))
run('producer-cases',[sys.executable,'tests/journal/test_producer.py','--probe',P/'model_journal_producer_probe.exe','--semantic-probe',P/'journal_semantic_probe.exe','--root',C,'--evidence',E/'producer-cases.json'])
producer=json.loads((E/'producer-cases.json').read_bytes());assert producer['passed'] and producer['cases']==158 and producer['generations']==166 and producer['prefix_inspections']==307 and producer['rejection_cases']==10 and all(x['passed'] for x in producer['observations'])
assert not any(producer[k] for k in ('file_io','authenticated','authorizes_effects','qualifies_durability'))
run('crash-audit-cases',[sys.executable,'tests/journal/test_crash_audit.py','--probe',P/'model_journal_producer_probe.exe','--root',C,'--evidence',E/'crash-audit-cases.json'])
audit=json.loads((E/'crash-audit-cases.json').read_bytes());assert audit['passed'] and audit['cases']==259 and audit['actions']==6370 and audit['generations']==326 and all(x['passed'] for x in audit['observations'])
assert not any(audit[k] for k in ('file_io','authorizes_effects','qualifies_durability'))
run('definition-cases',[sys.executable,'tests/journal/test_definitions.py','--probe',P/'plan_definition_probe.exe','--root',C,'--evidence',E/'definition-cases.json'])
cases=json.loads((E/'definition-cases.json').read_bytes());assert cases['passed'] and cases['cases']==243 and all(x['passed'] for x in cases['observations'])
assert not any(cases[k] for k in ('file_io','authenticated','authorizes_effects','validates_durability'))
run('codec-cases',[sys.executable,'tests/journal/test_codec.py','--probe',P/'journal_codec_probe.exe','--root',C,'--evidence',E/'codec-cases.json'])
codec=json.loads((E/'codec-cases.json').read_bytes());assert codec['passed'] and codec['cases']==784
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==931
manifest=run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']);manifest=json.loads(manifest.stdout);assert manifest['files']==248 and manifest['bytes']==1540773
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W040','--output','.aide-local/context/DE-W040-producer','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W040-producer'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision
assert len(identity['inputs'])==250 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all(not any(lib in x for lib in ('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer')) for x in deps)
(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','model_journal_producer_probe','journal_semantic_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads((E/'clean-launch.log').read_bytes())['result']['source_revision']==revision
artifacts=[]
for name in ('disked.exe','model_journal_producer_probe.exe','disked_model_journal_producer.lib','journal_semantic_probe.exe','disked_journal_semantics.lib','guarded_journal_probe.exe','disked_guarded_model.lib','plan_definition_probe.exe','disked_plan_prototype.lib','journal_codec_probe.exe','disked_journal_prototype.lib','disked_hash.lib','disked_json.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),sha256=sha(target),bytes=target.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups_run=10,native_ctest_groups_available=53,
    semantic_cases=191,semantic_native_inspections=382,guarded_cases=172,guarded_actions=4320,definition_cases=243,codec_cases=784,producer_cases=158,producer_generations=166,producer_prefix_inspections=307,producer_rejection_cases=10,crash_audit_cases=259,crash_audit_actions=6370,crash_audit_generations=326,product_links_prototypes=False,structural_checks=931,manifest_files=248,manifest_bytes=1540773,
    spec_tests=dict(run=175,passed=173,skipped=2),artifacts=artifacts,
    limitations=['Focused native validation only; other 43 native groups were not rerun at this revision. Historical full 48-group evidence remains bound to ce9ae70f',
    'Closed fake-memory stable/volatile journal and target model; fake observations, worker exit and qualified flush assumptions, not authenticated authority or OS/hardware evidence',
    'Semantic reader validates private declarations; live reconciliation remains required and no replay, retirement, authority or durability claim is granted. Native model-history binary production is integrated as declaration fixtures; it is not a live append/flush adapter',
    'No target/file writer, physical/power-loss qualification, other-platform execution or production admission; DE-DEC-004/008 and owner acceptance remain pending']))
print('Clean DE-W040 repeated-crash audit PASS at '+revision,flush=True)
