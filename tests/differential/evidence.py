"""Verify finalized differential evidence bytes and declared identities.

This checks a packet against a caller-bound manifest. It does not authenticate
execution, admit a worker, or qualify a product/provider.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat

from projections import native_request as request, field, native_projection, external_projection, strict_json


SHA = re.compile(r'sha256:[0-9a-f]{64}')


def canonical_digest(value):
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    return 'sha256:' + hashlib.sha256(body).hexdigest()


def digest(body):
    return 'sha256:' + hashlib.sha256(body).hexdigest()


class EvidenceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise EvidenceError(reason)


class Artifacts:
    """Bounded finalized packet reads, never arbitrary paths from metadata."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), 'artifact_root')
        self.files = {}
        self.states = {}
        self.payloads = {}
        self.total = 0
        self.bytes_read = 0

    def path(self, value):
        require(isinstance(value, str) and 0 < len(value) <= 512, 'artifact_path')
        name = PurePosixPath(value)
        require(not name.is_absolute() and name.as_posix() == value and
                not any(p in ('.', '..') for p in name.parts) and
                not any(c in value for c in '\\:*?[]\0'), 'artifact_path')
        return managed_path(self.root / value, self.root)

    def _read(self, path, size):
        managed_path(path, self.root)
        before = path.lstat()
        state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        require(path not in self.states or self.states[path] == state, 'artifact_replaced_or_changed')
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
                'artifact_form_or_size')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'artifact_replaced')
            body = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        final = path.lstat()
        require(len(body) == size and stat.S_ISREG(after.st_mode) and after.st_nlink == 1 and
                (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
                (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'artifact_changed')
        managed_path(path, self.root)
        self.states[path] = state
        return body

    def read(self, descriptor):
        require(isinstance(descriptor, dict) and set(descriptor) == {'path', 'bytes', 'sha256'}, 'artifact_descriptor')
        size, expected = descriptor['bytes'], descriptor['sha256']
        require(type(size) is int and 0 <= size <= 2 * 1024 * 1024 and
                isinstance(expected, str) and SHA.fullmatch(expected), 'artifact_descriptor_bounds')
        path = self.path(descriptor['path'])
        if path in self.files:
            previous, body = self.files[path]
            require(previous == descriptor, 'contradictory_artifact_descriptor')
            return body
        content = (size, expected)
        require(len(self.files) < 2048 and self.bytes_read + size <= 128 * 1024 * 1024 and
                (content in self.payloads or self.total + size <= 32 * 1024 * 1024), 'artifact_aggregate_bound')
        body = self._read(path, size)
        require(digest(body) == expected, 'artifact_hash')
        self.bytes_read += size
        if content in self.payloads:
            body = self.payloads[content]
        else:
            self.payloads[content] = body
            self.total += size
        self.files[path] = (dict(descriptor), body)
        return body

    def json(self, descriptor):
        body = self.read(descriptor)
        return strict_json(body)

    def capture(self, name):
        """Observe current ordinary-file bytes without inventing an expected hash."""
        path = self.path(name)
        size = path.lstat().st_size
        require(0 <= size <= 2 * 1024 * 1024, 'artifact_capture_bound')
        body = self._read(path, size)
        return dict(path=name, bytes=size, sha256=digest(body)), body

    def recheck(self):
        for path, (descriptor, _) in self.files.items():
            require(digest(self._read(path, descriptor['bytes'])) == descriptor['sha256'], 'artifact_changed')


def _hashes(value):
    return isinstance(value, dict) and 0 < len(value) <= 256 and all(
        isinstance(k, str) and 0 < len(k) <= 1024 and isinstance(v, str) and SHA.fullmatch(v)
        for k, v in value.items())


def _identity(reader, participant, declared):
    require(isinstance(declared, dict) and set(declared) == {'role', 'profile', 'identity'}, 'participant_descriptor')
    role = 'native' if participant == 'native' else 'reference'
    profile = declared['profile']
    keys = {'os', 'build', 'architecture', 'runtime', 'token', 'workspace', 'path_style'}
    require(declared['role'] == role and isinstance(profile, dict) and set(profile) == keys and
            all(isinstance(v, str) and 0 < len(v) <= 256 for v in profile.values()) and
            profile['path_style'] in ('windows', 'posix'), 'participant_profile')
    path_type = PureWindowsPath if profile['path_style'] == 'windows' else PurePosixPath
    require(path_type(profile['workspace']).is_absolute(), 'participant_workspace')
    value = reader.json(declared['identity'])
    require(isinstance(value, dict) and set(value) == {'schema', 'participant', 'role', 'profile', 'source', 'build'} and
            value['schema'] == 'org.disked.differential-identity/1' and value['participant'] == participant and
            value['role'] == role and value['profile'] == profile, 'participant_identity')
    source, build = value['source'], value['build']
    require(isinstance(source, dict) and set(source) == {'revision', 'inputs', 'upstream_source_verified'} and
            _hashes(source['inputs']) and type(source['upstream_source_verified']) is bool, 'source_identity')
    revision = source['revision']
    require((isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision)) or
            (role == 'reference' and revision is None and not source['upstream_source_verified']), 'source_revision')
    require(isinstance(build, dict) and set(build) == {'configuration', 'toolchain', 'executables'} and
            isinstance(build['configuration'], str) and 0 < len(build['configuration']) <= 1024 and
            _hashes(build['toolchain']) and _hashes(build['executables']), 'build_identity')
    return profile, build['executables']


def _policy(value, participant, profile, reader):
    keys = {'comparison', 'argv', 'input_path', 'allowed_outcomes', 'timeout_seconds'}
    require(isinstance(value, dict) and set(value) == keys, 'observation_policy')
    mode, argv, allowed, timeout = (value[k] for k in ('comparison', 'argv', 'allowed_outcomes', 'timeout_seconds'))
    require(mode == 'native' if participant == 'native' else mode in ('projection', 'diagnostic'), 'comparison_policy')
    require(isinstance(argv, list) and 1 <= len(argv) <= 32 and
            all(isinstance(v, str) and 0 < len(v) <= 1024 and '\0' not in v for v in argv), 'argv_policy')
    require(isinstance(allowed, list) and 0 < len(allowed) <= 2 and len(set(allowed)) == len(allowed) and
            set(allowed) <= {'completed', 'refused'} and
            (participant != 'native' or allowed == ['completed']), 'execution_policy')
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 300, 'timeout_policy')
    relative = value['input_path']; reader.path(relative)
    path_type = PureWindowsPath if profile['path_style'] == 'windows' else PurePosixPath
    argument = str(path_type(profile['workspace']).joinpath(*PurePosixPath(relative).parts))
    require(participant == 'native' or argument in argv, 'fixture_argument_policy')
    return argument


