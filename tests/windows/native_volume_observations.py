"""Independent expectations for the selected real guest namespace observations."""
MODES=('--binding','--observe','--no-mounts','--limit-one','--cancelled','--invalid-policy')


def require(value,reason):
    if not value:raise ValueError(reason)


def original(value):
    require(value['original_encoding']=='utf16le-code-units','name_encoding')
    raw=bytes.fromhex(value['original_hex'])
    require(len(raw)%2==0 and len(raw)<=512,'name_length')
    return raw.decode('utf-16-le',errors='surrogatepass')


def validate(value,mode,sid,pid,volume,mount):
    require(mode in MODES and value['mode']==mode,'mode')
    identity=value['identity']
    require(identity['sid']==sid and identity['pid']==str(pid) and identity['restricted'] is True and
            identity['elevated'] is False and identity['appcontainer'] is False and identity['in_job'] is True,'actor')
    require(value['native_table_bound'] is True,'native_binding')
    if mode=='--binding':
        require(value['dispatch_requested'] is False and value['close']=='not_open' and 'snapshot' not in value,'binding_dispatch')
        return dict(dispatch=False)
    if mode=='--invalid-policy':
        require(value['status']=='refused' and value['reason']=='nt_volume_policy' and value['close']=='not_open' and 'snapshot' not in value,'policy_refusal')
        return dict(policy_refused=True)
    snap=value['snapshot'];require(snap['api_binding']=='native-win32-table' and snap['capture_epoch']=='7','snapshot_binding')
    require(snap['scope']=='volume-namespace-only' and value['reuse_refused'] is True,'namespace_scope')
    claims=snap['claims']
    require(claims==dict(physical_identity='unknown',full_topology='not_observed',media_preservation='not_established',
            physical_admission=False,mutation_authority=False,complete_alias_proof=False),'claims')
    rows=snap['records'];require(len(rows)<=64,'volume_budget')
    if mode=='--cancelled':
        require(snap['status']=='cancelled' and snap['enumeration']['state']=='cancelled' and not rows and
                snap['close']['state']==value['repeat_close']=='not_open','cancel_before_dispatch')
        return dict(cancelled_before_dispatch=True)
    require(snap['close']['state']==value['repeat_close']=='closed','close')
    if mode=='--limit-one':
        require(len(rows)==1 and snap['status']=='partial' and snap['enumeration']['state']=='budget_exhausted' and
                snap['enumeration']['exhausted'] is False,'partial_budget')
        return dict(budget_exhausted=True,unknown_remainder=True)
    require(snap['enumeration']['state']=='exhausted' and snap['enumeration']['exhausted'] is True,'enumeration_exhaustion')
    selected=[row for row in rows if original(row['volume_path']).lower()==volume.lower()]
    require(len(selected)==1,'known_volume')
    target=selected[0];require(target['state']=='present','target_state')
    if mode=='--no-mounts':
        require(all(row['mounts']['state']=='not_selected' and not row['mounts']['paths'] for row in rows),'mounts_not_selected')
    else:
        require(target['mounts']['state']=='observed' and mount.lower() in
                [original(v).lower() for v in target['mounts']['paths']],'known_mount')
    return dict(known_volume_observed=True,known_mount_observed=mode=='--observe',
                namespace_complete=snap['status']=='complete',records=len(rows),status=snap['status'])
