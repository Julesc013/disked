"""One-off retirement of the stopped59a39c93 guest's exact session3 grants."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path('C:/ProgramData/DiskEd/qualification')
NONCE='8fa6e3000a5f4181b5cd9ea11e83a7c2'
REVISION='59a39c93b4f3d8f2edfb915a8e15deb1759af8b1'
HASHES={
    'window-station.py':'46bad7a3c0d8ebacb6e59c27d5114fe0cd640216d50e98241cd4b51b7cc12928',
    'object-namespace.py':'683e8f13898063ebacf9c1aae55a15f54f0f21ff6ac1749bfc81c7aefaddfa0e',
    'crypto-device.py':'e5c0c93b21ba4799d952b062ebd13c288d1c4180b899de64791ba27ae0b7450f'}
record=dict(status='running',scope=__doc__,nonce=NONCE,source_revision=REVISION,
            product_test_result=False,grants={})

def load(name):
    path=ROOT/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==HASHES[name]
    spec=importlib.util.spec_from_file_location('owned_recovery_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

try:
    assert Path(__file__).resolve().parent==ROOT
    assert ctypes.windll.shell32.IsUserAnAdmin()
    owner=json.loads((ROOT/'scratch/owner.json').read_bytes())
    actor=json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes())
    source=json.loads((ROOT/'source-owner.json').read_bytes())
    ack=json.loads((ROOT/'stop-acknowledged.json').read_bytes())
    proof=json.loads((ROOT/'proof-result.json').read_bytes())
    setup=json.loads((ROOT/'setup-result.json').read_bytes())
    assert owner['nonce']==actor['nonce']==source['nonce']==ack['nonce']==NONCE
    assert source['revision']==REVISION and ack['owned_job_processes_retired'] is True
    assert ack['command']=='build' and proof['controller_interruption']['product_failure'] is False
    assert all(v['active_processes']==0 for v in proof['job_retirements'])
    assert setup['interactive_dispatch']['quiescent'] is True
    assert actor['name']=='DiskEdTest-8fa6e300'
    assert actor['sid']=='S-1-5-21-385394198-2603589104-1765785984-1157'
    assert actor.get('crypto_device',{}).get('phase') in (None,'retired')
    assert actor.get('null_build',{}).get('phase')=='retired'
    assert actor.get('null_user',{}).get('phase') in (None,'retired')
    for name in HASHES:assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==HASHES[name]
    for key,name in (('object_namespace','object-namespace.py'),('window_station','window-station.py')):
        helper=load(name)
        grant=helper.Grant(recovery=True) if key=='object_namespace' else helper.Grant()
        try:
            grant.retire(quiescent=True)
            assert grant.report['retired'] is True
            record['grants'][key]=grant.report
        finally:grant.close()
    final=json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes())
    assert all(final[key]['phase']=='retired' for key in ('object_namespace','window_station','null_build'))
    record.update(status='pass',prior_owned_job_quiescence_verified=True)
except BaseException as error:
    record.update(status='fail',error=repr(error)[:2000]);raise
finally:
    body=(json.dumps(record,indent=2)+'\n').encode()
    assert len(body)<=32768
    with (ROOT/'recovered-grants.json').open('xb') as stream:stream.write(body)
