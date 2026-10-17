"""DE-W105 fixture facts and public projections, independent of the C++ view."""
import copy
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'images'))
from ntfs_name_order_native_expectations import layouts
from test_ntfs_name_order import JointVolume, canonical, sha
from test_ntfs_stream import ref
from test_ntfs_directory_commands import CAPS, DIRECTORY, display, prefix
from test_ntfs_upcase_commands import expected_observation as table_projection, chunks as table_chunks
from test_ntfs_capture import bytes_at

ARRAYS = ('order', 'adjacent', 'reference_groups', 'mapped_groups')
COUNTERS = ('keys_returned', 'adjacent_returned', 'reference_groups_returned', 'mapped_groups_returned')


def fixtures():
    for name, volume, request, diagnostic in layouts():
        yield name, volume, None, request['directory']['reference'], diagnostic
    for minor in (0, 1):
        for version, diagnostic in [('3.' + str(minor), ''),
                                    ('3.' + str(1 - minor), 'ntfs_volume_version')]:
            yield f'explicit-{minor}-{version}', JointVolume(minor=minor), version, None, diagnostic
    for minor in (0, 1):
        yield f'discover-root-{minor}', JointVolume(minor=minor), None, None, ''
    same = [(b'A\0', n % 4, ref(14, 9)) for n in range(320)]
    yield 'large-same-reference', JointVolume(kind='leaf', rows=same, size=32768), None, None, ''
    many = [(struct.pack('<2H', n, 0xffff), n % 4, ref(14 + n, 9))
            for n in range(160) for _ in range(2)]
    # Supplied ASCII folding descends at the lowercase range; keep that finding.
    yield 'many-groups', JointVolume(kind='leaf', rows=many, size=32768), None, None, 'ntfs_name_order_mapped_descent'


def parameters(v, path, version=None, reference=None):
    result = dict(path=str(path), view='ntfs-name-order', volume_offset=v.input['offset'],
                  volume_bytes=v.input['length'])
    if version is not None:
        result['ntfs_version'] = version
    if reference is not None:
        result['directory_reference'] = reference
    return result


def options(v, version=None, reference=None):
    result = ['--view', 'ntfs-name-order', '--volume-offset', v.input['offset'],
              '--volume-bytes', v.input['length']]
    if version is not None:
        result += ['--ntfs-version', version]
    if reference is not None:
        result += ['--directory-reference', reference]
    return result


def wire(params, identity='name-order:req'):
    return dict(schema='org.disked.request/1', request_id=identity, command='image.inspect',
                parameters=params, required_features=[])


def compact_record(record):
    if record is not None and 'attributes' in record:
        def attribute(row):
            if 'runs' in row:
                row['runs'] = prefix(row['runs'], 16, 2048)
            return row
        record['attributes'] = prefix(record['attributes'], 16, 8192, attribute)
    return record


def expected_observation(original):
    # Reuse the independently specified complete-table chunking/compact metadata.
    result = table_projection(original)
    result['schema'] = 'org.disked.ntfs-name-order-projection/1'
    result['directory_record'] = compact_record(result['directory_record'])
    result['directory_stream_queries'] = prefix(original['directory_stream_queries'], 8, 2048)
    directory = result['directory']
    if directory is not None:
        directory.update(original_schema=directory['schema'], schema='org.disked.ntfs-index-projection/1',
                         name_display_encoding='escaped-utf16le-code-units/1')
        def stream(row):
            row['runs'] = prefix(row['runs'], 16, 2048)
            row['parts'] = prefix(row['parts'], 8, 2048)
            return row
        directory['streams'] = prefix(directory['streams'], 4, 8192, stream)
        directory['blocks'] = prefix(directory['blocks'], 32, 8192)
        def entry(row):
            if 'name_hex' in row:
                row['name_display'] = display(bytes.fromhex(row['name_hex']))
            return row
        directory['entries'] = prefix(directory['entries'], 64, 16384, entry)
    audit = result['name_order']
    if audit is not None:
        audit.update(original_schema=audit['schema'],
                     schema='org.disked.ntfs-directory-name-order-projection/1',
                     header_number_domain='original-directory-entry-header-numbers/1')
        complete = True
        for key in ARRAYS:
            values = audit[key]
            def group(row):
                row['headers'] = prefix(row['headers'], 64, 2048)
                return row
            if key in ARRAYS[:2]:
                audit[key] = prefix(values, 128, 16384)
            else:
                audit[key] = prefix(values, 32, 8192, group)
                complete = complete and all(group(copy.deepcopy(row))['headers']['omitted'] == '0'
                                            for row in values)
            complete = complete and audit[key]['omitted'] == '0'
        audit['projection_complete'] = complete
        audit['directory_entries_complete'] = directory is not None and directory['entries']['omitted'] == '0'
    return result


