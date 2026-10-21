"""Guest coordinator conformance, with a named repository protocol fixture.

This never qualifies util-linux, a Linux profile, or a real reference campaign.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import traceback

FILES = (
    'tests/differential/coordinator.py', 'tests/differential/collector.py',
    'tests/differential/compare.py', 'tests/differential/evidence.py',
    'tests/differential/projections.py', 'tests/differential/observe_native.py',
    'tests/differential/observe_external.py', 'tests/differential/CONTRACT.md',
    'tests/differential/reference_fixture.cpp',
    'source/portable/hash/sha256.cpp', 'source/portable/hash/sha256.h')
REFERENCE = 'repository-protocol-fixture'


def exercise(g, work, environment, executor, result):
    import coordinator
    import observe_native
    import observe_external
    from collector import Output, executable_hash, process_result
    from compare import compare
    from evidence import digest
    expected = json.loads((g.ROOT/'expected.json').read_bytes())['coordinator_controls']
    assert expected['status'] == 'expected_before_execution'
    output = Output(work/'probe-observations')
    report = dict(status='running', scope=__doc__, independent_reference_run=False,
                  full_campaign_qualified=False, negative_replay=[], negative_execution=[])
    result['probe_run']['coordinator_controls'] = report
    binary = Path(environment['PATH'].split(os.pathsep)[0])
    fixture = work/'reference-fixture.exe'
    commands = [
        [str(binary/'cl.exe'), '/nologo', '/std:c++14', '/W4', '/WX', '/MT', '/O2', '/EHsc', '/GS', '/sdl',
         '/guard:cf', '/permissive-', '/utf-8', '/I'+str(g.ROOT/'source'), '/Fo'+str(work/'probe-obj')+'\\',
         '/c', str(g.ROOT/'source/portable/hash/sha256.cpp'), str(g.ROOT/'tests/differential/reference_fixture.cpp')],
        [str(binary/'link.exe'), '/nologo', '/INCREMENTAL:NO', '/MACHINE:X64', '/DYNAMICBASE', '/NXCOMPAT',
         '/guard:cf', '/SUBSYSTEM:CONSOLE', '/OUT:'+str(fixture),
         *[str(work/'probe-obj'/(name+'.obj')) for name in ('sha256', 'reference_fixture', 'json')], 'kernel32.lib']]
    report['compilation'] = []
    for index, argv in enumerate(commands):
        value = executor(argv=argv, cwd=work, payload=b'', timeout=120, output_limit=1048576)
        raw = {stream: output.artifact('control-build/'+str(index)+'.'+stream, value[stream]) for stream in ('stdout', 'stderr')}
        report['compilation'].append(dict(argv=argv, status=process_result(value, dict(timeout_seconds=120)),
                                          call_index=executor.calls, raw=raw))
        assert report['compilation'][-1]['status'] == 'completed'
    source_manifest = json.loads((g.ROOT/'source-manifest.json').read_bytes())
    revision = source_manifest['base_revision']
    sources = {path: 'sha256:'+value for path, value in result['probe_run']['source_inputs'].items()}
    sources.update({path: digest((g.ROOT/path).read_bytes()) for path in FILES})
    toolchain = {str(binary/name): executable_hash(str(binary/name)) for name in ('cl.exe', 'link.exe')}
    saved = os.environ.get('DISKED_WORK_ROOT')
    os.environ['DISKED_WORK_ROOT'] = str(work)
    try:
        def definitions(packet):
            values = {}
            for participant in ('native', REFERENCE):
                tools = dict(mbr=str(work/'mbr-probe.exe'), gpt=str(work/'gpt-probe.exe')) if participant == 'native' else dict(sfdisk=str(fixture))
                token = result['native_identity']
                assert token['restricted'] and token['in_job'] and not token['elevated'] and not token['appcontainer']
                profile = dict(os=platform.system(), build=platform.version(), architecture=platform.machine(),
                    runtime=sys.version.split()[0], token=token['sid']+';restricted;Medium;nonadmin;non-elevated',
                    workspace=str(packet), path_style='windows')
                identity = dict(schema='org.disked.differential-identity/1', participant=participant,
                    role='native' if participant == 'native' else 'reference', profile=profile,
                    source=dict(revision=revision, inputs=sources, upstream_source_verified=False),
                    build=dict(configuration='MSVC /MT /O2 x64; '+('actual DiskEd private probes' if participant == 'native'
                        else 'REPOSITORY PROTOCOL FIXTURE ONLY; NOT util-linux or independent reference'),
                        toolchain=toolchain, executables={path: executable_hash(path) for path in tools.values()}))
                values[participant] = dict(identity=identity, tools=tools)
            return values

        def ports(values, mode='normal'):
            answer = {}
            for participant, definition in values.items():
                def collect(*, manifest, snapshot, packet_root, who=participant, config=definition):
                    if mode == 'false_callback_success' and who == REFERENCE:
                        return dict(passed=True)  # Intentionally no required receipt.
                    def execute(**call):
                        value = executor(**call)
                        if mode == 'interrupted':
                            # An actual child ran and its entire job is already retired.
                            assert value['terminal'] and executor.observations[-1]['temporary_files_removed']
                            raise KeyboardInterrupt('Declared control after owned child retirement')
                        return value
                    if who == 'native':
                        return observe_native.collect(manifest, packet_root, snapshot, config['identity'],
                            config['tools']['mbr'], config['tools']['gpt'], execute)
                    return observe_external.collect(manifest, packet_root, snapshot, who, config['identity'],
                        config['tools']['sfdisk'], None, execute)
                answer[participant] = dict(definition, collect=collect)
            return answer

        packet = work/'probe-observations'/'coordinator-packet'
        values = definitions(packet)
        prepared = coordinator.prepare(packet, values, expected['cases'])
        manifest, snapshot = prepared['manifest'], prepared['manifest_sha256']
        assert [[v[k] for k in ('name', 'participant', 'kind')] for v in manifest['expected_observations']] == expected['expected_tuples']
        report['frozen_manifest_sha256'] = snapshot
        first = executor.calls
        receipt = coordinator.run(packet, snapshot, ports(values))
        comparison = json.loads((packet/'coordinator/comparison.json').read_bytes())
        wanted = expected['positive']
        assert executor.calls-first == wanted['actual_calls']
        assert receipt['complete_success'] is wanted['complete_success'] and receipt['status'] == 'evidence_complete'
        assert receipt['qualification'] == wanted['qualification'] and receipt['cleanup'] == wanted['cleanup']
        assert comparison['evidence_status'] == wanted['evidence_status'] and comparison['comparison_status'] == wanted['comparison_status']
        assert len(comparison['diagnostic_observations']) == wanted['diagnostics']
        conflict = next(v for v in comparison['comparisons'] if v['name'] == 'gpt-valid-disagreement')
        assert conflict['discrepancy'] == 'different_projection' and conflict['matching_candidates'] == []
        assert len(conflict['native']['candidates']) == 2 and conflict['native']['comparison'] == 2
        report['positive'] = dict(receipt=receipt, calls=list(range(first+1, executor.calls+1)),
                                  evidence_status=comparison['evidence_status'], comparison_status=comparison['comparison_status'])
        receipts = {who: json.loads((packet/'collections'/digest(who.encode())[7:23]/'results.json').read_bytes()) for who in values}
        for mode in expected['negative_replay']:
            changed = copy.deepcopy(receipts)
            if mode == 'missing': changed[REFERENCE]['observations'].pop()
            elif mode == 'duplicate': changed[REFERENCE]['observations'].append(copy.deepcopy(changed[REFERENCE]['observations'][0]))
            elif mode == 'wrong_geometry': changed[REFERENCE]['observations'][0]['unit'] = 4096
            else: changed[REFERENCE]['observations'][0]['stdout'] += 'tampered'
            checked = compare(manifest, changed['native'], {REFERENCE: changed[REFERENCE]},
                              artifact_root=packet, expected_manifest_sha256=snapshot)
            assert not checked['complete_success']
            report['negative_replay'].append(dict(name=mode, evidence_status=checked['evidence_status'], complete_success=False))
        for mode in ('false_callback_success', 'interrupted'):
            negative = work/'probe-observations'/mode
            values = definitions(negative)
            prepared = coordinator.prepare(negative, values, ['mbr-two', 'gpt-valid-disagreement'])
            first = executor.calls
            try: coordinator.run(negative, prepared['manifest_sha256'], ports(values, mode))
            except (KeyboardInterrupt, FileNotFoundError) as error:
                assert isinstance(error, KeyboardInterrupt if mode == 'interrupted' else FileNotFoundError)
            else: raise AssertionError('Invalid control yielded coordinator success: '+mode)
            observed = json.loads((negative/'coordinator/results.json').read_bytes())
            target = next(v for v in expected['negative_execution'] if v['name'] == mode)
            assert not observed['complete_success'] and executor.calls-first == target['native_calls']
            assert observed['status'] == ('interrupted' if mode == 'interrupted' else 'failed')
            assert observed['quiescence_unknown'] is True
            report['negative_execution'].append(dict(name=mode, receipt=observed, calls=list(range(first+1, executor.calls+1)),
                outer_jobs_retired=all(v['terminal'] and v['job_retirement']['active_processes'] == 0 for v in executor.observations)))
        assert executor.calls == expected['total_port_calls']
        report.update(status='pass', source_revision=revision, source_inputs=sources, total_port_calls=executor.calls,
                      actual_reference_fixture_calls=4, actual_independent_reference_calls=0)
    finally:
        if saved is None: os.environ.pop('DISKED_WORK_ROOT', None)
        else: os.environ['DISKED_WORK_ROOT'] = saved


def coordinate(g):
    native = g.load('control_native_probes', g.ROOT/'native-probes.py')
    port = g.load('control_native_port', g.ROOT/'native-port.py')
    def extension(work, environment, executor, result):
        try:
            native.exercise(g, work, environment, executor, result)
            exercise(g, work, environment, executor, result)
        except BaseException:
            result.get('probe_run', {}).update(status='fail', error=traceback.format_exc()[-16384:])
            if result.get('probe_run') and all(v['terminal'] and v['temporary_files_removed'] for v in executor.observations):
                native.retain(g, work, executor, result)
            raise
        else:
            native.retain(g, work, executor, result)
    port.coordinate(g, extension=extension)
