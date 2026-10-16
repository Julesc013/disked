"""Independent FILE_NAME instances, list closure, lossless bytes and bounded results."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

import test_ntfs_stream as fixture

BASE = fixture.BASE
EXT = fixture.EXT
PARENT = fixture.ref(5, 8)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def value(name=b'N\0', parent=PARENT, namespace=1, opaque=bytes(range(56)), suffix=b''):
    assert len(name) % 2 == 0 and len(name) <= 510 and len(opaque) == 56
    return struct.pack('<Q56sBB', parent, opaque, len(name)//2, namespace) + name + suffix


def wanted(raw, reference=BASE, instance=11, flags=0):
    parent = struct.unpack_from('<Q', raw)[0]
    end = 66 + raw[64]*2
    return dict(reference=str(reference), instance=str(instance), resident_flags=str(flags),
                parent_reference=str(parent), namespace=str(raw[65]),
                name=raw[66:end].hex(), value=raw.hex())


def attribute(raw=None, instance=11, **kw):
    return fixture.resident(value() if raw is None else raw, kind=0x30, instance=instance, **kw)


def request(records=None, **kw):
    result = fixture.request([fixture.row(fixture.record([attribute()]))] if records is None else records)
    result.pop('name')
    result['context']['source_id'] = 'generated-ntfs-names'
    result.update(kw)
    return result


def split(order=None, external=False):
    one = value(b'Long name\0'.decode('latin1').encode('utf-16le'))
    two = value(b'D\0O\0S\0', namespace=2)
    three = value(b'N\0', parent=fixture.ref(17, 65535), namespace=0, suffix=b'opaque\0suffix')
    descriptors = [fixture.entry(BASE, 11, kind=0x30), fixture.entry(EXT, 13, kind=0x30),
                   fixture.entry(EXT, 17, kind=0x30)]
    indices = [0, 1, 2] if order is None else order
    listing = b''.join(descriptors[i] for i in indices)
    list_attribute = fixture.nonresident(kind=0x20, instance=1, allocated=4096,
                                        data=len(listing), initialized=len(listing), runs=((1, 100),)) if external else fixture.resident(listing, kind=0x20, instance=1)
    base = fixture.record([attribute(one), list_attribute])
    extension = fixture.record([attribute(two, 13), attribute(three, 17)], number=7, sequence=9, base=BASE)
    result = request([fixture.row(base), fixture.row(extension, 7)])
    if external:
        result['list_capture'] = dict(base=str(BASE), instance='1', base_sha256=digest(base), hex=listing.hex())
    rows = [wanted(one), wanted(two, EXT, 13), wanted(three, EXT, 17)]
    return result, [rows[i] for i in indices]


def scenarios():
    def case(name, req, names=None, diagnostic='', refusal='', missing=(), prefix=None):
        return dict(case=name, request=copy.deepcopy(req), names=copy.deepcopy(names),
                    diagnostic=diagnostic, refusal=refusal, missing=[str(n) for n in missing],
                    prefix=copy.deepcopy(prefix))
    yield case('single', request(), [wanted(value())])
    yield case('empty-inventory', request([fixture.row(fixture.record([]))]), [])
    yield case('unselected-ordinary-data', request([fixture.row(fixture.record([fixture.resident()]))]), [])
    yield case('missing-base', request([]), diagnostic='ntfs_join_record_missing', missing=[BASE], prefix=[])
    same = value()
    yield case('identical-values-distinct-instances', request([fixture.row(fixture.record([attribute(same, 11), attribute(same, 12)]))]), [wanted(same), wanted(same, instance=12)])
    for code in range(4):
        for raw_name in (b'\0\0', b'\x1b\0', b'\0\xd8', b'\0\xdc', b'A\0a\0', b'X\0'*255):
            raw = value(raw_name, namespace=code, suffix=b'\xff\0opaque')
            yield case(f'lossless-{code}-{raw_name[:8].hex()}-{len(raw_name)}', request([fixture.row(fixture.record([attribute(raw)]))]), [wanted(raw)])
    for minor in ('0', '1'):
        req, names = split(); req['minor'] = minor
        yield case('list-version-' + minor, req, names)
    for order in ([2, 0, 1], [1, 2, 0], [2, 1, 0]):
        req, names = split(order)
        req['records'].reverse()
        yield case('preserve-descriptor-order-' + ''.join(map(str, order)), req, names)
    req, names = split(external=True)
    yield case('bound-nonresident-list', req, names)
    bad = copy.deepcopy(req); bad['limits'] = dict(list_bytes='95')
    yield case('list-byte-budget', bad, diagnostic='ntfs_join_list_byte_budget')
    base = fixture.record([attribute(bytes.fromhex(names[0]['value'])),
                           fixture.nonresident(kind=0x20, instance=1, allocated=8192,
                                               data=96, initialized=96, runs=((1, 100), (1, 200)))])
    req['records'][0]['hex'] = base.hex(); req['list_capture']['base_sha256'] = digest(base)
    for limit in (1, 2):
        bad = copy.deepcopy(req); bad['limits'] = dict(runs=str(limit))
        yield case('list-run-budget-' + str(limit), bad, names if limit == 2 else None,
                   diagnostic='' if limit == 2 else 'ntfs_join_run_budget')
    for flag in (0, 1):
        yield case('resident-flag-' + str(flag), request([fixture.row(fixture.record([attribute(resident_flags=flag)]))]), [wanted(value(), flags=flag)])
    yield case('directory-file-names', request([fixture.row(fixture.record([attribute()], flags=3))]), [wanted(value())])
    large = value(suffix=bytes(48000-68))
    yield case('maximum-record-owned-value', request([fixture.row(fixture.record([attribute(large)], size=49152))], record_bytes='49152'), [wanted(large)])
    for usa in (42, 48):
        ordinal = (1 << 40) + 19 if usa == 42 else (1 << 32) - 1
        ref = fixture.ref(ordinal, 65535)
        req = request([fixture.row(fixture.record([attribute()], number=ordinal, sequence=65535, usa=usa), ordinal)], base=str(ref))
        yield case('high-reference-' + str(usa), req, [wanted(value(), ref)])
    req, names = split(); req['records'].pop()
    yield case('missing-two-instances-one-record', req, diagnostic='ntfs_join_record_missing', missing=[EXT], prefix=names[:1])
    other = fixture.ref(13, 12)
    descriptors = fixture.entry(EXT, 13, kind=0x30) + fixture.entry(other, 17, kind=0x30)
    req = request([fixture.row(fixture.record([fixture.resident(descriptors, kind=0x20, instance=1)]))])
    yield case('all-missing', req, diagnostic='ntfs_join_record_missing', missing=[EXT, other], prefix=[])
    req = request([fixture.row(fixture.record([fixture.resident(fixture.entry(kind=0x80), kind=0x20, instance=1), fixture.resident()]))])
    yield case('empty-inventory-with-unrelated-list', req, [])
    req = request([fixture.row(fixture.record([fixture.resident(fixture.entry(EXT, 13, kind=0x30) + fixture.entry(BASE, 11, kind=0x30), kind=0x20, instance=1), attribute(b'bad')]))])
    yield case('known-invalid-value-clears-missing', req, diagnostic='ntfs_names_value', prefix=[])
    req, names = split(external=True)
    for field, wrong in [('base', str(fixture.ref(0, 6))), ('instance', '2'), ('base_sha256', 'sha256:' + '0'*64)]:
        bad = copy.deepcopy(req); bad['list_capture'][field] = wrong
        yield case('bad-list-binding-' + field, bad, diagnostic='ntfs_join_list_binding')
    bad = copy.deepcopy(req); bad['list_capture']['context'] = dict(bad['context'], epoch='18')
    yield case('bad-list-context', bad, diagnostic='ntfs_join_list_binding')
    bad = copy.deepcopy(req); bad['list_capture']['hex'] = bad['list_capture']['hex'][:-2]
    yield case('bad-list-size', bad, diagnostic='ntfs_join_list_sizes')
    bad = copy.deepcopy(req); bad.pop('list_capture')
    yield case('nonresident-list-without-binding', bad, diagnostic='ntfs_join_nonresident_list_unsupported')
    bad = request(); bad['list_capture'] = copy.deepcopy(req['list_capture'])
    yield case('unexpected-list', bad, diagnostic='ntfs_join_unexpected_list_capture')
    for count in (64, 256):
        descriptors = []; records = []; names = []
        for ordinal in range(count):
            ref = BASE if not ordinal else fixture.ref(ordinal, 9)
            raw = value(struct.pack('<H', ordinal), namespace=ordinal % 4)
            names.append(wanted(raw, ref))
            descriptors.append(fixture.entry(ref, 11, kind=0x30))
            if ordinal:
                records.append(fixture.row(fixture.record([attribute(raw)], number=ordinal, sequence=9, base=BASE), ordinal))
        listing = b''.join(descriptors); clusters = (len(listing)+4095)//4096
        base = fixture.record([attribute(value(b'\0\0', namespace=0)), fixture.nonresident(kind=0x20, instance=1, allocated=clusters*4096, data=len(listing), initialized=len(listing), runs=((clusters, 100),))])
        req = request([fixture.row(base), *records], limits=dict(records=str(count), record_bytes=str(count*1024)))
        req['list_capture'] = dict(base=str(BASE), instance='1', base_sha256=digest(base), hex=listing.hex())
        yield case('exact-record-count-' + str(count), req, names)
    for key, limit, code in [('records', '1', 'record'), ('record_bytes', '2047', 'byte'), ('attributes', '3', 'attribute'), ('list_entries', '2', 'list')]:
        req, _ = split(); req['limits'] = {key: limit}
        yield case('budget-' + key, req, diagnostic='ntfs_join_' + code + '_budget')
    req, names = split(); req['limits'] = dict(records='2', record_bytes='2048', attributes='4', list_entries='3')
    yield case('exact-selection-budgets', req, names)
    raw = value(b'X\0'*255)
    names = [wanted(raw, instance=i) for i in range(1, 6)]
    req = request([fixture.row(fixture.record([attribute(raw, i) for i in range(1, 6)], size=4096))], record_bytes='4096')
    charge = 4096 + 256 + 5*(512 + 2*len(raw) + 2*510)
    for maximum in (16384, charge-1, charge):
        bad = copy.deepcopy(req); bad['limits'] = dict(output_bytes=str(maximum))
        count = min(5, (maximum-4096-256)//(512+2*len(raw)+2*510))
        yield case('output-boundary-' + str(maximum), bad, names if maximum == charge else None,
                   diagnostic='' if maximum == charge else 'ntfs_join_output_budget', prefix=names[:count])
    for length in range(68):
        raw = value()[:length]
        yield case('truncated-value-' + str(length), request([fixture.row(fixture.record([attribute(raw)]))]), diagnostic='ntfs_names_value')
    for namespace in (4, 127, 255):
        yield case('unknown-namespace-' + str(namespace), request([fixture.row(fixture.record([attribute(value(namespace=namespace))]))]), diagnostic='ntfs_names_value')
    yield case('zero-parent-sequence', request([fixture.row(fixture.record([attribute(value(parent=5))]))]), diagnostic='ntfs_names_value')
    yield case('zero-name', request([fixture.row(fixture.record([attribute(value(b''))]))]), diagnostic='ntfs_names_value')
    for attrs in ([attribute(flags=0x4000)], [attribute(resident_flags=2)], [fixture.nonresident(kind=0x30, allocated=8192, data=10, initialized=10)]):
        yield case('unsupported-form-' + str(len(attrs[0])) + '-' + attrs[0].hex()[:28], request([fixture.row(fixture.record(attrs))]), diagnostic='ntfs_names_attribute_form')
    yield case('named-filename-attribute', request([fixture.row(fixture.record([attribute(name=b'A\0')]))]), diagnostic='ntfs_names_attribute_name')
    listing = fixture.entry(EXT, 13, kind=0x30, name=b'A\0')
    yield case('named-filename-descriptor', request([fixture.row(fixture.record([fixture.resident(listing, kind=0x20, instance=1)]))]), diagnostic='ntfs_names_attribute_name')
    for index, (listing, code) in enumerate([(fixture.entry()[:1], 'list'), (b'', 'list_empty'), (fixture.entry(kind=0x30, reference=0), 'list'), (fixture.entry(kind=0x30)*2, 'list_duplicate'), (fixture.entry(kind=0x30, instance=12), 'instance_missing'), (fixture.entry(kind=0x30, low=1), 'entry_mismatch'), (fixture.entry(kind=0x80), 'unlisted_attribute')]):
        req = request([fixture.row(fixture.record([attribute(), fixture.resident(listing, kind=0x20, instance=1)]))])
        yield case('bad-list-' + str(index) + '-' + code, req, diagnostic='ntfs_join_' + code)
    for entries in ([fixture.entry(EXT, 13, kind=0x30), fixture.entry(fixture.ref(7, 10), 17, kind=0x30)],):
        req = request([fixture.row(fixture.record([fixture.resident(b''.join(entries), kind=0x20, instance=1)]))])
        yield case('conflicting-generations', req, diagnostic='ntfs_join_reference_ambiguous')
    for at in (0, 4, 6, 20, 28, 510, 1022):
        req = request(); raw = bytearray.fromhex(req['records'][0]['hex']); raw[at] ^= 0xff; req['records'][0]['hex'] = raw.hex()
        yield case('invalid-file-' + str(at), req, diagnostic='ntfs_join_record_envelope')
    for flags in (0, 2, 5):
        yield case('file-flags-' + str(flags), request([fixture.row(fixture.record([attribute()], flags=flags))]), diagnostic='ntfs_join_record_flags')
    for field, raw_value, code in [('sequence', 8, 'sequence'), ('base', 0, 'base_reference'), ('number', 8, 'record_number')]:
        req, _ = split(); raw = bytearray.fromhex(req['records'][1]['hex']); at, fmt = {'sequence': (16, '<H'), 'base': (32, '<Q'), 'number': (44, '<I')}[field]
        struct.pack_into(fmt, raw, at, raw_value); req['records'][1]['hex'] = raw.hex()
        yield case('bad-extension-' + field, req, diagnostic='ntfs_join_' + code)
    req = request(); req['records'].append(copy.deepcopy(req['records'][0]))
    yield case('duplicate-ordinal', req, diagnostic='ntfs_join_record_ambiguous')
    yield case('duplicate-instance', request([fixture.row(fixture.record([attribute(), attribute()]))]), diagnostic='ntfs_join_instance_ambiguous')
    for field, wrong in [('source_id', 'another'), ('epoch', '18'), ('offset', '4097'), ('length', '8000')]:
        req, _ = split(); req['records'][1]['context'] = dict(req['context'], **{field: wrong})
        yield case('context-' + field, req, diagnostic='ntfs_join_context')
    for field, wrong in [('source_id', ''), ('source_id', 'x\0'), ('source_id', 'x'*129), ('epoch', '0'), ('length', '0'), ('offset', str((1 << 64)-1))]:
        req = request(); req['context'][field] = wrong
        yield case('invalid-context-' + field + '-' + str(len(wrong)), req, refusal='ntfs_join_inputs')
    for field, wrong in [('base', '0'), ('major', '2'), ('minor', '2'), ('clusters', '0'), ('cluster_bytes', '513'), ('record_bytes', '513')]:
        req = request(); req[field] = wrong
        yield case('invalid-control-' + field, req, refusal='ntfs_join_inputs')
    for field, maximum in [('records', 256), ('record_bytes', 1048576), ('attributes', 4096), ('list_entries', 4096), ('runs', 4096), ('list_bytes', 262144), ('output_bytes', 1048576)]:
        for limit in (0, maximum+1):
            req = request(); req['limits'] = {field: str(limit)}
            yield case('invalid-limit-' + field + '-' + str(limit), req, refusal='ntfs_join_limits')
    for key, wrong in [('number', str(1 << 48)), ('hex', bytes(49153).hex()), ('null_view', True)]:
        req = request(); req['records'][0][key] = wrong
        yield case('invalid-record-' + key, req, refusal='ntfs_join_record_inputs')
    rng = random.Random(0x4e414d45)
    for n in range(48):
        rows = []; attrs = []
        for i in range(1, rng.randrange(2, 5)):
            raw = value(bytes(rng.randrange(256) for _ in range(2*rng.randrange(1, 20))),
                        parent=fixture.ref(rng.randrange(1 << 48), rng.randrange(1, 65536)),
                        namespace=rng.randrange(4), opaque=bytes(rng.randrange(256) for _ in range(56)),
                        suffix=bytes(rng.randrange(256) for _ in range(rng.randrange(15))))
            attrs.append(attribute(raw, i)); rows.append(wanted(raw, instance=i))
        yield case('generated-distinct-' + str(n), request([fixture.row(fixture.record(attrs))]), rows)


def report_row(row):
    raw = bytes.fromhex(row['value']); name = bytes.fromhex(row['name']); suffix = raw[66+len(name):]
    return {**{k: row[k] for k in ('reference', 'instance', 'resident_flags', 'parent_reference', 'namespace')},
            'name_hex': name.hex(), 'name_sha256': digest(name), 'value_bytes': str(len(raw)),
            'value_sha256': digest(raw), 'duplicated_information_hex': raw[8:64].hex(),
            'suffix_bytes': str(len(suffix)), 'suffix_sha256': digest(suffix)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--probe', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); cases = list(scenarios()); records = []
    output = Path(args.output)
    def save(**extra):
        output.write_text(json.dumps(dict(count=len(records), passed=False, cases=records,
                                         scope='Supplied-record filename inventory only; no native membership or effects', **extra), indent=2)+'\n', encoding='utf-8', newline='\n')
    save()
    for at in range(0, len(cases), 4):
        batch = cases[at:at+4]
        proc = subprocess.run([args.probe], input=json.dumps([c['request'] for c in batch]).encode(), capture_output=True, timeout=30)
        if proc.returncode or proc.stderr:
            save(failed_batch=batch, process_exit=proc.returncode, stderr=proc.stderr.decode(errors='replace'), stdout=proc.stdout.decode(errors='replace'))
            raise AssertionError((proc.returncode, proc.stderr.decode(errors='replace')))
        observed = json.loads(proc.stdout); assert len(observed) == len(batch)
        for case, result in zip(batch, observed):
            try:
                assert result['source_unchanged'] and result['refusal'] == case['refusal']
                assert result['usable'] == (case['names'] is not None)
                if case['refusal']:
                    assert 'names' not in result and 'observation' not in result
                else:
                    report = result['observation']
                    assert report['diagnostic'] == case['diagnostic'], (case['diagnostic'], report['diagnostic'])
                    assert result['required_records'] == report['required_records'] == case['missing']
                    assert report['complete'] == result['usable']
                    assert not any(report[k] for k in ('atomic_snapshot', 'current_source_authority', 'effects_authorized'))
                    assert all(report[k] == 'unverified' for k in ('target_membership', 'collation', 'namespace'))
                    prefix = case['names'] if result['usable'] else case['prefix']
                    if prefix is not None:
                        assert report['names'] == [report_row(n) for n in prefix]
                    assert report['name_count'] == str(len(report['names']))
                    for row in report['records']:
                        raw = next(r for r in case['request']['records'] if r['number'] == row['number'])
                        assert row['sha256'] == digest(bytes.fromhex(raw['hex']))
                    if result['usable']:
                        assert result['names'] == case['names'] and report['context_matches']
                    else:
                        assert 'names' not in result
            except BaseException:
                save(failed_case=case, observed=result)
                raise
            records.append(dict(case=case['case'], request_sha256=digest(json.dumps(case['request'], sort_keys=True).encode()),
                                result_sha256=digest(json.dumps(result, sort_keys=True).encode()), passed=True))
    save()
    summary = json.loads(output.read_bytes()); summary['passed'] = True
    output.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(len(records), 'protected filename-instance cases passed')


if __name__ == '__main__':
    main()
