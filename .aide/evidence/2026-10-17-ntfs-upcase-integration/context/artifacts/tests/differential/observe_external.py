"""Linux-only bounded observation adapter for installed partition utilities."""
import argparse
import hashlib
import json
import os
import re
import resource
import selectors
import signal
import subprocess
import time
import uuid
from pathlib import Path

from observe_native import load_case


def digest(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def child_limits():
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run(argv, cwd, timeout=8, output_limit=1024*1024):
    start = time.monotonic(); buffers = [bytearray(), bytearray()]; outcome = 'exited'
    env = dict(os.environ, LC_ALL='C', LANG='C', HOME=str(cwd), TERM='dumb', NO_COLOR='1')
    with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, preexec_fn=child_limits) as child:
        def kill_group():
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass  # It may exit between observation and kill.
        with selectors.DefaultSelector() as selector:
            for i, stream in enumerate([child.stdout, child.stderr]):
                os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, i)
            while selector.get_map() or child.poll() is None:
                if time.monotonic()-start > timeout:
                    outcome = 'timeout'; kill_group(); break
                for key, _ in selector.select(0.05):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data: selector.unregister(key.fileobj); continue
                    remaining = output_limit-sum(len(b) for b in buffers)
                    buffers[key.data].extend(data[:remaining])
                    if len(data) > remaining:
                        outcome = 'output_limit'; kill_group(); break
                if outcome != 'exited': break
            child.wait(timeout=2)
    result = dict(argv=argv, exit_code=child.returncode, outcome=outcome,
                  elapsed_seconds=time.monotonic()-start)
    for name, buffer in zip(['stdout', 'stderr'], buffers):
        raw = bytes(buffer); result[name+'_sha256'] = 'sha256:'+hashlib.sha256(raw).hexdigest()
        try: result[name] = raw.decode('utf-8')
        except UnicodeDecodeError:
            result[name] = raw.decode('utf-8', 'backslashreplace'); result[name+'_bytes_hex'] = raw.hex()
    return result


def normalize(record, kind, path):
    if record['exit_code'] != 0 or record['outcome'] != 'exited': return None
    if 'stdout_bytes_hex' in record: return None
    if kind == 'sfdisk-json':
        try: value = json.loads(record['stdout'])['partitiontable']
        except (ValueError, KeyError, TypeError): return None
        if not isinstance(value, dict) or value.get('label') not in ['dos', 'gpt']: return None
        if value.get('unit') != 'sectors' or value.get('sectorsize') != 512: return None
        partitions = value.get('partitions', [])
        if not isinstance(partitions, list) or len(partitions) > 1024: return None
        rows = []; slots = set()
        for item in partitions:
            if not isinstance(item, dict) or not isinstance(item.get('node'), str): return None
            if any(type(item.get(key)) is not int or not 0 <= item[key] <= 0xffffffffffffffff for key in ['start', 'size']): return None
            if any(key in item and not isinstance(item[key], str) for key in ['type', 'uuid']): return None
            node = item.get('node', ''); suffix = node[len(str(path)):] if node.startswith(str(path)) else ''
            if not re.fullmatch(r'p?[1-9][0-9]*', suffix): return None
            row = dict(slot=int(suffix.lstrip('p')), start=item['start'], end=item['start']+item['size'])
            if row['slot'] in slots or row['end'] > 0xffffffffffffffff: return None
            slots.add(row['slot'])
            if 'type' in item: row['type'] = item['type'].lower()
            if 'uuid' in item: row['uuid'] = item['uuid'].lower()
            rows.append(row)
        result = dict(label=value['label'], rows=rows, fields=['slot', 'start', 'end', 'type', 'uuid'])
        if value['label'] == 'gpt' and 'id' in value:
            try: result['disk_uuid'] = str(uuid.UUID(value['id']))
            except (ValueError, TypeError, AttributeError): return None
        return result
    if kind == 'sgdisk-print':
        # Ignore names and tool-specific type codes; retain their raw text above.
        rows = [dict(slot=int(m[0]), start=int(m[1]), end=int(m[2])+1)
                for m in re.findall(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+.+$', record['stdout'], re.M)]
        if 'Number  Start (sector)' not in record['stdout']: return None
        result = dict(label='gpt', rows=rows, fields=['slot', 'start', 'end'])
        identity = re.search(r'^Disk identifier \(GUID\): ([0-9A-Fa-f-]{36})$', record['stdout'], re.M)
        if identity: result['disk_uuid'] = identity[1].lower()
        return result
    return None


def identity(tool):
    files = {}; resolved = Path(tool).resolve(); files[str(resolved)] = digest(resolved)
    linked = subprocess.run(['/usr/bin/ldd', tool], capture_output=True, text=True, timeout=15)
    for match in re.findall(r'(?:=>\s*)?(/[^\s()]+)', linked.stdout):
        path = Path(match).resolve()
        if path.is_file(): files[str(path)] = digest(path)
    package = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package} ${Version} ${source:Package} ${source:Version}\n',
                              'fdisk', 'libfdisk1'] if 'sfdisk' in tool else
                             ['/usr/bin/dpkg-query', '-W', '-f=${binary:Package} ${Version} ${source:Package} ${source:Version}\n', 'gdisk'],
                             capture_output=True, text=True, timeout=15)
    version = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=15)
    return dict(path=tool, files=files, version=version.stdout, version_exit=version.returncode,
                package_source_identity=package.stdout, package_exit=package.returncode,
                linked_libraries=linked.stdout, ldd_exit=linked.returncode,
                source_bytes_verified=False)


def observe(corpus, output, sgdisk=False):
    if os.geteuid() == 0: raise PermissionError('Root execution is outside this campaign')
    root = Path(corpus).resolve(); output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    tools = ['/usr/sbin/sfdisk']+(['/usr/sbin/sgdisk'] if sgdisk else [])
    identities = [identity(tool) for tool in tools]; observations = []
    for case in manifest['cases']:
        path = root/case['file']; data = load_case(root, case)
        commands = [('sfdisk-json', ['/usr/sbin/sfdisk', '--json', str(path)]),
                    ('sfdisk-verify', ['/usr/sbin/sfdisk', '--verify', str(path)])]
        if sgdisk and case['family'] == 'gpt':
            commands.append(('sgdisk-print', ['/usr/sbin/sgdisk', '--pretend', '--print', '--verify', str(path)]))
        for kind, argv in commands:
            assert load_case(root, case) == data
            record = run(argv, output)
            try: unchanged = load_case(root, case) == data
            except (OSError, ValueError): unchanged = False
            record.update(name=case['name'], kind=kind, sha256=case['sha256'], input_unchanged=unchanged)
            record['projection'] = normalize(record, kind, path)
            observations.append(record)
            (output/'observations.json').write_text(json.dumps(observations, indent=2)+'\n', encoding='utf-8')
            if not unchanged: raise AssertionError('External invocation changed its fixture; observation retained')
    for tool in identities:
        for path, expected in tool['files'].items():
            if digest(Path(path)) != expected: raise AssertionError('External tool closure changed during observation')
    receipt = dict(uid=os.geteuid(), tools=identities, cases=len(manifest['cases']), observations=observations,
                   scope='Ordinary synthetic 512-byte-sector files; observations are not correctness votes')
    (output/'results.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print('External observations retained:', len(observations))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--corpus', required=True)
    parser.add_argument('--output', required=True); parser.add_argument('--sgdisk', action='store_true')
    args = parser.parse_args(); observe(args.corpus, args.output, args.sgdisk)
