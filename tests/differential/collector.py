"""Write bounded participant evidence through a caller-owned execution port.

No process launcher lives here. The campaign owner supplies a qualified runner
and its measured identity; mocked runners establish serialization tests only.
"""
import copy
import json
import math
import os
from pathlib import Path
import stat

from evidence import Artifacts, EvidenceError, declared_inputs, digest, managed_path, require, write_report
from projections import external_projection, field, native_projection, native_request, strict_json


def executable_hash(value):
    path = Path(value)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not getattr(before, 'st_file_attributes', 0) & 0x400 and
            before.st_nlink == 1 and 0 < before.st_size <= 64 * 1024 * 1024, 'executable_file')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        body = stream.read(64 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    require(len(body) == before.st_size and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) and
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns), 'executable_changed')
    # Windows path/handle stat can expose different ctime meanings. Compare
    # each source to itself; file identity, size and mtime must agree across both.
    return digest(body)


class Output:
    def __init__(self, root):
        self.root = root
        self.bytes_written = 0
        self.files = 0

    def artifact(self, name, body):
        require(type(body) is bytes and len(body) <= 2 * 1024 * 1024, 'artifact_write_bound')
        require(self.bytes_written + len(body) <= 64 * 1024 * 1024 and self.files < 2048, 'collector_write_bound')
        path = Artifacts(self.root).path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        managed_path(path, self.root)
        with path.open('xb') as stream:
            stream.write(body)
        self.bytes_written += len(body)
        self.files += 1
        return dict(path=name, bytes=len(body), sha256=digest(body))

    def checkpoint(self, directory, value):
        temporary = directory / 'receipt.next.json'
        final = directory / 'results.json'
        for path in (temporary, final):
            managed_path(path, self.root)
        if final.exists():
            info = final.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'receipt_replaced')
        remaining = 64 * 1024 * 1024 - self.bytes_written
        written = write_report(temporary, value, limit=min(remaining, 8 * 1024 * 1024))
        self.bytes_written += written
        os.replace(temporary, final)


def process_result(value, policy):
    """Require terminal ownership evidence; never infer it from a timeout."""
    require(isinstance(value, dict) and set(value) == {'outcome', 'exit_code', 'elapsed_seconds', 'stdout', 'stderr', 'terminal'} and
            value['terminal'] is True, 'runner_terminal_result')
    stdout, stderr = value['stdout'], value['stderr']
    require(type(stdout) is bytes and type(stderr) is bytes and len(stdout) + len(stderr) <= 1024 * 1024, 'runner_output_bound')
    code, elapsed, outcome = (value[k] for k in ('exit_code', 'elapsed_seconds', 'outcome'))
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and
            0 <= elapsed <= policy['timeout_seconds'] + 2, 'runner_elapsed')
    require(outcome in ('exited', 'timeout', 'output_limit', 'unavailable') and
            (type(code) is int if outcome == 'exited' else code is None or type(code) is int) and
            (outcome != 'unavailable' or code is None), 'runner_outcome')
    if outcome == 'exited':
        status = 'completed' if code == 0 else 'refused' if 0 < code < 256 else 'crashed'
    else:
        status = dict(timeout='timed_out', output_limit='output_limited', unavailable='unavailable')[outcome]
    return status