def declared_inputs(manifest, root, expected_snapshot):
    """Shared declaration checks for collection and finalized packet reading."""
    require(isinstance(expected_snapshot, str) and SHA.fullmatch(expected_snapshot) and
            canonical_digest(manifest) == expected_snapshot, 'manifest_snapshot')
    binding = manifest['evidence']
    require(isinstance(binding, dict) and set(binding) == {'schema', 'contract', 'generator', 'fixtures', 'participants'} and
            binding['schema'] == 'org.disked.differential-evidence/1', 'binding_schema')
    participants = binding['participants']
    require(isinstance(participants, dict) and 2 <= len(participants) <= 9 and 'native' in participants, 'participant_set')
    empty = {name: dict(observations=[]) for name in participants if name != 'native'}
    inventory = evidence_set(manifest, dict(observations=[]), empty)
    require(inventory['status'] == 'incomplete' and not inventory['errors'], 'declaration_set')
    reader = Artifacts(root)
    require(reader.read(binding['contract']) == Path(__file__).with_name('CONTRACT.md').read_bytes(), 'comparison_contract')
    reader.read(binding['generator'])
    require(binding['generator']['sha256'] == manifest['generator_sha256'], 'generator_identity')
    cases = {v['name']: v for v in manifest['cases']}
    require(isinstance(binding['fixtures'], dict) and set(binding['fixtures']) == set(cases), 'fixture_set')
    for name, case in cases.items():
        descriptor = binding['fixtures'][name]
        reader.read(descriptor)
        require(descriptor['sha256'] == case['sha256'] and descriptor['bytes'] == case['bytes'], 'fixture_identity')
        require(case.get('family') in ('mbr', 'gpt') and 2 <= case['blocks'] <= 4096 and
                type(case.get('common_projection')) is bool and isinstance(case.get('checks'), dict) and
                0 < len(case['checks']) <= 256, 'fixture_contract')
    identities = {name: _identity(reader, name, value) for name, value in participants.items()}
    tuples = {(v['name'], v['participant'], v['kind']): v for v in manifest['expected_observations']}
    paths = {}
    for (name, participant, kind), row in tuples.items():
        require(participant != 'native' or kind == 'native', 'native_observation_kind')
        policy = row.get('policy')
        _policy(policy, participant, identities[participant][0], reader)
        require(policy['argv'][0] in identities[participant][1], 'executable_not_identified')
        pair = name, participant
        require(pair not in paths or paths[pair] == policy['input_path'], 'participant_copy_identity')
        paths[pair] = policy['input_path']
    require(len(set(paths.values())) == len(paths), 'participant_copy_identity')
    return reader, cases, tuples, identities


