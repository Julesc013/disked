"""Retain candidate-relative comparisons without selecting a winner."""
import argparse
import json
from pathlib import Path
import re


def evidence_set(manifest, native, external):
    """Check a predeclared set, never infer expected participants from results.

    This initial DE-W106 slice does not verify executable/raw artifact bytes.
    A complete set therefore remains unqualified evidence.
    """
    errors=[];missing=[];seen=set();expected=set();cases={}
    declarations=manifest.get('expected_observations')
    if declarations is None:return dict(status='undeclared',errors=['expected_set_not_declared'],missing=[])
    if not isinstance(declarations,list) or not 0<len(declarations)<=32768:
        return dict(status='invalid',errors=['expected_set_empty_or_unbounded'],missing=[])
    values=manifest.get('cases')
    if not isinstance(values,list) or not 0<len(values)<=4096:
        return dict(status='invalid',errors=['case_set_empty_or_unbounded'],missing=[])
    for case in values:
        if not isinstance(case,dict) or not isinstance(case.get('name'),str) or not case['name']:
            errors.append('case_identity');continue
        name=case['name']
        if name in cases:errors.append('duplicate_case:'+name)
        cases[name]=case
        if (not isinstance(case.get('sha256'),str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',case['sha256']) or
                type(case.get('bytes')) is not int or not 0<=case['bytes']<=2097152 or
                type(case.get('unit')) is not int or case['unit']!=512 or
                type(case.get('blocks')) is not int or not 2<=case['blocks']<=2**64-1 or
                case['bytes']>case['unit']*case['blocks']):errors.append('case_fixture:'+name)
    def key(row):
        if (not isinstance(row,dict) or set(row)!={'name','participant','kind'} or
                not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',v) for v in row.values())):
            return None
        return row['name'],row['participant'],row['kind']
    for row in declarations:
        item=key(row)
        if item is None:errors.append('expected_tuple_shape');continue
        if item in expected:errors.append('duplicate_expected:'+repr(item))
        if item[0] not in cases:errors.append('unknown_expected_case:'+item[0])
        expected.add(item)
    for name in cases:
        if (name,'native','native') not in expected:errors.append('native_not_expected:'+name)
        if not any(k[0]==name and k[1]!='native' for k in expected):errors.append('reference_not_expected:'+name)
    if not isinstance(external,dict):return dict(status='invalid',errors=errors+['reference_receipt_shape'],missing=[])
    receipts=[('native',native),*external.items()]
    if 'native' in external:errors.append('reference_uses_native_identity')
    declared_participants={item[1] for item in expected}
    for participant,receipt in receipts:
        if participant not in declared_participants:errors.append('unexpected_participant:'+str(participant))
        rows=receipt.get('observations') if isinstance(receipt,dict) else None
        if not isinstance(rows,list) or len(rows)>32768:
            errors.append('observation_list:'+str(participant));continue
        for row in rows:
            item=key(dict(name=row.get('name'),participant=participant,kind=row.get('kind'))) if isinstance(row,dict) else None
            if item is None:errors.append('observation_identity');continue
            if item in seen:errors.append('duplicate_observation:'+repr(item))
            seen.add(item)
            if item not in expected:errors.append('unexpected_observation:'+repr(item))
            case=cases.get(item[0])
            if case is None:errors.append('unknown_case:'+item[0]);continue
            for field in ('sha256','bytes','unit','blocks'):
                if type(row.get(field)) is not type(case.get(field)) or row.get(field)!=case.get(field):
                    errors.append('fixture_'+field+':'+repr(item))
    missing=sorted(expected-seen)
    return dict(status='invalid' if errors else 'incomplete' if missing else 'complete',
                errors=errors,missing=[dict(name=n,participant=p,kind=k) for n,p,k in missing],
                expected_count=len(expected),observed_unique_count=len(seen))


def compare(manifest, native, external):
    inventory=evidence_set(manifest,native,external)
    result=dict(adapter_controls_passed=False,set_status=inventory['status'],set_validation=inventory,
                evidence_status='unverified',complete_success=False,
                pending_validation=['participant identities','raw artifact hashes','input preservation receipts','execution outcomes'],
                control_failures=[],comparisons=[],diagnostic_observations=[],uncompared_records=[],
                scope='All discrepancies retained; matching an external selection never resolves a DiskEd candidate conflict')
    if inventory['status']=='invalid':
        # Preserve every contradictory input; do not select one duplicate.
        result['unvalidated_inputs']=dict(manifest=manifest,native=native,external=external)
        return result
    cases = {case['name']: case for case in manifest['cases']}
    observations={}
    for item in native['observations']:observations.setdefault(item['name'],[]).append(item)
    records = []; failures = []
    for source, evidence in external.items():
        for item in evidence['observations']:
            if item['kind'] == 'sfdisk-verify':
                result['diagnostic_observations'].append(dict(participant=source,observation=item));continue
            choices=observations.get(item['name'],[])
            if item['name'] not in cases or len(choices)!=1:
                result['uncompared_records'].append(dict(participant=source,observation=item));continue
            expected = choices[0]['projection']; actual = item['projection']
            matches = []
            if actual is not None and actual['label'] == expected['label']:
                for candidate in expected['candidates']:
                    if 'disk_uuid' in actual and candidate.get('disk_uuid') != actual['disk_uuid']: continue
                    def select(rows):
                        return [{k: row[k] for k in actual['fields'] if k in row} for row in rows]
                    if select(candidate['rows']) == select(actual['rows']): matches.append(candidate['role'])
            record = dict(name=item['name'], source=source, tool=item['kind'], sha256=item['sha256'],
                          matching_candidates=matches, external=actual,
                          native=expected, outcome=item['outcome'], exit_code=item['exit_code'],
                          discrepancy='no_projection' if actual is None else ('different_projection' if not matches else None),
                          stdout=item['stdout'], stderr=item['stderr'])
            # A valid common-profile control validates adapters, not parser correctness.
            if cases[item['name']]['common_projection'] and not matches:
                failures.append(dict(name=item['name'], source=source, tool=item['kind']))
            records.append(record)
    result.update(adapter_controls_passed=inventory['status']=='complete' and not failures,
                  control_failures=failures,comparisons=records)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--native', required=True)
    p.add_argument('--external', action='append', required=True); p.add_argument('--output', required=True)
    a = p.parse_args()
    def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
    result = compare(read(a.manifest), read(a.native), {str(Path(x).parent): read(x) for x in a.external})
    Path(a.output).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('Comparisons:', len(result['comparisons']), 'retained discrepancies:', sum(bool(x['discrepancy']) for x in result['comparisons']))
    if not result['complete_success']: raise SystemExit('Differential evidence is incomplete or unverified; evidence retained')
