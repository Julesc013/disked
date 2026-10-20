"""Retain candidate-relative comparisons without selecting a winner."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import stat


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


def managed_path(value,root):
    """Routing check only; the owning runner supplies resource enforcement."""
    path=Path(value)
    if '..' in path.parts:raise ValueError('Parent traversal is outside the campaign route')
    path=path.absolute()
    if not path.is_relative_to(root) or path==root:raise ValueError('Path outside managed campaign workspace')
    for current in (path,*path.parents):
        if current==root:break
        try:info=current.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Linked campaign paths are refused')
    if not path.resolve().is_relative_to(root):raise ValueError('Resolved campaign path escaped')
    return path


def read_receipt(path,remaining=8*1024*1024):
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=min(remaining,8*1024*1024):
        raise ValueError('Receipt must be a bounded ordinary single-link file')
    with path.open('rb') as stream:body=stream.read(min(remaining,8*1024*1024)+1)
    if len(body)!=info.st_size:raise ValueError('Receipt changed or exceeded its bound')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON field')
            result[key]=value
        return result
    def reject(value):raise ValueError('Non-finite JSON number')
    def finite(value):
        number=float(value)
        if not math.isfinite(number):reject(value)
        return number
    return json.loads(body.decode('utf-8'),object_pairs_hook=unique,
                      parse_constant=reject,parse_float=finite),len(body)


def write_report(path,value,limit=64*1024*1024):
    if type(limit) is not int or not 1<=limit<=64*1024*1024:raise ValueError('Invalid report byte bound')
    # Stream expansion; failed writes leave only bounded partial scratch output.
    written=0
    with path.open('xb') as stream:
        for text in json.JSONEncoder(indent=2,allow_nan=False).iterencode(value):
            body=text.encode('utf-8');written+=len(body)
            if written>limit-1:raise ValueError('Comparison report exceeded its bound')
            stream.write(body)
        stream.write(b'\n')
    return written+1


def main():
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--native', required=True)
    p.add_argument('--external', action='append', required=True,metavar='PARTICIPANT=PATH'); p.add_argument('--output', required=True)
    a = p.parse_args()
    if not os.environ.get('DISKED_WORK_ROOT'):raise ValueError('Managed campaign runner required')
    root=Path(os.environ['DISKED_WORK_ROOT']).resolve(strict=True)
    repository=Path(__file__).resolve().parents[2]
    if root.is_relative_to(repository):raise ValueError('Repository paths are not campaign scratch')
    output=managed_path(a.output,root)
    if output.exists():raise ValueError('Preserve existing campaign output')
    if not 1<=len(a.external)<=8:raise ValueError('External participant count is outside the bounded profile')
    remaining=16*1024*1024
    def read(value):
        nonlocal remaining
        result,size=read_receipt(managed_path(value,root),remaining)
        remaining-=size
        return result
    external={}
    for value in a.external:
        participant,separator,path=value.partition('=')
        if (not separator or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',participant) or
                participant=='native' or participant in external):
            raise ValueError('Unique explicit external participant identity required')
        external[participant]=read(path)
    result=compare(read(a.manifest),read(a.native),external)
    write_report(output,result)
    print('Comparisons:', len(result['comparisons']), 'retained discrepancies:', sum(bool(x['discrepancy']) for x in result['comparisons']))
    if not result['complete_success']: raise SystemExit('Differential evidence is incomplete or unverified; evidence retained')


if __name__ == '__main__':main()