def validate_bindings(manifest, native, external, root, expected_snapshot):
    """Verify consistency, not authenticated execution or capability admission."""
    result = dict(status='unverified', errors=[], execution=[], execution_passed=False,
                  artifacts_verified=0, bytes_verified=0,
                  scope='Finalized packet consistency against caller-bound manifest;not execution authentication or product qualification')
    if 'evidence' not in manifest or root is None or expected_snapshot is None:
        result['errors'] = ['binding_inputs_not_supplied']
        return result
    try:
        inventory = evidence_set(manifest, native, external)
        if inventory['status'] != 'complete':
            result.update(status='invalid' if inventory['status']=='invalid' else 'incomplete',
                          errors=['observation_set_not_complete'])
            return result
        reader, cases, tuples, identities = declared_inputs(manifest, root, expected_snapshot)
        binding = manifest['evidence']
        receipts = dict(external, native=native)
        participants = binding['participants']
        require(set(participants) == set(receipts), 'participant_set')
        for participant, receipt in receipts.items():
            profile, executables = identities[participant]
            identity_hash = participants[participant]['identity']['sha256']
            require(receipt.get('participant') == participant and receipt.get('identity_sha256') == identity_hash, 'receipt_identity')
            require(receipt.get('status', 'collected') == 'collected' and receipt.get('active') is None, 'receipt_not_finalized')
            for row in receipt['observations']:
                key = row['name'], participant, row['kind']; case = cases[row['name']]
                policy = tuples[key].get('policy')
                fixture_argument = _policy(policy, participant, profile, reader)
                require(policy['argv'][0] in executables, 'executable_not_identified')
                require(row.get('executable_before_sha256') == executables[policy['argv'][0]] and
                        row.get('executable_after_sha256') == executables[policy['argv'][0]], 'executable_identity_changed')
                require(row.get('participant') == participant and row.get('identity_sha256') == identity_hash, 'observation_identity_binding')
                execution = row['execution']
                require(isinstance(execution, dict) and set(execution) == {'status', 'argv', 'exit_code', 'elapsed_seconds'}, 'execution_shape')
                status, code, elapsed = (execution[k] for k in ('status', 'exit_code', 'elapsed_seconds'))
                expected_outcomes = {'completed': 'exited', 'refused': 'exited', 'timed_out': 'timeout',
                                     'crashed': 'exited', 'unavailable': 'unavailable', 'output_limited': 'output_limit'}
                require(status in expected_outcomes and row['outcome'] == expected_outcomes[status] and
                        row['exit_code'] == code and type(row['exit_code']) is type(code) and
                        execution['argv'] == policy['argv'] and row['argv'] == policy['argv'], 'execution_binding')
                require((status == 'completed' and type(code) is int and code == 0) or
                        (status == 'refused' and type(code) is int and 0 < code < 2**31) or
                        (status == 'crashed' and type(code) is int and code != 0) or
                        (status in ('timed_out', 'output_limited') and (code is None or type(code) is int)) or
                        (status == 'unavailable' and code is None), 'execution_exit_relationship')
                require(type(elapsed) in (int, float) and math.isfinite(elapsed) and
                        0 <= elapsed <= policy['timeout_seconds'] + 2, 'execution_elapsed')
                result['execution'].append(dict(name=row['name'], participant=participant, kind=row['kind'],
                                                status=status, allowed=status in policy['allowed_outcomes']))
                for phase in ('input_before', 'input_after'):
                    data = reader.read(row[phase])
                    require(digest(data) == case['sha256'] and len(data) == case['bytes'], 'input_preservation')
                require(row['input_after']['path'] == policy['input_path'] and
                        reader.path(row['input_before']['path']) != reader.path(policy['input_path']) and
                        row.get('input_unchanged') is True, 'input_effect_receipt')
                raw = row['raw']
                require(isinstance(raw, dict) and set(raw) == ({'stdout', 'stderr', 'request'} if participant == 'native' else {'stdout', 'stderr'}), 'raw_artifact_set')
                display = {}
                for stream in ('stdout', 'stderr'):
                    data = reader.read(raw[stream]); display[stream] = data.decode('utf-8', 'backslashreplace')
                    require(row.get(stream) == display[stream] and row.get(stream + '_sha256') == digest(data), 'raw_display_binding')
                    try:data.decode('utf-8')
                    except UnicodeDecodeError:require(row.get(stream + '_bytes_hex') == data.hex(), 'raw_encoding_binding')
                    else:require(stream + '_bytes_hex' not in row, 'spurious_raw_hex')
                if participant == 'native':
                    data = reader.read(raw['request'])
                    require(data == (json.dumps(request(reader.read(row['input_before']), case), separators=(',', ':')) + '\n').encode() and
                            row.get('input_sha256') == digest(data), 'native_request_binding')
                    projected = None
                    if status == 'completed':
                        value = strict_json(reader.read(raw['stdout']))
                        for path, expected in case['checks'].items():
                            actual = field(value, path)
                            require(type(actual) is type(expected) and actual == expected, 'native_fixture_check')
                        projected = native_projection(value, case['family'])
                elif policy['comparison'] == 'diagnostic':
                    projected = None
                else:
                    require(row['kind'] in ('sfdisk-json', 'sgdisk-print'), 'unsupported_projection')
                    display.update(exit_code=code, outcome=row['outcome'])
                    if 'stdout_bytes_hex' in row:display['stdout_bytes_hex'] = row['stdout_bytes_hex']
                    projected = external_projection(display, row['kind'], fixture_argument)
                require(row.get('projection') == projected, 'raw_projection_binding')
        paths = [v['policy']['input_path'] for v in tuples.values()]
        require(len(set(paths)) == len({(v['name'], v['participant']) for v in tuples.values()}) and
                all(len({v['policy']['input_path'] for v in tuples.values() if (v['name'], v['participant']) == pair}) == 1
                    for pair in {(v['name'], v['participant']) for v in tuples.values()}), 'participant_copy_identity')
        copy_ids = {reader.states[reader.path(path)][:2] for path in paths}
        fixture_ids = {reader.states[reader.path(v['path'])][:2] for v in binding['fixtures'].values()}
        require(len(copy_ids) == len({(v['name'],v['participant']) for v in tuples.values()}) and
                not copy_ids & fixture_ids, 'participant_copy_file_identity')
        reader.recheck()
        result.update(status='complete', artifacts_verified=len(reader.files), bytes_verified=reader.bytes_read,
                      unique_payload_bytes=reader.total, recheck_bytes_verified=reader.bytes_read,
                      execution_passed=all(v['allowed'] for v in result['execution']))
    except (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError, RecursionError):
        # Stable diagnostics do not echo untrusted presentation data to a terminal.
        import sys
        error = sys.exception()
        result.update(status='invalid', errors=[str(error) if isinstance(error, EvidenceError) else type(error).__name__])
    return result


