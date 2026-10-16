"""Independent protected metadata, raw name tuples and ordered source requests."""
import copy
import struct

from ntfs_directory_fixture import (DirectoryVolume, filename, index_entry,
                                    resident, nonresident, record, list_entry, ref, sha)

MASK = (1 << 48) - 1


class MembershipVolume(DirectoryVolume):
    def __init__(self, list_form='none', target_flags=1, extras=(), **options):
        super().__init__(**options)
        self.input['membership'] = {}
        self.directory_reads_only = self.initial_reads.copy()
        self.target_reads = []
        self.inventories = {}
        self.target_recipes = {}
        self.reads_by_target = {}
        self.edges = []
        for header, (_, (_, edge)) in enumerate(self.expected_rows, 1):
            if not edge['end_marker']:
                self.edges.append(dict(header=header, reference=int(edge['segment_reference']),
                                       parent=int(edge['filename']['parent_reference']),
                                       namespace=edge['filename']['namespace'],
                                       name=bytes.fromhex(edge['filename']['name_hex'])))
        grouped = {}
        for edge in self.edges:
            grouped.setdefault(edge['reference'], [])
            key = (edge['parent'], edge['namespace'], edge['name'])
            if key not in grouped[edge['reference']]:
                grouped[edge['reference']].append(key)
        for target, names in grouped.items():
            values = [filename(name, namespace=ns, parent=parent)[0]
                      for parent, ns, name in names]
            self.install_target(target, values + list(extras), list_form=list_form,
                                flags=target_flags)
        self.finish_reads()

    def install_target(self, reference, values, list_form='none', flags=1,
                       extension=ref(18, 11), list_runs=None, descriptors=None,
                       extension_owner=None, extension_sequence=None,
                       base_number=None, base_reference=0):
        number = reference & MASK
        assert list_form in {'none', 'resident', 'nonresident'}
        base_attrs, ext_attrs, expected = [], [], []
        locations = []
        for at, value in enumerate(values):
            instance = 11 + at * 2
            owner = reference if list_form == 'none' or at == 0 else extension
            attr = resident(value, kind=0x30, instance=instance)
            (base_attrs if owner == reference else ext_attrs).append(attr)
            locations.append((owner, instance))
            expected.append(dict(reference=owner, instance=instance, value=bytes(value),
                                 parent=struct.unpack_from('<Q', value)[0], namespace=value[65],
                                 name=bytes(value[66:66 + value[64]*2])))
        listing = b''
        runs = [(1, 1500 + len(self.target_recipes))] if list_runs is None else list_runs
        if list_form != 'none':
            if descriptors is None:
                descriptors = [list_entry(reference=owner, instance=instance, kind=0x30)
                               for owner, instance in locations]
            listing = b''.join(descriptors)
            attr = (resident(listing, kind=0x20, instance=1) if list_form == 'resident'
                    else nonresident(runs=runs, allocated=sum(n for n, _ in runs)*self.cluster,
                                     data=len(listing), initialized=len(listing), kind=0x20,
                                     instance=1, high=sum(n for n, _ in runs)-1))
            base_attrs.append(attr)
        raw = record(base_attrs, number=number if base_number is None else base_number,
                     sequence=reference >> 48, flags=flags, base=base_reference,
                     size=self.size, usa=self.usa)
        self.place_record(number, raw)
        reads = self.record_regions[number].copy()
        if list_form == 'nonresident':
            reads += self.place_logical(runs, 0, listing)
        if ext_attrs:
            ext_number = extension & MASK
            ext_raw = record(ext_attrs, number=ext_number,
                             sequence=extension >> 48 if extension_sequence is None else extension_sequence,
                             base=reference if extension_owner is None else extension_owner,
                             flags=flags, size=self.size, usa=self.usa)
            self.place_record(ext_number, ext_raw)
            reads += self.record_regions[ext_number]
        self.inventories[reference] = expected
        self.target_recipes[reference] = dict(values=copy.deepcopy(values), list_form=list_form,
                                             flags=flags, extension=extension,
                                             list_runs=runs, descriptors=descriptors,
                                             extension_owner=extension_owner,
                                             extension_sequence=extension_sequence,
                                             base_number=base_number, base_reference=base_reference)
        self.reads_by_target[reference] = reads
        self.target_reads = [span for target in dict.fromkeys(e['reference'] for e in self.edges)
                             if target in self.reads_by_target
                             for span in self.reads_by_target[target]]

    def replace_target(self, reference=None, **changes):
        reference = self.edges[0]['reference'] if reference is None else reference
        recipe = copy.deepcopy(self.target_recipes[reference])
        recipe.update(changes)
        self.install_target(reference, **recipe)
        self.finish_reads()

    def finish_reads(self):
        self.initial_reads = self.directory_reads_only + self.target_reads

    def leaf_edges(self, recipes):
        """Replace the graph with explicitly authored (reference, raw filename) rows."""
        assert self.kind == 'leaf'
        rows = [index_entry(key=(raw, filename()[1]), target=target) for target, raw in recipes]
        rows.append(index_entry(end=True))
        self.replace_root(rows, children=False)
        self.edges = [dict(header=at, reference=target, parent=struct.unpack_from('<Q', raw)[0],
                           namespace=raw[65], name=raw[66:66+raw[64]*2])
                      for at, (target, raw) in enumerate(recipes, 1)]
        self.target_reads = []
        for target in dict.fromkeys(e['reference'] for e in self.edges):
            if target in self.reads_by_target:
                self.target_reads += self.reads_by_target[target]
        self.finish_reads()

    def correspondence(self):
        targets = list(dict.fromkeys(e['reference'] for e in self.edges))
        rows = []
        for edge in self.edges:
            count = sum((name['parent'], name['namespace'], name['name']) ==
                        (edge['parent'], edge['namespace'], edge['name'])
                        for name in self.inventories[edge['reference']])
            rows.append(dict(header_number=str(edge['header']), reference=str(edge['reference']),
                             target_index=str(targets.index(edge['reference'])),
                             matching_instances=str(count), corresponds=bool(count)))
        return rows
