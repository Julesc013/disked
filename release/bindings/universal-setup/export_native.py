"""Export an exact pinned source closure into a new owned fixture directory.

Read Git blobs as data. Never run upstream scripts or modify their checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
LOCK = ROOT / 'external/universal-setup/native-source-lock.json'


def export(repository, output):
    lock = json.loads(LOCK.read_bytes())
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('new export root required')
    # Resolve and inspect existing parents before creating the owned root.
    parent = output.parent.resolve(strict=True)
    for path in [output.parent, *output.parent.parents]:
        if path.is_symlink() or path.is_junction():
            raise ValueError('linked export parent')
    output = parent / output.name
    tree = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', lock['revision']+'^{tree}']).decode().strip()
    if tree != lock['tree']:
        raise ValueError('source tree identity mismatch')
    # Retrieve and verify the whole bounded closure before creating output.
    content = []
    seen = set()
    total = 0
    for row in lock['files']:
        name = row['path']
        if not name or '\\' in name or ':' in name or any(p in ('', '.', '..') for p in name.split('/')):
            raise ValueError('unsafe source path')
        if name.casefold() in seen:
            raise ValueError('duplicate source path')
        seen.add(name.casefold())
        data = subprocess.check_output(['git', '-C', str(repository), 'show', lock['revision']+':'+name])
        total += len(data)
        if total > 8*1024*1024 or len(content) >= 128:
            raise ValueError('source closure budget')
        if len(data) != row['bytes'] or 'sha256:'+hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('source content mismatch: '+name)
        blob = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', lock['revision']+':'+name]).decode().strip()
        if blob != row['blob']:
            raise ValueError('source blob mismatch: '+name)
        content.append((name, data))
    output.mkdir()
    for name, data in content:
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as file:
            file.write(data)
    (output/'disked-source-export.json').write_text(json.dumps({
        'schema':'org.disked.setup-native-export/1','revision':lock['revision'],
        'tree':tree,'lock_sha256':'sha256:'+hashlib.sha256(LOCK.read_bytes()).hexdigest(),
        'files':len(content),'bytes':total,'upstream_scripts_executed':False},indent=2)+'\n',
        encoding='utf-8',newline='\n')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        output=export(args.repository,args.output)
        print(json.dumps({'export':str(output),'upstream_scripts_executed':False}))
        return 0
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as error:
        print(json.dumps({'status':'refused','reason':str(error),'partial_output':'retained_if_created'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