def collect(manifest, root, expected_snapshot, participant, measured_identity, commands, execute):
    """Collect one participant; commands come from the fixed adapter, not data.

    execute(argv=..., cwd=..., payload=..., timeout=..., output_limit=...) must
    enforce the selected worker profile, own/retire the entire process tree,
    and return terminal raw bytes or raise without claiming quiescence.
    """
    manifest = copy.deepcopy(manifest)
    require(callable(execute) and isinstance(os.environ.get('DISKED_WORK_ROOT'), str), 'managed_runner_required')
    managed = Path(os.environ['DISKED_WORK_ROOT']).resolve(strict=True)
    require(not managed.is_relative_to(Path(__file__).resolve().parents[2]), 'repository_is_not_scratch')
    root = managed_path(root, managed)
    reader, cases, tuples, identities = declared_inputs(manifest, root, expected_snapshot)
    require(participant in identities, 'participant_not_declared')
    profile, binaries = identities[participant]
    require(profile['path_style'] == ('windows' if os.name == 'nt' else 'posix') and
            Path(profile['workspace']) == root, 'worker_workspace')
    identity_descriptor = manifest['evidence']['participants'][participant]['identity']
    require(reader.json(identity_descriptor) == measured_identity, 'measured_worker_identity')
    selected = [(key, row['policy']) for key, row in tuples.items() if key[1] == participant]
    require(0 < len(selected) <= 256 and set(commands) == {(key[0], key[2]) for key, _ in selected}, 'adapter_command_set')
    copy_paths = {}
    for (name, _, kind), policy in selected:
        require(commands[name, kind] == policy['argv'], 'adapter_command_mismatch')
        require(executable_hash(commands[name, kind][0]) == binaries[policy['argv'][0]], 'executable_identity')
        path = reader.path(policy['input_path'])
        require(not path.exists(), 'preserve_existing_fixture_copy')
        copy_paths[name] = policy['input_path']
    directory = reader.path('collections/' + digest(participant.encode())[7:23])
    require(not directory.exists(), 'preserve_existing_collection')
    reader.recheck()
    directory.mkdir(parents=True, exist_ok=False)
    output = Output(root)
    receipt = dict(participant=participant, identity_sha256=identity_descriptor['sha256'], observations=[],
                   manifest_sha256=expected_snapshot, status='collecting', active=None,
                   scope='Collected declarations and raw artifacts;worker/campaign qualification is separate')
    prefix = directory.relative_to(root).as_posix()
    try:
        output.checkpoint(directory, receipt)
        for name, path in copy_paths.items():
            output.artifact(path, reader.read(manifest['evidence']['fixtures'][name]))
        for index, ((name, _, kind), policy) in enumerate(selected):
            case = cases[name]
            item = prefix + '/' + str(index)
            source = reader.path(policy['input_path'])
            data = Artifacts(root).read(dict(path=policy['input_path'], bytes=case['bytes'], sha256=case['sha256']))
            before_info = source.lstat()
            row = dict(name=name, participant=participant, kind=kind, identity_sha256=identity_descriptor['sha256'],
                       **{k: case[k] for k in ('sha256', 'bytes', 'unit', 'blocks')})
            row['input_before'] = output.artifact(item + '.before', data)
            row['executable_before_sha256'] = executable_hash(policy['argv'][0])
            require(row['executable_before_sha256'] == binaries[policy['argv'][0]], 'executable_identity')
            payload = None
            if participant == 'native':
                payload = (json.dumps(native_request(data, case), separators=(',', ':')) + '\n').encode()
            row['raw'] = {}
            if payload is not None:
                row['raw']['request'] = output.artifact(item + '.request', payload)
                row['input_sha256'] = digest(payload)
            receipt['active'] = dict(name=name, kind=kind, input_before=row['input_before'],
                                     raw=copy.deepcopy(row['raw']), argv=list(commands[name, kind]),
                                     executable_before_sha256=row['executable_before_sha256'])
            output.checkpoint(directory, receipt)
            result = execute(argv=list(commands[name, kind]), cwd=root, payload=payload,
                             timeout=policy['timeout_seconds'], output_limit=1024 * 1024)
            status = process_result(result, policy)
            receipt['active']['terminal'] = True
            row.update(outcome=result['outcome'], exit_code=result['exit_code'], argv=list(policy['argv']),
                       execution=dict(status=status, argv=list(policy['argv']), exit_code=result['exit_code'],
                                      elapsed_seconds=result['elapsed_seconds']))
            for stream in ('stdout', 'stderr'):
                body = result[stream]
                row['raw'][stream] = output.artifact(item + '.' + stream, body)
                row[stream] = body.decode('utf-8', 'backslashreplace')
                row[stream + '_sha256'] = digest(body)
                try:
                    body.decode('utf-8')
                except UnicodeDecodeError:
                    row[stream + '_bytes_hex'] = body.hex()
            # Read actual current bytes, even on a failed operation. Do not use
            # the before snapshot as a substitute for the after observation.
            after_reader = Artifacts(root)
            row['input_after'], after = after_reader.capture(policy['input_path'])
            row['input_unchanged'] = after == data and after_reader.states[source][:2] == (before_info.st_dev, before_info.st_ino)
            row['executable_after_sha256'] = executable_hash(policy['argv'][0])
            row['projection'] = None
            if participant == 'native' and status == 'completed':
                try:
                    value = strict_json(result['stdout'])
                    row['checks'] = [dict(path=path, expected=expected, actual=field(value, path),
                        matched=type(field(value, path)) is type(expected) and field(value, path) == expected)
                        for path, expected in case['checks'].items()]
                    row['projection'] = native_projection(value, case['family'])
                except (ValueError, KeyError, TypeError, IndexError, OverflowError, RecursionError):
                    row['parse_error'] = 'invalid_native_result'
            elif participant != 'native' and policy['comparison'] == 'projection':
                try:
                    row['projection'] = external_projection(row, kind, str(source))
                except (ValueError, KeyError, TypeError, IndexError, OverflowError, RecursionError):
                    row['parse_error'] = 'invalid_reference_result'
            receipt['observations'].append(row)
            receipt['active'] = None
            output.checkpoint(directory, receipt)
            require(row['input_unchanged'] and row['executable_after_sha256'] == row['executable_before_sha256'], 'observed_input_or_executable_change')
        reader.recheck()
        receipt['status'] = 'collected'
        output.checkpoint(directory, receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                       error=type(error).__name__, error_code=str(error) if isinstance(error, EvidenceError) else type(error).__name__,
                       quiescence_unknown=receipt['active'] is not None and
                       not receipt['active'].get('terminal', False))
        # A bounded checkpoint may itself fail (disk full/output cap). Preserve
        # its prior in-progress receipt and partial raw files in that case.
        try:
            output.checkpoint(directory, receipt)
        except (OSError, ValueError):
            pass
        raise