def managed_path(value,root):
    """Routing check only; the owning runner supplies resource enforcement."""
    path=Path(value)
    if '..' in path.parts:raise ValueError('Parent traversal is outside the campaign route')
    path=path.absolute()
    if not path.is_relative_to(root) or path==root:raise ValueError('Path outside managed campaign workspace')
    for current in (path,*path.parents):
        if current==root:break
        try:info=current.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Linked campaign paths are refused')
    if not path.resolve().is_relative_to(root):raise ValueError('Resolved campaign path escaped')
    return path


def read_receipt(path,remaining=8*1024*1024):
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=min(remaining,8*1024*1024):
        raise ValueError('Receipt must be a bounded ordinary single-link file')
    with path.open('rb') as stream:body=stream.read(min(remaining,8*1024*1024)+1)
    if len(body)!=info.st_size:raise ValueError('Receipt changed or exceeded its bound')
    return strict_json(body.decode('utf-8')),len(body)


def write_report(path,value,limit=64*1024*1024):
    if type(limit) is not int or not 1<=limit<=64*1024*1024:raise ValueError('Invalid report byte bound')
    # Stream expansion; failed writes leave only bounded partial scratch output.
    written=0
    with path.open('xb') as stream:
        for text in json.JSONEncoder(indent=2,allow_nan=False).iterencode(value):
            body=text.encode('utf-8');written+=len(body)
            if written>limit-1:raise ValueError('Comparison report exceeded its bound')
            stream.write(body)
        stream.write(b'\n')
    return written+1



