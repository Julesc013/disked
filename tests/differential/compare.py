"""Retain candidate-relative comparisons without selecting a winner."""
import argparse
import json
import os
from pathlib import Path
import re

from evidence import managed_path, read_receipt, write_report, evidence_set, validate_bindings


def compare(manifest, native, external, *, artifact_root=None, expected_manifest_sha256=None):
    inventory=evidence_set(manifest,native,external)
    result=dict(adapter_controls_passed=False,set_status=inventory['status'],set_validation=inventory,
                evidence_status='unverified',complete_success=False,
                pending_validation=['participant identities','raw artifact hashes','input preservation receipts','execution outcomes'],
                control_failures=[],comparisons=[],diagnostic_observations=[],uncompared_records=[],
                scope='All discrepancies retained; matching an external selection never resolves a DiskEd candidate conflict')
    if inventory['status']=='invalid':
        # Preserve every contradictory input; do not select one duplicate.
        result['unvalidated_inputs']=dict(manifest=manifest,native=native,external=external)
        result['evidence_status']='invalid'
        return result
    bindings=validate_bindings(manifest,native,external,artifact_root,expected_manifest_sha256)
    result.update(evidence_status=bindings['status'],evidence_validation=bindings,
                  execution=bindings['execution'],execution_passed=bindings['execution_passed'])
    if bindings['status']=='invalid':
        result['unvalidated_inputs']=dict(manifest=manifest,native=native,external=external)
        return result
    policies={(v['name'],v['participant'],v['kind']):v.get('policy')
              for v in manifest.get('expected_observations',[])}
    cases = {case['name']: case for case in manifest['cases']}
    observations={}
    for item in native['observations']:observations.setdefault(item['name'],[]).append(item)
    records = []; failures = []
    for source, evidence in external.items():
        for item in evidence['observations']:
            policy=policies.get((item['name'],source,item['kind']))
            if (policy and policy.get('comparison')=='diagnostic') or (not policy and item['kind']=='sfdisk-verify'):
                result['diagnostic_observations'].append(dict(participant=source,observation=item));continue
            choices=observations.get(item['name'],[])
            if item['name'] not in cases or len(choices)!=1:
                result['uncompared_records'].append(dict(participant=source,observation=item));continue
            expected = choices[0]['projection']; actual = item['projection']
            matches = []
            if actual is not None and expected is not None and actual['label'] == expected['label']:
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
    if bindings['status']=='complete':result['pending_validation']=[]
    result['comparison_status']=('disagreement' if any(v['discrepancy']=='different_projection' for v in records)
        else 'not_comparable' if not records or any(v['discrepancy']=='no_projection' for v in records) else 'agreement')
    result['complete_success']=bool(result['adapter_controls_passed'] and
        bindings['status']=='complete' and bindings['execution_passed'])
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--native', required=True)
    p.add_argument('--external', action='append', required=True,metavar='PARTICIPANT=PATH'); p.add_argument('--output', required=True)
    p.add_argument('--expected-manifest-sha256',help='Snapshot frozen by the campaign owner before collection')
    p.add_argument('--artifact-root',help='Finalized packet directory beneath DISKED_WORK_ROOT')
    a = p.parse_args()
    if not os.environ.get('DISKED_WORK_ROOT'):raise ValueError('Managed campaign runner required')
    root=Path(os.environ['DISKED_WORK_ROOT']).resolve(strict=True)
    repository=Path(__file__).resolve().parents[2]
    if root.is_relative_to(repository):raise ValueError('Repository paths are not campaign scratch')
    output=managed_path(a.output,root)
    artifact_root=root if a.artifact_root is None else managed_path(a.artifact_root,root)
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
    result=compare(read(a.manifest),read(a.native),external,artifact_root=artifact_root,
                   expected_manifest_sha256=a.expected_manifest_sha256)
    write_report(output,result)
    print('Comparisons:', len(result['comparisons']), 'retained discrepancies:', sum(bool(x['discrepancy']) for x in result['comparisons']))
    if not result['complete_success']: raise SystemExit('Differential evidence is incomplete or unverified; evidence retained')


if __name__ == '__main__':main()
