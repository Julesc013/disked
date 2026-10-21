"""Pure DE-W107 requests and raw Windows-layout checks; no device/process access."""
import hashlib
import struct
import uuid

CASES=('mbr-valid','gpt-valid','gpt-primary-damaged','gpt-conflicting')

def request(data,case):
    if (type(data) is not bytes or case['name'] not in CASES or len(data)!=4194304 or
            case['blocks']!=8192 or case['unit']!=512 or
            'sha256:'+hashlib.sha256(data).hexdigest()!=case['sha256']):
        raise ValueError('Windows fixture identity')
    if case['family']=='mbr':
        # These two-primary-entry fixtures have no EBRs. Supply the requested
        # sector only, not an 8 MiB JSON rendering of every unused block.
        return dict(blocks='8192',unit='512',limit='128',heads='0',sectors='0',image={'0':data[:512].hex()})
    if case['family']!='gpt':raise ValueError('Windows fixture family')
    result=dict(blocks='8192',unit='512',max_entries='1024',max_entry_size='4096',max_bytes='1048576')
    for role,lba in (('primary',1),('backup',8191)):
        header=data[lba*512:(lba+1)*512]
        array,count,width=struct.unpack_from('<QII',header,72)
        if count!=128 or width!=128 or array not in (2,8159):raise ValueError('Windows fixture table bounds')
        result[role]=header.hex();result[role+'_array']=data[array*512:array*512+16384].hex()
    return result

def native_expectations(case):
    if case['family']=='mbr':return {'mbr.issues':0}
    values={'comparison':2 if case['name']=='gpt-conflicting' else 0 if case['name']=='gpt-primary-damaged' else 1,
            'copies.0.header.issues':16 if case['name']=='gpt-primary-damaged' else 0,
            'copies.1.header.issues':0,'copies.1.candidate.issues':0,
            'copies.1.candidate.entries.0.first':str(case['backup_first'])}
    if case['name']!='gpt-primary-damaged':
        values.update({'copies.0.candidate.issues':0,'copies.0.candidate.entries.0.first':'2048'})
    return values

def matching_candidates(native,observed):
    if observed is None or observed['label']!=native['label']:return []
    result=[]
    for candidate in native['candidates']:
        if native['label']=='gpt' and (candidate['header_issues']!=0 or candidate['array_issues']!=0 or
                not candidate['complete'] or not candidate['consistent']):continue
        if native['label']=='dos' and candidate['issues']!=0:continue
        if [dict(start=v['start'],end=v['end'],type=v['type']) for v in candidate['rows']]==observed['rows']:
            result.append(candidate['role'])
    return result

def api_projection(value,abi):
    """Re-decode raw SDK bytes before trusting the producer's parsed projection."""
    if value.get('decode_error'):raise ValueError('Producer could not decode raw layout')
    if (value['handle_inheritable'] is not False or value['write_denied'] is not True or
            value['write_success'] is not False or value['write_bytes']!=0 or value['write_winerror'] not in (5,19)):
        raise ValueError('Read-only capability control')
    if set(value['queries'])!={'length','geometry','device','layout'}:raise ValueError('Required query set')
    for name,row in value['queries'].items():
        raw=bytes.fromhex(row['raw_hex'])
        if (row['control']!=abi['query_controls'][name] or row['returned_bytes']!=len(raw) or
                len(raw)>65536 or type(row['success']) is not bool or (row['success'] and row['winerror']!=0)):
            raise ValueError('Raw query relationship')
    for name in ('length','geometry','device'):
        if not value['queries'][name]['success']:raise ValueError('Required identity query failed')
    length=bytes.fromhex(value['queries']['length']['raw_hex']);geometry=bytes.fromhex(value['queries']['geometry']['raw_hex'])
    device=bytes.fromhex(value['queries']['device']['raw_hex'])
    if (len(length)!=8 or struct.unpack('<q',length)[0]!=4194304 or value['disk_bytes']!='4194304' or
            len(geometry)<32 or struct.unpack_from('<I',geometry,20)[0]!=512 or value['sector_bytes']!=512 or
            struct.unpack_from('<q',geometry,24)[0]!=4194304 or value['geometry_disk_bytes']!='4194304' or
            len(device)!=12 or tuple(value[k] for k in ('device_type','device_number','partition_number'))!=struct.unpack('<III',device)):
        raise ValueError('Identity/geometry contradiction')
    layout=value['queries']['layout']
    if not layout['success']:return None  # A real refusal is retained, not a table.
    raw=bytes.fromhex(layout['raw_hex']);offset,width=abi['layout_entries_offset'],abi['partition_bytes']
    if offset!=48 or width!=144 or len(raw)<offset:raise ValueError('Unqualified layout ABI')
    style,count=struct.unpack_from('<II',raw)
    if style not in (0,1,2) or count>128 or len(raw)<offset+count*width or style!=value['style'] or count!=value['partition_count'] or len(value['partitions'])!=count:
        raise ValueError('Layout header contradiction')
    if style==0 and value['disk_signature']!=struct.unpack_from('<I',raw,8)[0]:raise ValueError('MBR signature contradiction')
    if style==1 and value['disk_guid']!=str(uuid.UUID(bytes_le=raw[8:24])):raise ValueError('GPT disk identity contradiction')
    projected=[]
    for index,row in enumerate(value['partitions']):
        start=offset+index*width;kind=struct.unpack_from('<I',raw,start)[0]
        first,length=struct.unpack_from('<qq',raw,start+8);number=struct.unpack_from('<I',raw,start+24)[0]
        if (row['index']!=index or row['style']!=kind or row['number']!=number or
                row['offset_bytes']!=str(first) or row['length_bytes']!=str(length) or row['rewrite_partition']!=(raw[start+28]!=0)):
            raise ValueError('Partition/raw contradiction')
        if kind==0:
            if (row['type']!=raw[start+32] or row['boot_indicator']!=(raw[start+33]!=0) or
                    row['recognized']!=(raw[start+34]!=0) or row['hidden_sectors']!=struct.unpack_from('<I',raw,start+36)[0]):
                raise ValueError('MBR/raw contradiction')
            entry_type=format(row['type'],'x')
        elif kind==1:
            if (row['type_guid']!=str(uuid.UUID(bytes_le=raw[start+32:start+48])) or
                    row['unique_guid']!=str(uuid.UUID(bytes_le=raw[start+48:start+64])) or
                    row['attributes']!=str(struct.unpack_from('<Q',raw,start+64)[0]) or
                    row['name_utf16le_hex']!=raw[start+72:start+144].hex()):
                raise ValueError('GPT/raw contradiction')
            entry_type=row['type_guid']
        else:
            if length:raise ValueError('Unknown active partition style')
            continue
        if length==0:continue
        if first<0 or length<0 or first%512 or length%512 or first+length>4194304:
            raise ValueError('Partition extent contradiction')
        projected.append(dict(start=first//512,end=(first+length)//512,type=entry_type))
    return dict(label={0:'dos',1:'gpt',2:'raw'}[style],rows=projected)
