"""Independent expectations for native containment and immutable publication."""
import hashlib
import json
from native_volume_observations import original


def require(value,reason):
    if not value:raise ValueError(reason)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def uint(value):
    require(type(value) is str and value.isascii() and value.isdecimal() and len(value)<=20,'integer')
    number=int(value);require(number<=18446744073709551615,'integer_bound');return number


def frame(value,epoch,volume,mount,*,include_mounts=True,limited=False,cancelled=False):
    require(value['api_binding']=='native-win32-table' and uint(value['capture_epoch'])==epoch,'frame_binding')
    claims=value['claims']
    require(claims['physical_identity']=='unknown' and claims['full_topology']=='not_observed' and claims['media_preservation']=='not_established','frame_scope')
    require(all(claims[k] is False for k in ('physical_admission','mutation_authority','complete_alias_proof')),'frame_authority')
    rows=value['records'];require(len(rows)<=64,'row_bound')
    if cancelled:
        require(value['status']=='cancelled' and not rows and value['enumeration']['state']=='cancelled' and value['close']['state']=='not_open','cancel_before_dispatch');return
    require(value['close']['state']=='closed','search_close')
    if limited:
        require(value['status']=='partial' and len(rows)==1 and value['enumeration']['state']=='budget_exhausted' and value['enumeration']['exhausted'] is False,'unknown_remainder');return
    require(value['enumeration']['state']=='exhausted' and value['enumeration']['exhausted'] is True,'exhaustion')
    require(value['status'] in ('complete','partial'),'namespace_outcome')
    selected=[row for row in rows if original(row['volume_path']).lower()==volume.lower()]
    require(len(selected)==1,'known_original_volume')
    if include_mounts:
        require(selected[0]['mounts']['state']=='observed' and mount.lower() in [original(p).lower() for p in selected[0]['mounts']['paths']],'known_original_mount')
    else:require(all(r['mounts']['state']=='not_selected' and not r['mounts']['paths'] for r in rows),'no_mount_dispatch')


def observation(value,code_sha,*,native=True,completed=True):
    schema='org.disked.nt-native-namespace-worker-observation/1' if native else 'org.disked.nt-namespace-worker-observation/1'
    require(value['schema']==schema and value['code_sha256']==code_sha,'code_or_schema')
    require(uint(value['worker']['pid'])>0 and uint(value['worker']['created'])>0 and value['worker']['observation']=='exited','actual_exit')
    require(len(value['request_digest'])==64 and len(value['worker_epoch'])>7 and len(value['observer_epoch'])>9,'epochs')
    if completed:
        require(value['status']=='completed' and value['worker']['exit_code']=='0' and value['admitted'] is True and value['claims']['live_namespace'] is True,'completed')
    else:require(value['status']=='unknown' and value['worker']['exit_code']=='3' and value['admitted'] is False and value['result'] is None,'refused_before_admission')
    require(all(value['claims'][k] is False for k in ('physical_admission','mutation_authority','durable_reconnect')),'worker_authority')


def graph(value,*,stale=False):
    body=dict(value);revision=body.pop('revision');require(revision=='sha256:'+hashlib.sha256(canonical(body)).hexdigest(),'graph_digest')
    rows=value['nodes'];require(rows and len({n['id'] for n in rows})==len(rows),'graph_nodes')
    seen=False
    for row in rows:
        p=row['properties'];require(p['physical_identity']=='unknown' and p['physical_admission'] is False and p['mutation_authority'] is False,'graph_authority')
        require(p['identity'] is None and p['media_generation'] is None and p['capacity_bytes'] is None,'graph_identity')
        require(p['state'] in ('unknown','stale'),'graph_state');seen=seen or p['state']=='stale'
        expected=hashlib.sha256(canonical(dict(binding=p['observation_binding'],kind=row['kind'],label=p['label'],payload=p['observation']))).hexdigest()
        require(row['id']=='observation:'+expected,'observation_id')
        require(p['label']==p['observation']['name']['display'] and all(32<=ord(c)<=126 for c in p['label']),'inert_display')
    require(seen==stale,'stale_background')


def validate(value,case,pointer_bytes,code_sha,volume,mount):
    require(value['schema']=='org.disked.native-namespace-test/1' and value['case']==case and value['pointer_bytes']==str(pointer_bytes),'case_identity')
    result=value['result']
    if case=='worker.invalid':
        require(result['invalid_epoch_refused'] is True and result['invalid_count_refused'] is True,'policy');return
    if case.startswith('worker.'):
        prepared=result['prepared'];require(prepared['worker']['observation']=='not_started' and prepared['result'] is None and prepared['claims']['live_namespace'] is True,'inert_prepare')
        if case=='worker.prepare_only':
            require(result['retirement']['retired'] is True and result['retirement']['worker']['observation']=='not_started','unlaunched_retirement');return
        final=result['final'];observation(final,code_sha)
        frame(final['result'],9,volume,mount,include_mounts=case!='worker.no_mounts',limited=case=='worker.limit',cancelled=case=='worker.cancel_before')
        require(result['entered_after'] is (case!='worker.cancel_before'),'dispatch_checkpoint')
        if case=='worker.gate_wait':
            before=result['gated'];require(before['attempt_id']==final['attempt_id'] and before['worker']==dict(final['worker'],observation='running',exit_code='259') and before['result'] is None and result['entered_before_release'] is False,'same_gated_attempt')
        return
    if case.startswith('native.child_') or case=='fixture.native_table_guard':
        observation(result['observation'],code_sha,native=case!='fixture.native_table_guard',completed=False)
        if case.startswith('native.child_'):require(result['dispatch_entered'] is False,'malformed_dispatched')
        return
    if case=='validation.cross_binding':
        observation(result['observation'],code_sha);require(result['cross_binding_refusals']=='6','cross_binding');frame(result['observation']['result'],9,volume,mount);return
    if case=='inventory.publication':
        observation(result['observation'],code_sha);frame(result['frame'],1,volume,mount);graph(result['graph']);require(result['owner_retained_after_session'] is True,'owner_retention');return
    require(case in ('graph.complete','graph.refresh','graph.partial'),'unknown_case')
    observation(result['first'],code_sha);frame(result['first']['result'],1,volume,mount);graph(result['graph'])
    if case!='graph.complete':
        observation(result['second'],code_sha);frame(result['second']['result'],2,volume,mount,limited=case=='graph.partial')
        graph(result['new_graph'],stale=case=='graph.partial');require(result['old_unchanged'] is True,'old_owner')
        frame(result['last_complete'],1 if case=='graph.partial' else 2,volume,mount)
