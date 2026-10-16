"""Independent correspondence and source-order expectations, fixed before evaluation."""
import argparse
import copy
import json
import struct
import subprocess
from pathlib import Path

from ntfs_membership_fixture import (MembershipVolume, filename, resident, nonresident,
                                     record, list_entry, ref, sha)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def complete(report, volume):
    expected = volume.correspondence()
    matched = sum(row['corresponds'] for row in expected)
    assert report['complete'] and report['reread_equal']
    assert report['applicable'] == (matched == len(expected))
    assert not any(report[k] for k in ('atomic_snapshot', 'current_source_authority', 'effects_authorized'))
    assert report['schema'] == 'org.disked.ntfs-membership-observation-prototype/1'
    assert report['regions'] == volume.regions()
    assert report['read_requests'] == str(2*len(volume.initial_reads))
    assert report['read_bytes'] == str(2*sum(n for _, n in volume.initial_reads))
    assert report['retained_bytes'] == str(sum(n for _, n in volume.initial_reads))
    membership = report['membership']
    assert membership['collection_complete'] and membership['all_edges_matched'] == (matched == len(expected))
    assert membership['edges'] == expected
    assert membership['compared_edges'] == membership['edge_count'] == str(len(expected))
    assert membership['matched_edges'] == str(matched)
    assert membership['unmatched_edges'] == str(len(expected)-matched)
    assert not any(membership[k] for k in ('namespace_verified', 'collation_verified', 'lookup_verified', 'uniqueness_verified'))
    targets = list(dict.fromkeys(edge['reference'] for edge in volume.edges))
    assert membership['target_count'] == str(len(targets))
    assert len(membership['targets']) == len(targets)
    for target, actual in zip(targets, membership['targets']):
        assert actual['reference'] == str(target) and actual['inventory_complete']
        inventory = actual['inventory']
        assert inventory['complete'] and inventory['source_id'] == report['source_id']
        assert inventory['epoch'] == report['epoch']
        assert inventory['volume_offset'] == report['volume_offset']
        assert inventory['volume_bytes'] == report['volume_bytes']
        assert inventory['base_reference'] == str(target)
        assert inventory['name_count'] == str(len(volume.inventories[target]))
        for wanted, name in zip(volume.inventories[target], inventory['names']):
            assert name['reference'] == str(wanted['reference'])
            assert name['instance'] == str(wanted['instance'])
            assert name['parent_reference'] == str(wanted['parent'])
            assert name['namespace'] == str(wanted['namespace'])
            assert name['name_hex'] == wanted['name'].hex()
            assert name['name_sha256'] == sha(wanted['name'])
            assert name['value_sha256'] == sha(wanted['value'])
            assert name['duplicated_information_hex'] == wanted['value'][8:64].hex()


