"""Independent generated attribute-list spans and Python integer/struct oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

TRUNCATED, LENGTH, ALIGNMENT, NAME, VCN, TYPE, BUDGET = (1, 2, 4, 8, 16, 32, 64)
HEADER = struct.Struct('<IHBBQQH')


def entry(kind=0x80, name=b'', at=26, vcn=0, record=0, sequence=0, identifier=9, size=None):
    assert len(name) % 2 == 0 and len(name) <= 510
    size = size if size is not None else (max(26, at + len(name) if name else 0) + 7) // 8 * 8
    raw = bytearray(size)
    HEADER.pack_into(raw, 0, kind, size, len(name)//2, at, vcn, record | sequence << 48, identifier)
    if name:
        assert at >= 26 and at+len(name) <= size
        raw[at:at+len(name)] = name
    return raw


def expected(raw, budget=4096, major=3, minor=1):
    if major != 3 or minor not in (0, 1):
        return dict(init_status=1, cursor_unchanged=True)
    if not 1 <= budget <= 4096:
        return dict(init_status=7, cursor_unchanged=True)
    result = dict(init_status=0, cursor_unchanged=False, items=[], count=0, offset='0', issues=0,
                  terminated=not raw, stopped=False, empty_unchanged=True)
    position = 0
    while position < len(raw):
        remaining = len(raw)-position
        row = dict(type=0, record_length=0, name_length=0, name_offset=0, lowest_vcn='0',
                   segment_reference='0', record_number='0', sequence=0, attribute_id=0,
                   raw_bytes=str(remaining), name_hex='', present=False, envelope_valid=False, issues=0)
        if result['count'] == budget:
            row['issues'] = BUDGET
            result['stopped'] = True
        elif remaining < HEADER.size:
            row['issues'] = TRUNCATED
            result['stopped'] = True
        else:
            kind, size, count, at, vcn, reference, identifier = HEADER.unpack_from(raw, position)
            row.update(type=kind, record_length=size, name_length=count, name_offset=at,
                       lowest_vcn=str(vcn), segment_reference=str(reference),
                       record_number=str(reference % (1 << 48)), sequence=reference >> 48,
                       attribute_id=identifier, present=True)
            result['count'] += 1
            faults = set()
            if kind not in range(16, 257, 16):faults.add(TYPE)
            if vcn >= 1 << 63:faults.add(VCN)
            if size < HEADER.size or size > remaining:faults.add(LENGTH)
            if size > remaining:faults.add(TRUNCATED)
            if size % 8:faults.add(ALIGNMENT)
            framed = size >= HEADER.size and size <= remaining and size % 8 == 0
            if framed:
                row['raw_bytes'] = str(size)
                if count:
                    if at < HEADER.size or at + count*2 > size:faults.add(NAME)
                    else:row['name_hex'] = raw[position+at:position+at+count*2].hex()
                row['envelope_valid'] = not (faults-{TYPE})
                position += size
                result['terminated'] = position == len(raw)
            else:result['stopped'] = True
            row['issues'] = sum(faults)
        result['items'].append(row)
        result['issues'] |= row['issues']
        if result['stopped']:break
    result['offset'] = str(position)
    return result


def scenarios():
    def case(name, raw, **controls):
        values=dict(budget=4096,major=3,minor=1);values.update(controls)
        request=dict(hex=bytes(raw).hex(),**{k:str(v) for k,v in values.items()})
        return name, request, expected(raw, **values)
    for minor in (0, 1):
        yield case(f'empty-{minor}', b'', minor=minor)
        yield case(f'unnamed-{minor}', entry(at=255), minor=minor)
        yield case(f'named-{minor}', entry(name='original'.encode('utf-16-le')), minor=minor)
    normal=entry(name=b'a\0')
    for size in range(len(normal)):
        yield case(f'all-header-and-name-prefixes-{size}', normal[:size])
    for size in range(1, 26):yield case(f'nonempty-trailer-{size}', entry()+bytes(size))
    for size in (0,1,2,7,8,16,24,25,26,27,28,31,32,33,40,65528,65535):
        raw=entry();struct.pack_into('<H',raw,4,size)
        yield case(f'declared-length-{size}',raw)
    yield case('full-maximum-framed-entry',entry(size=65528))
    yield case('beyond-file-record-limit',entry(size=49160))
    for at in range(256):
        raw=entry(name=b'N\0');raw[7]=at
        yield case(f'every-name-offset-{at}',raw)
    for count in (0,1,2,3,4,127,254,255):
        raw=entry();raw[6]=count
        yield case(f'name-length-bound-{count}',raw)
    for at in (26,27,31,255):
        for name in (b'\0\0',b'\0\xd8',b'\xff\xdf',bytes(range(256))*1+b'\x1b\0'):
            yield case(f'lossless-name-{at}-{len(name)}-{name[:2].hex()}',entry(name=name,at=at))
    yield case('maximum-raw-name',entry(name=bytes(range(255))*2,at=255))
    for reference in (0,1,2**32-1,2**32,2**48-1):
        for sequence in (0,1,32768,65535):
            yield case(f'reference-{reference}-{sequence}',entry(record=reference,sequence=sequence,identifier=65535))
    for value in (0,1,2**32,2**63-1,2**63,2**64-1):
        yield case(f'lowest-vcn-{value}',entry(vcn=value))
    for kind in list(range(16,257,16))+[0,1,15,17,257,2**31,2**32-1]:
        yield case(f'type-{kind}',entry(kind=kind))
    yield case('record-marker-is-truncated-tail',b'\xff'*4)
    yield case('unknown-type-is-not-terminator',entry(kind=2**32-1)+entry())
    yield case('zero-tail-is-not-silently-stripped',entry()+bytes(8))
    invalid_name=entry();invalid_name[6]=255
    yield case('bounded-invalid-name-continues',invalid_name+entry())
    yield case('negative-vcn-continues',entry(vcn=2**63)+entry())
    for budget in (0,1,2,3,4096,4097,65535):
        yield case(f'budget-{budget}',entry()*2,budget=budget)
    yield case('maximum-exact-budget',entry()*4096)
    yield case('single-exact-budget',entry(),budget=1)
    yield case('budget-before-short-tail',entry()+b'\xff',budget=1)
    yield case('maximum-budget-prefix',entry()*4097)
    yield case('million-byte-value-budget-prefix',entry()+bytes(1048576-32),budget=1)
    for major,minor in ((2,0),(3,2),(65535,0),(3,65535)):
        yield case(f'unsupported-profile-{major}-{minor}',entry(),major=major,minor=minor)
    randomizer=random.Random(0x4c495354)
    for index in range(128):
        name=bytes(randomizer.randrange(256) for _ in range(randomizer.randrange(24)*2))
        raw=entry(kind=randomizer.choice(list(range(16,257,16))),name=name,at=randomizer.randrange(26,80),
                  vcn=randomizer.randrange(2**63),record=randomizer.randrange(2**48),
                  sequence=randomizer.randrange(65536),identifier=randomizer.randrange(65536))
        yield case(f'generated-valid-{index}',raw)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();records=[];batch=[];size=0
    def evaluate(rows):
        data=json.dumps([request for _,request,_ in rows]).encode()
        result=subprocess.run([args.probe],input=data,capture_output=True,timeout=30)
        assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr.decode(errors='replace'))
        outputs=json.loads(result.stdout);assert len(outputs)==len(rows)
        for (name,request,wanted),observed in zip(rows,outputs):
            assert observed.pop('source_unchanged'),name
            assert observed==wanted,(name,wanted,observed)
            records.append(dict(case=name,input_sha256=hashlib.sha256(bytes.fromhex(request['hex'])).hexdigest(),
                                result_sha256=hashlib.sha256(json.dumps(observed,sort_keys=True,separators=(',',':')).encode()).hexdigest(),passed=True))
    for row in scenarios():
        cost=len(row[1]['hex'])
        if batch and (len(batch)==16 or size+cost>524288):evaluate(batch);batch=[];size=0
        batch.append(row);size+=cost
    if batch:evaluate(batch)
    Path(args.output).write_text(json.dumps(dict(count=len(records),cases=records,scope='Supplied-byte NTFS attribute-list envelopes, not resolved references or streams',physical_devices=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'{len(records)} protected-byte NTFS list cases passed')


if __name__=='__main__':main()
