"""Actual exFAT command, protocol and native frontend journeys on owned images."""
import argparse
import copy
import hashlib
import json
import os
import queue
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'images'))
from test_exfat_capture import Volume
from test_exfat_file import write, file_digest, canonical
from test_exfat_upcase import mapping
from gui_fixture import Gui, U, wait
from test_image_commands import Gate

def main():
    parser = argparse.ArgumentParser()
    for name in ['exe', 'fault', 'root', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.exe, args.fault, args.root = args.exe.resolve(), args.fault.resolve(), args.root.resolve()
    records = []
    passed = False
    env = {k: v for k, v in os.environ.items() if not k.startswith('DISKED_EXFAT_COMMAND_TEST_')}
    def record(name, **fields):
        print('CASE ' + name, flush=True)
        records.append(dict(name=name, **fields))
    def options(volume, format=None):
        values = ['--view', 'exfat', '--volume-offset', str(volume.offset), '--volume-bytes', str(volume.length)]
        return values + (['--upcase-format', format] if format else [])
    def wire(path, volume, format=None):
        parameters = dict(path=str(path), view='exfat', volume_offset=str(volume.offset), volume_bytes=str(volume.length))
        if format: parameters['upcase_format'] = format
        return dict(schema='org.disked.request/1', request_id='exfat:req', command='image.inspect',
                    parameters=parameters, required_features=[])
    def launch(name, argv, expected=0, exe=None, settings=None, data=b''):
        callenv = dict(env, **(settings or {}))
        command = [str(exe or args.exe), *argv]
        result = subprocess.run(command, input=data, capture_output=True, timeout=20, env=callenv)
        assert result.returncode == expected, (name, result.returncode, result.stdout[:2000], result.stderr)
        assert not result.stderr, (name, result.stderr)
        response = json.loads(result.stdout)
        assert len(result.stdout) <= 524288
        assert response['operation_id'] is None
        record(name, command=command, exit_code=expected, response_sha256='sha256:' + hashlib.sha256(result.stdout).hexdigest())
        return response
    def stable(response):
        result = copy.deepcopy(response['result'])
        for key in ['context', 'worker', 'file_sha256', 'capture_sha256']: result.pop(key)
        result['observation'].pop('epoch')
        for key in ['process_id', 'process_created', 'sequence', 'capture_domain']: result['capture'].pop(key)
        return result
    def compare(left, right):
        assert left['status'] == right['status'] and left['diagnostics'] == right['diagnostics']
        assert stable(left) == stable(right), (stable(left), stable(right))
    try:
        with tempfile.TemporaryDirectory(prefix='disked-exfat-command-') as temporary:
            folder = Path(temporary).resolve()
            ambiguous = mapping(); ambiguous[128:130] = [65535, 2]
            literal_only = mapping(); literal_only[128:130] = [65535, 0]
            fixtures = [(Volume(offset=173), 'compressed', 0),
                        (Volume(copies=2, active=1, offset=173), 'compressed', 0),
                        (Volume(compressed=False, table=literal_only, offset=173), 'literal', 0),
                        (Volume(compressed=False, table=mapping(), offset=173), 'equivalent', 0),
                        (Volume(compressed=False, table=ambiguous, offset=173), 'ambiguous', 4)]
            for index, (volume, selection, exit_code) in enumerate(fixtures):
                path = folder / ('generated-' + str(index) + '.img')
                write(volume, path)
                before = file_digest(path)
                response = launch('cli-' + selection, ['--json', 'image', 'inspect', str(path), *options(volume)], exit_code)
                result = response['result']
                assert result['scope'] == 'ordinary-local-file-exfat'
                assert result['observation']['upcase']['selection'] == selection
                assert result['observation']['applicable'] == (exit_code == 0)
                assert result['worker']['worker']['observation'] == 'exited'
                assert not result['authorizes_effects']
                protocol = launch('protocol-' + selection, ['protocol', 'serve', '--json'], exit_code,
                                  data=canonical(wire(path, volume)))
                compare(response, protocol)
                assert file_digest(path) == before
                if selection == 'ambiguous':
                    forced = launch('explicit-literal', ['--json', 'image', 'inspect', str(path), *options(volume, 'literal')])
                    assert forced['result']['observation']['applicable']
                if index == 0:
                    current = set(p.name for p in folder.iterdir())
                    gui = Gui(args.exe, ['--gui', 'image', 'inspect', str(path), *options(volume)], render=True)
                    try:
                        assert not U.IsWindowEnabled(gui.child(110))
                        gui.click(109); assert gui.details()['reviewed']
                        assert 'status' not in gui.details()
                        gui.click(110)
                        actual = wait(lambda: gui.details() if 'status' in gui.details() else None)
                        compare(response, actual)
                        record('gui', native=gui.observation(), response=actual)
                    finally: gui.close()
                    assert gui.code == 0 and gui.created_files == []
                    for frontend in ['tui', 'shell']:
                        report = folder / (frontend + '.json')
                        startup = subprocess.STARTUPINFO(); startup.dwFlags = subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
                        command = [sys.executable, str(args.root / 'tests/frontend/image_console_fixture.py'),
                                   str(args.exe), frontend, 'image.inspect', str(path), '-', str(report), json.dumps(options(volume))]
                        run = subprocess.run(command, cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE,
                                             startupinfo=startup, timeout=35)
                        actual = json.loads(report.read_bytes())
                        assert run.returncode == 0, actual
                        compare(response, actual['response'])
                        record(frontend, observation=actual)
                        report.unlink()
                    assert set(p.name for p in folder.iterdir()) == current
                    assert file_digest(path) == before
            detailed = Volume(compressed=False, table=mapping(), offset=173)
            system = [raw for raw in detailed.records if raw[0] in (0x81, 0x82)]
            # Literal upcase storage uses even clusters100..610. Keep the independent
            # large root disjoint so this tests projection limits on coherent media.
            detailed.root = [2, 9] + list(range(1500, 1518))
            assert not set(detailed.root).intersection(detailed.upcase_chain + detailed.bitmap_chain)
            for index, cluster in enumerate(detailed.root):
                detailed.links[cluster] = detailed.root[index + 1] if index + 1 < len(detailed.root) else 0xffffffff
                detailed.bitmap[(cluster - 2) // 8] |= 1 << ((cluster - 2) % 8)
            detailed.records = [bytes([1]) + bytes(31)] * 301 + system
            detail_path = folder / 'detail.img'; write(detailed, detail_path)
            detail_before = file_digest(detail_path)
            detail = launch('bounded-detail-cli', ['--json', 'image', 'inspect', str(detail_path), *options(detailed)])
            obs = detail['result']['observation']
            assert obs['complete'] and obs['applicable']
            expected_records = []
            for index, raw in enumerate(detailed.records + [bytes(32)]):
                cluster = detailed.root[index // (detailed.size // 32)]
                offset = detailed.offset + detailed.cluster_offset(cluster) + (index % (detailed.size // 32)) * 32
                expected_records.append(dict(source_offset=str(offset), raw=raw.hex()))
            projected = obs['root_records']
            assert projected['items'] == expected_records[:int(projected['returned'])]
            assert int(projected['total']) == len(expected_records)
            assert projected['sha256'] == 'sha256:' + hashlib.sha256(canonical(expected_records)).hexdigest()
            assert projected['sha256'] != 'sha256:' + hashlib.sha256(canonical(projected['items'])).hexdigest()
            for rows in [obs['root_records'], obs['regions'], obs['upcase_chain']['cells']]:
                assert int(rows['omitted']) > 0, rows
                assert int(rows['returned']) == len(rows['items'])
                assert int(rows['total']) == int(rows['returned']) + int(rows['omitted'])
                assert rows['sha256'].startswith('sha256:')
            plain = subprocess.run([str(args.exe), 'image', 'inspect', str(detail_path), *options(detailed)],
                                   capture_output=True, timeout=20, env=env)
            assert plain.returncode == 0 and not plain.stderr, (plain.returncode, plain.stderr, plain.stdout[:1000])
            compare(detail, json.loads(plain.stdout))
            record('bounded-detail-plain-cli', exit_code=plain.returncode, output_bytes=len(plain.stdout))
            detail_wire = launch('bounded-detail-protocol', ['protocol', 'serve', '--json'], data=canonical(wire(detail_path, detailed)))
            compare(detail, detail_wire)
            detail_gui = Gui(args.exe, ['--gui', 'image', 'inspect', str(detail_path), *options(detailed)], render=True)
            try:
                detail_gui.click(109); detail_gui.click(110)
                actual = wait(lambda: detail_gui.details() if 'status' in detail_gui.details() else None)
                compare(detail, actual); record('bounded-detail-gui', native=detail_gui.observation())
            finally: detail_gui.close()
            assert file_digest(detail_path) == detail_before
            missing = folder / 'missing.img'
            invalid = [['--view', 'exfat'], ['--view', 'exfat', '--volume-offset', '0', '--volume-bytes', '1'],
                ['--view', 'exfat', '--volume-offset', '0', '--volume-bytes', '512', '--upcase-format', 'bad'],
                ['--view', 'exfat', '--volume-offset', '0', '--volume-bytes', '512', '--fat-copy', '0'],
                ['--view', 'exfat', '--volume-offset', '18446744073709551615', '--volume-bytes', '512']]
            for index, flags in enumerate(invalid):
                response = launch('invalid-before-source-' + str(index), ['--json', 'image', 'inspect', str(missing), *flags],
                    2, exe=args.fault, settings={'DISKED_EXFAT_COMMAND_TEST_OPEN_GUARD': '1'})
                # The shared CLI parser maps schema relationship errors to the
                # established invalid_option_value diagnostic; the service itself
                # uses invalid_parameter for an already constructed bad request.
                diagnostic = 'missing_parameter' if index == 0 else 'invalid_option_value'
                assert response['diagnostics'][0]['code'] == diagnostic, (index, response)
            response = launch('missing-source', ['--json', 'image', 'inspect', str(missing), '--view', 'exfat',
                                               '--volume-offset', '0', '--volume-bytes', '512'], 3)
            volume, _, _ = fixtures[0]
            path = folder / 'generated-0.img'
            for flag, expected, diagnostic in [
                    ('VERIFY_CHANGED', 4, 'exfat_source_changed'), ('VERIFY_ERROR', 4, 'exfat_capture_incomplete'),
                    ('INVALID_REPLY', 6, 'exfat_reader_validation_unresolved'), ('HANG', 6, None)]:
                response = launch('fault-' + flag, ['--json', 'image', 'inspect', str(path), *options(volume)], expected,
                                  exe=args.fault, settings={'DISKED_EXFAT_COMMAND_TEST_' + flag: '1'})
                if diagnostic: assert diagnostic in [d['code'] for d in response['diagnostics']]
            normal = launch('normal-ignores-fixture', ['--json', 'image', 'inspect', str(path), *options(volume)],
                            settings={'DISKED_EXFAT_COMMAND_TEST_HANG': '1'})
            assert normal['status'] == 'completed'
            gate = Gate()
            process = subprocess.Popen([str(args.fault), 'protocol', 'serve', '--format=ndjson'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=dict(env, DISKED_EXFAT_COMMAND_TEST_GATE=gate.name))
            messages = queue.Queue()
            thread = threading.Thread(target=lambda: [messages.put(json.loads(line)) for line in process.stdout], daemon=True)
            thread.start()
            def send(request):
                process.stdin.write(canonical(request) + b'\n'); process.stdin.flush()
            try:
                send(wire(path, volume)); gate.entered()
                expired = messages.get(timeout=6)
                assert expired['status'] == 'unknown' and expired['diagnostics'][0]['code'] == 'request_wait_expired'
                # The source handle remains pinned while the callback owns its slot.
                try:
                    with path.open('r+b'):
                        raise AssertionError('Source became writable during unresolved callback')
                except PermissionError: pass
                send(wire(path, volume)); busy = messages.get(timeout=2)
                assert busy['diagnostics'][0]['code'] == 'request_resource_limit'
                send(dict(schema='org.disked.request/1', request_id='essential', command='build.inspect', parameters={}, required_features=[]))
                assert messages.get(timeout=2)['status'] == 'completed'
                gate.release()
                after = None
                for _ in range(35):
                    time.sleep(.1); send(wire(path, volume)); after = messages.get(timeout=3)
                    if after['status'] == 'completed': break
                    assert after['diagnostics'][0]['code'] == 'request_resource_limit'
                assert after and after['status'] == 'completed' and messages.empty()
                process.stdin.close(); assert process.wait(timeout=8) == 6 and not process.stderr.read()
                record('wait-retains-source-slot-and-essential-service', expired=expired, busy=busy)
            finally:
                gate.release(); gate.close()
                if process.poll() is None: process.kill(); process.wait(timeout=5)
            for argv in [['help', '--json'], ['build', 'inspect', '--json'], ['command', 'list', '--json']]:
                launch('essential-' + argv[0], argv, exe=args.fault,
                       settings={'DISKED_EXFAT_COMMAND_TEST_OPEN_GUARD': '1'})
        passed = True
    finally:
        args.output.write_text(json.dumps(dict(passed=passed, cases=len(records), records=records), indent=2) + '\n', encoding='utf-8')
    print('exFAT command/frontend cases:', len(records))
if __name__ == '__main__': main()
