"""Independent sparse NTFS sources, physical mappings and bounded callback facts."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'property'))
from test_ntfs_boot import boot
from test_ntfs_attributes import resident, nonresident

U64 = (1 << 64) - 1


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def record(payload, size, number, usa=48, sequence=0x57c3, flags=1, base=0):
    count = size // 512 + 1
    offset = (usa + 2*count + 7) // 8 * 8
    assert offset + len(payload) <= size
    logical = bytearray(size)
    logical[:4] = b'FILE'
    struct.pack_into('<HHQHHHHIIQH', logical, 4, usa, count, 9, 3, 1, offset,
                     flags, offset+len(payload), size, base, 8)
    if usa >= 48:
        struct.pack_into('<I', logical, 44, number)
    logical[offset:offset+len(payload)] = payload
    tails = [bytes(logical[i-2:i]) for i in range(512, size+1, 512)]
    raw = bytearray(logical)
    struct.pack_into('<H', raw, usa, sequence)
    for index, tail in enumerate(tails):
        raw[usa+2+2*index:usa+4+2*index] = tail
        struct.pack_into('<H', raw, 512*(index+1)-2, sequence)
    return raw, offset


def mapping(runs):
    previous = 0
    out = bytearray()
    for count, lcn in runs:
        width = max(1, (count.bit_length()+8)//8)
        if lcn is None:
            out += bytes([width]) + count.to_bytes(width, 'little')
        else:
            delta = lcn-previous
            size = next(n for n in range(1, 9) if -(1 << (n*8-1)) <= delta < (1 << (n*8-1)))
            out += bytes([width | (size << 4)]) + count.to_bytes(width, 'little') + delta.to_bytes(size, 'little', signed=True)
            previous = lcn
    return out + b'\0'


class Volume:
    def __init__(self, sector=512, spc=1, size=1024, offset=0, fragmented=True,
                 first_lcn=8, second_lcn=100, usa=48, minor=1, runs=None,
                 data_payload=None, info_payload=None, primary_options=None,
                 volume_options=None, mirror_sequence=0x57c3, volume_number=3):
        self.cluster = sector*spc
        self.size = size
        total = max(4, (size*8+self.cluster-1)//self.cluster)
        first = max((size+self.cluster-1)//self.cluster, min(7, total-1))
        self.runs = runs or ([(first, first_lcn), (total-first, second_lcn)] if fragmented else [(total, first_lcn)])
        self.allocated = sum(count for count, _ in self.runs)*self.cluster
        data = nonresident(mapping(self.runs), high=sum(n for n, _ in self.runs)-1,
                           allocated=self.allocated, data=size*8, initialized=size*8)[0]
        self.data = bytes(data) if data_payload is None else bytes(data_payload)
        info = resident(b'\0'*8+bytes([3, minor])+b'\0\0', kind=0x70)[0]
        self.info = bytes(info) if info_payload is None else bytes(info_payload)
        payload = self.data + b'\xff'*4
        raw, self.attr_offset = record(payload, size, 0, usa=usa, **(primary_options or {}))
        mirror, _ = record(payload, size, 0, usa=usa, sequence=mirror_sequence, **(primary_options or {}))
        volume, self.info_offset = record(self.info+b'\xff'*4, size, volume_number, usa=usa, **(volume_options or {}))
        boot_bytes = boot(sector, spc, 256-(size.bit_length()-1), sectors=10000*spc-1,
                          mft=first_lcn, mirror=5000)
        self.window = 10000*spc*sector
        self.input = dict(source_id='generated-ntfs', epoch='7', source_bytes=str(offset+self.window),
                          offset=str(offset), length=str(self.window), major='3', minor=str(minor), regions=[])
        def region(at, value):
            self.input['regions'].append(dict(offset=str(offset+at), hex=bytes(value).hex()))
        region(0, boot_bytes)
        region(first_lcn*self.cluster, raw)
        region(5000*self.cluster, mirror)
        self.initial_reads = [(offset, 512)]
        if sector != 512:
            self.initial_reads += [(offset, sector)]
        self.initial_reads += [(offset+first_lcn*self.cluster, size), (offset+5000*self.cluster, size)]
        next_byte = size*3
        end = size*4
        vcn = 0
        for count, lcn in self.runs:
            begin, last = vcn*self.cluster, (vcn+count)*self.cluster
            vcn += count
            if next_byte >= last:
                continue
            if next_byte < begin:
                break
            length = min(end-next_byte, last-next_byte)
            if lcn is not None:
                at = lcn*self.cluster+next_byte-begin
                region(at, volume[next_byte-size*3:next_byte-size*3+length])
                self.initial_reads += [(offset+at, length)]
            next_byte += length
            if next_byte == end:
                break

    def change(self, region, at, value=None):
        item = self.input['regions'][region]
        raw = bytearray.fromhex(item['hex'])
        raw[at] = raw[at] ^ 1 if value is None else value
        item['hex'] = raw.hex()


def bytes_at(value, start, size):
    out = bytearray(size)
    for item in value['regions']:
        raw = bytes.fromhex(item['hex'])
        at = int(item['offset'])
        first, last = max(start, at), min(start+size, at+len(raw))
        if first < last:
            out[first-start:last-start] = raw[first-at:last-at]
    return bytes(out)


def cases():
    out = []
    def add(name, volume=None, diagnostic='', valid=True, refusal='', controls=None):
        v = volume or Volume()
        value = copy.deepcopy(v.input)
        value.update(controls or {})
        out.append((name, value, diagnostic, valid, refusal, list(v.initial_reads)))
        return value
    add('fragmented-record3-split')
    add('contiguous', Volume(fragmented=False))
    add('backwards-physical-run', Volume(first_lcn=32, second_lcn=8))
    add('old-header', Volume(usa=42))
    add('version3.0', Volume(minor=0))
    add('different-USA-sequence', Volume(mirror_sequence=0x1234))
    for sector in (512, 1024, 2048, 4096):
        for spc in (1, 8):
            add(f'geometry-{sector}-{spc}', Volume(sector=sector, spc=spc))
    for size in (512, 2048, 4096, 16384, 32768):
        add(f'record-{size}', Volume(size=size))
    for offset in (1, 4096, 1 << 32, (1 << 53)+13, U64-5120000):
        add(f'offset-{offset}', Volume(offset=offset))
    add('owned-controls-and-reader', controls={'fault': dict(mode='mutate-controls', call='1')})
    add('escaped-context-control-data', controls={'source_id': '\x1b[31m\n'*16})
    add('maximum-escaped-context', controls={'source_id': '\x01'*128})
    v = Volume(); v.change(2, v.size-10)
    add('mirror-unused-slack', v)
    v = Volume(); v.change(2, 16)
    add('mirror-used-payload', v, 'ntfs_mirror_disagreement', False)
    v = Volume(); v.change(2, 510)
    add('mirror-torn', v, 'ntfs_mirror_record', False)
    info = resident(b'\0'*8+b'\x03\x01\x01\x80', kind=0x70)[0]
    add('volume-flags-are-raw', Volume(info_payload=info))
    for major, minor in ((2, 0), (3, 0), (3, 2), (255, 255)):
        info = resident(b'\0'*8+bytes([major, minor])+b'\0\0', kind=0x70)[0]
        add(f'observed-version-{major}-{minor}', Volume(info_payload=info), 'ntfs_volume_version', False)
    for field, value, code in [('source_id', '', 'inputs'), ('source_id', 'x\0y', 'inputs'),
                               ('source_id', 'x'*129, 'inputs'), ('epoch', '0', 'inputs'),
                               ('source_bytes', '1', 'window'), ('offset', str(U64), 'window'),
                               ('length', '511', 'inputs'), ('major', '2', 'inputs'), ('minor', '2', 'inputs')]:
        add('invalid-'+field+'-'+str(value), refusal='ntfs_capture_'+code, controls={field: value})
    add('empty-reader', refusal='ntfs_capture_reader', controls={'empty_reader': True})
    add('invalid-UTF8-context', refusal='ntfs_capture_inputs', controls={'invalid_utf8_id': True})
    for field, maximum in [('read_requests', 512), ('read_bytes', 2097152), ('retained_bytes', 524288),
                           ('attributes', 4096), ('runs', 4096), ('output_bytes', 1048576)]:
        for value in (0, maximum+1):
            add(f'invalid-limit-{field}-{value}', refusal='ntfs_capture_limits', controls={'limits': {field: str(value)}})
    base = Volume()
    n = len(base.initial_reads)
    for field, value, code in [('read_requests', n-1, 'read'), ('read_requests', n, 'read'),
                               ('read_requests', n+1, 'read'), ('read_bytes', 511, 'read'),
                               ('retained_bytes', 512, 'retained'), ('attributes', 2, 'attribute'), ('runs', 3, 'run')]:
        add(f'budget-{field}-{value}', diagnostic='ntfs_'+code+'_budget', valid=False, controls={'limits': {field: str(value)}})
    total = sum(size for _, size in base.initial_reads)
    add('exact-read-retention-budgets', controls={'limits': {'read_requests': str(n*2), 'read_bytes': str(total*2), 'retained_bytes': str(total)}})
    for call in range(1, n*2+1):
        for mode in ('short', 'null', 'oversize', 'throw'):
            add(f'{mode}-call-{call}', diagnostic='ntfs_reader_failure' if mode == 'throw' else 'ntfs_read_length', valid=False,
                controls={'fault': dict(mode=mode, call=str(call))})
        if call > n:
            add(f'changed-reread-{call}', diagnostic='ntfs_source_changed', valid=False,
                controls={'fault': dict(mode='change', call=str(call))})
    add('changed-overlapping-boot', Volume(sector=1024), diagnostic='ntfs_source_changed', valid=False,
        controls={'fault': dict(mode='change', call='2')})
    for which, at, value, code in [(0, 3, 0, 'boot_geometry'), (0, 11, 1, 'boot_geometry'),
                                    (1, 0, 0, 'primary_record'), (1, 510, 0, 'primary_record'),
                                    (1, 44, 1, 'primary_record')]:
        v = Volume(); v.change(which, at, value)
        add(f'corrupt-{which}-{at}', v, 'ntfs_'+code, False)
    for flags in (0, 2, 3, 0x8001):
        add(f'primary-flags-{flags}', Volume(primary_options={'flags': flags}), 'ntfs_primary_record', False)
    add('extension-primary-record', Volume(primary_options={'base': 0x1000000000001}), 'ntfs_primary_record', False)
    add('unsafe-attribute-prefix', Volume(data_payload=b'\x80'+b'\0'*15), 'ntfs_primary_record', False)
    v = Volume()
    for index in (1, 2):
        raw = bytearray.fromhex(v.input['regions'][index]['hex'])
        used = struct.unpack_from('<I', raw, 24)[0]
        struct.pack_into('<I', raw, 24, used-4)
        v.input['regions'][index]['hex'] = raw.hex()
    add('missing-attribute-end-marker', v, 'ntfs_primary_record', False)
    good = Volume()
    for name, payload, code in [
        ('duplicate', good.data+good.data, 'data_ambiguous'),
        ('attribute-list', good.data+resident(b'', kind=0x20)[0], 'attribute_list_unsupported'),
        ('resident', resident(b'abcd')[0], 'data_unsupported'),
        ('named', nonresident(mapping(good.runs), name=b'x\0', high=15, allocated=8192, data=8192, initialized=8192)[0], 'data_unsupported'),
        ('sparse', nonresident(mapping(good.runs), flags=0x8000, high=15, allocated=8192, data=8192, initialized=8192)[0], 'data_unsupported'),
        ('compressed', nonresident(mapping(good.runs), flags=1, high=15, allocated=8192, data=8192, initialized=8192)[0], 'data_unsupported'),
        ('continuation', nonresident(mapping(good.runs), low=1, high=16)[0], 'data_unsupported'),
        ('bad-run', nonresident(b'\x99\0', high=15, allocated=8192, data=8192, initialized=8192)[0], 'data_unsupported'),
        ('allocation-size', nonresident(mapping(good.runs), high=15, allocated=8704, data=8192, initialized=8192)[0], 'sizes'),
        ('partial-data-record', nonresident(mapping(good.runs), high=15, allocated=8192, data=8191, initialized=7168)[0], 'sizes'),
        ('partial-initialized-record', nonresident(mapping(good.runs), high=15, allocated=8192, data=8192, initialized=8191)[0], 'sizes'),
        ('uninitialized-volume-record', nonresident(mapping(good.runs), high=15, allocated=8192, data=8192, initialized=3072)[0], 'sizes'),
    ]:
        add('mft-'+name, Volume(data_payload=payload), 'ntfs_mft_'+code, False)
    for name, runs, code in [('self-alias', [(7,8),(9,12)], 'physical_alias'),
                             ('boot-alias', [(7,8),(9,0)], 'physical_alias'),
                             ('mirror-alias', [(7,8),(9,5000)], 'physical_alias'),
                             ('seed-disagreement', [(1,8),(15,100)], 'seed_mapping')]:
        payload = nonresident(mapping(runs), high=15, allocated=8192, data=8192, initialized=8192)[0]
        add(name, Volume(data_payload=payload), 'ntfs_mft_'+code, False)
    for name, payload, code in [('missing', resident(b'', kind=0x10)[0], 'information'),
                                ('duplicate', good.info+good.info, 'information_ambiguous'),
                                ('named', resident(b'\0'*12, name=b'x\0', kind=0x70)[0], 'information'),
                                ('short', resident(b'\0'*11, kind=0x70)[0], 'information'),
                                ('flags', resident(b'\0'*12, flags=1, kind=0x70)[0], 'information'),
                                ('list', good.info+resident(b'', kind=0x20)[0], 'attribute_list_unsupported')]:
        add('volume-'+name, Volume(info_payload=payload), 'ntfs_volume_'+code, False)
    add('volume-wrong-number', Volume(volume_number=4), 'ntfs_volume_record', False)
    v = Volume(volume_options={'flags': 3})
    add('volume-directory-record', v, 'ntfs_volume_record', False)
    many = b''.join(resident(b'hello', instance=i, kind=0x30)[0] for i in range(100)) + Volume(size=8192).data
    add('output-budget-prefix', Volume(size=8192, data_payload=many), 'ntfs_output_budget', False,
        controls={'limits': {'output_bytes': '16384'}})
    many_names = b''.join(resident(b'', name=bytes([n, 0])*255, kind=0x30)[0] for n in range(1, 50)) + Volume(size=32768).data
    add('long-name-output-budget', Volume(size=32768, data_payload=many_names), 'ntfs_output_budget', False,
        controls={'source_id': '\x01'*128, 'limits': {'output_bytes': '16384'}})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    scenarios = cases()
    receipts = []
    for at in range(0, len(scenarios), 8):
        batch = scenarios[at:at+8]
        process = subprocess.run([str(args.probe.resolve())], input=json.dumps([c[1] for c in batch]).encode(), capture_output=True, timeout=30)
        assert process.returncode == 0 and not process.stderr, (process.returncode, process.stderr, [c[0] for c in batch])
        observed = json.loads(process.stdout)
        assert len(observed) == len(batch)
        for (name, value, diagnostic, valid, refusal, expected_reads), result in zip(batch, observed):
            assert result['source_unchanged'], name
            assert result['refusal'] == refusal, (name, result['refusal'], refusal)
            if refusal:
                assert not result['requests'], name
            else:
                report = result['report']
                assert report['diagnostic'] == diagnostic, (name, report['diagnostic'], diagnostic)
                assert report['applicable'] == valid, (name, report)
                assert not report['atomic_snapshot'] and not report['current_source_authority'] and not report['effects_authorized'], name
                requests = [(int(r['offset']), int(r['bytes'])) for r in result['requests']]
                assert int(report['read_requests']) == len(requests), name
                assert int(report['read_bytes']) == sum(n for _, n in requests), name
                assert all(int(value['offset']) <= start < start+size <= int(value['offset'])+int(value['length']) for start, size in requests), name
                assert int(report['retained_bytes']) == sum(int(r['bytes']) for r in report['regions']), name
                assert len(json.dumps(report, separators=(',', ':'), ensure_ascii=False).encode()) <= int(value.get('limits', {}).get('output_bytes', '1048576')), name
                if valid or diagnostic in ('ntfs_mirror_disagreement', 'ntfs_mirror_record', 'ntfs_volume_version'):
                    assert report['complete'] and report['reread_equal'], name
                    assert requests == expected_reads*2, (name, requests, expected_reads)
                    assert int(report['reread_requests']) == len(expected_reads), name
                    assert len(report['regions']) == len(expected_reads), name
                    for item, (start, size) in zip(report['regions'], expected_reads):
                        assert (int(item['offset']), int(item['bytes']), item['sha256']) == (start, size, sha(bytes_at(value, start, size))), name
                    assert int(report['mft']['initialized_bytes']) >= 4*int(report['boot']['record_bytes']), name
                    if valid:
                        assert report['mirror_used_payload_equal'] and report['volume_information']['profile_matches'], name
                        assert (report['volume_information']['major'], report['volume_information']['minor']) == (value['major'], value['minor']), name
                    if name in ('different-USA-sequence', 'mirror-unused-slack'):
                        assert report['primary']['raw_sha256'] != report['mirror']['raw_sha256'], name
                else:
                    assert not report['complete'], name
                if name == 'output-budget-prefix':
                    assert 0 < len(report['primary']['attributes']) < 100, name
                if name == 'budget-runs-3':
                    assert len(report['primary']['attributes'][0]['runs']) == 2 and len(report['mirror']['attributes'][0]['runs']) == 1, name
                if name == 'unsafe-attribute-prefix':
                    assert report['primary']['attributes'] and int(report['primary']['attribute_issues']) != 0, name
                if name == 'volume-flags-are-raw':
                    assert report['volume_information']['flags'] == '32769', name
            receipts.append(dict(name=name, passed=True, request_sha256=sha(json.dumps(value, sort_keys=True).encode()),
                                 observation_sha256=sha(json.dumps(result, sort_keys=True).encode())))
    summary = dict(count=len(receipts), cases=receipts, scope='Generated supplied-reader NTFS bootstrap only; no native opener/provider/effects or full product qualification.')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'Passed {len(receipts)} independent supplied-reader NTFS capture cases.')


if __name__ == '__main__':
    main()
