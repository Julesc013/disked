"""Observe a controlled late FAT capture without changing its completion contract."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

root = Path.cwd()
parser = argparse.ArgumentParser()
parser.add_argument('--exe', type=Path)
parser.add_argument('--label', default='exfat-checkpoint-fat-retention-diagnostic')
args = parser.parse_args()
campaign = root / '.aide-local/exfat-command-exact-60376a0e'
source = campaign / 'source'
sys.path.insert(0, str(source / 'tests/frontend'))
sys.path.insert(0, str(source / 'tests/images'))
from test_fat_retention import Protocol
from test_fat_auxiliary import MetadataVolume
from test_image_commands import Gate
exe = args.exe.resolve() if args.exe else campaign / 'build/Release/disked_fat_test.exe'
records = []
timeline = []
gate = Gate()
port = None
def record(**fields):
    records.append(fields)
env = {k: v for k, v in os.environ.items() if not k.startswith(('DISKED_FAT_COMMAND_TEST_', 'DISKED_FAT_TEST_'))}
env.update(DISKED_FAT_COMMAND_TEST_GATE='1', DISKED_IMAGE_TEST_GATE=gate.name)
try:
    with tempfile.TemporaryDirectory(prefix='disked-fat-late-diagnostic-', dir=source / '.aide-local') as folder:
        path = Path(folder) / 'generated.img'
        volume = MetadataVolume(12); volume.write(path)
        initial = hashlib.sha256(path.read_bytes()).hexdigest()
        port = Protocol(exe, env, record)
        request = dict(path=str(path), view='fat', volume_offset=str(volume.offset),
                       volume_bytes=str(volume.length), retain_capture='yes')
        result = port.request('image.inspect', request, 6, 'request_wait_expired', request_id='late-origin')
        row = port.request('image.capture.inspect', {})['result']['captures']
        assert len(row) == 1 and row[0]['state'] == 'reserved'
        cid = row[0]['capture_id']
        port.request('image.capture.release', dict(capture_id=cid), 3, 'capture_retention_busy')
        started = time.monotonic(); gate.release()
        for _ in range(150):
            response = port.request('image.capture.inspect', {})
            rows = response['result']['captures']
            timeline.append(dict(elapsed_seconds=round(time.monotonic() - started, 3), rows=rows))
            print(json.dumps(timeline[-1]), flush=True)
            if not rows or rows[0]['state'] == 'retained': break
            time.sleep(.1)
        # Read a fresh semantic outcome after the gate is open; retain it even
        # if the preceding timed-out callback had to abandon its reservation.
        port.sequence += 1
        request_id = 'diagnostic-after-gate'
        port.process.stdin.write(json.dumps(dict(schema='org.disked.request/1', request_id=request_id,
            command='image.inspect', parameters=request, required_features=[])).encode() + b'\n')
        port.process.stdin.flush()
        response, response_sha256, size = port.queue.get(timeout=12)
        records.append(dict(request_id=request_id, response=response, response_sha256=response_sha256, bytes=size))
        print(json.dumps(response), flush=True)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == initial
        # Always stop this owned protocol process before temporary-file cleanup.
        port.abort(); port = None
finally:
    gate.release(); gate.close()
    if port: port.abort()
    (root / ('.aide-local/' + args.label + '.json')).write_text(json.dumps(dict(
        source_revision='working_tree' if args.exe else '60376a0e90eaeae35810b2f411e3e569c721f259',
        artifact_sha256='sha256:' + hashlib.sha256(exe.read_bytes()).hexdigest(),
        records=records, timeline=timeline), indent=2) + '\n', encoding='utf-8', newline='\n')
