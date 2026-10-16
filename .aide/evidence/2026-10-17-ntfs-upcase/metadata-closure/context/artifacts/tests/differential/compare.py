"""Retain candidate-relative comparisons without selecting a winner."""
import argparse
import json
from pathlib import Path


def compare(manifest, native, external):
    cases = {case['name']: case for case in manifest['cases']}
    observations = {item['name']: item for item in native['observations']}
    records = []; failures = []
    for source, evidence in external.items():
        for item in evidence['observations']:
            if item['kind'] == 'sfdisk-verify': continue
            expected = observations[item['name']]['projection']; actual = item['projection']
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
    return dict(adapter_controls_passed=not failures, control_failures=failures, comparisons=records,
                scope='All discrepancies retained; matching an external selection never resolves a DiskEd candidate conflict')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--native', required=True)
    p.add_argument('--external', action='append', required=True); p.add_argument('--output', required=True)
    a = p.parse_args()
    def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
    result = compare(read(a.manifest), read(a.native), {str(Path(x).parent): read(x) for x in a.external})
    Path(a.output).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('Comparisons:', len(result['comparisons']), 'retained discrepancies:', sum(bool(x['discrepancy']) for x in result['comparisons']))
    if not result['adapter_controls_passed']: raise SystemExit('Common-profile adapter controls failed; evidence retained')
