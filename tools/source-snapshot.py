"""Exact shallow/sparse Git snapshot: selected blobs and current trees, no history."""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess

SOURCE_LIMIT = 32 * 1024 * 1024
PACK_LIMIT = 32 * 1024 * 1024
FILE_LIMIT = 2000


def git(root, *arguments, data=None):
    result = subprocess.run(['git', '-C', str(root), *arguments], input=data,
                            capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Snapshot Git command failed: ' + result.stderr[:8192].decode(errors='replace'))
    return result.stdout


def relative(name):
    if not isinstance(name, str):
        raise ValueError('Snapshot path must be text')
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or
            any(c in name for c in '\\:*?[]\0\r\n') or path.as_posix() != name or
            any(p.casefold() == '.git' or p.endswith(('.', ' ')) for p in path.parts)):
        raise ValueError('Unsafe or pattern-ambiguous snapshot path')
    return name


def plain_ancestors(path):
    for parent in (path, *path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if parent.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked snapshot ancestor')


def exact_revision(root, revision):
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('An explicit snapshot revision must be an exact Git commit ID')
    resolved = git(root, 'rev-parse', revision + '^{commit}').decode().strip()
    if resolved != revision:
        raise ValueError('Snapshot revision does not identify the exact commit')
    return revision


def selected_inputs(root, work_id, *, revision=None):
    if revision is not None:
        revision = exact_revision(root, revision)
    def read(name):
        return json.loads(git(root, 'cat-file', 'blob', revision + ':' + name) if revision else (root / name).read_bytes())
    names = set(read('tools/build-inputs.json')['files'])
    rows = read('spec/work/units.json')
    rows = rows if isinstance(rows, list) else rows.get('work_units', rows.get('units', []))
    registry=read('spec/catalog/input-dependencies.json')
    definition=importlib.util.spec_from_file_location('snapshot_input_graph',Path(__file__).resolve().parents[1]/'spec/tools/input_graph.py')
    graph=importlib.util.module_from_spec(definition);definition.loader.exec_module(graph)
    paths=(git(root,'ls-tree','-r','--name-only',revision).decode().splitlines() if revision else
           git(root,'ls-files','--cached','--others','--exclude-standard').decode().splitlines())
    view=dict(meta=read('spec/bundle.json'),concepts={i['id']:i for i in read('spec/catalog/concepts.json')['concepts']},
              work={i['id']:i for i in rows},decisions={i['id']:i for i in read('spec/catalog/decisions.json')['decisions']},
              inputs={i['id']:i for i in registry['inputs']},always=registry['always'],
              instructions=[p for p in paths if PurePosixPath(p).name in ('AGENTS.md','CLAUDE.md') and not p.startswith('.aide-local/')])
    names.update(graph.resolve_inputs(work_id,view,relative)['files'])
    names.update(['AGENTS.md', 'spec/START-HERE.md', 'spec/index.md', 'spec/work/units.json',
                  'spec/bundle.json', '.aide/programmes/disked-0.1.0.json', '.gitattributes', '.gitignore'])
    return sorted(relative(name) for name in names)


def export(root, names, output, work, *, revision=None):
    for path in (root, output, work):
        plain_ancestors(Path(path).absolute())
    root, output, work = Path(root).resolve(), Path(output).resolve(), Path(work).resolve()
    plain_ancestors(output)
    if output == work or not output.is_relative_to(work) or output.exists() or output.is_relative_to(root):
        raise ValueError('Fresh snapshot output must be inside managed work and outside source')
    dirty = bool(git(root, 'status', '--porcelain', '--untracked-files=normal'))
    if revision is None and dirty:
        raise ValueError('An exact snapshot requires a clean source checkout')
    names = sorted(set(relative(name) for name in names))
    if not 0 < len(names) <= FILE_LIMIT:
        raise ValueError('Snapshot selected-file bound exceeded')
    revision = exact_revision(root, revision) if revision is not None else git(root, 'rev-parse', 'HEAD').decode().strip()
    objects = {revision, git(root, 'rev-parse', revision + '^{tree}').decode().strip()}
    entries = {}
    for entry in git(root, 'ls-tree', '-r', '-t', '-z', revision).split(b'\0'):
        if not entry:
            continue
        head, path = entry.split(b'\t', 1)
        mode, kind, oid = head.decode().split()
        if kind == 'tree':
            objects.add(oid)
        entries[path.decode('utf-8')] = (mode, kind, oid)
    requested = []
    for name in names:
        if name not in entries:
            raise ValueError('Untracked selected snapshot input: ' + name)
        mode, kind, oid = entries[name]
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Only ordinary tracked snapshot files are admitted')
        requested.append((name, oid))
    identifiers = ('\n'.join(oid for _, oid in requested)+'\n').encode()
    headers = git(root, 'cat-file', '--batch-check', data=identifiers).splitlines()
    if len(headers) != len(requested) or any(line.split()[1] != b'blob' for line in headers):
        raise ValueError('Selected snapshot object is not an ordinary blob')
    size = sum(int(line.split()[2]) for line in headers)
    if size > SOURCE_LIMIT:
        raise ValueError('Snapshot source-content budget exceeded')
    payload = git(root, 'cat-file', '--batch', data=identifiers)
    files, offset = [], 0
    for name, oid in requested:
        end = payload.index(b'\n', offset)
        actual_oid, kind, length = payload[offset:end].split()
        count = int(length)
        if actual_oid.decode() != oid or kind != b'blob' or count > SOURCE_LIMIT:
            raise ValueError('Snapshot batch object identity/length mismatch')
        data = payload[end+1:end+1+count]
        if len(data) != count or payload[end+1+count:end+2+count] != b'\n':
            raise ValueError('Truncated snapshot batch object')
        offset = end + count + 2
        files.append({'path': name, 'git_blob': oid, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
        objects.add(oid)
    if offset != len(payload):
        raise ValueError('Unexpected trailing snapshot batch bytes')
    if len(objects) > 10000:
        raise ValueError('Snapshot Git-object count exceeds bound')
    metadata = git(root, 'cat-file', '--batch-check', data=('\n'.join(sorted(objects))+'\n').encode())
    if sum(int(line.split()[2]) for line in metadata.splitlines()) > PACK_LIMIT - 1048576:
        raise ValueError('Uncompressed snapshot objects exceed pack admission bound')
    output.mkdir()
    pack = output / 'source.pack'
    with pack.open('xb') as stream:
        result = subprocess.run(['git', '-C', str(root), 'pack-objects', '--stdout', '--compression=9',
                                 '--no-reuse-object', '--no-reuse-delta'],
                                input=('\n'.join(sorted(objects))+'\n').encode(), stdout=stream,
                                stderr=subprocess.PIPE, timeout=120)
    if result.returncode or pack.stat().st_size > PACK_LIMIT:
        raise ValueError('Snapshot pack failed or exceeds its bound')
    manifest = {'schema': 'org.disked.exact-source-snapshot/1', 'revision': revision,
                'exporter_worktree_dirty': dirty,
                'files': files, 'content_bytes': size, 'git_objects': len(objects),
                'pack_bytes': pack.stat().st_size, 'pack_sha256': hashlib.sha256(pack.read_bytes()).hexdigest(),
                'git_history_included': False, 'unselected_blobs_included': False,
                'qualification': 'Exact selected Git blobs and current tree; not a complete repository export'}
    (output / 'source.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    return manifest


def materialize(pack, manifest, destination, git_exe='git'):
    pack, destination = Path(pack), Path(destination)
    plain_ancestors(pack)
    plain_ancestors(destination)
    if destination.exists() or len(manifest['files']) > FILE_LIMIT or manifest['content_bytes'] > SOURCE_LIMIT:
        raise ValueError('Fresh bounded snapshot destination required')
    if pack.stat().st_size > PACK_LIMIT or hashlib.sha256(pack.read_bytes()).hexdigest() != manifest['pack_sha256']:
        raise ValueError('Source pack hash/size mismatch')
    for entry in manifest['files']:
        relative(entry['path'])
    destination.mkdir()
    template = destination / '.empty-template'
    template.mkdir()
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')

    def execute(*arguments, stdin=None):
        command = [git_exe, '-C', str(destination), *arguments]
        result = subprocess.run(command, stdin=stdin, capture_output=True, env=env, timeout=120)
        if result.returncode:
            raise RuntimeError('Source materialization failed: ' + result.stderr[:8192].decode(errors='replace'))
        return result.stdout

    execute('init', '-q', '--template=' + str(template))
    template.rmdir()
    execute('config', 'core.autocrlf', 'false')
    # text=auto without an explicit eol attribute otherwise uses Windows native
    # CRLF even with autocrlf=false. Exact blob transport requires LF here.
    execute('config', 'core.eol', 'lf')
    execute('config', 'core.sparseCheckout', 'true')
    execute('config', 'core.sparseCheckoutCone', 'false')
    with pack.open('rb') as stream:
        execute('index-pack', '--stdin', stdin=stream)
    (destination / '.git/shallow').write_text(manifest['revision']+'\n', encoding='ascii', newline='\n')
    (destination / '.git/info').mkdir(exist_ok=True)
    (destination / '.git/info/sparse-checkout').write_text(
        '\n'.join('/'+entry['path'] for entry in manifest['files'])+'\n', encoding='utf-8', newline='\n')
    execute('update-ref', 'refs/heads/snapshot', manifest['revision'])
    execute('symbolic-ref', 'HEAD', 'refs/heads/snapshot')
    execute('read-tree', '-mu', 'HEAD')
    for entry in manifest['files']:
        path = destination / entry['path']
        if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked snapshot output')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Materialized source differs from its exact Git blob: ' + entry['path'])
    if execute('rev-parse', 'HEAD').decode().strip() != manifest['revision'] or execute('status', '--porcelain'):
        raise ValueError('Materialized selected source is not the exact clean revision')
    return {'status': 'pass', 'revision': manifest['revision'], 'selected_files_verified': len(manifest['files']),
            'source_content_bytes': manifest['content_bytes'], 'git_state': 'clean',
            'scope': 'Shallow sparse checkout of exact selected inputs, without unselected blobs/history'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True)
    parser.add_argument('--revision', help='Exact immutable Git commit; checkout cleanliness is recorded separately')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = Path(os.environ['DISKED_WORK_ROOT'])
    result = export(root, selected_inputs(root, args.work, revision=args.revision), work / 'source-export', work, revision=args.revision)
    print(json.dumps({key: result[key] for key in ('revision', 'content_bytes', 'pack_bytes', 'pack_sha256', 'git_objects')}))
