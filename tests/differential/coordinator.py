"""Prepare frozen comparison packets and coordinate caller-supplied workers.

No worker launcher, transport, scheduler or execution admission is supplied here.
The full native/sanitizer/worker qualification gates remain separate.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from collector import Output
from compare import compare
from evidence import (Artifacts, EvidenceError, canonical_digest, comparison_inputs,
                      declared_inputs, digest, managed_path, read_receipt, require, write_report)
from observe_external import reference_command


def packet_path(value):
    require(bool(os.environ.get('DISKED_WORK_ROOT')), 'managed_runner_required')
    managed = Path(os.environ['DISKED_WORK_ROOT']).resolve(strict=True)
    require(not managed.is_relative_to(Path(__file__).resolve().parents[2]), 'repository_is_not_scratch')
    return managed_path(value, managed)


def original_path(value, style):
    require(isinstance(value, str) and '\0' not in value, 'original_path')
    kind = PureWindowsPath if style == 'windows' else PurePosixPath
    path = kind(value)
    require(path.is_absolute() and '..' not in path.parts and str(path) == value, 'original_path')
    return path


def commands_for(manifest, participant, definition):
    """Derive only fixed adapter commands from explicitly supplied tool paths."""
    profile, tools = definition['identity']['profile'], definition['tools']
    require(profile['path_style'] in ('windows', 'posix') and isinstance(tools, dict), 'worker_tools')
    allowed = {'mbr', 'gpt'} if participant == 'native' else {'sfdisk', 'sgdisk'}
    require(0 < len(tools) <= 2 and set(tools) <= allowed and
            (participant == 'native' or 'sfdisk' in tools), 'worker_tools')
    for executable in tools.values():
        original_path(executable, profile['path_style'])
        require(executable in definition['identity']['build']['executables'], 'unmeasured_tool')
    workspace = original_path(profile['workspace'], profile['path_style'])
    cases = {case['name']: case for case in manifest['cases']}
    commands = {}
    for row in manifest['expected_observations']:
        if row['participant'] != participant:
            continue
        name, kind = row['name'], row['kind']
        if participant == 'native':
            require(kind == 'native' and cases[name]['family'] in tools, 'native_tool_selection')
            argv = [tools[cases[name]['family']]]
        else:
            tool = 'sgdisk' if kind == 'sgdisk-print' else 'sfdisk'
            require(tool in tools, 'reference_tool_selection')
            argument = str(workspace.joinpath(*PurePosixPath(row['policy']['input_path']).parts))
            argv = reference_command(kind, tools[tool], argument)
        commands[name, kind] = argv
    return commands


def corpus_recipes(case_names):
    """Resolve the repository-owned corpus, never fixture code named by data."""
    generator = Path(__file__).resolve().parents[1] / 'corpus/partition_images.py'
    generator_bytes = generator.read_bytes()
    spec = importlib.util.spec_from_file_location('disked_differential_corpus', generator)
    corpus = importlib.util.module_from_spec(spec); spec.loader.exec_module(corpus)
    recipes = corpus.recipes()
    require(generator.read_bytes() == generator_bytes, 'generator_changed')
    known = {case['name'] for case in recipes}
    require(case_names is None or isinstance(case_names, list) and 0 < len(case_names) <= len(known) and
            all(isinstance(name, str) for name in case_names) and len(set(case_names)) == len(case_names) and
            set(case_names) <= known, 'case_selection')
    selected = [case for case in recipes if case_names is None or case['name'] in case_names]
    return generator_bytes, selected


def case_definition(recipe):
    case = {k: v for k, v in recipe.items() if k != 'data'}
    case.update(bytes=len(recipe['data']), sha256=digest(recipe['data']))
    case['file'] = case['sha256'][7:] + '.img'
    return case


def prepare(root, workers, case_names=None):
    """Write a new packet without invoking any worker; return its frozen digest."""
    root = packet_path(root)
    require(not root.exists(), 'preserve_existing_packet')
    workers = copy.deepcopy(workers)
    require(isinstance(workers, dict) and 2 <= len(workers) <= 9 and 'native' in workers and
            all(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', name) for name in workers) and
            all(isinstance(v, dict) and set(v) == {'identity', 'tools'} for v in workers.values()), 'worker_definitions')
    generator_bytes, selected = corpus_recipes(case_names)
    root.mkdir(exist_ok=False)
    output = Output(root)
    manifest = dict(schema='org.disked.partition-corpus/1', cases=[], expected_observations=[],
                    generator_sha256=digest(generator_bytes), comparison_inputs=comparison_inputs(),
                    selection=dict(mode='all' if case_names is None else 'explicit', names=[v['name'] for v in selected]),
                    evidence=dict(schema='org.disked.differential-evidence/1', fixtures={}, participants={}))
    binding = manifest['evidence']
    binding['contract'] = output.artifact('inputs/CONTRACT.md', Path(__file__).with_name('CONTRACT.md').read_bytes())
    binding['generator'] = output.artifact('inputs/partition_images.py', generator_bytes)
    fixture_files = {}
    order = ['native', *sorted(name for name in workers if name != 'native')]
    for participant in order:
        identity = workers[participant]['identity']
        descriptor = output.artifact('identities/' + digest(participant.encode())[7:23] + '.json',
                                     (json.dumps(identity, indent=2, allow_nan=False) + '\n').encode())
        binding['participants'][participant] = dict(role='native' if participant == 'native' else 'reference',
                                                   profile=identity['profile'], identity=descriptor)
    for recipe in selected:
        case = case_definition(recipe)
        body = recipe['data']
        manifest['cases'].append(case)
        if case['sha256'] not in fixture_files:
            fixture_files[case['sha256']] = output.artifact('fixtures/' + case['file'], body)
        binding['fixtures'][case['name']] = fixture_files[case['sha256']]
        for participant in order:
            kinds = ['native'] if participant == 'native' else ['sfdisk-json', 'sfdisk-verify']
            if participant != 'native' and 'sgdisk' in workers[participant]['tools'] and case['family'] == 'gpt':
                kinds.append('sgdisk-print')
            for kind in kinds:
                mode = 'native' if kind == 'native' else 'diagnostic' if kind == 'sfdisk-verify' else 'projection'
                allowed = ['completed'] if participant == 'native' or case['common_projection'] and mode == 'projection' else ['completed', 'refused']
                manifest['expected_observations'].append(dict(name=case['name'], participant=participant, kind=kind,
                    policy=dict(comparison=mode, argv=[], input_path='copies/' + digest(participant.encode())[7:23] + '/' + case['name'] + '.img',
                                allowed_outcomes=allowed, timeout_seconds=15 if participant == 'native' else 8)))
    for participant in order:
        commands = commands_for(manifest, participant, workers[participant])
        for row in manifest['expected_observations']:
            if row['participant'] == participant:
                row['policy']['argv'] = commands[row['name'], row['kind']]
    snapshot = canonical_digest(manifest)
    reader, _, _, _ = declared_inputs(manifest, root, snapshot)
    reader.recheck()
    output.artifact('manifest.json', (json.dumps(manifest, indent=2, allow_nan=False) + '\n').encode())
    return dict(manifest=manifest, manifest_sha256=snapshot, packet_root=str(root))


def run(root, expected_snapshot, workers):
    """Coordinate evidence collection only; never qualify a full campaign here.

    Each trusted collect(manifest=..., snapshot=..., packet_root=...) port must
    return only after its workers are terminal and its bounded artifacts/receipt
    are transported to the declared relative paths under this packet root.
    """
    root = packet_path(root)
    manifest, size = read_receipt(Artifacts(root).path('manifest.json'))
    reader, cases, tuples, identities = declared_inputs(manifest, root, expected_snapshot)
    require('comparison_inputs' in manifest, 'coordinator_inputs_required')
    selection = manifest.get('selection')
    require(isinstance(selection, dict) and set(selection) == {'mode', 'names'} and
            selection['mode'] in ('all', 'explicit'), 'corpus_selection')
    generator_bytes, recipes = corpus_recipes(None if selection['mode'] == 'all' else selection['names'])
    require(selection['names'] == [v['name'] for v in recipes] and
            manifest['generator_sha256'] == digest(generator_bytes) and
            canonical_digest(manifest['cases']) == canonical_digest([case_definition(v) for v in recipes]), 'corpus_recipe_identity')
    require(isinstance(workers, dict) and set(workers) == set(identities), 'coordinator_worker_set')
    participants = manifest['evidence']['participants']
    for participant, definition in workers.items():
        require(isinstance(definition, dict) and set(definition) == {'identity', 'tools', 'collect'} and
                callable(definition['collect']) and
                definition['identity'] == reader.json(participants[participant]['identity']), 'coordinator_worker_identity')
        commands = commands_for(manifest, participant, definition)
        require(all(commands[name, kind] == row['policy']['argv']
                    for (name, who, kind), row in tuples.items() if who == participant), 'coordinator_worker_commands')
    workers = {name: dict(identity=copy.deepcopy(value['identity']), tools=copy.deepcopy(value['tools']),
                          collect=value['collect']) for name, value in workers.items()}
    require(all(not reader.path(row['policy']['input_path']).exists() for row in tuples.values()),
            'preserve_existing_fixture_copy')
    require(all(not reader.path('collections/' + digest(name.encode())[7:23]).exists() for name in workers),
            'preserve_existing_collection')
    reader.recheck()
    directory = reader.path('coordinator')
    require(not directory.exists(), 'preserve_existing_coordination')
    directory.mkdir()
    output = Output(root)
    receipt = dict(status='collecting', manifest_sha256=expected_snapshot, active_participant=None,
                   participants=[], complete_success=False, comparison=None,
                   qualification='not_assessed', cleanup='outer_runner_pending',
                   scope='Comparison evidence only;no sanitizer,native-product,worker,platform,owner or release qualification')
    remaining = 16 * 1024 * 1024 - size
    observations = {}
    try:
        output.checkpoint(directory, receipt)
        for participant in ['native', *sorted(name for name in workers if name != 'native')]:
            receipt['active_participant'] = participant
            output.checkpoint(directory, receipt)
            workers[participant]['collect'](manifest=copy.deepcopy(manifest), snapshot=expected_snapshot, packet_root=root)
            path = reader.path('collections/' + digest(participant.encode())[7:23] + '/results.json')
            value, count = read_receipt(path, remaining); remaining -= count
            require(value.get('participant') == participant and value.get('manifest_sha256') == expected_snapshot,
                    'coordinator_receipt_identity')
            observations[participant] = value
            receipt['participants'].append(dict(participant=participant, path=path.relative_to(root).as_posix(),
                                                bytes=count, canonical_sha256=canonical_digest(value)))
            receipt['active_participant'] = None
            output.checkpoint(directory, receipt)
        reader.recheck()
        require(manifest['comparison_inputs'] == comparison_inputs(), 'comparison_tool_identity')
        result = compare(manifest, observations['native'], {k: v for k, v in observations.items() if k != 'native'},
                         artifact_root=root, expected_manifest_sha256=expected_snapshot)
        controls = {participant: any(cases[name]['common_projection'] and
                    row['policy']['comparison'] == ('native' if participant == 'native' else 'projection')
                    for (name, who, _), row in tuples.items() if who == participant) for participant in workers}
        report = reader.path('coordinator/comparison.json')
        written = write_report(report, result, limit=min(64 * 1024 * 1024 - output.bytes_written, 64 * 1024 * 1024))
        output.bytes_written += written
        report_hash = hashlib.sha256()
        with report.open('rb') as stream:
            left = written
            while left:
                body = stream.read(min(left, 65536))
                require(bool(body), 'comparison_report_changed')
                report_hash.update(body); left -= len(body)
            require(not stream.read(1), 'comparison_report_changed')
        receipt.update(comparison=dict(path=report.relative_to(root).as_posix(), bytes=written,
                                       sha256='sha256:' + report_hash.hexdigest()),
                       positive_controls_declared=controls,
                       complete_success=bool(result['complete_success'] and all(controls.values())))
        receipt['status'] = 'evidence_complete' if receipt['complete_success'] else 'evidence_failed'
        output.checkpoint(directory, receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                       complete_success=False, error=type(error).__name__,
                       error_code=str(error) if isinstance(error, EvidenceError) else type(error).__name__,
                       quiescence_unknown=receipt['active_participant'] is not None)
        try:
            output.checkpoint(directory, receipt)
        except (OSError, ValueError):
            pass
        raise


if __name__ == '__main__':
    raise SystemExit('No standalone execution profile is admitted; use prepare/run with explicit worker ports')