def evidence_set(manifest, native, external):
    """Check a predeclared set, never infer expected participants from results.

    This initial DE-W106 slice does not verify executable/raw artifact bytes.
    A complete set therefore remains unqualified evidence.
    """
    errors=[];missing=[];seen=set();expected=set();cases={}
    if not all(isinstance(v,dict) for v in (manifest,native,external)):
        return dict(status='invalid',errors=['receipt_object_required'],missing=[])
    declarations=manifest.get('expected_observations')
    if declarations is None:return dict(status='undeclared',errors=['expected_set_not_declared'],missing=[])
    if not isinstance(declarations,list) or not 0<len(declarations)<=32768:
        return dict(status='invalid',errors=['expected_set_empty_or_unbounded'],missing=[])
    values=manifest.get('cases')
    if not isinstance(values,list) or not 0<len(values)<=4096:
        return dict(status='invalid',errors=['case_set_empty_or_unbounded'],missing=[])
    for case in values:
        if not isinstance(case,dict) or not isinstance(case.get('name'),str) or not case['name']:
            errors.append('case_identity');continue
        name=case['name']
        if name in cases:errors.append('duplicate_case:'+name)
        cases[name]=case
        if (not isinstance(case.get('sha256'),str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',case['sha256']) or
                type(case.get('bytes')) is not int or not 0<=case['bytes']<=2097152 or
                type(case.get('unit')) is not int or case['unit']!=512 or
                type(case.get('blocks')) is not int or not 2<=case['blocks']<=2**64-1 or
                case['bytes']>case['unit']*case['blocks']):errors.append('case_fixture:'+name)
    def key(row):
        if (not isinstance(row,dict) or set(row) not in ({'name','participant','kind'},{'name','participant','kind','policy'}) or
                ('policy' in row and not isinstance(row['policy'],dict)) or
                not all(isinstance(row[k],str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',row[k]) for k in ('name','participant','kind'))):
            return None
        return row['name'],row['participant'],row['kind']
    for row in declarations:
        item=key(row)
        if item is None:errors.append('expected_tuple_shape');continue
        if item in expected:errors.append('duplicate_expected:'+repr(item))
        if item[0] not in cases:errors.append('unknown_expected_case:'+item[0])
        expected.add(item)
    for name in cases:
        if (name,'native','native') not in expected:errors.append('native_not_expected:'+name)
        if not any(k[0]==name and k[1]!='native' for k in expected):errors.append('reference_not_expected:'+name)
    if not isinstance(external,dict):return dict(status='invalid',errors=errors+['reference_receipt_shape'],missing=[])
    receipts=[('native',native),*external.items()]
    if 'native' in external:errors.append('reference_uses_native_identity')
    declared_participants={item[1] for item in expected}
    for participant,receipt in receipts:
        if participant not in declared_participants:errors.append('unexpected_participant:'+str(participant))
        rows=receipt.get('observations') if isinstance(receipt,dict) else None
        if not isinstance(rows,list) or len(rows)>32768:
            errors.append('observation_list:'+str(participant));continue
        for row in rows:
            item=key(dict(name=row.get('name'),participant=participant,kind=row.get('kind'))) if isinstance(row,dict) else None
            if item is None:errors.append('observation_identity');continue
            if item in seen:errors.append('duplicate_observation:'+repr(item))
            seen.add(item)
            if item not in expected:errors.append('unexpected_observation:'+repr(item))
            case=cases.get(item[0])
            if case is None:errors.append('unknown_case:'+item[0]);continue
            for field in ('sha256','bytes','unit','blocks'):
                if type(row.get(field)) is not type(case.get(field)) or row.get(field)!=case.get(field):
                    errors.append('fixture_'+field+':'+repr(item))
    missing=sorted(expected-seen)
    return dict(status='invalid' if errors else 'incomplete' if missing else 'complete',
                errors=errors,missing=[dict(name=n,participant=p,kind=k) for n,p,k in missing],
                expected_count=len(expected),observed_unique_count=len(seen))
