"""Replay the framed regression through the existing strict control auditor."""
import copy
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path,PurePosixPath
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
background='--background' in sys.argv
if background:HERE=HERE.parent/'background-controls'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
C=load('framed_control_auditor',ROOT/'.aide/evidence/2026-10-21-cooperative-capture/replay.py');C.TRANSPORT=True
V=load('framed_frame_codec',ROOT/'tests/support/cooperative_capture.py')
receipt=json.loads(C.decode(HERE/'receipt.json.xz',1048576));proof=receipt['guest']['proof'];report=proof['cooperative_capture']
archive=HERE/'retained.tar.xz';C.check(C.sha(archive.read_bytes())==proof['archive_sha256']==report['archive']['sha256'],'archive_identity')
files={}
with tarfile.open(fileobj=io.BytesIO(C.decode(archive,2097152)),mode='r:') as stream:
    for member in stream:
        path=PurePosixPath(member.name)
        C.check(member.isfile() and len(files)<64 and member.size<=262144 and len(path.parts)==1 and member.name not in files and not path.is_absolute(),'archive_member')
        files[member.name]=stream.extractfile(member).read(262145)
expected=json.loads((ROOT/'.aide/evidence/2026-10-21-cooperative-tree/expected.json').read_bytes())
expected['capture_transport']=json.loads((ROOT/'.aide/evidence/2026-10-21-capture-transport/expected.json').read_bytes())
if background:expected['control_modes']+=['background']
expected['control_modes']+=['receiver','receiver_hang']
if background:C.check(expected['control_modes']==json.loads((HERE.parent/'background-expected.json').read_bytes())['control_modes'],'fixed_background_mode_set')
summary=C.audit(files,receipt,expected,V)
launch=json.loads(C.decode(HERE/'launch.json.xz',1048576))
previous=json.loads((HERE/'audit.json').read_bytes()) if (HERE/'audit.json').exists() else {}
revision=launch.get('source_revision',previous.get('source_revision'))
if revision is None:revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
C.check(re.fullmatch('[0-9a-f]{40}',revision),'exact_source_revision');bindings={}
for name,digest in report['sources'].items():
    body=subprocess.check_output(['git','show',revision+':'+name],cwd=ROOT);C.check(hashlib.sha256(body).hexdigest()==digest,'compiled_source_binding:'+name);bindings[name]=digest
cleanup=json.loads(C.decode(HERE/'cleanup.json.xz',1048576));setup=receipt['guest']['setup']
C.check(all(setup[k] for k in ('image_removed','actor_removed','actor_profile_absent','backing_acl_unchanged')) and cleanup[0]['cleanup']['qualification_removed'] and cleanup[0]['cleanup']['image_already_removed'],'owned_cleanup')
rejected=[]
for name in ('altered_raw','missing_frame','false_report'):
    changed=dict(files);other=copy.deepcopy(receipt)
    if name=='altered_raw':changed['normal.stdout']=changed['normal.stdout'][:-1]+bytes([changed['normal.stdout'][-1]^1])
    elif name=='missing_frame':del changed['normal.stdout']
    else:
        control=json.loads(changed['control.json']);control['modes'][0]['transfer']['access']=8;other['guest']['proof']['cooperative_capture']['modes'][0]['transfer']['access']=8
        changed['control.json']=(json.dumps(control,indent=2)+'\n').encode()
        for row in other['guest']['proof']['cooperative_capture']['archive']['entries']:
            if row['path']=='control.json':row.update(bytes=len(changed['control.json']),sha256=C.sha(changed['control.json']))
    try:C.audit(changed,other,expected,V)
    except (ValueError,KeyError):rejected.append(name)
    else:raise ValueError('Corruption accepted:'+name)
result=dict(status='pass',source_revision=revision,summary=summary,source_bindings=bindings,negative_replays=rejected,owned_cleanup_verified=True,product_capture_qualified=False,full_native_suite=False,owner_accepted=False)
(HERE/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k!='source_bindings'}))
