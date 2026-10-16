"""Actual recursive command failure, cancellation and disconnected-client journeys."""
import argparse, copy, json, os, subprocess, sys, time, threading
from pathlib import Path
from gui_fixture import Gui, wait
from test_fat_recursive_product import arguments, grants, admission, canonical, sha, sc


def main():
    parser = argparse.ArgumentParser()
    for name in ('exe', 'fault', 'disabled', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    exe, fault, disabled = (str(getattr(args, key).resolve()) for key in ('exe', 'fault', 'disabled'))
    clean = {key: value for key, value in os.environ.items() if not key.startswith(
        ('DISKED_TEST_', 'DISKED_ACQ_', 'DISKED_FAT_'))}
    records, cases = [], []
    bundle = sc.Bundle(Path(__file__).resolve().parents[2]/'spec')
    passed = False

    def record(name, **data):
        records.append(dict(name=name, **data))
        print('PASS '+name, flush=True)

    def cli(words, binary=exe, controls=None):
        result = subprocess.run([binary, '--json', *words], env=dict(clean, **(controls or {})),
                                capture_output=True, timeout=35)
        assert result.returncode in (0, 2, 3, 4, 5, 6) and not result.stderr, result
        value=json.loads(result.stdout)
        bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',value)
        return value

    def setup(binary=exe):
        root, inputs, expected = admission.fixture()
        params = dict(phase='prepare', source=inputs['source'], destination=inputs['destination'],
                      ledger=inputs['ledger'], state_directory=inputs['store'],
                      volume_offset=inputs['offset'], volume_bytes=inputs['length'],
                      fat_copy=inputs['copy'], capture_epoch='17', oem_code_page='437')
        source = (root/'source.img').read_bytes()
        review = cli(arguments(params), binary)['result']
        cases.append(dict(root=str(root), source_sha256=sha(source)))
        return root, params, grants(review), source, expected

    def observe(params, operation, terminal=True):
        deadline = time.monotonic()+90
        while True:
            value = cli(['operation', 'inspect', operation, '--state-dir', params['state_directory']])['result']
            history = value.get('history') or {}
            if terminal and history.get('state') in (
                    'recorded_complete', 'recorded_partial', 'recorded_exit_unresolved'):
                return value
            if not terminal and value.get('writer', {}).get('observation') == 'running':
                return value
            assert time.monotonic() < deadline, value
            time.sleep(.04)

    def request(frontend, root, command, params):
        if frontend == 'cli':
            return cli(command)
        if frontend == 'protocol':
            frame = dict(schema='org.disked.request/1', request_id='failure:req', command=
                         'operation.cancel.request', parameters=params, required_features=[])
            result = subprocess.run([exe, 'protocol', 'serve', '--format', 'json'],
                                    input=canonical(frame), capture_output=True, env=clean, timeout=30)
            assert result.returncode in (0, 6) and not result.stderr, result
            return json.loads(result.stdout)
        if frontend == 'gui':
            ui = Gui(Path(exe), ['--gui', *command], render=True)
            try:
                ui.click(109)
                assert ui.details().get('reviewed'), ui.details()
                ui.click(110)
                value = wait(lambda: ui.details() if ui.details().get('schema') ==
                             'org.disked.response/1' else None, 10)
            finally:
                ui.close()
            assert ui.code == 0 and not ui.error
            return value
        inputs, output = root/'cancel-input.json', root/'cancel-console.json'
        inputs.write_bytes(canonical(dict(parameters=params, command=command)))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags, startup.wShowWindow = 1, 0
        result = subprocess.run([sys.executable, str(Path(__file__).with_name(
            'fat_extraction_console_fixture.py')), exe, str(inputs), str(output), frontend],
            env=clean, timeout=45, creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        report = json.loads(output.read_bytes())
        assert result.returncode == 0 and all(report['restored'].values()), report
        return report['response']

    try:
        for frontend in ('cli', 'protocol', 'gui', 'tui', 'shell'):
            root, params, execution, source, _ = setup(fault)
            response = cli(arguments(execution), fault,
                           {'DISKED_TEST_RECURSIVE_WORKER': 'execute_wait_cancel'})
            operation = response['operation_id']
            assert response['status'] == 'accepted_running', response
            active = observe(params, operation, terminal=False)
            assert active['controller']['observation'] == 'running', active
            # The launching CLI has already exited. This caller observes the same
            # independently owned operation, with no replacement dispatch.
            assert (root/'output').is_dir() and not list((root/'output').iterdir())
            op = dict(operation_id=operation, state_directory=params['state_directory'])
            command = ['operation', 'cancel', operation, '--state-dir', params['state_directory']]
            cancelled = request(frontend, root, command, op)
            assert cancelled['result']['cancellation_request'] == 'requested', cancelled
            final = observe(params, operation)
            assert final['history']['state'] == 'recorded_partial', final
            assert final['history']['last_worker']['outcome']['cancellation_observed'], final
            assert (root/'source.img').read_bytes() == source
            assert json.loads((root/'store/recursive-request.json').read_bytes())['operation_id'] == operation
            record('disconnected-launcher-and-'+frontend+'-cancellation', operation_id=operation)

        root, params, execution, source, expected = setup()
        controls = {'DISKED_TEST_RECURSIVE_WORKER': 'execute_wait_cancel',
                    'DISKED_TEST_STORE_FAULT': 'fat_tree_request.full'}
        response = cli(arguments(execution), controls=controls)
        final = observe(params, response['operation_id'])
        assert final['history']['state'] == 'recorded_complete', final
        for name, (data, _) in expected.items():
            assert (root/'output'/name).read_bytes() == data
        assert (root/'source.img').read_bytes() == source
        record('ordinary-development-composition-ignores-fault-controls')

        root, params, execution, source, _ = setup(fault)
        response = cli(arguments(execution), fault,
                       {'DISKED_TEST_RECURSIVE_WORKER': 'execute_wait_cancel'})
        operation = response['operation_id']
        observe(params, operation, terminal=False)
        frame = dict(schema='org.disked.request/1', request_id='disconnect:req',
                     command='operation.watch', parameters=dict(operation_id=operation,
                     state_directory=params['state_directory'], follow_ms='2000'),
                     required_features=['org.disked.fat-tree-operation-events/1'])
        watcher = subprocess.Popen([exe, 'protocol', 'serve', '--format', 'ndjson'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean)
        rows, arrived = [], threading.Event()
        def first_event():
            line = watcher.stdout.readline()
            if line:
                rows.append(json.loads(line))
                arrived.set()
        try:
            watcher.stdin.write(canonical(frame)+b'\n')
            watcher.stdin.close()
            reader = threading.Thread(target=first_event, daemon=True)
            reader.start()
            assert arrived.wait(8), 'actual watch emitted no first event'
            reader.join(timeout=2)
            assert not reader.is_alive() and rows[0]['schema'] == 'org.disked.event/1'
            bundle.validate('urn:disked:schema:fat-tree-operation-event-prototype:1', rows[0])
            watcher.stdout.close()
            code = watcher.wait(timeout=10)
            assert not watcher.stderr.read()
            assert code != 0, 'failed output channel was reported as success'
            active = observe(params, operation, terminal=False)
            assert active['controller']['observation'] == 'running'
            assert active['history']['state'] == 'recorded_active'
            assert not active['history']['last_worker']['cancellation_requested']
            first = rows[0]
            resume = dict(operation_id=operation,state_directory=params['state_directory'],
                          after_sequence=first['sequence'],
                          after_digest=first['payload']['record_digest'][7:],
                          worker_epoch=first['payload']['worker_epoch'])
            resumed = cli(['operation','watch',operation,'--state-dir',params['state_directory'],
                           '--after-sequence',resume['after_sequence'],'--after-digest',resume['after_digest'],
                           '--worker-epoch',resume['worker_epoch']])
            for event in resumed['result']['events']:
                assert int(event['sequence']) > int(first['sequence'])
            record('closed-watch-pipe-keeps-owner-live-and-cursor-resumable', exit_code=code)
        finally:
            if watcher.poll() is None:
                watcher.kill(); watcher.wait(timeout=5)
            cli(['operation','cancel',operation,'--state-dir',params['state_directory']])
            final = observe(params,operation)
            assert final['history']['state'] == 'recorded_partial'
            assert (root/'source.img').read_bytes() == source

        for mode, expected_exit in (('execute_hang','31'),('exit_after_root','93')):
            root, params, execution, source, _ = setup(fault)
            response = cli(arguments(execution), fault, {'DISKED_TEST_RECURSIVE_WORKER':mode})
            operation = response['operation_id']
            if mode == 'execute_hang':
                cancelled = cli(['operation','cancel',operation,'--state-dir',params['state_directory']])
                assert cancelled['result']['cancellation_request'] == 'requested'
            final = observe(params,operation)
            assert final['history']['state'] == 'recorded_exit_unresolved', final
            assert final['history']['last_worker']['worker']['exit_code'] == expected_exit, final
            assert final['history']['last_worker']['outcome'] is None
            assert (root/'source.img').read_bytes() == source
            assert (root/'output').is_dir() and not list((root/'output').iterdir())
            before = {p.name:p.read_bytes() for p in (root/'store').iterdir()}
            repeated = cli(arguments(execution),fault)
            assert repeated['status'] in ('refused','unknown'),repeated
            assert before == {p.name:p.read_bytes() for p in (root/'store').iterdir()}
            record('owned-unresponsive-or-exited-writer-no-replacement', fault=mode,exit_code=expected_exit)

        for mode in ('fat_tree_request.full', 'fat_tree_state.short', 'fat_tree_state.flush'):
            root, params, execution, source, _ = setup(fault)
            response = cli(arguments(execution), fault, {'DISKED_TEST_STORE_FAULT': mode})
            assert response['status'] == 'unknown', response
            assert isinstance(response['operation_id'], str), response
            observed = cli(['operation', 'inspect', response['operation_id'],
                            '--state-dir', params['state_directory']])
            if mode == 'fat_tree_state.flush':
                # Reading the intact prefix succeeds; it does not establish a
                # terminal operation or resolve whether the write was durable.
                assert observed['status'] == 'completed', observed
                assert observed['result']['history']['state'] == 'recorded_active', observed
                assert not observed['result']['claims']['replay_authority']
            else:
                assert observed['status'] == 'unknown', observed
            assert not (root/'output').exists() and not (root/'metadata.ndjson').exists()
            assert (root/'source.img').read_bytes() == source
            before = {p.name: p.read_bytes() for p in (root/'store').iterdir()}
            repeated = cli(arguments(execution), fault)
            assert repeated['status'] in ('refused', 'unknown'), repeated
            assert before == {p.name: p.read_bytes() for p in (root/'store').iterdir()}
            record('uncertain-store-retained-without-replay', fault=mode)

        root, params, execution, source, _ = setup()
        for binary in (exe, fault):
            invalid = dict(params, worker_fault='execute_hang')
            frame = dict(schema='org.disked.request/1', request_id='invalid:req',
                         command='filesystem.tree.extract', parameters=invalid, required_features=[])
            result = subprocess.run([binary, 'protocol', 'serve', '--format', 'json'],
                                    input=canonical(frame), capture_output=True, env=clean, timeout=30)
            assert json.loads(result.stdout)['status'] == 'refused' and not result.stderr
            assert not list((root/'store').iterdir()) and not (root/'output').exists()
        for changed in ('source', 'destination'):
            stale = copy.deepcopy(execution)
            stale['definition']['backend']['paths'][changed] = str(root/'changed')
            rejected = cli(arguments(stale))
            assert rejected['status'] == 'refused', rejected
            assert not list((root/'store').iterdir()) and not (root/'output').exists()
        rejected = cli(arguments(execution), disabled, controls)
        assert rejected['status'] == 'refused'
        assert not list((root/'store').iterdir()) and (root/'source.img').read_bytes() == source
        record('invalid-mutation-fields-stale-digests-and-disabled-composition')

        root, params, execution, source, _ = setup()
        with (root/'source.img').open('r+b') as stream:
            stream.seek(-1, os.SEEK_END)
            stream.write(bytes([source[-1] ^ 1]))
        changed = (root/'source.img').read_bytes()
        rejected = cli(arguments(execution))
        assert rejected['status'] == 'refused', rejected
        assert not list((root/'store').iterdir()) and not (root/'output').exists()
        assert (root/'source.img').read_bytes() == changed
        record('changed-source-generation-refused-before-effects')

        root, params, execution, source, _ = setup()
        foreign = root/'store/recursive-request.json'
        foreign.write_bytes(b'foreign resource\n')
        rejected = cli(arguments(execution))
        assert rejected['status'] == 'refused', rejected
        assert foreign.read_bytes() == b'foreign resource\n'
        assert len(list((root/'store').iterdir())) == 1 and not (root/'output').exists()
        assert (root/'source.img').read_bytes() == source
        record('foreign-control-resource-preserved')
        passed = True
    finally:
        args.output.write_text(json.dumps(dict(passed=passed, checks=len(records), records=records,
            cases=cases, scope='Generated images and isolated fault composition; no physical access, '
            'other-host or release qualification'), indent=2)+'\n',
            encoding='utf-8', newline='\n')
    assert passed


if __name__ == '__main__':
    main()
