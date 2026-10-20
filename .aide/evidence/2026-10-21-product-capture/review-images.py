"""Check retained GUI pixels without extracting artifacts or granting visual approval."""
import argparse
import ast
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import tarfile
from types import SimpleNamespace
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-dir',type=Path,default=HERE/'full-native')
DATA=parser.parse_args().evidence_dir.resolve()
definition=importlib.util.spec_from_file_location('capture_receipts',HERE.parent/'2026-10-18-ordinary-worker/review-native.py')
reviewer=importlib.util.module_from_spec(definition);definition.loader.exec_module(reviewer)
check=reviewer.require
record=dict(status='running',actual_images_reviewed=False,owner_accepted=False,release_qualified=False,
            reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

try:
    check(DATA.is_relative_to(HERE) and DATA.is_dir(),'Owned capture evidence directory required')
    result=reviewer.load_receipt(DATA,'receipt');proof=result['guest']['proof']
    check(result['status']==proof['status']=='pass','Native campaign failed')
    revision=proof['source_revision'];check(isinstance(revision,str) and re.fullmatch('[0-9a-f]{40}',revision),'Source revision')
    record['source_revision']=revision
    archive=DATA/'retained.tar.xz';check(archive.stat().st_size<=67108864,'Compressed archive bound')
    with archive.open('rb') as stream:check(hashlib.file_digest(stream,'sha256').hexdigest()==proof['archive_sha256'],'Archive identity')
    prefix='groups/frontend.gui_capture/'
    cases={mode+'-'+str(i) for mode in ('inventory','review','minimum') for i in range(2)}
    wanted={prefix+name+'.png' for name in cases}|{prefix+'gui-capture-cases.json','entry-manifest.json'}
    files={};names=set();total=0
    with lzma.open(archive,'rb') as decoded,tarfile.open(fileobj=decoded,mode='r|') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in names,'Archive member')
            names.add(member.name);total+=member.size
            check(len(names)<=20001 and 0<=member.size<=67108864 and total<=2147483648,'Archive expansion bound')
            if member.name in wanted:
                check(member.size<=16777216,'Selected artifact bound')
                body=stream.extractfile(member).read(member.size+1);check(len(body)==member.size,'Truncated artifact');files[member.name]=body
    check(set(files)==wanted,'Missing GUI artifacts')
    check(hashlib.sha256(files['entry-manifest.json']).hexdigest()==proof['entry_manifest_sha256'],'Manifest identity')
    manifest=json.loads(files['entry-manifest.json'])
    for name,body in files.items():
        if name!='entry-manifest.json':check(manifest[name]==dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest()),'Artifact identity: '+name)
    summary=json.loads(files[prefix+'gui-capture-cases.json'])
    check(summary['passed'] is True and not summary['source_dirty'] and summary['source_revision']==revision,'Capture summary')
    check(summary['executable_sha256'].removeprefix('sha256:')==proof['executables']['disked']['sha256'].removeprefix('sha256:'),'Product identity')
    check(len(summary['captures'])==6 and {c['name'] for c in summary['captures']}==cases,'Six exact cases')
    scope=dict(struct=struct,zlib=zlib);bindings={}
    for path,functions in [('tests/frontend/gui_fixture.py',('capture_background_matches',)),('tests/frontend/test_gui_capture.py',('png',))]:
        body=subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT,timeout=30)
        bindings[path]=hashlib.sha256(body).hexdigest();tree=ast.parse(body)
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions]
        check(len(nodes)==len(functions),'Build-bound pixel reader')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),path,'exec'),scope)
    observations=[]
    for case in summary['captures']:
        body=files[prefix+case['name']+'.png'];geometry=case['geometry']
        check(hashlib.sha256(body).hexdigest()==case['sha256'].removeprefix('sha256:'),'Case PNG identity')
        width,height,pixels=scope['png'](SimpleNamespace(read_bytes=lambda:body))
        check((width,height)==(geometry['width'],geometry['height']),'Client dimensions')
        check(geometry.get('background_matches') is True and scope['capture_background_matches'](pixels,width,height,geometry['background_color']),'Incomplete client background')
        observations.append(dict(name=case['name'],width=width,height=height,background_matches=True))
    record.update(status='pass',scope='Artifact/pixel checks only;actual display and visual review remain required',
                  source_bindings=bindings,archive_sha256=proof['archive_sha256'],
                  product_sha256=proof['executables']['disked']['sha256'].removeprefix('sha256:'),
                  pngs={c['name']:c['sha256'] for c in summary['captures']},observations=observations)
except BaseException as error:
    record.update(status='fail',error=repr(error));raise
finally:
    (DATA/'image-evidence-review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record))
