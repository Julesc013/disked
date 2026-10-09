"""Native read-only Setup source-candidate qualification on owned fixtures.

Requires a compiled probe and an independently retained original inventory.
This runner never installs, extracts, dispatches apply, or invokes upstream scripts.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import time
import zipfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / 'external/universal-setup/contracts/schema/setup'
PROFILE = json.loads((ROOT / 'spec/catalog/setup-source-consumer-prototype.json').read_bytes())
BUDGETS = dict(max_entries=64, max_uncompressed_bytes=16777216,
               max_entry_bytes=16777216, max_depth=8, max_ratio=100, max_elapsed_ms=10000)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
            for p in sorted(root.rglob('*')) if p.is_file()}


def validate(name, value):
    schema = json.loads((SCHEMAS / (name + '.v1.schema.json')).read_bytes())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


class Campaign:
    def __init__(self, probe, output):
        self.probe, self.output = probe, output
        self.records = []
        self.assertions = 0

    def require(self, value, reason):
        self.assertions += 1
        if not value:
            raise AssertionError(reason)

    def call(self, label, command, payload, exit_code=0):
        request = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
        directory = self.output / 'observations' / label
        directory.mkdir(parents=True)
        (directory / 'request.bin').write_bytes(request)
        args = [str(self.probe), command]
        started = time.monotonic()
        result = subprocess.run(args, input=request, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=20)
        (directory / 'stdout.json').write_bytes(result.stdout)
        (directory / 'stderr.log').write_bytes(result.stderr)
        record = dict(label=label, command=args, exit_code=result.returncode,
                      expected_exit_code=exit_code, elapsed_seconds=round(time.monotonic()-started, 4))
        self.records.append(record)
        (directory / 'execution.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
        self.require(result.returncode == exit_code, label + ': native process exit')
        self.require(not result.stderr, label + ': unexpected stderr')
        response = json.loads(result.stdout)
        if exit_code == 0 and command != 'selftest':
            self.require(response['abi'] == 65536 and response['lifecycle_configured'] is False,
                         label + ': ABI or lifecycle authority')
            self.require(response['context_allocations'] == response['context_frees'], label + ': allocator imbalance')
            self.require(response['provider_return'] == response['provider_response_status'], label + ': supplier status mismatch')
        return response

    def success(self, label, command, request):
        response = self.call(label, command, request)
        self.require(response['provider_return'] == 0 and response['response']['status'] == 'ok', label + ': supplier success')
        return response['response']['payload']

    def refused(self, label, command, request, error):
        response = self.call(label, command, request)
        self.require(response['provider_return'] == 1 and response['response']['status'] == 'refused', label + ': supplier refusal')
        self.require(response['response']['error']['code'] == error, label + ': refusal identity')
        return response['response']


def request(path, **limits):
    return dict(schema='usk.archive_inspect_request.v1', archive_path=str(path.absolute()),
                archive_format='zip', budgets=dict(BUDGETS, **limits))


def zip_fixture(path, entries, method=zipfile.ZIP_STORED):
    with zipfile.ZipFile(path, 'x', compression=method) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return path


def run(args):
    if args.output.exists():
        raise ValueError('new campaign root required')
    original_inventory = json.loads(args.inventory.read_bytes())
    if not args.probe.is_file() or not args.package.is_dir():
        raise ValueError('existing compiled probe and package fixtures required')
    args.output.mkdir()
    fixtures = args.output / 'fixtures'
    fixtures.mkdir()
    package = fixtures / 'package'
    shutil.copytree(args.package, package)
    # These inputs remain separate from the copied package metadata.
    (args.output / 'original-inventory.json').write_bytes(args.inventory.read_bytes())
    spec = importlib.util.spec_from_file_location('independent_artifact_check', ROOT/'tools/release/artifact_check.py')
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    independent.validate_inventory(original_inventory)
    independent.verify_zip(original_inventory, package/'payload.zip')
    good = zip_fixture(fixtures/'stored.zip', [('fixture.txt', b'bounded disposable bytes')])
    deflated = zip_fixture(fixtures/'deflated.zip', [('folder/fixture.txt', bytes(range(256))*4)], zipfile.ZIP_DEFLATED)
    two = zip_fixture(fixtures/'two.zip', [('one.txt', b'one'), ('two.txt', b'two')])
    deep = zip_fixture(fixtures/'deep.zip', [('a/b/c.txt', b'depth')])
    traversal = zip_fixture(fixtures/'traversal.zip', [('../outside.txt', b'disposable')])
    collision = zip_fixture(fixtures/'collision.zip', [('ONE.txt', b'one'), ('one.txt', b'two')])
    empty = zip_fixture(fixtures/'empty.zip', [])
    truncated = fixtures/'truncated.zip'
    truncated.write_bytes(good.read_bytes()[:-12])
    corrupt = fixtures/'corrupt-payload.zip'
    data = bytearray((package/'payload.zip').read_bytes())
    name_bytes, extra_bytes = struct.unpack_from('<HH', data, 26)
    data[30+name_bytes+extra_bytes] ^= 1
    corrupt.write_bytes(data)
    for name in ('source', 'case', 'evidence', 'recovery', 'foreign'):
        directory = fixtures/name
        directory.mkdir()
        (directory/'sentinel.bin').write_bytes(('owned fixture '+name).encode())
    before = snapshot(fixtures)
    (args.output/'fixtures-before.json').write_text(json.dumps(before, indent=2)+'\n', encoding='utf-8', newline='\n')
    campaign = Campaign(args.probe, args.output)
    result = {'status': 'failed', 'qualification': 'read-only-source-candidate-only',
              'probe_sha256': sha(args.probe), 'probe_bytes': args.probe.stat().st_size,
              'profile_sha256': sha(ROOT/'spec/catalog/setup-source-consumer-prototype.json'),
              'lifecycle_configured': False, 'installed_sdk_qualified': False,
              'unit_complete': False, 'owner_accepted': False}
    try:
        native = campaign.call('abi-ownership', 'selftest', b'')
        campaign.require(native['checks'] == 6 and native['abi'] == 65536, 'six native ABI/ownership checks')
        campaign.require(native['context_allocations'] == native['context_frees'] == 2, 'graph allocator balance')
        campaign.require(native['borrowed_pointer_used_after_invalidation'] is False, 'borrowed pointer reuse')
        policy = campaign.success('policy', 'policy.inspect', {})
        for field in ('network_allowed', 'registry_allowed', 'elevation_allowed', 'installer_execution_allowed', 'credential_access_allowed'):
            campaign.require(policy[field] is False, 'policy restriction: '+field)
        graph = campaign.success('graph', 'command_graph.inspect_v2', {})
        commands = {row['command']: row for row in graph['commands']}
        for command in PROFILE['upstream_commands']:
            campaign.require(commands[command]['mutating'] is False, 'read-only descriptor: '+command)
        campaign.require(commands['audit.list']['availability'] == 'planned' and commands['audit.list']['executable'] is False, 'planned discovery')
        campaign.require(commands['install_local.apply']['mutating'] is True, 'descriptor does not grant apply authority')
        for command in ('install_local.apply', 'repair.apply', 'live_evidence.capture', 'unknown.command'):
            response = campaign.call('consumer-refusal-'+command, command, {}, 2)
            campaign.require(response['context_created'] is False and response['reason'] == 'command_not_in_read_only_probe', 'pre-context dispatch refusal')
        for label, payload in [('empty', b''), ('over-budget', b' ' * 8193), ('nul', b'{}\0')]:
            response = campaign.call('consumer-request-'+label, 'policy.inspect', payload, 2)
            campaign.require(response['context_created'] is False and response['reason'] == 'bounded_request_required', 'bounded request refusal')
        payload = request(package/'payload.zip')
        validate('archive_inspect_request', payload)
        inspection = campaign.success('disked-zip', 'install_local.inspect', payload)
        validate('archive_inspection', inspection)
        campaign.require(inspection['source']['sha256'] == sha(package/'payload.zip'), 'archive SHA against exact bytes')
        campaign.require(inspection['source']['size_bytes'] == (package/'payload.zip').stat().st_size, 'archive byte size')
        expected = original_inventory['files']
        campaign.require({(row['normalized_path'], row['uncompressed_size']) for row in inspection['entries']} ==
                         {(row['path'], int(row['bytes'])) for row in expected}, 'entry set against original independent inventory')
        campaign.require(inspection['totals']['uncompressed_bytes'] == sum(int(row['bytes']) for row in expected), 'entry total')
        repeated = campaign.success('disked-zip-repeat', 'install_local.inspect', payload)
        campaign.require(repeated['entry_set_digest'] == inspection['entry_set_digest'], 'stable entry-set identity')
        for label, path in [('stored', good), ('deflated', deflated)]:
            observation = campaign.success(label, 'install_local.inspect', request(path))
            validate('archive_inspection', observation)
            campaign.require(observation['source']['sha256'] == sha(path), label + ': source hash')
            campaign.require(observation['entries'][0]['compression_method'] == ('deflate' if label == 'deflated' else 'stored'), label + ': compression metadata')
        cases = [('traversal', traversal, {}), ('case-collision', collision, {}), ('empty-archive', empty, {}),
                 ('truncated', truncated, {}), ('entry-count', two, {'max_entries': 1}),
                 ('entry-size', good, {'max_entry_bytes': 2}), ('total-size', two, {'max_uncompressed_bytes': 2}),
                 ('depth', deep, {'max_depth': 2}), ('ratio', deflated, {'max_ratio': 1}),
                 ('missing-file', fixtures/'missing.zip', {})]
        for label, path, limits in cases:
            campaign.refused(label, 'install_local.inspect', request(path, **limits), 'archive_inspection_refused')
        for label, change in [('format', {'archive_format':'tar'}), ('unknown-field', {'unknown':1}),
                              ('relative-path', {'archive_path':'relative.zip'}), ('zero-budget', {'budgets':dict(BUDGETS, max_entries=0)})]:
            campaign.refused('request-'+label, 'install_local.inspect', dict(request(good), **change), 'archive_inspection_refused')
        campaign.refused('malformed-json', 'install_local.inspect', b'{', 'archive_inspection_refused')
        # Public inspection is structural; it deliberately does not establish decoded payload integrity.
        corrupt_observation = campaign.success('corrupt-payload-structural', 'install_local.inspect', request(corrupt))
        validate('archive_inspection', corrupt_observation)
        campaign.require(corrupt_observation['source']['sha256'] == sha(corrupt) and sha(corrupt) != sha(package/'payload.zip'), 'corrupt source hash remains exact')
        try:
            independent.verify_zip(original_inventory, corrupt)
        except independent.Rejected as error:
            result['independent_corruption_refusal'] = str(error)
        else:
            raise AssertionError('independent content checker accepted corrupted original payload')
        campaign.require(bool(result['independent_corruption_refusal']), 'independent verification required')
        for command in ('package.verify', 'package.audit'):
            payload = dict(schema='usk.package_verify_request.v1', package_root=str(package))
            validate('package_verify_request', payload)
            response = campaign.refused('generic-'+command, command, payload, 'package_verification_refused')
            validate('package_verify_report', response['payload'])
            campaign.require(response['error']['message'] == 'required package metadata is missing', 'FacMan format gap retained')
            campaign.require(response['payload']['completeness'] == 'not_checked', 'no generic package qualification')
        campaign.refused('unconfigured-plan', 'install_local.plan', {}, 'live_target_acceptance_required')
        after = snapshot(fixtures)
        campaign.require(after == before, 'source/case/evidence/recovery/foreign/package fixtures changed')
        result.update(status='pass', fixture_snapshot_unchanged=True,
                      generic_package_verified=False, payload_integrity_established_by_inspector=False)
    except Exception as error:
        result['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        result.update(assertions=campaign.assertions, native_executions=len(campaign.records), executions=campaign.records)
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'executions'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for field in ('probe', 'package', 'inventory', 'output'):
        setattr(args, field, getattr(args, field).absolute())
    run(args)


if __name__ == '__main__':
    main()