def independent_facts(v):
    expected = v.expected()
    return dict(expected=expected, table_sha256=sha(v.table.table),
                table_chunk_sha256=[sha(v.table.table[at:at + 16384]) for at in range(0, 131072, 16384)],
                table_base_reference=str(v.table.reference), table_base_record_sha256=sha(v.table.base_raw),
                directory_reference=str(v.directory.reference),
                source_layout_sha256=sha(canonical(v.input)),
                regions=v.regions(), initial_reads=[dict(offset=str(at), bytes=str(n)) for at, n in v.initial_reads])


def layout_manifest():
    return [dict(case=name, version=version, requested_reference=reference,
                 diagnostic=diagnostic, exit_code=4 if diagnostic else 0, **independent_facts(v))
            for name, v, version, reference, diagnostic in fixtures()]


def stable(response):
    result = copy.deepcopy(response['result'])
    for key in ('context', 'worker', 'file_sha256', 'capture_sha256', 'capture'):
        result.pop(key, None)
    def clean(value):
        if isinstance(value, dict):
            wrapped = all(k in value for k in ('items', 'total', 'returned', 'omitted'))
            return {k: clean(v) for k, v in value.items() if k not in ('source_id', 'epoch')
                    and not (wrapped and k == 'sha256')}
        return [clean(v) for v in value] if isinstance(value, list) else value
    return clean(result)


class Recorder:
    """Retain every raw request/reply/identity before any test assertion."""
    def __init__(self, output, root, env):
        self.output, self.root, self.env = output, root, env
        self.calls = []

    def run(self, name, command, data=b'', expected=0, settings=None, timeout=25):
        ordinal = len(self.calls)
        request = self.output.with_name(self.output.stem + f'-request-{ordinal}.bin')
        reply = self.output.with_name(self.output.stem + f'-response-{ordinal}.bin')
        error = self.output.with_name(self.output.stem + f'-stderr-{ordinal}.bin')
        request.write_bytes(data)
        start = time.monotonic()
        process = subprocess.Popen(list(map(str, command)), cwd=self.root,
                                   env=dict(self.env, **(settings or {})), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timed_out = False
        try:
            stdout, stderr = process.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate()
        reply.write_bytes(stdout)
        error.write_bytes(stderr)
        record = dict(name=name, command=list(map(str, command)), exit_code=process.returncode,
                      expected_exit_code=expected, seconds=time.monotonic() - start,
                      raw_input=str(request), raw_output=str(reply), raw_stderr=str(error),
                      input_sha256=sha(data), output_sha256=sha(stdout), stderr_sha256=sha(stderr),
                      process_id=process.pid, timed_out=timed_out, timeout_seconds=timeout)
        times = [wintypes.FILETIME() for _ in range(4)]
        query = ctypes.windll.kernel32.GetProcessTimes
        query.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        query.restype = wintypes.BOOL
        if query(int(process._handle), *(ctypes.byref(t) for t in times)):
            record['process_created'] = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        else:
            record['identity_observation_error'] = ctypes.GetLastError()
        self.calls.append(record)
        self.output.with_name(self.output.stem + '-raw-receipts.json').write_text(
            json.dumps(self.calls, indent=2) + '\n', encoding='utf-8', newline='\n')
        assert not timed_out and process.returncode == expected and not stderr, record
        assert not any(n < 32 and n not in (9, 10, 13) for n in stdout)
        return json.loads(stdout)
