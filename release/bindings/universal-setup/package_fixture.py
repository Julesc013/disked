"""Offline USK schema mapping and ordinary owned-fixture payload staging.

No USK lifecycle execution or installed-state ownership. No cleanup on failure.
Use quiescent reviewed inputs; path checks are not a hostile-filesystem sandbox.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('disked_artifact_check', ROOT / 'tools/release/artifact_check.py')
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)
PROFILE = ROOT / 'spec/catalog/setup-fixture-prototype.json'
LOCK = ROOT / 'external/universal-setup/source-lock.json'
MARKER = '.disked-setup-fixtures.json'
MEMBERS = {'payload.zip', 'inventory.json', 'build-info.json', 'product-package.json', 'setup-recipe.json', 'binding.json'}
META_MAX = 4194304
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z')
SHA = re.compile(r'sha256:[0-9a-f]{64}\Z')


def refuse(code):
    raise ac.Rejected(code)


def read_json(path):
    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                refuse('duplicate_json_key')
            value[key] = child
        return value
    with ac.pinned(path) as (file, info):
        if info.st_size > META_MAX:
            refuse('metadata_budget')
        data = file.read(META_MAX + 1)
    if len(data) > META_MAX:
        refuse('metadata_budget')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        refuse('metadata_json')


def write_json(path, value):
    data = ac.canonical(value) + b'\n'
    if len(data) > META_MAX:
        refuse('metadata_budget')
    with path.open('xb') as file:
        file.write(data)


def file_row(path):
    with ac.pinned(path) as (file, info):
        sha = ac.hash_file(file, info.st_size)
    return {'path': path.name, 'bytes': str(info.st_size), 'sha256': sha}


def directory(path):
    ac.local_source(path)
    path = Path(path).absolute()
    ac.no_link(path, True)
    for parent in path.parents:
        ac.no_link(parent, True)
    return path.resolve(strict=True)


def new_root(path):
    ac.local_source(path)
    path = Path(path).absolute()
    path = directory(path.parent) / path.name
    # mkdir refuses every existing root, including an empty root or link.
    path.mkdir()
    return directory(path)


def init_fixtures(path):
    root = new_root(path)
    write_json(root / MARKER, {'schema': 'org.disked.setup-fixture-workspace/1',
                              'root': str(root), 'purpose': 'disposable-fixtures-only'})
    return root


def workspace(path):
    root = directory(path)
    if read_json(root / MARKER) != {'schema': 'org.disked.setup-fixture-workspace/1',
                                   'root': str(root), 'purpose': 'disposable-fixtures-only'}:
        refuse('fixture_workspace_required')
    return root


def child(root, name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        refuse('fixture_child_name')
    ac.safe_path(name)
    return root / name


def disjoint(left, right):
    if left == right or left.is_relative_to(right) or right.is_relative_to(left):
        refuse('source_output_overlap')


def pinned_contracts():
    lock = read_json(LOCK)
    if lock.get('schema') != 'org.disked.setup-source-lock-prototype/1':
        refuse('source_lock_shape')
    schemas = {}
    for row in lock['setup']['retained']:
        path = ROOT / row['retained_path']
        if file_row(path)['sha256'] != row['sha256'] or path.stat().st_size != row['bytes']:
            refuse('pinned_contract_changed')
        if path.name.endswith('.schema.json'):
            value = read_json(path)
            Draft202012Validator.check_schema(value)
            schemas[value['$id']] = value
    if len(schemas) != 5:
        refuse('schema_closure')
    registry = Registry().with_resources((key, Resource.from_contents(value)) for key, value in schemas.items())
    # Registry has no network retrieval. All five relative-ref targets are pinned.
    return lock, schemas, registry


def upstream_validate(value, filename, schemas, registry):
    matches = [s for key, s in schemas.items() if key.endswith('/' + filename)]
    if len(matches) != 1:
        refuse('schema_identity')
    try:
        Draft202012Validator(matches[0], registry=registry).validate(value)
    except Exception as error:
        # Stable outward refusal; source values are never rendered as commands.
        raise ac.Rejected('upstream_contract_shape') from error


def identity_check(info, profile):
    if not isinstance(info, dict) or info.get('product') != 'DiskEd' or info.get('source_state') != 'clean':
        refuse('clean_build_identity_required')
    if not re.fullmatch(r'0\.1\.0-dev\.[1-9][0-9]*', str(info.get('version', ''))):
        refuse('prototype_version_required')
    if info.get('target') != profile['target'] or info.get('composition') != profile['composition']:
        refuse('target_composition_unqualified')
    if not re.fullmatch('[0-9a-f]{40}', str(info.get('source_revision', ''))) or not SHA.fullmatch(str(info.get('input_digest', ''))):
        refuse('build_source_identity')


def definitions(expected, info, archive):
    profile = read_json(PROFILE)
    identity_check(info, profile)
    ac.validate_inventory(expected)
    if expected['required_entrypoints'] != [profile['entrypoint']]:
        refuse('entrypoint_selection')
    entries = [{'path': r['path'], 'kind': 'file', 'size_bytes': int(r['bytes']),
                'sha256': r['sha256'][7:]} for r in expected['files']]
    package = {
        'schema': 'usk.product_package.v1', 'product_id': 'org.disked',
        'product_version': info['version'], 'publisher_ref': 'org.disked.unverified-fixture',
        'source': {'schema': 'usk.source_manifest.v1', 'source_id': 'disked.prototype.local',
                   'kind': 'local_package', 'package_ref': 'payload.zip',
                   'size_bytes': int(archive['bytes']), 'sha256': archive['sha256'][7:],
                   'authenticity_refs': [], 'provenance_refs': ['build-info.json']},
        'components': [{'schema': 'usk.component_manifest.v1', 'component_id': 'disked.prototype',
                        'platform': 'windows', 'architecture': 'x64', 'entries': entries}],
        'immutable_paths': [r['path'] for r in entries], 'mutable_paths': [], 'preserved_paths': [],
        'license_refs': [], 'sbom_refs': [], 'provenance_refs': ['build-info.json'], 'authenticity_refs': []}
    recipe = {
        'schema': 'usk.setup_recipe.v1', 'recipe_id': 'org.disked.prototype.verify',
        'recipe_version': '1', 'product_id': package['product_id'], 'product_version': info['version'],
        'package_digest': archive['sha256'][7:], 'component_ids': ['disked.prototype'],
        'target_topology': {'scope': 'portable', 'payload_root': '{INSTALL_ROOT}',
                            'mutable_root': '{CONFIG_ROOT}', 'preserved_root': '{CASE_ROOT}'},
        'migrations': [], 'lifecycle_operations': ['verify'], 'rollback_disposition': 'refused',
        'recovery_disposition': 'refused', 'installed_state_compatibility': {
            'schema': 'usk.installed_state_compatibility.v1', 'state_schema': 'usk.installed_state.v1',
            'minimum_reader': '1.0', 'maximum_tested_reader': 'not_run', 'migration_required_from': []}}
    lock, schemas, registry = pinned_contracts()
    upstream_validate(package, 'product_package.v1.schema.json', schemas, registry)
    upstream_validate(recipe, 'product_setup_recipe.v1.schema.json', schemas, registry)
    return package, recipe, lock, profile


def binding(root, lock, profile):
    return {'schema': 'org.disked.setup-fixture-binding/1',
            'profile_sha256': file_row(PROFILE)['sha256'], 'source_lock_sha256': file_row(LOCK)['sha256'],
            'setup_source': lock['setup']['revision'], 'target': profile['target'],
            'composition': profile['composition'],
            'files': [file_row(root / p) for p in sorted(MEMBERS - {'binding.json'})],
            'claims': {'payload_equality': 'checked', 'authenticity': 'not_established',
                       'owner_accepted': False, 'live_setup': 'not_run', 'installation': 'not_run',
                       'runtime': 'not_run', 'publication': 'not_run', 'rollback': 'unavailable'}}


def assemble(root, name, staging, expected, info):
    root = workspace(root)
    output = child(root, name)
    staging = directory(staging)
    disjoint(staging, output)
    # Reject malformed identity/entrypoint/contracts before any output creation.
    definitions(expected, info, {'bytes': '1', 'sha256': 'sha256:' + '0' * 64})
    if ac.inventory(staging, expected['required_entrypoints']) != expected:
        refuse('staging_inventory_changed')
    output = new_root(output)
    # All later failure paths retain their partial output; no private installer.
    with (output / 'payload.zip').open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for row in expected['files']:
                entry = zipfile.ZipInfo(row['path'], (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                entry.file_size = int(row['bytes'])
                with ac.pinned(staging / row['path']) as (source, opened):
                    if opened.st_size != int(row['bytes']):
                        refuse('staging_inventory_changed')
                    h = hashlib.sha256()
                    n = 0
                    with archive.open(entry, 'w') as dest:
                        while data := source.read(ac.CHUNK):
                            n += len(data)
                            if n > int(row['bytes']):
                                refuse('staging_inventory_changed')
                            h.update(data)
                            dest.write(data)
                    if n != int(row['bytes']) or 'sha256:' + h.hexdigest() != row['sha256']:
                        refuse('staging_inventory_changed')
    ac.verify_zip(expected, output / 'payload.zip')
    if ac.inventory(staging, expected['required_entrypoints']) != expected:
        refuse('staging_inventory_changed')
    package, recipe, lock, profile = definitions(expected, info, file_row(output / 'payload.zip'))
    for filename, value in [('inventory.json', expected), ('build-info.json', info),
                             ('product-package.json', package), ('setup-recipe.json', recipe)]:
        write_json(output / filename, value)
    write_json(output / 'binding.json', binding(output, lock, profile))
    verify(output, expected, info)
    return output


def verify(root, expected, info):
    root = directory(root)
    if {p.name for p in root.iterdir()} != MEMBERS:
        refuse('bundle_closure')
    # Never derive the trusted expected inventory from the package under test.
    ac.validate_inventory(expected)
    if read_json(root / 'inventory.json') != expected or read_json(root / 'build-info.json') != info:
        refuse('independent_inputs_changed')
    report = ac.verify_zip(expected, root / 'payload.zip')
    package, recipe, lock, profile = definitions(expected, info, file_row(root / 'payload.zip'))
    if read_json(root / 'product-package.json') != package or read_json(root / 'setup-recipe.json') != recipe:
        refuse('package_recipe_binding')
    if read_json(root / 'binding.json') != binding(root, lock, profile):
        refuse('bundle_binding')
    return {'schema': 'org.disked.setup-fixture-check/1', 'status': 'pass',
            'archive_sha256': report['archive_sha256'], 'files': report['files'],
            'bytes': report['bytes'], 'setup_source': lock['setup']['revision'],
            'upstream_schema_validation': 'pass', 'live_setup': 'not_run', 'authenticity': 'not_established'}


def extract_fixture(root, name, package_root, expected, info):
    root = workspace(root)
    output = child(root, name)
    package_root = directory(package_root)
    disjoint(output, package_root)
    verify(package_root, expected, info)
    output = new_root(output)
    with ac.pinned(package_root / 'payload.zip') as (stream, _):
        with zipfile.ZipFile(stream) as archive:
            # Selection comes only from the checked independent inventory.
            for row in expected['files']:
                path = output / row['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                directory(path.parent)
                h = hashlib.sha256()
                n = 0
                with archive.open(row['path']) as source, path.open('xb') as dest:
                    while data := source.read(ac.CHUNK):
                        n += len(data)
                        if n > int(row['bytes']):
                            refuse('extracted_size')
                        h.update(data)
                        dest.write(data)
                if n != int(row['bytes']) or 'sha256:' + h.hexdigest() != row['sha256']:
                    refuse('extracted_content')
    if ac.inventory(output, expected['required_entrypoints']) != expected:
        refuse('extracted_inventory')
    verify(package_root, expected, info)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init-fixtures'); p.add_argument('--root', type=Path, required=True)
    p = sub.add_parser('assemble')
    for option in ('workspace', 'staging', 'inventory', 'build-info'):
        p.add_argument('--' + option, type=Path, required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('verify'); p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--inventory', type=Path, required=True); p.add_argument('--build-info', type=Path, required=True)
    p = sub.add_parser('extract-fixture')
    p.add_argument('--workspace', type=Path, required=True); p.add_argument('--output', required=True)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--inventory', type=Path, required=True); p.add_argument('--build-info', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init-fixtures':
            result = {'workspace': str(init_fixtures(args.root))}
        elif args.command == 'assemble':
            expected, _ = ac.load_inventory(args.inventory)
            result = {'bundle': str(assemble(args.workspace, args.output, args.staging, expected, read_json(args.build_info)))}
        elif args.command == 'verify':
            expected, _ = ac.load_inventory(args.inventory)
            result = verify(args.bundle, expected, read_json(args.build_info))
        else:
            expected, _ = ac.load_inventory(args.inventory)
            result = {'extracted_fixture': str(extract_fixture(args.workspace, args.output, args.bundle,
                                                               expected, read_json(args.build_info)))}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ac.Rejected, OSError, ValueError, KeyError, TypeError, RecursionError, zipfile.BadZipFile) as error:
        print(json.dumps({'status': 'refused', 'reason': str(error), 'partial_output': 'retained_if_created'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
