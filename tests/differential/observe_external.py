"""Linux-only bounded observation adapter for installed partition utilities."""
import hashlib
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path

from projections import external_projection as normalize


def digest(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def child_limits():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run(argv, cwd, timeout=8, output_limit=1024*1024):
    if os.name != 'posix': raise RuntimeError('Linux process helper requires its qualified Linux worker')
    start = time.monotonic(); buffers = [bytearray(), bytearray()]; outcome = 'exited'
    env = dict(os.environ, LC_ALL='C', LANG='C', HOME=str(cwd), TERM='dumb', NO_COLOR='1')
    with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, preexec_fn=child_limits) as child:
        def kill_group():
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass  # It may exit between observation and kill.
        with selectors.DefaultSelector() as selector:
            for i, stream in enumerate([child.stdout, child.stderr]):
                os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, i)
            while selector.get_map() or child.poll() is None:
                if time.monotonic()-start > timeout:
                    outcome = 'timeout'; kill_group(); break
                for key, _ in selector.select(0.05):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data: selector.unregister(key.fileobj); continue
                    remaining = output_limit-sum(len(b) for b in buffers)
                    buffers[key.data].extend(data[:remaining])
                    if len(data) > remaining:
                        outcome = 'output_limit'; kill_group(); break
                if outcome != 'exited': break
            child.wait(timeout=2)
    result = dict(argv=argv, exit_code=child.returncode, outcome=outcome,
                  elapsed_seconds=time.monotonic()-start)
    for name, buffer in zip(['stdout', 'stderr'], buffers):
        raw = bytes(buffer); result[name+'_sha256'] = 'sha256:'+hashlib.sha256(raw).hexdigest()
        try: result[name] = raw.decode('utf-8')
        except UnicodeDecodeError:
            result[name] = raw.decode('utf-8', 'backslashreplace'); result[name+'_bytes_hex'] = raw.hex()
    return result


def collect(manifest, root, expected_snapshot, participant, measured_identity, sfdisk, sgdisk, execute):
    """Construct fixed read-only reference commands, never execute manifest argv."""
    from collector import collect as collect_participant
    if participant == 'native':
        raise ValueError('Reference adapter cannot use native identity')
    commands = {}
    for row in manifest['expected_observations']:
        if row['participant'] != participant:
            continue
        path = str(Path(root) / row['policy']['input_path'])
        kind = row['kind']
        if kind in ('sfdisk-json', 'sfdisk-verify'):
            argv = [str(Path(sfdisk).absolute()), '--json' if kind == 'sfdisk-json' else '--verify', path]
        elif kind == 'sgdisk-print' and sgdisk is not None:
            argv = [str(Path(sgdisk).absolute()), '--pretend', '--print', '--verify', path]
        else:
            raise ValueError('Unknown or unavailable reference observation kind')
        commands[row['name'], kind] = argv
    return collect_participant(manifest, root, expected_snapshot, participant, measured_identity, commands, execute)


def observe(*args, **kwargs):
    raise RuntimeError('Legacy external collector suspended: use collect with a frozen manifest and qualified runner')


if __name__ == '__main__':
    observe()
