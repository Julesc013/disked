"""Real common name-order views and explicit pure-port contract tests; generated files only."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import ntfs_name_order_command_expectations as E
from ntfs_name_order_command_expectations import canonical, sha, CAPS, DIRECTORY
from test_ntfs_commands import file_digest, Gui, wait, Gate
from test_ntfs_directory_commands import prefix
from protocol_trace import ProtocolTrace
import test_ntfs_file as held


def main():
    parser = argparse.ArgumentParser()
    for name in ('exe', 'fault', 'worker', 'worker-fault', 'probe', 'root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    for key in vars(a):
        setattr(a, key, getattr(a, key).resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith('DISKED_')}
    recorder = E.Recorder(a.output, a.root, env)
    observations, sources, families, layouts_tested = [], [], [], []
    passed = False
    temp = tempfile.TemporaryDirectory(prefix='disked-name-order-command-')
    folder = Path(temp.name).resolve()
    assert folder.parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith('disked-name-order-command-')

    def observed(name, raw, **extra):
        path = a.output.with_name(a.output.stem + '-observation-' + str(len(observations)) + '.bin')
        path.write_bytes(raw)
        observations.append(dict(name=name, raw_output=str(path), output_sha256=sha(raw), **extra))
        a.output.with_name(a.output.stem + '-observations.json').write_text(
            json.dumps(observations, indent=2) + '\n', encoding='utf-8', newline='\n')

    def family(name):
        families.append(name)
        print('CASE', name, flush=True)

    def launch(name, argv, expected=0, exe=None, settings=None, data=b''):
        value = recorder.run(name, [exe or a.exe, *argv], data=data, expected=expected, settings=settings)
        assert value['operation_id'] is None and len(canonical(value)) + 1 <= 524288
        return value

    def pure(params, full=None, status='captured', **extra):
        payload = dict(parameters=params, status=status, **extra)
        if full is not None:
            payload['file'] = full
        return recorder.run('pure-port', [a.probe], data=canonical(payload))

    def worker(v, path, version=None, reference=None, fixture=None):
        row = dict(path=str(path), offset=v.input['offset'], length=v.input['length'],
                   capture_epoch='19', name_order=True, limits=CAPS,
                   directory=dict(reference=reference or '0', limits=DIRECTORY))
        if version is not None:
            row['profile'] = version
        if fixture is not None:
            row['fixture'] = fixture
        value = recorder.run('owned-worker', [a.worker_fault if fixture else a.worker],
                             data=canonical(row) + b'\n', timeout=35)
        assert value['has_snapshot'], value
        return value['snapshot']

    def compare(left, right):
        assert left['status'] == right['status'] and left['diagnostics'] == right['diagnostics']
        assert E.stable(left) == E.stable(right)

    def facts(value, volume, diagnostic, reference=None):
        result = value['result']
        obs, capture, context = result['observation'], result['capture'], result['context']
        assert result['schema'] == 'org.disked.ntfs-name-order-inspection/1'
        assert result['scope'] == 'ordinary-local-file-ntfs-name-order'
        assert result['applicability_scope'] == 'single-directory-primary-mapped-name-order'
        assert result['requested_directory_reference'] == (reference or '0')
        assert obs['schema'] == 'org.disked.ntfs-name-order-projection/1'
        assert obs['original_schema'] == 'org.disked.ntfs-name-order-observation-prototype/1'
        assert not result['authorizes_effects'] and not any(obs[k] for k in (
            'atomic_snapshot', 'current_source_authority', 'effects_authorized'))
        assert capture['domain']['provider'] == 'ntfs-name-order-file-prototype'
        assert capture['domain']['limits'] == CAPS and capture['domain']['directory_limits'] == DIRECTORY
        assert capture['domain']['directory_reference'] == (reference or '0') and 'target_limit' not in capture['domain']
        assert result['capture_sha256'] == sha(canonical(capture))
        owned = result['worker']['worker']
        assert owned['observation'] == 'exited' and owned['pid'] == context['pid'] == capture['process_id']
        assert owned['created'] == context['created'] == capture['process_created']
        assert context['image_profile'] == 'ordinary-file-ntfs-name-order'
        assert context['code_sha256'] == sha(a.exe.read_bytes())[7:]
        if obs['upcase'] is not None and obs['upcase']['complete']:
            table = obs['upcase']
            raw = b''.join(bytes.fromhex(chunk['hex']) for chunk in table['table_data']['chunks'])
            assert raw == volume.table.table and len(raw) == 131072
            assert table['table_data'] == E.table_chunks(volume.table.table)
            assert table['table_sha256'] == sha(raw) and table['table_data']['sha256'] == sha(raw)
            assert table['base_reference'] == str(volume.table.reference)
            assert table['base_record_sha256'] == sha(volume.table.base_raw)
            assert table['source_id'] == obs['source_id'] == capture['source_identity_digest']
            assert table['epoch'] == obs['epoch'] == capture['sequence']
        audit = obs['name_order']
        if audit is not None and audit['complete']:
            expected = volume.expected()
            assert audit['key_count'] == expected['key_count'] and audit['mapped_nondecreasing'] == expected['mapped_nondecreasing']
            assert audit['directory_reference'] == str(volume.directory.reference)
            assert audit['source_id'] == obs['source_id'] and audit['epoch'] == obs['epoch']
            assert audit['table_sha256'] == sha(volume.table.table)
            assert audit['header_number_domain'] == 'original-directory-entry-header-numbers/1'
            for key in E.ARRAYS:
                project = (lambda row: dict(row, headers=prefix(row['headers'], 64, 2048))) if key in E.ARRAYS[2:] else (lambda row: row)
                assert audit[key] == prefix(expected[key], 128 if key in E.ARRAYS[:2] else 32,
                                            16384 if key in E.ARRAYS[:2] else 8192, project)
            assert not any(audit[k] for k in ('namespace_verified', 'collation_verified',
                'target_membership_verified', 'alias_resolution_admitted', 'lookup_admitted'))
            assert audit['case_policy'] == 'unobserved'
        codes = [d['code'] for d in value['diagnostics']]
        if diagnostic:
            assert value['status'] == 'failed' and obs['diagnostic'] == diagnostic
            if diagnostic == 'ntfs_name_order_mapped_descent':
                assert diagnostic in codes and 'ntfs_capture_incomplete' not in codes
                assert obs['complete'] and obs['reread_equal'] and not obs['applicable'] and not capture['observed_stable']
            else:
                assert 'ntfs_capture_incomplete' in codes
        else:
            assert value['status'] == 'completed' and obs['complete'] and obs['applicable'] and capture['observed_stable']

    def write(v, name):
        owner = type('OwnedFixture', (), {})()
        owner.root, owner.index = folder, len(sources)
        owner.skipTest = lambda reason: (_ for _ in ()).throw(AssertionError(reason))
        return held.Tests.fixture(owner, v, name)[1]

    def reject(full, params, change):
        bad = copy.deepcopy(full)
        change(bad)
        value = pure(params, bad)
        assert value['port_called'] and value['exit_code'] == 4
        assert value['response']['diagnostics'][0]['code'] == 'internal_error'

    try:
        baseline = None
        for index, (name, v, version, reference, diagnostic) in enumerate(E.fixtures()):
            path = write(v, 'generated-' + str(index) + '.img')
            before = file_digest(path)
            try:
                code = 4 if diagnostic else 0
                cli = launch('cli-' + name, ['--json', 'image', 'inspect', path, *E.options(v, version, reference)], code)
                facts(cli, v, diagnostic, reference)
                stdio = launch('stdio-' + name, ['protocol', 'serve', '--json'], code,
                               data=canonical(E.wire(E.parameters(v, path, version, reference))))
                compare(cli, stdio)
                original = worker(v, path, version, reference)
                expected_result = copy.deepcopy(cli)
                expected_result['result']['observation'] = E.expected_observation(original['observation'])
                assert E.stable(cli) == E.stable(expected_result)
                layouts_tested.append(dict(case=name, version=version, requested_reference=reference,
                                           diagnostic=diagnostic, exit_code=code, **E.independent_facts(v)))
                if name == 'profile-1-siblings':
                    baseline = v, path, cli, reference, before
                if name in ('large-order', 'large-same-reference', 'many-groups'):
                    audit = cli['result']['observation']['name_order']
                    assert not audit['projection_complete'] and not audit['directory_entries_complete']
            finally:
                after = file_digest(path)
                sources.append(dict(case=name, path=str(path), bytes=path.stat().st_size,
                                    before_sha256=before, after_sha256=after))
                a.output.with_name(a.output.stem + '-source-receipts.json').write_text(
                    json.dumps(sources, indent=2) + '\n', encoding='utf-8', newline='\n')
                assert before == after
        family('52-independent-native-layouts-and-stdio')
        assert baseline is not None
        v, path, response, reference, baseline_before = baseline
        params = E.parameters(v, path, reference=reference)
        full = worker(v, path, reference=reference)
        projected = pure(params, full)
        assert projected['port_called'] and projected['exit_code'] == 0
        assert projected['response']['result']['observation'] == E.expected_observation(full['observation'])
        assert projected['response']['result']['file_sha256'] == sha(canonical(full))
        compare(response, projected['response'])
        family('exact-pure-projection-of-parent-verified-ingredients')

        for name in ('schema', 'policy', 'case_policy', 'source_id', 'epoch', 'volume_offset',
                     'volume_bytes', 'directory_reference', 'directory_sha256', 'table_sha256',
                     'key_count', *E.COUNTERS):
            def change(bad, key=name):
                audit = bad['observation']['name_order']
                old = audit[key]
                audit[key] = str(int(old) + 1) if isinstance(old, str) and old.isdecimal() else 'wrong'
            reject(full, params, change)
        for name in ('namespace_verified', 'collation_verified', 'target_membership_verified',
                     'alias_resolution_admitted', 'lookup_admitted'):
            reject(full, params, lambda b, key=name: b['observation']['name_order'].__setitem__(key, True))
        reject(full, params, lambda b: b['observation']['name_order'].__setitem__('unknown_critical', True))
        for key in E.ARRAYS:
            reject(full, params, lambda b, key=key: b['observation']['name_order'].__setitem__(key, {}))
        reject(full, params, lambda b: b['observation']['name_order']['order'][0].__setitem__('header_number', '999'))
        reject(full, params, lambda b: b['observation']['name_order']['adjacent'][0].__setitem__('raw_order', '9'))
        def directory_forgery(bad):
            obs = bad['observation']
            obs['directory']['entries'][0]['name_hex'] = '5a00'
            obs['name_order']['directory_sha256'] = sha(canonical(obs['directory']))
        reject(full, params, directory_forgery)
        reject(full, params, lambda b: b['observation']['name_order'].__setitem__('mapped_nondecreasing', False))
        family('audit-scalars-arrays-and-coherently-rehashed-directory-forgeries')

        tied = E.JointVolume(kind='leaf', rows=[(b'A\0', 0, E.ref(14, 9)), (b'a\0', 1, E.ref(14, 9)),
                                               (b'A\0', 2, E.ref(14, 9))], size=4096)
        tied_path = write(tied, 'tied.img')
        tied_before = file_digest(tied_path)
        tied_full = worker(tied, tied_path)
        tied_params = E.parameters(tied, tied_path)
        for key in E.ARRAYS[2:]:
            reject(tied_full, tied_params, lambda b, key=key: b['observation']['name_order'][key][0]['headers'].__setitem__(0, '999'))
        reject(tied_full, tied_params, lambda b: b['observation']['name_order']['reference_groups'][0].__setitem__('namespace_codes', ['3']))
        reject(tied_full, tied_params, lambda b: b['observation']['name_order']['mapped_groups'][0].__setitem__('distinct_references', '2'))
        reject(tied_full, tied_params, lambda b: b['observation']['name_order']['mapped_groups'][0].__setitem__('raw_equal', True))
        for stage, key in enumerate(E.ARRAYS):
            partial = copy.deepcopy(tied_full)
            obs, audit = partial['observation'], partial['observation']['name_order']
            for n in range(stage, 4):
                audit[E.ARRAYS[n]] = []
                audit[E.COUNTERS[n]] = '0'
            audit.update(complete=False, mapped_nondecreasing=None)
            obs.update(complete=False, applicable=False, reread_equal=False, diagnostic='ntfs_output_budget')
            partial['capture']['observed_stable'] = False
            result = pure(tied_params, partial)
            assert result['exit_code'] == 4 and result['response']['diagnostics'][0]['code'] == 'ntfs_capture_incomplete'
            assert result['response']['result']['observation'] == E.expected_observation(obs)
            # This is a synthetic port-shape case; it is not a new parent-authenticated capture.
            reject(partial, tied_params, lambda b: b['observation']['name_order'].__setitem__('mapped_nondecreasing', True))
            if stage < 3:
                def later_phase(bad, n=stage + 1):
                    audit = bad['observation']['name_order']
                    audit[E.ARRAYS[n]].append(copy.deepcopy(tied_full['observation']['name_order'][E.ARRAYS[n]][0]))
                    audit[E.COUNTERS[n]] = '1'
                reject(partial, tied_params, later_phase)
        impossible_partial = copy.deepcopy(tied_full)
        impossible_partial['observation'].update(complete=False, applicable=False, reread_equal=False, diagnostic='ntfs_output_budget')
        impossible_partial['observation']['name_order'].update(complete=False, mapped_nondecreasing=None)
        impossible_partial['capture']['observed_stable'] = False
        result = pure(tied_params, impossible_partial)
        assert result['exit_code'] == 4 and result['response']['diagnostics'][0]['code'] == 'internal_error'
        family('candidate-group-relationships-and-synthetic-phase-prefixes')

        for field in ('schema', 'source_id', 'epoch', 'volume_offset', 'volume_bytes', 'base_reference',
                      'base_record_sha256', 'table_bytes', 'table_sha256'):
            def change(bad, key=field):
                table = bad['observation']['upcase']
                old = table[key]
                table[key] = str(int(old) + 1) if old.isdecimal() else 'wrong'
            reject(full, params, change)
        for change in [lambda b: b['observation']['upcase'].__setitem__('table_hex', '00'),
                       lambda b: b['observation']['upcase'].__setitem__('volume_serial', True),
                       lambda b: b['capture'].__setitem__('capture_domain', 'sha256:' + '0' * 64),
                       lambda b: b.__setitem__('authorizes_effects', True),
                       lambda b: b['observation'].__setitem__('atomic_snapshot', True),
                       lambda b: b['observation'].__setitem__('name_order', None),
                       lambda b: b['observation'].__setitem__('diagnostic', 'ntfs_name_order_mapped_descent')]:
            reject(full, params, change)
        for key, new in [('target_limit', '64'), ('volume_offset', '1'), ('sequence', '999'),
                         ('directory_reference', '281474976710661')]:
            def domain_change(bad, key=key, new=new):
                bad['capture']['domain'][key] = new
                bad['capture']['capture_domain'] = sha(canonical(bad['capture']['domain']))
            reject(full, params, domain_change)
        for key, new in [('limits', dict(CAPS, read_requests='511')),
                         ('directory_limits', dict(DIRECTORY, blocks='127'))]:
            def limits_change(bad, key=key, new=new):
                bad['capture']['domain'][key] = new
                bad['capture']['capture_domain'] = sha(canonical(bad['capture']['domain']))
            reject(full, params, limits_change)
        family('table-context-domain-and-outer-claim-forgeries')

        for fault, call in [('short', len(v.initial_reads)), ('changed', 2 * len(v.initial_reads))]:
            partial = worker(v, path, reference=reference, fixture=dict(capture_fault=fault, capture_call=str(call)))
            result = pure(params, partial)
            assert result['exit_code'] == 4 and result['response']['result']['observation'] == E.expected_observation(partial['observation'])
            codes = [d['code'] for d in result['response']['diagnostics']]
            assert ('ntfs_source_changed' if fault == 'changed' else 'ntfs_capture_incomplete') in codes
            if fault == 'changed':
                assert result['response']['result']['observation']['name_order']['complete']
        family('authentic-parent-verified-partials-and-later-source-change')

        boundary = copy.deepcopy(full)
        context = dict(padding=[])
        size = pure(params, boundary, context=context)['wire_bytes']
        remaining = 524288 - size
        while remaining:
            charge = 3 if context['padding'] else 2
            n = min(32768, remaining - charge)
            assert n >= 0
            if remaining - n - charge in (1, 2):
                n -= 3
            context['padding'].append('x' * n)
            remaining -= n + charge
        result = pure(params, boundary, context=context)
        assert result['exit_code'] == 0 and result['wire_bytes'] == 524288
        context['padding'][-1] += 'x'
        result = pure(params, boundary, context=context)
        assert result['exit_code'] == 4 and result['response']['diagnostics'][0]['code'] == 'ntfs_report_limit'
        family('exact-framing-boundary-and-one-byte-overflow')

        missing = folder / 'missing.img'
        for key, invalid in [('volume_bytes', '511'), ('volume_offset', str((1 << 63) - 512)),
                             ('directory_reference', '1'), ('ntfs_target_limit', '64'),
                             ('upcase_format', 'auto'), ('fat_copy', '0'), ('lookup', {}), ('ntfs_version', True)]:
            invalid_params = E.parameters(v, missing)
            invalid_params[key] = invalid
            result = launch('invalid-before-source', ['protocol', 'serve', '--json'], 2, exe=a.fault,
                            settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD': '1'}, data=canonical(E.wire(invalid_params)))
            assert result['diagnostics'][0]['code'] == 'invalid_parameter'
            assert not pure(invalid_params, status='unresolved')['port_called']
        for flag in (['--ntfs-target-limit', '64'], ['--upcase-format', 'auto'], ['--directory-reference', '1'], ['--ntfs-version', '2.0']):
            result = launch('invalid-cli-before-source', ['--json', 'image', 'inspect', missing, *E.options(v), *flag],
                            2, exe=a.fault, settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD': '1'})
            assert result['diagnostics'][0]['code'] == 'invalid_option_value'
        for name in ('upcase', 'name_order'):
            assert recorder.run('known-kind', [a.probe], data=canonical(dict(private_kind=name))) == dict(rejected=False)
        assert recorder.run('unknown-kind', [a.probe], data=canonical(dict(private_kind='unknown'))) == dict(rejected=True, diagnostic='ntfs_inspection_kind')
        for status, code in [('refused', 3), ('unresolved', 6)]:
            assert pure(params, status=status)['exit_code'] == code
        launch('missing-source', ['--json', 'image', 'inspect', missing, *E.options(v)], 3)
        family('source-free-invalid-controls-statuses-and-kind-guards')

        compare(response, launch('human-cli', ['--cli', 'image', 'inspect', path, *E.options(v, reference=reference)]))
        compare(response, launch('ndjson', ['protocol', 'serve', '--format=ndjson'], data=canonical(E.wire(params)) + b'\n'))
        ui = Gui(a.exe, ['--gui', 'image', 'inspect', str(path), *E.options(v, reference=reference)], render=True)
        try:
            ui.click(110)
            report = wait(lambda: ui.details() if 'status' in ui.details() else None)
            observed('gui', ui.text(101).encode('utf-8'))
            compare(response, report)
        finally:
            ui.close()
        assert ui.code == 0 and not ui.error and ui.created_files == []
        for frontend in ('tui', 'shell'):
            report = folder / (frontend + '.json')
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = 1
            startup.wShowWindow = 0
            command = [sys.executable, str(a.root / 'tests/frontend/image_console_fixture.py'), str(a.exe),
                       frontend, 'image.inspect', str(path), '-', str(report),
                       json.dumps(E.options(v, reference=reference)), '8000']
            p = subprocess.run(command, cwd=folder, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE,
                               startupinfo=startup, timeout=40)
            raw = report.read_bytes()
            observed(frontend, raw, command=command, exit_code=p.returncode,
                     stdio_capture='not_captured_owned_console')
            result = json.loads(raw)
            assert p.returncode == 0
            compare(response, result['response'])
        family('actual-human-ndjson-gui-tui-shell-views')

        for flag, code, diagnostic in [('VERIFY_CHANGED', 4, 'ntfs_source_changed'),
                                       ('VERIFY_ERROR', 4, 'ntfs_capture_incomplete'),
                                       ('INVALID_REPLY', 6, 'ntfs_reader_validation_unresolved'), ('HANG', 6, None)]:
            result = launch('fault-' + flag, ['--json', 'image', 'inspect', path, *E.options(v, reference=reference)],
                            code, exe=a.fault, settings={'DISKED_NTFS_COMMAND_TEST_' + flag: '1'})
            if diagnostic:
                assert diagnostic in [d['code'] for d in result['diagnostics']]
        launch('normal-fault-isolation', ['--json', 'image', 'inspect', path, *E.options(v, reference=reference)],
               settings={'DISKED_NTFS_COMMAND_TEST_HANG': '1'})
        family('actual-fault-and-normal-binary-isolation')

        gate = Gate()
        process = subprocess.Popen([str(a.fault), 'protocol', 'serve', '--format=ndjson'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=a.root,
                                   env=dict(env, DISKED_NTFS_COMMAND_TEST_GATE=gate.name))
        trace = ProtocolTrace(process, a.output, canonical)
        before = file_digest(path)
        try:
            trace.send(E.wire(params))
            gate.entered()
            trace.event('gate_entered')
            expired = trace.get(6)
            assert expired['status'] == 'unknown' and expired['diagnostics'][0]['code'] == 'request_wait_expired'
            try:
                with path.open('r+b'):
                    raise AssertionError('Source writable before actual worker completion')
            except PermissionError:
                pass
            trace.send(E.wire(params, 'busy'))
            assert trace.get(2)['diagnostics'][0]['code'] == 'request_resource_limit'
            essential = E.wire({}, 'essential')
            essential['command'] = 'command.list'
            trace.send(essential)
            assert trace.get(2)['status'] == 'completed'
            gate.release()
            trace.event('gate_release')
            after = None
            for _ in range(35):
                time.sleep(.1)
                trace.send(E.wire(params, 'fresh'))
                after = trace.get(3)
                if after['status'] == 'completed':
                    break
                assert after['diagnostics'][0]['code'] == 'request_resource_limit'
            trace.event('final_assertion', status=after and after['status'], queued=trace.messages.qsize())
            assert after and after['status'] == 'completed' and trace.messages.empty()
            process.stdin.close()
            code = process.wait(timeout=8)
            stderr = process.stderr.read()
            observed('late-parent-stderr', stderr, exit_code=code)
            assert code == 6 and not stderr and file_digest(path) == before
        except BaseException as error:
            trace.event('failure', error=repr(error), parent_returncode=process.poll(), queued=trace.messages.qsize())
            trace.snapshot('failure_pending_responses')
            raise
        finally:
            gate.release()
            gate.close()
            if process.poll() is None:
                if not process.stdin.closed:
                    process.stdin.close()
                process.wait(timeout=15)
            trace.event('teardown', parent_returncode=process.poll(), queued=trace.messages.qsize())
        family('late-reply-source-and-slot-retention')
        for argv in (['help', '--json'], ['build', 'inspect', '--json'], ['command', 'list', '--json']):
            launch('essential-' + argv[0], argv, exe=a.fault, settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD': '1'})
        family('source-free-essential-commands')
        for name, selected_path, before in [('all-baseline-views', path, baseline_before),
                                            ('tied-parent-verified-source', tied_path, tied_before)]:
            after = file_digest(selected_path)
            sources.append(dict(case=name, path=str(selected_path), bytes=selected_path.stat().st_size,
                                before_sha256=before, after_sha256=after))
            assert before == after
        passed = True
    finally:
        a.output.write_text(json.dumps(dict(status='pass' if passed else 'fail', passed=passed,
            calls=len(recorder.calls), receipts=recorder.calls, observations=observations, source_receipts=sources,
            layouts_tested=layouts_tested, families=families, recipe_sha256=sha(Path(__file__).read_bytes()),
            helper_sha256=sha(Path(E.__file__).read_bytes()), owner_accepted=False,
            full_0_1_0_complete=False), indent=2) + '\n', encoding='utf-8', newline='\n')
        assert folder.parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith('disked-name-order-command-')
        temp.cleanup()


if __name__ == '__main__':
    main()
