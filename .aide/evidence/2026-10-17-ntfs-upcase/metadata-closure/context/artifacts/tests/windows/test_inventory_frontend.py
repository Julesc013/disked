"""Actual owned Windows renderers over frozen injected native inventory."""
import argparse, copy, hashlib, json, subprocess, sys, time
from pathlib import Path
from test_observation_frontend import selected_registry
from test_identity_frame import fixture as identity, identity_disk
from test_storage_queries import disk, volume, packet, digest
from test_volume_namespace import fixture as namespace, reply, OTHER


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pointer-bytes', type=int, choices=(4, 8), required=True)
    a = p.parse_args(); root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'tests/frontend'))
    from gui_fixture import Gui, caption
    out = a.output.absolute(); out.mkdir(); probe = a.probe.absolute()
    code = hashlib.sha256(probe.read_bytes()).hexdigest(); registry = selected_registry(root)
    checks, executions, children = [], [], set()

    def check(label, value):
        checks.append(dict(label=label, passed=bool(value)))
        assert value, label

    def save(path, value):
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')

    def stage(ns=None, storage=None):
        return dict(namespace=namespace() if ns is None else ns, storage=identity() if storage is None else storage)

    def verify(label, value, states):
        nodes = value['graph']['nodes']; by_id = {n['id']: n for n in nodes}
        unbound = copy.deepcopy(value['graph']); revision = unbound.pop('revision')
        check(label + ' independent complete graph identity', revision == digest(unbound))
        check(label + ' actual architecture/process budget and frozen backing',
              value['pointer_bytes'] == str(a.pointer_bytes) and value['frontend_budget_ready']
              and value['retained_after_session_and_renderer'] and value['renderer_exit'] == '0'
              and int(value['callbacks']) > 0)
        check(label + ' no controller storage/namespace/health dispatch',
              value['namespace_api_calls'] == value['storage_api_calls'] == value['health_calls'] == '0')
        check(label + ' exact retired source coverage', [s['state'] for s in value['sources']] == list(states)
              and not any(s['outstanding'] for s in value['sources']))
        workers = {}
        for worker in value['workers']:
            check(label + ' actual owned child code and observation authority', worker['code_sha256'] == code
                  and not worker['claims']['physical_admission'] and not worker['claims']['mutation_authority'])
            pid, created = worker['worker']['pid'], worker['worker']['created']
            if pid is not None:
                check(label + ' observed native process identity', int(pid) > 0 and int(created) > 0)
                children.add((pid, created)); workers[(worker['attempt_id'], pid, created)] = worker
        check(label + ' every row retains complete native frame', [b['node'] for b in value['bindings']] == list(by_id))
        for binding in value['bindings']:
            properties = by_id[binding['node']]['properties']; b = properties['observation_binding']; c = binding['context']
            check(label + ' independent observation identity without media substitution',
                  binding['node'] == 'observation:' + digest(dict(binding=b, kind=by_id[binding['node']]['kind'],
                    label=properties['label'], payload=properties['observation']))[7:]
                  and properties['identity'] is None and properties['media_generation'] is None
                  and properties['capacity_bytes'] is None and properties['aliases'] == [])
            check(label + ' exact frame/context bytes and evidence scope', b['frame_digest'] == digest(value['artifacts'][binding['artifact']])
                  and b['context_digest'] == digest(c) and properties['scope'] == 'observation-only'
                  and not properties['physical_admission'] and not properties['mutation_authority'])
            w = workers[(c['attempt_id'], c['pid'], c['created'])]
            expected = {k: w[k] for k in ('attempt_id', 'observer_epoch', 'worker_epoch', 'request_digest', 'code_sha256')}
            expected.update({k: w['worker'][k] for k in ('pid', 'created')})
            if b['source'] == 'storage' and value['composition'] != 'metadata':
                expected['storage_profile'] = 'identity-layout'
            check(label + ' exact actual worker binding', c == expected)
        for ref in value['resolved']:
            check(label + ' complete advertised native reference', ref['reference']['digest'] == digest(value['artifacts'][ref['artifact']])
                  and by_id[ref['node']]['properties']['observation']['references'][ref['name']] == ref['reference'])
        return nodes

    def gui(name, composition, stages, states):
        request = out / (name + '.request.json'); receipt = out / (name + '.receipt.json')
        save(request, dict(registry=registry, composition=composition, stages=stages))
        observed = []; g = None; start = time.monotonic()
        try:
            g = Gui(probe, ['__disked_nt_inventory_renderer_fixture', 'gui', str(request), str(receipt)], render=True)
            check(name + ' explicit cached native caption', caption(g.window) == 'DiskEd - Cached observation prototype')
            check(name + ' explicit cached native summary', g.text(102).startswith('Current: cached observations | Proposed: none'))
            rows = g.list_ids(); check(name + ' nonempty native controls', bool(rows))
            for i in range(len(rows)):
                g.choose(i); g.click(108); value = g.details()
                check(name + ' native inspector completed and inert', value['status'] == 'completed' and '\x1b' not in g.text(101))
                observed.append(value)
            selected = observed[-1]['result']['node']['id']; g.click(106)
            check(name + ' cached refresh retains original selection', selected in g.text(102))
            g.click(105); commands = g.list_ids(); index = next(i for i, row in enumerate(commands) if row.startswith('health.assess'))
            g.choose(index); g.click(108)
            for page in range(8):
                slot = next((i for i in range(2) if 'target_id' in g.text(220 + i)), None)
                if slot is not None:
                    g.set(200 + slot, selected)
                    break
                g.click(114)
            else:
                raise AssertionError('Health form did not expose target_id')
            g.click(109); g.click(110)
            health = g.details(); check(name + ' actual GUI health refuses observation', health['status'] == 'refused'
                                      and health['diagnostics'][0]['code'] == 'observation_not_storage_target')
            g.click(105); commands = g.list_ids()
            unavailable = next(i for i, row in enumerate(commands) if 'unavailable' in row)
            g.choose(unavailable); g.click(108)
            unavailable_result = g.details()
            check(name + ' actual GUI unavailable command remains inert', unavailable_result['status'] == 'refused'
                  and unavailable_result['diagnostics'][0]['code'] == 'command_unavailable')
            host = g.observation(); capture = g.screenshot(out / (name + '.png')); g.close()
            check(name + ' actual owned desktop teardown and channels', g.code == 0 and not g.output and not g.error and not g.created_files)
            value = json.loads(receipt.read_bytes()); nodes = verify(name, value, states)
            check(name + ' all exact native inspector rows', [x['result']['node'] for x in observed] == nodes)
            save(out / (name + '.host.json'), dict(host=host, capture=capture, inspections=observed, health=health,
                                                  unavailable=unavailable_result))
            executions.append(dict(label=name, frontend='gui', exit_code=g.code, elapsed_seconds=round(time.monotonic() - start, 3)))
        finally:
            if g is not None and g.desktop is not None:
                g.close()

    def console(name, mode, composition, stages, states):
        request = out / (name + '.request.json'); receipt = out / (name + '.receipt.json'); report = out / (name + '.host.json')
        save(request, dict(registry=registry, composition=composition, stages=stages))
        startup = subprocess.STARTUPINFO(); startup.dwFlags = subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
        start = time.monotonic()
        r = subprocess.run([sys.executable, str(root / 'tests/windows/inventory_console_fixture.py'), str(probe), mode,
                            str(request), str(receipt), str(report)], startupinfo=startup,
                           creationflags=subprocess.CREATE_NEW_CONSOLE, timeout=45)
        host = json.loads(report.read_bytes()); executions.append(dict(label=name, frontend=mode, exit_code=r.returncode,
                           elapsed_seconds=round(time.monotonic() - start, 3)))
        check(name + ' actual hidden-console completion', r.returncode == 0 and host['status'] == 'pass')
        value = json.loads(receipt.read_bytes()); nodes = verify(name, value, states)
        check(name + ' actual cached display remains inert', all('\x1b' not in f['text'] for f in host['frames'])
              and any('CACHED OBSERVATIONS' in f['text'] for f in host['frames']))
        check(name + ' native console restoration', all(host['before'][k] == host['after'][k]
              for k in ('modes', 'codepages', 'cursor_style', 'attributes')))
        if mode == 'shell':
            check(name + ' actual shell health refusal', any('observation_not_storage_target' in f['text'] for f in host['frames']))
            check(name + ' actual shell exact observation inspection', host['inspected_id'] in {n['id'] for n in nodes})

    def rejected(name, arguments, code=3, reason=None, existing=None):
        start = time.monotonic(); startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
        before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
        r = subprocess.run([str(probe), *map(str, arguments)], cwd=out, capture_output=True,
                           startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        after = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
        check(name + ' exact exit and no receipt/input mutation', r.returncode == code and before == after and not r.stderr)
        if code == 2:
            check(name + ' invalid argument shape has no output', not r.stdout)
        else:
            diagnostic = json.loads(r.stdout)
            check(name + ' typed refusal precedes readers and controller APIs', diagnostic['status'] == 'refused'
                  and diagnostic['reason'] == reason and diagnostic['reader_starts'] == '0'
                  and diagnostic['namespace_api_calls'] == diagnostic['storage_api_calls'] == '0')
        if existing is not None:
            check(name + ' original receipt bytes retained', existing.read_bytes() == b'original receipt\r\n')
        (out / (name + '.stdout.log')).write_bytes(r.stdout)
        executions.append(dict(label=name, frontend='launcher-rejection', exit_code=r.returncode,
                               elapsed_seconds=round(time.monotonic() - start, 3)))

    def launcher_rejections():
        request = out / 'valid-rejection-input.json'; receipt = out / 'must-not-be-created.json'
        base = dict(registry=registry, composition='identity', stages=[stage()]); save(request, base)
        prefix = '__disked_nt_inventory_renderer_fixture'
        for name, args in (('no-arguments', []), ('wrong-role', ['unknown', 'gui', request, receipt]),
                           ('short-arguments', [prefix, 'gui', request]),
                           ('extra-arguments', [prefix, 'gui', request, receipt, 'extra']),
                           ('unknown-mode', [prefix, 'cli', request, receipt])):
            rejected(name, args, 2)
        bad_paths = [('relative', 'input.json'), ('unc', '\\\\invalid-host\\share\\input.json'),
                     ('namespace', '\\\\?\\C:\\input.json'), ('extra-colon', str(out / 'input.json') + ':stream.json'),
                     ('reserved', str(out / 'CON.json')), ('reserved-spaces', str(out / 'con .json')),
                     ('reserved-superscript', str(out / 'COM\u00b9.json')), ('reserved-component', str(out / 'NUL' / 'input.json')),
                     ('parent-component', str(out) + '\\..\\input.json'),
                     ('trailing-component-space', str(out / 'space ' / 'input.json')),
                     ('wildcard', str(out / 'wild*.json')), ('extension', str(out / 'input.txt'))]
        for name, bad in bad_paths:
            rejected('input-path-' + name, [prefix, 'gui', bad, receipt], reason='fixture_path')
            rejected('receipt-path-' + name, [prefix, 'gui', request, bad], reason='fixture_path')
        for name, patch, reason in (
                ('unknown-composition', {'composition': 'live'}, 'fixture_composition'),
                ('nonstring-composition', {'composition': True}, 'fixture_shape'),
                ('no-stages', {'stages': []}, 'fixture_stages'),
                ('too-many-stages', {'stages': [stage()] * 4}, 'fixture_stages'),
                ('wrong-stages', {'stages': {}}, 'fixture_stages'),
                ('wrong-namespace', {'stages': [dict(namespace=[], storage={})]}, 'fixture_stages'),
                ('missing-storage', {'stages': [dict(namespace={})]}, 'fixture_shape'),
                ('wrong-registry', {'registry': dict(commands={}, syntax={}, schemas={})}, 'fixture_registry')):
            value = copy.deepcopy(base); value.update(patch); invalid = out / (name + '.request.json'); save(invalid, value)
            rejected(name, [prefix, 'gui', invalid, receipt], reason=reason)
        for name, data, reason in (
                ('invalid-json', b'{', 'invalid_json'), ('duplicate-json-key', b'{"a":1,"a":2}', 'duplicate_key'),
                ('json-depth-limit', b'[' * 36 + b'0' + b']' * 36, 'depth_limit_exceeded'),
                ('json-string-limit', json.dumps('x' * 32769).encode(), 'string_limit_exceeded'),
                ('fixture-byte-limit', b' ' * 1048577, 'fixture_input_limit')):
            invalid = out / (name + '.request.json'); invalid.write_bytes(data)
            rejected(name, [prefix, 'gui', invalid, receipt], reason=reason)
        existing = out / 'existing-receipt.json'; existing.write_bytes(b'original receipt\r\n')
        rejected('existing-receipt', [prefix, 'gui', request, existing], reason='fixture_receipt_unavailable', existing=existing)
        rejected('receipt-aliases-input', [prefix, 'gui', request, request], reason='fixture_receipt_unavailable')

    try:
        launcher_rejections()
        good = ('complete', 'complete'); metadata = dict(subjects=[disk(), volume()])
        gui('gui-metadata', 'metadata', [stage(storage=metadata)], good)
        gui('gui-identity-frame', 'identity-frame', [stage()], good)
        gui('gui-identity', 'identity', [stage()], good)
        denied = identity_disk(); denied['replies']['alignment'] = [packet(ok=False, error=5)]
        partial = stage(namespace(names=(OTHER,), terminal_error='5'), identity(denied, volume()))
        gui('gui-partial-stale', 'identity', [stage(), partial], ('partial', 'partial'))
        hostile = namespace(mounts=[[reply(('C:\\label\x1b[2J\ud800\u202e\\',))]])
        gui('gui-inert-names', 'identity', [stage(hostile)], good)
        for composition, storage in (('metadata', metadata), ('identity-frame', identity()), ('identity', identity())):
            for mode in ('tui', 'shell'):
                console(mode + '-' + composition, mode, composition, [stage(storage=storage)], good)
        for mode in ('tui', 'shell'):
            console(mode + '-partial-stale', mode, 'identity', [stage(), partial], ('partial', 'partial'))
            console(mode + '-inert-names', mode, 'identity', [stage(hostile)], good)
        result = dict(status='pass', pointer_bytes=a.pointer_bytes, controller_executions=len(executions),
                      actual_child_launches=len(children), assertions=len(checks), executions=executions, checks=checks,
                      probe_sha256='sha256:' + code)
    except Exception:
        save(out / 'results.json', dict(status='fail', pointer_bytes=a.pointer_bytes, controller_executions=len(executions),
             actual_child_launches=len(children), assertions=len(checks), executions=executions, checks=checks))
        raise
    save(out / 'results.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'controller_executions', 'actual_child_launches', 'assertions')}))


if __name__ == '__main__':
    main()
