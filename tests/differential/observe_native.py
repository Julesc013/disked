"""Adapt synthetic raw files to the existing private native observation probes."""
import hashlib
import stat
from pathlib import Path

from projections import native_request as request, field, native_projection as projection


def sha(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def load_case(root, case):
    path = root/case['file']
    if path.name != case['file'] or path.is_symlink() or path.resolve().parent != root:
        raise ValueError('Fixture must be an immediate ordinary corpus file')
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 2*1024*1024:
        raise ValueError('Fixture type or byte budget')
    data = path.read_bytes()
    if len(data) != case['bytes'] or sha(data) != case['sha256']:
        raise ValueError('Fixture identity changed')
    return data


def collect(manifest, root, expected_snapshot, measured_identity, mbr_probe, gpt_probe, execute):
    """Use explicit probe paths and a separately qualified campaign runner."""
    from collector import collect as collect_participant
    cases = {case['name']: case for case in manifest['cases']}
    probes = dict(mbr=str(Path(mbr_probe).absolute()), gpt=str(Path(gpt_probe).absolute()))
    commands = {}
    for row in manifest['expected_observations']:
        if row['participant'] == 'native':
            if row['kind'] != 'native':
                raise ValueError('Unknown native observation kind')
            commands[row['name'], row['kind']] = [probes[cases[row['name']]['family']]]
    return collect_participant(manifest, root, expected_snapshot, 'native', measured_identity, commands, execute)


def observe(*args, **kwargs):
    raise RuntimeError('Legacy native collector suspended: use collect with a frozen manifest and qualified runner')


if __name__ == '__main__':
    observe()
