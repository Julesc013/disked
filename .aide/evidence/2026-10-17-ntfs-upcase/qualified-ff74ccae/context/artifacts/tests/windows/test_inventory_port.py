"""Mixed owned native inventory publications and cached frontend ownership."""
import argparse, copy, hashlib, json, struct, subprocess, time
from pathlib import Path
from test_identity_frame import fixture as identity, identity_disk
from test_identity_queries import identifiers, entry, layout
from test_storage_queries import disk, volume, packet, digest
from test_volume_namespace import fixture as namespace, reply, VOLUME, OTHER
from test_observation_frontend import selected_registry


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pointer-bytes', type=int, choices=(4, 8), required=True)
    a = p.parse_args()
    out = a.output.absolute(); out.mkdir()
    probe = a.probe.absolute(); code = hashlib.sha256(probe.read_bytes()).hexdigest()
    registry = selected_registry(Path(__file__).resolve().parents[2])
    checks, runs, children = [], [], set()

    def check(label, ok):
        checks.append(dict(label=label, passed=bool(ok)))
        assert ok, label

    def stage(ns=None, storage=None, **kw):
        return dict(namespace=namespace() if ns is None else ns,
                    storage=identity() if storage is None else storage, **kw)

    def run(name, stages, *, composition='identity', states=None):
        request = json.dumps(dict(mode='inventory-port', registry=registry, composition=composition,
                                  stages=stages), separators=(',', ':'), ensure_ascii=True).encode()
        (out / (name + '.request.json')).write_bytes(request)
        start = time.monotonic()
        r = subprocess.run([probe], input=request, capture_output=True, timeout=90)
        (out / (name + '.stdout')).write_bytes(r.stdout)
        (out / (name + '.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name, exit_code=r.returncode, expected_exit=0,
                         elapsed_seconds=round(time.monotonic() - start, 3)))
        check(name + ' actual native exit', r.returncode == 0 and not r.stderr)
        v = json.loads(r.stdout)
        check(name + ' architecture/job and zero controller native API',
              v['pointer_bytes'] == str(a.pointer_bytes) and v['frontend_budget_ready']
              and v['namespace_api_calls'] == v['storage_api_calls'] == v['health_calls'] == '0')
        check(name + ' actual cached callbacks and lifetime after source teardown',
              int(v['callbacks']) > 0 and v['retained_after_session_destruction'])
        check(name + ' owned/null/by-value construction contract',
              v['null_owner_refused'] and v['value_construction_unowned'])
        previous_workers = {}
        for i, row in enumerate(v['stages']):
            label = name + ':' + str(i)
            nodes = row['graph']['nodes']; by_id = {n['id']: n for n in nodes}
            check(label + ' both sources pending and actually retained',
                  [s['id'] for s in row['pending']['sources']] == ['namespace', 'storage']
                  and all(s['outstanding'] for s in row['pending']['sources']))
            check(label + ' cached pending/published delivery does not advance readers',
                  row['pending_cached_pure'] and row['getter_no_allocation'] and row['delivered_owner']
                  and row['retrieval_and_presentation_pure'] and row['domains_retained'])
            check(label + ' held snapshots own exact native data without history chain',
                  row['held_snapshot_retains_publication'] and row['old_publication_released'])
            check(label + ' missing native data is refused',
                  row['missing_node_refused'] and row['missing_reference_refused'])
            check(label + ' actual retirement and no replacement',
                  row['replacement_refused'] and not any(s['outstanding'] for s in row['retired']['sources']))
            if states:
                check(label + ' exact independent source coverage',
                      [s['state'] for s in row['state']['sources']] == list(states[i]))
            workers = dict(previous_workers)
            for worker in row['workers']:
                check(label + ' native child executable identity and bounded authority',
                      worker['code_sha256'] == code and not worker['claims']['physical_admission']
                      and not worker['claims']['mutation_authority'])
                pid, created = worker['worker']['pid'], worker['worker']['created']
                if pid is not None:
                    check(label + ' observed process handle identity', int(pid) > 0 and int(created) > 0)
                    children.add((pid, created))
                    key = (worker['attempt_id'], worker['worker']['pid'], worker['worker']['created'])
                    workers[key] = worker
            check(label + ' every displayed row binds complete native frame',
                  [x['node'] for x in row['bindings']] == list(by_id))
            for binding in row['bindings']:
                node = by_id[binding['node']]; properties = node['properties']
                b = properties['observation_binding']; context = binding['context']
                frame = row['artifacts'][binding['artifact']]
                check(label + ' exact retained frame/context digests',
                      b['frame_digest'] == digest(frame) and binding['artifact'] == 'frame:' + digest(frame)
                      and b['context_digest'] == digest(context) and properties['scope'] == 'observation-only')
                w = workers[(context['attempt_id'], context['pid'], context['created'])]
                expected = {k: w[k] for k in ('attempt_id', 'observer_epoch', 'worker_epoch', 'request_digest', 'code_sha256')}
                expected.update({k: w['worker'][k] for k in ('pid', 'created')})
                if b['source'] == 'storage' and composition != 'metadata':
                    expected['storage_profile'] = 'identity-layout'
                check(label + ' exact actual worker context', context == expected and context['code_sha256'] == code)
                check(label + ' native frame epoch/source schema',
                      frame['schema'] == ('org.disked.nt-volume-namespace-prototype/1' if b['source'] == 'namespace'
                                          else 'org.disked.nt-storage-observation-prototype/' + ('1' if composition == 'metadata' else '2')))
                if properties['state'] != 'stale':
                    source = next(s for s in row['state']['sources'] if s['id'] == b['source'])
                    check(label + ' current exact capture/worker',
                          b['capture_epoch'] == row['state']['capture'] == source['attempt_capture']
                          and b['worker_epoch'] == source['worker'])
            previous_workers = workers
            identity_nodes = [n for n in nodes if n['kind'] == 'storage-identity-observation']
            check(label + ' explicit projection only', bool(identity_nodes) == (composition == 'identity' and any(
                n['properties']['observation_binding']['source'] == 'storage' for n in nodes)))
            check(label + ' every advertised reference resolved completely', len(row['resolved']) == sum(
                len(n['properties']['observation']['references']) for n in identity_nodes))
            for resolved in row['resolved']:
                ref = resolved['reference']; content = row['artifacts'][resolved['artifact']]
                check(label + ' exact full native reference bytes', ref['digest'] == digest(content)
                      and resolved['artifact'] == ref['kind'] + ':' + ref['digest']
                      and by_id[resolved['node']]['properties']['observation']['references'][resolved['name']] == ref)
            for source in ('namespace', 'storage'):
                owned = [n for n in nodes if n['properties']['observation_binding']['source'] == source]
                inspections = row[source + '_inspections']
                check(label + ' every ' + source + ' row inspected through actual cached port',
                      [x['id'] for x in inspections] == [n['id'] for n in owned])
                for inspection, node in zip(inspections, owned):
                    basis = inspection['direct']['result']
                    check(label + ' exact common model/render semantics', basis['node'] == node
                          and all(inspection[k] == digest(basis) for k in ('gui', 'tui', 'shell', 'cli_human', 'gui_display', 'tui_display'))
                          and inspection['cli_background'] == digest(inspection['direct'])
                          and inspection['health_refused'] and inspection['capability_unqualified'])
                focus = row.get(source + '_focus')
                if focus:
                    old = by_id.get(focus['old_id'])
                    check(label + ' exact original focus and stale revision refusal',
                          focus['selection']['observation_id'] == focus['old_id']
                          and focus['selection']['target_id'] is None and focus['present'] == bool(old)
                          and focus['stale']['diagnostics'][0]['code'] == 'revision_conflict')
                    check(label + ' old row never rebound by name', focus['inspection']['result']['node'] == old if old
                          else focus['inspection']['diagnostics'][0]['code'] == 'target_not_found')
            for fault in ('provider', 'frontend'):
                expected = fault + '_allocation' in stages[i]
                check(label + ' selected actual ' + fault + ' allocation result', row[fault + '_allocation_failed'] == expected)
                if expected:
                    check(label + ' failed ' + fault + ' publication retains original and retry', row[fault + '_failure_preserved'])
        check(name + ' exact selected provider allocation count', int(v['allocation_checkpoint_hits']) == sum(
            'provider_allocation' in s for s in stages))
        return v

    try:
        good = ('complete', 'complete')
        run('metadata-default', [stage(storage=dict(subjects=[disk(), volume()]))], composition='metadata', states=[good])
        run('identity-frame-default', [stage()], composition='identity-frame', states=[good])
        run('identity-explicit', [stage()], states=[good])
        run('repeated-complete', [stage(), stage(), stage(), stage()], states=[good] * 4)
        partial_disk = identity_disk(); partial_disk['replies']['alignment'] = [packet(ok=False, error=5)]
        partial = stage(namespace(names=(OTHER,), terminal_error='5'), identity(partial_disk, volume()))
        run('repeated-partial', [stage(), partial, copy.deepcopy(partial)], states=[good, ('partial', 'partial'), ('partial', 'partial')])
        run('recovered', [stage(), partial, stage()], states=[good, ('partial', 'partial'), good])
        run('denied-namespace', [stage(), stage(namespace(names=(), terminal_error='5'))], states=[good, ('denied', 'complete')])
        run('empty-namespace', [stage(), stage(namespace(names=()))], states=[good, good])
        run('partial-first', [partial], states=[('partial', 'partial')])
        run('allocation-provider', [stage(), stage(provider_allocation=True)], states=[good, good])
        run('allocation-frontend', [stage(), stage(frontend_allocation=True)], states=[good, good])
        run('allocation-both', [stage(), stage(provider_allocation=True, frontend_allocation=True)], states=[good, good])
        run('held-readers', [stage(namespace(reply_fault='hold'), identity(reply_fault='hold'))], states=[good])
        run('late-current', [stage(), stage(namespace(worker_fault='delay'), identity(worker_fault='delay'), namespace_action='timeout', storage_action='timeout')], states=[good, good])
        run('superseded', [stage(), stage(namespace(worker_fault='delay'), identity(worker_fault='delay'), namespace_action='superseded')], states=[good, ('not_started', 'not_started')])
        run('cancel-before', [stage(), stage(namespace_action='cancel-before', storage_action='cancel-before')], states=[good, ('partial', 'partial')])
        run('cancel-during', [stage(), stage(namespace(worker_fault='delay'), identity(worker_fault='delay'), namespace_action='cancel-during', storage_action='cancel-during')], states=[good, ('partial', 'partial')])
        run('crashed', [stage(), stage(namespace(worker_fault='crash'), identity(worker_fault='crash'))], states=[good, ('unavailable', 'unavailable')])
        run('forced-retirement', [stage(), stage(namespace(worker_fault='hang'), identity(worker_fault='hang'), namespace_action='retire', storage_action='retire')], states=[good, ('unavailable', 'unavailable')])
        lossless = namespace(mounts=[[reply(('C:\\label\x1b[2J\ud800\u202e\\',))]])
        duplicate = identity_disk(ids=identifiers([(1, 3, 0, b'ID'), (1, 3, 0, b'ID')]))
        run('lossless-ambiguous', [stage(lossless, identity(duplicate, volume()))], states=[('complete', 'partial')])
        changed = identity(identity_disk(serial=b'NEW'), volume())
        v = run('explicit-comparison', [stage(), stage(storage=changed, comparisons=[dict(previous_subject='disk', current_subject='disk')])], states=[good, good])
        comparison = next(x for x in v['stages'][1]['artifacts'].values() if x.get('schema') == 'org.disked.nt-identity-comparison-prototype/1')
        check('explicit comparison retained actual changed facts', comparison['relation'] == 'changed-reported-evidence')
        subjects = []
        for i in range(16):
            key = 'disk' if i == 0 else 'peer' + str(i)
            table = bytearray(layout(entries=[entry(number=j + 1, start=4096 + j * 512, length=512,
                guid=(key + '.' + str(j)).encode().ljust(16, b'\0')) for j in range(4)]))
            table[8:24] = key.encode().ljust(16, b'\0')
            struct.pack_into('<q', table, 32, 1048576 - 4096)
            subjects.append(identity_disk(key, i, table=bytes(table), serial=key.encode()))
        names = tuple('\\\\?\\Volume{' + format(i, '08x') + '-1234-abcd-abcd-123456789abc}\\' for i in range(31))
        mounts = [[reply(('C:\\' + str(i) + '\\a\\', 'C:\\' + str(i) + '\\b\\'))] for i in range(31)]
        maximum_ns = namespace(names=names, mounts=mounts)
        maximum_storage = identity(*subjects)
        declarations = [dict(previous_subject=s['key'], current_subject=s['key']) for s in subjects]
        run('mixed-max-and-comparisons', [stage(maximum_ns, maximum_storage),
            stage(maximum_ns, maximum_storage, comparisons=declarations)], states=[good, good])
        denied_storage = copy.deepcopy(maximum_storage)
        denied_storage['subjects'][0]['replies']['alignment'] = [packet(ok=False, error=5)]
        partial_ns = dict(maximum_ns, terminal_error='5')
        v = run('aggregate-stale-refusal', [stage(maximum_ns, maximum_storage), stage(partial_ns, denied_storage)],
                composition='identity-frame', states=[good, ('partial', 'malformed')])
        first, second = v['stages']
        original_storage = {n['id'] for n in first['graph']['nodes'] if n['properties']['observation_binding']['source'] == 'storage'}
        retained_storage = [n for n in second['graph']['nodes'] if n['properties']['observation_binding']['source'] == 'storage']
        check('aggregate refusal retains exact prior storage rows without truncation',
              original_storage == {n['id'] for n in retained_storage}
              and all(n['properties']['state'] == 'stale' for n in retained_storage)
              and len(second['graph']['nodes']) <= 320)
        result = dict(status='pass', pointer_bytes=a.pointer_bytes, controller_executions=len(runs), actual_child_launches=len(children),
                      assertions=len(checks), executions=runs, checks=checks, probe_sha256='sha256:' + code)
    except Exception:
        result = dict(status='fail', pointer_bytes=a.pointer_bytes, controller_executions=len(runs), actual_child_launches=len(children),
                      assertions=len(checks), executions=runs, checks=checks)
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
        raise
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'controller_executions', 'actual_child_launches', 'assertions')}))


if __name__ == '__main__':
    main()
