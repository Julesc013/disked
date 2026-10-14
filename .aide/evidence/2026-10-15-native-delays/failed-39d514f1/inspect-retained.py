import json
from pathlib import Path

root = Path(__file__).resolve().parent / 'source/.aide-local'
for folder in ['disked-acq-worker-qjzst3ul', 'disked-acq-worker-o40js1yk']:
    for path in sorted((root / folder).rglob('*.records')):
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        if not rows:
            continue
        first, last = rows[0]['state'], rows[-1]['state']
        receipt = last.get('receipt') or {}
        outcome = last.get('outcome') or {}
        if last.get('checkpoint_bytes') is not None and int(last['checkpoint_bytes']) > 10000000:
            timeline = [dict(sequence=r['state']['sequence'],
                seconds=round((int(r['state']['observed_filetime']) - int(first['observed_filetime'])) / 1e7, 3),
                checkpoint=r['state']['checkpoint_bytes']) for r in rows]
        else:
            timeline = []
        print(json.dumps(dict(path=str(path.relative_to(root)), records=len(rows),
            phase=last['phase'], quiescent=last['quiescent'],
            process_id=last['binding']['process_id'],
            elapsed_ms=receipt.get('elapsed_ms'),
            checkpoint_bytes=last.get('checkpoint_bytes'),
            outcome_status=outcome.get('status'), timeline=timeline,
            recorded_seconds=(int(last['observed_filetime']) - int(first['observed_filetime'])) / 1e7)))
