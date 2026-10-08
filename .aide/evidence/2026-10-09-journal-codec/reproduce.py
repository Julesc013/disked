import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();resume='--resume-existing' in sys.argv
C=R/('.aide-local/goal-0.1.0/clean-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-journal-codec/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W040-codec-'+revision[:8])
if resume:
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
    assert C.exists() and E.exists() and A.exists() and not list(A.iterdir())
    commands=json.loads((E/'commands.json').read_bytes());assert commands[-1]['status']=='fail'
    identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
    assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean'
    assert all('sha256:'+hashlib.sha256((C/name).read_bytes()).hexdigest()==digest for name,digest in identity['inputs'].items())
else:
    assert not subprocess.check_output(['git','status','--porcelain']) and not C.exists()
    E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    print('Running clean '+name,flush=True);argv=[str(x) for x in args]
    try:p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path=E/('clean-'+name+'.log');path.write_bytes((error.stdout or b'')+(error.stderr or b''))
        commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path=E/('clean-'+name+'.log');path.write_bytes(p.stdout+p.stderr)
    commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=p.returncode,status='pass' if p.returncode==0 else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(p.returncode),flush=True)
    if p.returncode:raise RuntimeError(name+' failed; retained log')
    return p
if not resume:run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
if not resume:
    run('configure',['cmake','--preset','windows-bootstrap']);run('build',['cmake','--build','--preset','windows-bootstrap'])
native=run('native-tests-revalidation' if resume else 'native-tests',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=900);assert b'0 tests failed out of 48' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes());P=C/'build/windows-bootstrap/Release'
run('gated-image-cases',[sys.executable,'tests/frontend/test_image_commands.py','--exe',P/'disked.exe','--fault',P/'disked_image_test.exe','--probe',P/'image_file_capture_probe.exe','--root',C,'--validate-schemas','--evidence',E/'gated-image-cases.json'])
images=json.loads((E/'gated-image-cases.json').read_bytes());assert images['passed']
gate=next(x for x in images['records'] if x['name']=='stdio-wait-slot-late')
assert gate['controlled_gate'] and 3.8<=gate['expired_seconds']<5 and gate['after']['status']=='completed' and gate['release_seconds']<8
assert any(x['name']=='product-ignores-test-gate' for x in images['records'])
run('codec-cases',[sys.executable,'tests/journal/test_codec.py','--probe',P/'journal_codec_probe.exe','--root',C,'--evidence',E/'codec-cases.json'])
cases=json.loads((E/'codec-cases.json').read_bytes());assert cases['passed'] and cases['cases']==784 and all(x['passed'] for x in cases['observations'])
assert not cases['production_writer_admitted'] and not cases['physical_durability_qualified'] and not cases['file_io']
run('check',[sys.executable,'spec/tools/specctl.py','check']);run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'])
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W040','--output','.aide-local/context/DE-W040-codec','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W040-codec'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision
assert len(identity['inputs'])==230 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_journal_prototype' not in x for x in deps)
(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ['disked','journal_codec_probe']:
    for kind in ['HEADERS','IMPORTS','DEPENDENTS']:run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
run('launch',[P/'disked.exe','build','inspect','--json'])
assert json.loads((E/'clean-launch.log').read_bytes())['result']['source_revision']==revision
artifacts=[]
for name in ['disked.exe','journal_codec_probe.exe','disked_journal_prototype.lib','disked_hash.lib','disked_json.lib']:
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),sha256=sha(target),bytes=target.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups=48,codec_cases=784,initial_native_campaign_failed=resume,
    product_links_codec=False,controlled_image_gate=dict(cases=images['cases'],expired_seconds=gate['expired_seconds'],release_seconds=gate['release_seconds']),spec_tests=dict(run=175,passed=173,skipped=2),artifacts=artifacts,
    limitations=['Private framing codec and memory sources only; payload semantics, immutable receipt model and guarded flush/effect recovery remain unfinished',
    'No file journal writer, effect dispatch, tail repair, physical/power-loss qualification or production admission; DE-DEC-004 remains proposed',
    'Other hosts/platforms, owner acceptance and independent safety qualification remain unverified']))
print('Clean W040 proposed binary journal codec PASS at '+revision,flush=True)