def cases():
    def case(label, v=None, diagnostic='', refusal='', controls=None, reads=None, check=None):
        v = v or MembershipVolume()
        request = copy.deepcopy(v.input)
        request.update(controls or {})
        return label, v, request, diagnostic, refusal, reads, check

    for kind in ('leaf', 'empty', 'single', 'siblings', 'deep', 'preallocated'):
        yield case('graph-'+kind, MembershipVolume(kind=kind))
    for minor in (0, 1):
        for form in ('none', 'resident', 'nonresident'):
            for flags in (1, 3):
                yield case(f'profile-list-flags-{minor}-{form}-{flags}',
                           MembershipVolume(minor=minor, list_form=form, target_flags=flags))
    for opts in (dict(cluster=512, index=512, size=1024), dict(cluster=512, size=1024),
                 dict(cluster=8192, index=4096, size=2048), dict(size=4096, index=8192),
                 dict(offset=(1 << 53)+17), dict(number=17, sequence=65535),
                 dict(minor=0, usa=42)):
        yield case('geometry-'+str(opts), MembershipVolume(**opts))
    for namespace in (0, 1, 2, 3):
        yield case('namespace-'+str(namespace), MembershipVolume(namespace=namespace))
    for minor in (0, 1):
        for directory_list in ('resident', 'nonresident'):
            for bitmap in ('resident', 'nonresident'):
                yield case(f'combined-closures-{minor}-{directory_list}-{bitmap}',
                           MembershipVolume(minor=minor, directory_list_form=directory_list,
                                            bitmap_form=bitmap, list_form='nonresident', mft_closure=True,
                                            split_allocation=True, fragmented_allocation=True))
    for name in (b'\0\0', b'\x1b\0[\0m\0', b'\0\xd8\xff\xdc', bytes([255, 255])*255):
        yield case('original-name-'+name.hex()[:18], MembershipVolume(kind='single', size=4096, name=name))
    v = MembershipVolume()
    names = v.target_recipes[v.edges[0]['reference']]['values']
    v.replace_target(values=names + [names[0], names[0], filename(b'D\0O\0S\0', namespace=2, parent=v.reference)[0],
                                    filename(b'other\0'.decode('latin1').encode('utf-16le'), parent=ref(20, 8))[0]])
    yield case('distinct-identical-instances-and-aliases', v)
    v = MembershipVolume()
    values = [raw[:8]+bytes(reversed(range(56)))+raw[64:]+b'opaque\0suffix'
              for raw in v.target_recipes[v.edges[0]['reference']]['values']]
    v.replace_target(values=values)
    yield case('duplicated-information-and-suffix-not-identity', v)
    for field in ('parent', 'name', 'namespace'):
        v = MembershipVolume()
        values = []
        for raw in v.target_recipes[v.edges[0]['reference']]['values']:
            raw = bytearray(raw)
            if field == 'parent':struct.pack_into('<Q', raw, 0, ref(5, 4))
            elif field == 'namespace':raw[65] = 2
            else:raw[66] ^= 1
            values.append(bytes(raw))
        v.replace_target(values=values)
        yield case('complete-mismatch-'+field, v, 'ntfs_membership_name_mismatch')
    v = MembershipVolume();v.replace_target(values=[])
    yield case('complete-empty-inventory-mismatch', v, 'ntfs_membership_name_mismatch')
    for limit in (1, 64, 256):
        yield case('target-control-'+str(limit), controls={'membership':dict(targets=str(limit))})
    for limit in (0, 257):
        yield case('invalid-target-control-'+str(limit), refusal='ntfs_membership_limits',
                   controls={'membership':dict(targets=str(limit))})
    yield case('empty-reader', refusal='ntfs_capture_reader', controls={'empty_reader':True})
    yield case('invalid-window', refusal='ntfs_capture_window', controls={'length':str(1 << 63)})

    # Two separately owned targets, one repeated edge, then a conflicting generation.
    for limit in (1, 2, 256):
        v = MembershipVolume(kind='leaf', size=4096)
        a, b = ref(14, 9), ref(15, 10)
        one, two = filename(b'A\0', parent=v.reference)[0], filename(b'B\0', parent=v.reference)[0]
        v.leaf_edges([(a, one), (b, two), (a, one)])
        v.install_target(a, [one]);v.install_target(b, [two]);v.finish_reads()
        yield case('distinct-target-limit-'+str(limit), v,
                   '' if limit >= 2 else 'ntfs_membership_target_budget',
                   controls={'membership':dict(targets=str(limit))},
                   reads=None if limit >= 2 else len(v.directory_reads_only)+1)
    v = MembershipVolume(kind='leaf', size=4096)
    raw = filename(b'middle'.decode().encode('utf-16le'), parent=v.reference)[0]
    v.leaf_edges([(ref(14, 9), raw), (ref(14, 10), raw)])
    yield case('conflicting-target-generation', v, 'ntfs_membership_reference_conflict',
               reads=len(v.directory_reads_only)+1)
    v = MembershipVolume(kind='leaf');raw = filename(b'middle'.decode().encode('utf-16le'), parent=v.reference)[0]
    v.leaf_edges([(ref(64, 9), raw)])
    yield case('target-outside-initialized-mft', v, 'ntfs_membership_reference_bounds', reads=len(v.directory_reads_only))

    for at, raw, label in [(16, b'\x08\0', 'stale-sequence'), (16, b'\0\0', 'zero-sequence'),
                            (22, b'\0\0', 'unused'), (22, b'\x05\0', 'unknown-flags'),
                            (32, struct.pack('<Q', ref(5, 3)), 'extension-as-base'),
                            (44, struct.pack('<I', 15), 'wrong-on-record-ordinal'),
                            (0, b'BAAD', 'invalid-record'), (510, b'\0\0', 'bad-fixup')]:
        v = MembershipVolume();v.mutate_record(14, at, raw)
        yield case('target-'+label, v, 'ntfs_membership_target_record', reads=len(v.directory_reads_only)+1)
    for form in ('resident', 'nonresident'):
        for field, value in [('extension_owner', ref(14, 8)), ('extension_sequence', 12)]:
            v = MembershipVolume(list_form=form);v.replace_target(**{field:value})
            yield case(f'extension-{form}-{field}', v, 'ntfs_membership_extension_record', reads=len(v.initial_reads))
    for code, descriptors in [('instance_missing', [list_entry(ref(14, 9), 12, kind=0x30)]),
                               ('list_duplicate', [list_entry(ref(14, 9), 11, kind=0x30)]*2),
                               ('entry_mismatch', [list_entry(ref(14, 9), 11, low=1, kind=0x30)])]:
        v = MembershipVolume(kind='leaf');v.replace_target(list_form='resident', descriptors=descriptors)
        yield case('target-list-'+code, v, 'ntfs_membership_join_'+code, reads=len(v.initial_reads))
    for region, runs, code in [('mft', [(1, 8)], 'ntfs_list_physical_alias'),
                                ('boot', [(1, 0)], 'ntfs_metadata_physical_alias'),
                                ('mirror', [(1, 5000)], 'ntfs_metadata_physical_alias'),
                                ('allocation', [(1, 1000)], 'ntfs_membership_physical_alias')]:
        v = MembershipVolume(list_form='nonresident')
        # Change only the mapping; do not overwrite the known source region with list bytes.
        attrs = [resident(raw, kind=0x30, instance=11+2*i)
                 for i, raw in enumerate(v.target_recipes[ref(14, 9)]['values'][:1])]
        listing = b''.join(list_entry(owner, instance, kind=0x30)
                           for owner, instance in [(ref(14, 9), 11), (ref(18, 11), 13), (ref(18, 11), 15)])
        attrs.append(nonresident(runs=runs, allocated=v.cluster, data=len(listing), initialized=len(listing), kind=0x20, instance=1, high=0))
        v.place_record(14, record(attrs, number=14, sequence=9, size=v.size))
        yield case('list-alias-before-payload-'+region, v, code, reads=len(v.directory_reads_only)+1)

    v = MembershipVolume(list_form='nonresident')
    n, total = len(v.initial_reads), sum(size for _, size in v.initial_reads)
    yield case('exact-source-quotas', v, controls={'limits':dict(read_requests=str(2*n), read_bytes=str(2*total), retained_bytes=str(total))})
    yield case('read-count-exceeded', v, 'ntfs_read_budget', controls={'limits':dict(read_requests=str(2*n-1))}, reads=2*n-1)
    yield case('read-bytes-exceeded', v, 'ntfs_read_budget', controls={'limits':dict(read_bytes=str(2*total-1))}, reads=2*n-1)
    yield case('retained-bytes-exceeded', v, 'ntfs_retained_budget', controls={'limits':dict(retained_bytes=str(total-1))}, reads=n-1)
    yield case('exact-attribute-and-run-quotas', v, controls={'limits':dict(attributes='10', runs='6')})
    yield case('attribute-quota-exceeded', v, 'ntfs_attribute_budget', controls={'limits':dict(attributes='9')}, reads=n)
    yield case('run-quota-exceeded', v, 'ntfs_run_budget', controls={'limits':dict(runs='5')}, reads=len(v.directory_reads_only)+1)
    yield case('output-quota-exceeded', v, 'ntfs_output_budget', controls={'limits':dict(output_bytes='16384')})
    # Every source and reread callback, including target list and extension, fails independently.
    for call in range(1, 2*n+1):
        for mode, code in [('throw', 'ntfs_reader_failure'), ('null', 'ntfs_read_length'),
                           ('short', 'ntfs_read_length'), ('oversize', 'ntfs_read_length')]:
            yield case(f'callback-{mode}-{call}', v, code,
                       controls={'fault':dict(mode=mode, call=str(call))}, reads=call)
        if call > n:
            yield case('final-change-'+str(call), v, 'ntfs_source_changed',
                       controls={'fault':dict(mode='change', call=str(call))}, reads=call)
    for call in (1, len(v.directory_reads_only)+1, n, 2*n):
        yield case('sealed-controls-'+str(call), v, controls={'fault':dict(mode='mutate-controls', call=str(call))})

    # A complete valid inventory may disagree; malformed evidence cannot become a mismatch.
    for raw, label in [(b'bad', 'truncated'), (filename(b'')[0], 'empty-name'),
                        (filename(b'A\0', namespace=4)[0], 'unknown-namespace'),
                        (filename(b'A\0', parent=5)[0], 'zero-parent-generation')]:
        v = MembershipVolume(kind='leaf')
        v.place_record(14, record([resident(raw, kind=0x30, instance=11)], number=14, sequence=9, size=v.size))
        yield case('malformed-target-name-'+label, v, 'ntfs_membership_names_value', reads=len(v.directory_reads_only)+1)

    # Retain a completed first comparison and stop at a stale second target.
    v = MembershipVolume(kind='leaf', size=4096)
    one, two = filename(b'A\0', parent=v.reference)[0], filename(b'B\0', parent=v.reference)[0]
    a, b = ref(14, 9), ref(15, 10)
    v.leaf_edges([(a, one), (b, two)])
    v.install_target(a, [one]);v.install_target(b, [two]);v.finish_reads()
    v.mutate_record(15, 16, b'\x0b\0')
    def prefix(actual):
        m = actual['report']['membership']
        assert m['compared_edges'] == '1' and m['matched_edges'] == '1'
        assert m['target_count'] == '2' and len(m['targets']) == 2
        assert m['targets'][0]['inventory_complete'] and not m['targets'][1]['inventory_complete']
        assert m['targets'][1]['record']['sequence'] == '11'
        assert not m['collection_complete'] and not m['all_edges_matched']
    yield case('completed-prefix-before-stale-second-target', v, 'ntfs_membership_target_record',
               reads=len(v.initial_reads), check=prefix)

    # Two ordinary lists that individually map correctly must still be disjoint.
    v = MembershipVolume(kind='leaf', size=4096)
    v.leaf_edges([(a, one), (b, two)])
    v.install_target(a, [one], list_form='nonresident', list_runs=[(1, 1500)])
    v.install_target(b, [two], list_form='nonresident', list_runs=[(1, 1501)]);v.finish_reads()
    listing = list_entry(b, 11, kind=0x30)
    attrs = [resident(two, kind=0x30, instance=11),
             nonresident(runs=[(1, 1500)], allocated=v.cluster, data=len(listing), initialized=len(listing), kind=0x20, instance=1, high=0)]
    v.place_record(15, record(attrs, number=15, sequence=10, size=v.size))
    yield case('earlier-target-list-alias-before-payload', v, 'ntfs_membership_physical_alias',
               reads=len(v.directory_reads_only)+3)
    for lcn, code, label in [(300, 'ntfs_list_physical_alias', 'mft-list'),
                              (700, 'ntfs_membership_physical_alias', 'volume-list'),
                              (1200, 'ntfs_membership_physical_alias', 'directory-list'),
                              (1300, 'ntfs_membership_physical_alias', 'directory-bitmap')]:
        v = MembershipVolume(list_form='nonresident', directory_list_form='nonresident',
                             bitmap_form='nonresident', mft_closure=True)
        first = v.target_recipes[ref(14, 9)]['values'][0]
        listing = b''.join(list_entry(owner, instance, kind=0x30)
                           for owner, instance in [(ref(14, 9), 11), (ref(18, 11), 13), (ref(18, 11), 15)])
        attrs = [resident(first, kind=0x30, instance=11),
                 nonresident(runs=[(1, lcn)], allocated=v.cluster, data=len(listing), initialized=len(listing), kind=0x20, instance=1, high=0)]
        v.place_record(14, record(attrs, number=14, sequence=9, size=v.size))
        yield case('known-metadata-list-alias-'+label, v, code, reads=len(v.directory_reads_only)+1)
    for target, label in [(ref(5, 3), 'directory-itself'), (ref(0, 3), 'mft'), (ref(3, 3), 'volume')]:
        v = MembershipVolume(kind='leaf')
        raw = filename(b'A\0', parent=v.reference)[0]
        v.leaf_edges([(target, raw)])
        v.inventories[target] = []
        v.target_reads = (v.record_regions[5] if label == 'directory-itself'
                          else v.bootstrap_reads[1:2] if label == 'mft' else v.bootstrap_reads[3:4])
        v.finish_reads()
        yield case('repeated-known-base-'+label, v, 'ntfs_membership_name_mismatch')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    rows = list(cases())
    assert len({row[0] for row in rows}) == len(rows)
    receipts = []
    for at in range(0, len(rows), 3):
        batch = rows[at:at+3]
        process = subprocess.run([str(args.probe.resolve())], input=canonical([r[2] for r in batch]),
                                 capture_output=True, timeout=90)
        assert process.returncode == 0 and not process.stderr, (batch[0][0], process.returncode, process.stderr)
        actuals = json.loads(process.stdout)
        assert len(actuals) == len(batch)
        for (label, volume, request, diagnostic, refusal, reads, check), actual in zip(batch, actuals):
            try:
                assert actual['source_unchanged'] and actual['refusal'] == refusal, actual
                if refusal:
                    assert actual['report'] is None and actual['requests'] == []
                else:
                    report = actual['report']
                    assert report['diagnostic'] == diagnostic, report
                    if not diagnostic or diagnostic == 'ntfs_membership_name_mismatch':
                        complete(report, volume)
                        assert actual['requests'] == volume.requests()
                    else:
                        assert not report['complete'] and not report['applicable']
                        if reads is not None:
                            assert actual['requests'] == volume.requests()[:reads], (actual['requests'], volume.requests()[:reads])
                    assert not report['atomic_snapshot'] and not report['current_source_authority'] and not report['effects_authorized']
                if check:check(actual)
            except AssertionError as error:
                args.output.write_text(json.dumps(dict(failed_case=label, request=request, result=actual,
                                                       passed_prefix=receipts), indent=2)+'\n', encoding='utf-8')
                raise AssertionError(label, error) from error
            receipts.append(dict(case=label, input_sha256=sha(canonical(request)), expected_diagnostic=diagnostic,
                                 expected_refusal=refusal, expected_read_prefix=reads,
                                 result_sha256=sha(canonical(actual)), passed=True))
    args.output.write_text(json.dumps(dict(count=len(receipts), cases=receipts,
                                          scope='Private supplied-reader exact filename correspondence; no native source/public admission, lookup or full namespace qualification',
                                          physical_devices=False), indent=2)+'\n', encoding='utf-8', newline='\n')
    print(len(receipts), 'guarded source-bound membership cases passed')


if __name__ == '__main__':
    main()
