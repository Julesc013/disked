"""Build/verify a finite read-only H/D/ZIP fixture, never an installer.

No supplied code executes; only the independently verified fixed D entry is
copied to new owned staging. No carrier is extracted. Original D inventory and H
observation are separate caller-selected inputs, not publisher authentication.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_fixture', ROOT/'release/bindings/universal-setup/package_fixture.py')
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)
pf.META_MAX = 262144
ac = pf.ac
PROFILE = ROOT/'spec/catalog/carrier-fixture-prototype.json'
MARKER = '.disked-carrier-fixtures.json'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')


def profile():
    return pf.read_json(PROFILE)


def topology(value):
    """Closed three-role fixture: no general resolver or recursive bindings."""
    if not isinstance(value, dict) or set(value) != {'H', 'D', 'S'}:
        pf.refuse('carrier_roles')
    if value != {'H': [], 'D': [], 'S': ['H', 'D']}:
        pf.refuse('carrier_containment')


def host_receipt(value):
    expected = profile()['host_observation']
    keys = set(expected) | {'source_revision', 'source_state', 'setup_revision'}
    if not isinstance(value, dict) or set(value) != keys:
        pf.refuse('host_observation_shape')
    if ac.canonical({key: value[key] for key in expected}) != ac.canonical(expected):
        pf.refuse('host_observation_claim')
    if not isinstance(value['source_revision'], str) or not HEX40.fullmatch(value['source_revision']):
        pf.refuse('host_source_identity')
    if value['source_state'] != 'clean':
        pf.refuse('host_source_not_clean')
    lock = pf.read_json(ROOT/'external/universal-setup/native-source-lock.json')
    if value['setup_revision'] != lock['revision']:
        pf.refuse('host_setup_pin')


def host_input(receipt):
    if not isinstance(receipt, dict) or set(receipt) != {'schema', 'artifact', 'observation'} or receipt['schema'] != 'org.disked.carrier-host-input/1':
        pf.refuse('host_input_shape')
    host_receipt(receipt['observation'])
    row = receipt['artifact']
    if not isinstance(row, dict) or set(row) != {'bytes', 'sha256'}:
        pf.refuse('host_artifact_shape')
    if not isinstance(row['bytes'], str) or not re.fullmatch(r'[1-9][0-9]{0,9}', row['bytes']) or int(row['bytes']) > profile()['limits']['host_bytes']:
        pf.refuse('host_byte_budget')
    if not isinstance(row['sha256'], str) or not pf.SHA.fullmatch(row['sha256']):
        pf.refuse('host_digest')


def definitions(expected, info, receipt):
    rows = ac.validate_inventory(expected)
    selected = profile()
    pf.identity_check(info, pf.read_json(pf.PROFILE))
    host_input(receipt)
    if set(rows) != {'disked.exe'}:
        pf.refuse('carrier_single_payload')
    data = rows['disked.exe']
    if int(data['bytes']) > selected['limits']['payload_bytes']:
        pf.refuse('carrier_payload_budget')
    layout = selected['layout']
    manifest = dict(schema='org.disked.carrier-manifest-prototype/1', product_id=selected['product_id'],
                    target=selected['target'], kind='external-read-only-host-offline-zip-fixture',
                    containment=selected['containment'], installed_owner='unmanaged',
                    lifecycle_available=False, authorizes_storage=False,
                    payload_source=info, host_observation=receipt['observation'],
                    artifacts={'H':dict(path=layout['H'], **receipt['artifact']),
                               'D':dict(path=layout['D'], bytes=data['bytes'], sha256=data['sha256'])})
    topology(manifest['containment'])
    contents = ac.canonical(manifest)+b'\n'
    if len(contents) > selected['limits']['metadata_bytes']:
        pf.refuse('carrier_metadata_budget')
    files = [dict(path=layout['H'], type='regular', **receipt['artifact']),
             dict(path=layout['D'], type='regular', bytes=data['bytes'], sha256=data['sha256']),
             dict(path=layout['manifest'], type='regular', bytes=str(len(contents)), sha256=ac.digest(contents))]
    inventory = dict(schema=ac.SCHEMA, files=sorted(files, key=lambda row: row['path']),
                     required_entrypoints=sorted([layout['H'], layout['D']]))
    ac.validate_inventory(inventory)
    return manifest, contents, inventory


def binding(archive, expected, info, receipt):
    return dict(schema='org.disked.carrier-binding-prototype/1', fixture_only=True,
                profile_sha256=pf.file_row(PROFILE)['sha256'],
                independent_inventory_sha256=ac.digest(ac.canonical(expected)),
                independent_build_info_sha256=ac.digest(ac.canonical(info)),
                independent_host_input_sha256=ac.digest(ac.canonical(receipt)),
                artifact={'role':'S-offline-zip-fixture', **pf.file_row(archive)},
                authenticity='not_established', installed_state='not_created', owner_accepted=False)


def check_root(root):
    root = pf.directory(root)
    if pf.read_json(root/MARKER) != {'schema':'org.disked.carrier-fixture-root/1', 'purpose':'disposable-fixtures-only'}:
        pf.refuse('carrier_fixture_root')
    if {p.name for p in root.iterdir()} != {MARKER, 'staging', 'carrier.zip', 'carrier-inventory.json', 'carrier-binding.json'}:
        pf.refuse('carrier_root_closure')
    return root


def verify(root, expected, info, receipt):
    root = check_root(root)
    _, contents, inventory = definitions(expected, info, receipt)
    archive = root/'carrier.zip'
    if pf.read_json(root/'carrier-inventory.json') != inventory:
        pf.refuse('carrier_independent_inventory')
    if ac.canonical(pf.read_json(root/'carrier-binding.json')) != ac.canonical(binding(archive, expected, info, receipt)):
        pf.refuse('carrier_external_binding')
    stage = root/'staging'
    if ac.inventory(stage, inventory['required_entrypoints']) != inventory:
        pf.refuse('carrier_staged_bytes')
    if (stage/profile()['layout']['manifest']).read_bytes() != contents:
        pf.refuse('carrier_manifest_bytes')
    ac.verify_zip(inventory, archive)
    return dict(schema='org.disked.carrier-fixture-check/1', status='pass', fixture_only=True,
                archive_sha256=pf.file_row(archive)['sha256'], entries=3,
                installed_state='not_created', lifecycle_available=False, owner_accepted=False)


def assemble(package, host, expected, info, receipt, output):
    package = pf.directory(package)
    host = Path(host).absolute()
    # Validate every independent input before creating output. No supplied code runs.
    pf.verify(package, expected, info)
    _, contents, inventory = definitions(expected, info, receipt)
    observed = pf.file_row(host)
    if {key: observed[key] for key in ('bytes', 'sha256')} != receipt['artifact']:
        pf.refuse('carrier_host_bytes')
    candidate = pf.directory(Path(output).absolute().parent)/Path(output).name
    for original in (package, host, PROFILE):
        pf.disjoint(candidate, original)
    root = pf.new_root(candidate)
    pf.write_json(root/MARKER, {'schema':'org.disked.carrier-fixture-root/1', 'purpose':'disposable-fixtures-only'})
    stage = root/'staging'
    stage.mkdir()
    selected = profile()
    for name in ('host', 'payload'):
        (stage/name).mkdir()
    # Read only the independently verified fixed payload entry; never execute it.
    remaining = int(expected['files'][0]['bytes'])
    with ac.pinned(package/'payload.zip') as (source, _), zipfile.ZipFile(source) as archive:
        with archive.open('disked.exe') as payload, (stage/selected['layout']['D']).open('xb') as target:
            while remaining:
                chunk = payload.read(min(remaining, ac.CHUNK))
                if not chunk:
                    pf.refuse('carrier_payload_changed')
                target.write(chunk)
                remaining -= len(chunk)
            if payload.read(1):
                pf.refuse('carrier_payload_changed')
    with ac.pinned(host) as (file, stat):
        if stat.st_size != int(receipt['artifact']['bytes']):
            pf.refuse('carrier_host_changed')
        with (stage/selected['layout']['H']).open('xb') as target:
            shutil.copyfileobj(file, target, ac.CHUNK)
    with (stage/selected['layout']['manifest']).open('xb') as file:
        file.write(contents)
    if ac.inventory(stage, inventory['required_entrypoints']) != inventory:
        pf.refuse('carrier_staged_bytes')
    archive_path = root/'carrier.zip'
    with archive_path.open('xb') as file, zipfile.ZipFile(file, 'w', compression=zipfile.ZIP_STORED) as archive:
        for row in inventory['files']:
            item = zipfile.ZipInfo(row['path'], (2000, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_STORED
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            with ac.pinned(stage/row['path']) as (source, _), archive.open(item, 'w') as target:
                shutil.copyfileobj(source, target, ac.CHUNK)
    ac.verify_zip(inventory, archive_path)
    pf.write_json(root/'carrier-inventory.json', inventory)
    pf.write_json(root/'carrier-binding.json', binding(archive_path, expected, info, receipt))
    return verify(root, expected, info, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    for name in ('assemble', 'verify'):
        action = actions.add_parser(name)
        action.add_argument('--inventory', type=Path, required=True)
        action.add_argument('--build-info', type=Path, required=True)
        action.add_argument('--host-input', type=Path, required=True)
        if name == 'assemble':
            action.add_argument('--package', type=Path, required=True)
            action.add_argument('--host', type=Path, required=True)
            action.add_argument('--output', type=Path, required=True)
        else:
            action.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        expected, info, receipt = [pf.read_json(path) for path in (args.inventory, args.build_info, args.host_input)]
        result = (assemble(args.package, args.host, expected, info, receipt, args.output) if args.action == 'assemble'
                  else verify(args.root, expected, info, receipt))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ac.Rejected, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json.dumps(dict(status='refused', reason=str(error), partial_output='retained_if_created')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
