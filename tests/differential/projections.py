"""Pure partition observation projections; no process or platform operations."""
import json
import re
import uuid
import struct
import math


def strict_json(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate JSON field')
            value[key] = item
        return value
    def invalid(value):
        raise ValueError('Non-finite JSON number')
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            invalid(value)
        return number
    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite)


def field(value, path):
    for part in path.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def native_projection(value, family):
    result = dict(label='dos' if family == 'mbr' else 'gpt', candidates=[])
    if family == 'mbr':
        rows = []
        for i, entry in enumerate(value['mbr']['entries']):
            if entry['active'] and entry['range_valid']:
                rows.append(dict(slot=i+1, start=int(entry['start']), end=int(entry['end']),
                                 type=format(bytes.fromhex(entry['raw'])[4], 'x')))
        logical = 5
        for walk in value['walks']:
            for node in walk['nodes']:
                entry = node['entries'][0]
                if entry['active'] and entry['range_valid'] and entry['kind'] == 1:
                    rows.append(dict(slot=logical, start=int(entry['start']), end=int(entry['end']),
                                     type=format(bytes.fromhex(entry['raw'])[4], 'x')))
                    logical += 1
        result['candidates'].append(dict(role='mbr', rows=rows, issues=value['mbr']['issues'],
                                        walks=[dict(issues=w['issues'], complete=w['complete']) for w in value['walks']]))
    else:
        result['comparison'] = value['comparison']
        for side, copy in enumerate(value['copies']):
            candidate = copy.get('candidate', {})
            rows = []
            for i, entry in enumerate(candidate.get('entries', [])):
                if entry['active'] and entry['range_valid']:
                    rows.append(dict(slot=i+1, start=int(entry['first']), end=int(entry['end']),
                                     type=entry['type_guid'], uuid=entry['unique_guid']))
            result['candidates'].append(dict(role='primary' if side == 0 else 'backup', rows=rows,
                disk_uuid=copy['header']['disk_guid'],
                header_issues=copy['header']['issues'], array_issues=candidate.get('issues'),
                complete=candidate.get('complete', False), consistent=candidate.get('consistent', False)))
    return result


def external_projection(record, kind, path):
    if record['exit_code'] != 0 or record['outcome'] != 'exited': return None
    if 'stdout_bytes_hex' in record: return None
    if kind == 'sfdisk-json':
        try: value = strict_json(record['stdout'])['partitiontable']
        except (ValueError, KeyError, TypeError): return None
        if not isinstance(value, dict) or value.get('label') not in ['dos', 'gpt']: return None
        if value.get('unit') != 'sectors' or value.get('sectorsize') != 512: return None
        partitions = value.get('partitions', [])
        if not isinstance(partitions, list) or len(partitions) > 1024: return None
        rows = []; slots = set()
        for item in partitions:
            if not isinstance(item, dict) or not isinstance(item.get('node'), str): return None
            if any(type(item.get(key)) is not int or not 0 <= item[key] <= 0xffffffffffffffff for key in ['start', 'size']): return None
            if any(key in item and not isinstance(item[key], str) for key in ['type', 'uuid']): return None
            node = item.get('node', ''); suffix = node[len(str(path)):] if node.startswith(str(path)) else ''
            if not re.fullmatch(r'p?[1-9][0-9]*', suffix): return None
            row = dict(slot=int(suffix.lstrip('p')), start=item['start'], end=item['start']+item['size'])
            if row['slot'] in slots or row['end'] > 0xffffffffffffffff: return None
            slots.add(row['slot'])
            if 'type' in item: row['type'] = item['type'].lower()
            if 'uuid' in item: row['uuid'] = item['uuid'].lower()
            rows.append(row)
        result = dict(label=value['label'], rows=rows, fields=['slot', 'start', 'end', 'type', 'uuid'])
        if value['label'] == 'gpt' and 'id' in value:
            try: result['disk_uuid'] = str(uuid.UUID(value['id']))
            except (ValueError, TypeError, AttributeError): return None
        return result
    if kind == 'sgdisk-print':
        # Ignore names and tool-specific type codes; retain their raw text above.
        rows = [dict(slot=int(m[0]), start=int(m[1]), end=int(m[2])+1)
                for m in re.findall(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+.+$', record['stdout'], re.M)]
        if 'Number  Start (sector)' not in record['stdout']: return None
        result = dict(label='gpt', rows=rows, fields=['slot', 'start', 'end'])
        identity = re.search(r'^Disk identifier \(GUID\): ([0-9A-Fa-f-]{36})$', record['stdout'], re.M)
        if identity: result['disk_uuid'] = identity[1].lower()
        return result
    return None



def native_request(data, case):
    unit, blocks = case['unit'], case['blocks']
    assert unit == 512 and 2 <= blocks <= 4096
    if case['family'] == 'mbr':
        return dict(blocks=str(blocks), unit=str(unit), limit='128', heads='0', sectors='0',
                    image={str(n): data[n*unit:(n+1)*unit].hex()
                           for n in range(max(1, (len(data)+unit-1)//unit))})
    out = dict(blocks=str(blocks), unit=str(unit), max_entries='1024',
               max_entry_size='4096', max_bytes='1048576')
    for side, lba in [('primary', 1), ('backup', blocks-1)]:
        header = data[lba*unit:(lba+1)*unit]; out[side] = header.hex()
        array = b''
        if len(header) == unit:
            start, count, width = struct.unpack_from('<QII', header, 72)
            size = ((count*width+unit-1)//unit)*unit
            if size <= 1048576:
                array = data[start*unit:start*unit+size]
        out[side+'_array'] = array.hex()
    return out
