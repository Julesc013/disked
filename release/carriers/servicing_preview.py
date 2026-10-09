"""Finite read-only servicing review over explicit synthetic ownership views.

No installed-state discovery, executor, registration, policy application or
deletion. Eligible is a review constraint, not software/storage authority.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('carrier_fixture', ROOT/'release/carriers/fixture.py')
carrier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carrier)
pf, ac = carrier.pf, carrier.ac
PROFILE = ROOT/'spec/catalog/servicing-preview-prototype.json'
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z')


def shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        pf.refuse('servicing_shape')


def token(value):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        pf.refuse('servicing_identity')


def epoch(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', value) or int(value) > 18446744073709551615:
        pf.refuse('servicing_epoch')


def digest(value):
    if not isinstance(value, str) or not pf.SHA.fullmatch(value):
        pf.refuse('servicing_digest')


def array(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        pf.refuse('servicing_array_budget')


def reference(value):
    shape(value, ('id', 'generation', 'sha256'))
    token(value['id']); token(value['generation']); digest(value['sha256'])
    return value['id'], value['generation'], value['sha256']


def preview(view, request):
    contract = pf.read_json(PROFILE)
    limits = carrier.profile()['limits']
    shape(view, ('schema', 'ownership_epoch', 'capture_epoch', 'capture_complete', 'selections', 'exclusions',
                 'policy_digest', 'resources', 'operations'))
    shape(request, ('schema', 'ownership_epoch', 'capture_epoch', 'actor', 'action', 'resources'))
    if view['schema'] != contract['view_schema'] or request['schema'] != contract['request_schema']:
        pf.refuse('servicing_schema')
    for key in ('ownership_epoch', 'capture_epoch'):
        epoch(view[key]); epoch(request[key])
    if type(view['capture_complete']) is not bool:
        pf.refuse('servicing_capture_shape')
    digest(view['policy_digest'])
    for key in ('selections', 'exclusions'):
        array(view[key], 64)
        for value in view[key]: token(value)
        if len(set(view[key])) != len(view[key]):
            pf.refuse('servicing_selection_duplicate')
    if set(view['selections']) & set(view['exclusions']):
        pf.refuse('servicing_selection_conflict')
    array(view['resources'], limits['resources'])
    array(view['operations'], limits['operations'])
    array(request['resources'], limits['request_resources'])
    if not request['resources'] or request['action'] not in contract['actions'] or request['actor'] not in contract['owners']:
        pf.refuse('servicing_request')
    resources = {}
    paths = []
    for row in view['resources']:
        shape(row, ('id', 'generation', 'sha256', 'path', 'role', 'owner'))
        key = reference({name:row[name] for name in ('id','generation','sha256')})
        if (key[0], key[1]) in resources or row['role'] not in contract['resource_roles'] or row['owner'] not in contract['owners']:
            pf.refuse('servicing_resource')
        ac.safe_path(row['path'])
        name = row['path'].casefold()
        if any(name == old or name.startswith(old+'/') or old.startswith(name+'/') for old in paths):
            pf.refuse('servicing_resource_overlap')
        paths.append(name)
        resources[(key[0],key[1])] = row
    affected = []
    for row in request['resources']:
        key = reference(row)
        known = resources.get(key[:2])
        if known is None or known['sha256'] != key[2] or key in affected:
            pf.refuse('servicing_resource_reference')
        affected.append(key)
    operation_ids = set()
    deps = 0
    deferred = set()
    reasons = set()
    for operation in view['operations']:
        shape(operation, ('operation_id', 'attempt_id', 'worker_epoch', 'capture_epoch', 'logical', 'worker', 'effect',
                          'cancellation', 'release', 'recovery_required', 'dependencies'))
        token(operation['operation_id']); token(operation['attempt_id'])
        epoch(operation['worker_epoch']); epoch(operation['capture_epoch'])
        if operation['operation_id'] in operation_ids or type(operation['recovery_required']) is not bool:
            pf.refuse('servicing_operation')
        operation_ids.add(operation['operation_id'])
        for key, choices in [('logical','logical_states'),('worker','worker_states'),('effect','effect_states'),
                             ('cancellation','cancellation_states'),('release','release_states')]:
            if operation[key] not in contract[choices]:
                pf.refuse('servicing_operation_state')
        array(operation['dependencies'], limits['dependency_entries'])
        if not operation['dependencies'] or not any(row.get('purpose') == 'execution' for row in operation['dependencies'] if isinstance(row, dict)):
            pf.refuse('servicing_execution_closure_required')
        entries = set()
        for row in operation['dependencies']:
            shape(row, ('id', 'generation', 'sha256', 'purpose'))
            key = reference({name:row[name] for name in ('id','generation','sha256')})
            known = resources.get(key[:2])
            if known is None or known['sha256'] != key[2] or row['purpose'] not in ('execution','recovery') or (key,row['purpose']) in entries:
                pf.refuse('servicing_dependency_reference')
            entries.add((key,row['purpose']))
        deps += len(entries)
        if deps > limits['dependency_entries']:
            pf.refuse('servicing_dependency_budget')
        if operation['capture_epoch'] != view['capture_epoch'] or operation['worker'] == 'unreachable':
            reasons.add('dependency_scope_unknown'); deferred.update(affected)
        blocked = (operation['logical'] != 'completed' or operation['worker'] != 'exited' or
                   operation['effect'] != 'certain' or operation['release'] != 'released' or operation['recovery_required'])
        if blocked:
            for key, _ in entries:
                if key in affected:
                    deferred.add(key); reasons.add('generation_required_by_operation')
    if not view['capture_complete']:
        deferred.update(affected); reasons.add('capture_incomplete')
    failures = set()
    for key in affected:
        row = resources[key[:2]]
        if row['role'] not in ('payload','provider','integration'):
            failures.add('external_data_preserved')
        if request['action'] == 'withdraw' and row['role'] != 'provider':
            failures.add('withdraw_requires_provider')
        if row['owner'] in ('unmanaged','external'):
            failures.add('explicit_enrollment_or_transfer_required')
        elif row['owner'] != request['actor']:
            failures.add('servicing_owner_conflict')
    if request['actor'] in ('unmanaged','external'):
        failures.add('recognized_servicing_owner_required')
    if any(view[key] != request[key] for key in ('ownership_epoch','capture_epoch')):
        failures.add('servicing_view_stale')
    status = 'refused' if failures else 'deferred' if deferred else 'eligible'
    def rows(keys):
        return [dict(id=key[0], generation=key[1], sha256=key[2]) for key in sorted(keys)]
    return dict(schema=contract['outcome_schema'], status=status, fixture_only=True, authorizes_lifecycle=False, authorizes_storage=False,
                requires_atomic_recheck=True, action=request['action'], actor=request['actor'],
                reasons=sorted(failures|reasons), retained_generations=rows(affected if failures else deferred),
                retirement_candidates=rows([] if failures or request['action']=='withdraw' else set(affected)-deferred),
                proposed_admission='deny_new_work' if request['action']=='withdraw' and not failures else 'unchanged',
                preserved_selections=view['selections'], preserved_exclusions=view['exclusions'], preserved_policy_digest=view['policy_digest'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = preview(pf.read_json(args.view), pf.read_json(args.request))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ac.Rejected, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(status='refused', reason=str(error), authorizes_lifecycle=False)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
