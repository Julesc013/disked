"""Generated protected FILE records with independent attribute span expectations."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path

U64 = (1 << 64)-1


def resident(value=b'abc', name=b'', flags=0, name_offset=None, value_offset=None,
             kind=0x80, instance=7, resident_flags=0):
    assert len(name) % 2 == 0 and len(name) <= 510
    no = 24 if name_offset is None else name_offset
    vo = (no+len(name)+7)//8*8 if value_offset is None else value_offset
    size = (max(24, no+len(name) if name else 0, vo+len(value))+7)//8*8
    raw = bytearray(size)
    struct.pack_into('<IIBBHHH',raw,0,kind,size,0,len(name)//2,no,flags,instance)
    struct.pack_into('<IHBB',raw,16,len(value),vo,resident_flags,0)
    if name: raw[no:no+len(name)] = name
    raw[vo:vo+len(value)] = value
    expected = dict(type=kind,record_length=size,form=0,name_length=len(name)//2,name_offset=no,
                    flags=flags,instance=instance,value_length=len(value),value_offset=vo,
                    resident_flags=resident_flags,name_hex=name.hex(),value_hex=value.hex(),mapping_hex='',
                    present=True,end_marker=False,variant_fields=True,envelope_valid=True,ordinary_mapping=False,
                    issues=(32 if flags or resident_flags & 0xfe else 0) | (512 if kind<16 or kind>256 or kind%16 else 0))
    return raw,expected


def nonresident(pairs=b'\x11\x03\x14\0',name=b'',flags=0,low=0,high=2,
                allocated=12288,data=8,initialized=5,total=4096,unit=0,kind=0x80):
    first = low == 0
    extended = first and bool(flags & 0x80ff)
    header = 72 if extended else 64
    no = header
    mo = (no+len(name)+7)//8*8
    size = (mo+len(pairs)+7)//8*8
    raw = bytearray(size)
    struct.pack_into('<IIBBHHH',raw,0,kind,size,1,len(name)//2,no,flags,9)
    struct.pack_into('<QQHHIQQQ',raw,16,low,high,mo,unit,0,allocated,data,initialized)
    if extended: struct.pack_into('<Q',raw,64,total)
    raw[no:no+len(name)] = name
    raw[mo:mo+len(pairs)] = pairs
    empty = first and high == U64 and not any((allocated,data,initialized,total if extended else 0))
    issues = 32 if flags & 0x7fff or unit else 0
    if kind<16 or kind>256 or kind%16: issues |= 512
    if first and (any(number >= (1 << 63) for number in (allocated,data,initialized,total if extended else 0)) or
                  initialized>data or flags==0 and data>allocated): issues |= 128
    span = 0 if empty else high-low+1
    if not empty and (low >= (1 << 63) or high >= (1 << 63) or not 0 < span <= U64):
        issues |= 64
        span = 0
    expected = dict(type=kind,record_length=size,form=1,name_length=len(name)//2,name_offset=no,
                    flags=flags,instance=9,mapping_offset=mo,compression_unit=unit,
                    lowest_vcn=str(low),highest_vcn=str(high),cluster_span=str(span),
                    allocated_size=str(allocated),data_size=str(data),initialized_size=str(initialized),
                    total_allocated=str(total if extended else 0),name_hex=name.hex(),value_hex='',mapping_hex=bytes(raw[mo:]).hex(),
                    present=True,end_marker=False,variant_fields=True,sizes_applicable=first,has_total_allocated=extended,
                    empty_stream=empty,issues=issues,envelope_valid=not bool(issues & ~(32|512)),
                    ordinary_mapping=not bool(issues))
    return raw,expected


def protected(payload):
    # Construct logical records first, then protect every stride independently.
    size = 512
    while True:
        offset = (48+2*(size//512+1)+7)//8*8
        needed = max(512,(offset+len(payload)+511)//512*512)
        if needed == size: break
        size = needed
    assert size <= 49152 and len(payload)>=4
    logical = bytearray(size)
    logical[:4] = b'FILE'
    struct.pack_into('<HHQHHHHIIQH',logical,4,48,size//512+1,0,3,1,offset,1,
                     offset+len(payload),size,0,8)
    logical[offset:offset+len(payload)] = payload
    raw = bytearray(logical)
    tails = [bytes(logical[end-2:end]) for end in range(512,size+1,512)]
    struct.pack_into('<H',raw,48,0x57c3)
    for index,tail in enumerate(tails):
        raw[50+index*2:52+index*2] = tail
        raw[(index+1)*512-2:(index+1)*512] = b'\xc3\x57'
    return raw,offset


def scenarios():
    end = dict(present=False,end_marker=True,issues=0)
    def case(name,attributes,marker=True,slack=b'',budget=4096,stop=False,extra=None,advance=None,**controls):
        payload = b''.join(bytes(item[0]) for item in attributes)
        raw,offset = protected(payload+(b'\xff'*4 if marker else b'')+slack)
        items = [item[1] for item in attributes]
        issues = 0
        for item in items: issues |= item.get('issues',0)
        if extra is not None:
            items.append(extra)
            issues |= extra['issues']
        elif marker and not stop:
            items.append(end)
        request = dict(op='attrs',hex=raw.hex(),budget=str(budget),major='3',minor='1')
        request.update(controls)
        count = sum(bool(item.get('present',True)) for item in items)
        if advance is None: advance = sum(len(item[0]) for item in attributes)
        expected = dict(init_status=0,items=items,count=count,issues=issues,offset=offset+advance,
                        terminated=marker and not stop,stopped=stop)
        return name,request,expected
    for length in (0,1,2,7,8,127,255,510,1000,48000):
        value = bytes((i*37+9)%256 for i in range(length))
        yield case(f'resident-{length}',[resident(value,value_offset=0 if not length else None)])
    for name in (b'',b'A\0',b'\0\0',b'\0\xd8\x00\xdc',b'\x1b\0',bytes(range(255))*2):
        yield case('name-'+hashlib.sha256(name).hexdigest()[:8],[resident(b'abc',name)])
    yield case('unaligned-name-and-value',[resident(b'xyz',b'A\0B\0',name_offset=25,value_offset=29)])
    yield case('name-after-disjoint-value',[resident(b'abc',b'n\0',name_offset=30,value_offset=24)])
    raw,expected = resident(b'',value_offset=0)
    struct.pack_into('<H',raw,10,65535); expected['name_offset']=65535
    yield case('undefined-name-offset',[ (raw,expected) ])
    for flags in (0,1,2,0x4000,0x8000,65535):
        yield case(f'resident-flags-{flags}',[resident(flags=flags)])
    for flags in (0,1,2,128,255):
        yield case(f'resident-variant-flags-{flags}',[resident(resident_flags=flags)])
    for kind in (0,0x10,0x80,0x100,0x101,0x300):
        yield case(f'type-{kind}',[resident(kind=kind)])
    for flags in (0,1,2,0x4000,0x8000,0x8001,0x100,65535):
        yield case(f'nonresident-flags-{flags}',[nonresident(flags=flags,name=b'n\0')])
    for low,high in ((0,0),(0,2),(7,10),(10,7),(U64-1,U64-1),(U64,U64),(0,U64)):
        yield case(f'vcn-{low}-{high}',[nonresident(low=low,high=high)])
    for flags in (0,0x8000,1):
        yield case(f'empty-stream-{flags}',[nonresident(b'\0',flags=flags,high=U64,allocated=0,data=0,initialized=0,total=0)])
    yield case('empty-with-nonzero-physical',[nonresident(b'\0',flags=0x8000,high=U64,allocated=0,data=0,initialized=0,total=1)])
    yield case('continuation-undefined-sizes',[nonresident(flags=0x8000,low=7,high=10,allocated=0,data=U64,initialized=U64)])
    for allocated,data,initialized in ((0,1,0),(4096,5,6),(4096,8,5),(U64,U64,U64),(0,0,0)):
        yield case(f'sizes-{allocated}-{data}-{initialized}',[nonresident(allocated=allocated,data=data,initialized=initialized)])
    for value in ((1 << 63)-1, 1 << 63, U64):
        yield case(f'signed-size-boundary-{value}',[nonresident(allocated=value,data=value,initialized=value)])
        yield case(f'signed-vcn-boundary-{value}',[nonresident(low=value,high=value)])
        yield case(f'signed-total-boundary-{value}',[nonresident(flags=0x8000,total=value)])
    for unit in (0,1,4,256,65535):
        yield case(f'compression-unit-{unit}',[nonresident(unit=unit)])
    for location,encoding,values,issue in (
        (10,'H',(0,15,23,65535),8),
        (16,'I',(0xffffffff,),16),
        (20,'H',(0,23,65535),16)):
        for value in values:
            raw,expected = resident(b'abc',b'n\0')
            struct.pack_into('<'+encoding,raw,location,value)
            expected = dict(present=True,issues=issue,envelope_valid=False)
            # ValueOffset0/23 overlaps the header, but does not expose bytes.
            yield case(f'resident-span-{location}-{value}',[(raw,expected)])
    raw,expected = resident(b'abc',b'n\0')
    struct.pack_into('<H',raw,20,24)
    yield case('name-value-overlap',[(raw,dict(present=True,issues=8,envelope_valid=False))])
    for mo in (0,63,65535):
        raw,expected = nonresident(name=b'n\0')
        struct.pack_into('<H',raw,32,mo)
        yield case(f'mapping-offset-{mo}',[(raw,dict(present=True,issues=256,envelope_valid=False))])
    normal,_ = resident()
    for length in (0,1,15,17,65535,0xffffffff):
        raw = bytearray(normal)
        struct.pack_into('<I',raw,4,length)
        yield case(f'bad-length-{length}',[(raw,dict(present=True,issues=2,envelope_valid=False))],stop=True,advance=0)
    for size in range(4,24):
        raw = normal[:size]
        present = size >= 16
        issue = 2 if present else 1
        yield case(f'prefix-{size}',[(raw,dict(present=present,issues=issue,envelope_valid=False))],marker=False,stop=True,advance=0)
    raw = bytearray(normal[:16]); struct.pack_into('<I',raw,4,16)
    yield case('short-variant',[(raw,dict(present=True,issues=2,variant_fields=False,envelope_valid=False))])
    raw = bytearray(normal); raw[8]=2
    yield case('unknown-form',[(raw,dict(present=True,issues=4,envelope_valid=False))])
    raw,_ = nonresident()
    raw = raw[:56]; struct.pack_into('<I',raw,4,56)
    yield case('short-nonresident-variant',[(raw,dict(present=True,issues=2,variant_fields=False,envelope_valid=False))])
    raw,_ = nonresident(flags=0x8000)
    raw = raw[:64]; struct.pack_into('<I',raw,4,64)
    yield case('missing-extended-total',[(raw,dict(present=True,issues=258,variant_fields=True,has_total_allocated=False,envelope_valid=False))])
    yield case('missing-marker',[resident()],marker=False,stop=True,extra=dict(present=False,end_marker=False,issues=2049))
    yield case('marker-slack',[resident()],slack=bytes(range(256)))
    first,second = resident(b'one'),resident(b'two',instance=8)
    name,request,expected = case('one-item-budget',[first,second],budget=1,stop=True,advance=len(first[0]))
    expected['items']=[first[1],dict(present=False,issues=1024)]
    expected['count']=1; expected['issues']=1024
    yield name,request,expected
    yield case('exact-item-budget',[first,second],budget=2)
    for controls,status in ((dict(budget='0'),7),(dict(budget='4097'),7),(dict(capacity='0'),3),
                            (dict(alias='same'),1),(dict(alias='forward'),1),(dict(alias='backward'),1),
                            (dict(major='2'),1),(dict(minor='2'),1)):
        name,request,_ = case('init-'+str(controls),[resident()])
        request.update(controls)
        yield name,request,dict(init_status=status,cursor_unchanged=True,destination_unchanged=True)
    name,request,_ = case('torn-record',[resident()])
    raw = bytearray.fromhex(request['hex']); raw[510]^=1; request['hex']=raw.hex()
    yield name,request,dict(init_status=1,cursor_unchanged=True,destination_unchanged=True)
    name,request,_ = case('record-budget',[resident()]); request['hex']=bytes(49153).hex()
    yield name,request,dict(init_status=7,cursor_unchanged=True,destination_unchanged=True)
    rng = random.Random(0x41545452)
    for index in range(128):
        value = bytes(rng.randrange(256) for _ in range(rng.randrange(512)))
        name = bytes(rng.randrange(256) for _ in range(rng.randrange(16)*2))
        yield case(f'generated-valid-{index}',[resident(value,name,instance=index)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe',required=True); parser.add_argument('--output',required=True)
    args = parser.parse_args()
    cases,records = list(scenarios()),[]
    for start in range(0,len(cases),16):
        batch = cases[start:start+16]
        process = subprocess.run([args.probe],input=json.dumps([row for _,row,_ in batch]).encode(),capture_output=True,timeout=30)
        assert process.returncode == 0,(start,process.returncode,process.stderr.decode(errors='replace'))
        actual = json.loads(process.stdout)
        assert len(actual)==len(batch)
        for (name,request,expected),observed in zip(batch,actual):
            for key,value in expected.items():
                if key=='items':
                    assert len(observed['items'])==len(value),(name,len(value),observed['items'])
                    for index,item in enumerate(value):
                        for field,wanted in item.items():
                            assert observed['items'][index].get(field)==wanted,(name,index,field,wanted,observed['items'][index].get(field))
                else:
                    assert observed.get(key)==value,(name,key,value,observed.get(key))
            assert observed['source_unchanged'],name
            records.append(dict(case=name,input_sha256=hashlib.sha256(bytes.fromhex(request['hex'])).hexdigest(),passed=True,
                                init_status=observed['init_status'],issues=observed.get('issues')))
    Path(args.output).write_text(json.dumps(dict(count=len(records),cases=records,physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'{len(records)} post-fixup NTFS attribute cases passed; no volume/content authority')


if __name__=='__main__':
    main()
