"""Synthetic sparse-image oracle. Never opens a device, mounts, or runs image bytes."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
import unittest
from pathlib import Path

SIGNATURE, BOOT, INACTIVE, RANGE, OVERLAP = 1, 2, 4, 8, 16
PROTECTIVE, HYBRID, CHS, TRUNCATED, LAYOUT = 32, 64, 128, 256, 512
CYCLE, BUDGET, METADATA, UNAVAILABLE = 1024, 2048, 4096, 8192


def chs(lba, heads=16, sectors=63):
    cylinder, rem = divmod(lba, heads * sectors)
    head, sector = divmod(rem, sectors)
    assert cylinder < 1024
    return bytes([head, sector + 1 + ((cylinder >> 8) << 6), cylinder & 255])


def entry(kind=0, start=0, count=0, boot=0, first=b'\0'*3, last=b'\0'*3):
    return bytes([boot]) + first + bytes([kind]) + last + struct.pack('<II', start, count)


def block(entries=(), unit=512, opaque=False):
    data = bytearray(unit)
    if opaque:
        data[:446] = bytes((i * 17 + 1) % 256 for i in range(446))
        data[512:] = b'\x9b' * (unit - 512)
    for i, value in enumerate(entries):
        data[446+16*i:462+16*i] = value
    data[510:512] = b'\x55\xaa'
    return data


def request(image, blocks=100, unit=512, limit=128, heads=0, sectors=0):
    return dict(blocks=str(blocks), unit=str(unit), limit=str(limit), heads=str(heads),
                sectors=str(sectors), image={str(k): bytes(v).hex() for k, v in image.items()})


def corpus():
    cases = []
    def add(name, data, **expected):
        cases.append(dict(name=name, input=data, expected=expected))
    add('empty', request({0: block()}), mbr_issues=0, root_extents=[])
    for unit in (512, 520, 4096, 1048576):
        # The largest unit exercises a complete block, not an assumption of 512 bytes.
        add('device-end-unit-'+str(unit), request({0:block([entry(7,90,10)],unit,True)},unit=unit),
            mbr_issues=0, root_extents=[['90','100']])
    add('u32-end-widened', request({0:block([entry(7,0xffffffff,0xffffffff)])},blocks=8589934590),
        mbr_issues=0, root_extents=[['4294967295','8589934590']])
    add('one-past-device', request({0:block([entry(7,90,11)])}),mbr_issues=RANGE,root_extents=[])
    add('metadata-zero',request({0:block([entry(7,0,10)])}),mbr_issues=METADATA)
    add('adjacent-primary',request({0:block([entry(7,1,9),entry(0x83,10,90)])}),mbr_issues=0)
    add('overlap-primary',request({0:block([entry(7,1,10),entry(0x83,10,90)])}),mbr_issues=OVERLAP)
    add('odd-boot-flag',request({0:block([entry(7,1,10,3)])}),mbr_issues=BOOT)
    add('inactive-type',request({0:block([entry(0,1,10)])}),mbr_issues=INACTIVE,root_extents=[])
    add('inactive-count',request({0:block([entry(7,1,0)])}),mbr_issues=INACTIVE,root_extents=[])
    no_signature=block([entry(7,1,10)]);no_signature[510]=0
    add('no-signature-no-entries',request({0:no_signature}),mbr_issues=SIGNATURE,root_extents=[])
    for length in (0,1,445,446,461,462,509,510,511):
        add('short-mbr-'+str(length),request({0:block()[:length]}),mbr_issues=TRUNCATED,root_extents=[])
    add('short-non512',request({0:block()},unit=520),mbr_issues=TRUNCATED)
    add('oversized-block',request({0:block(unit=520)}),status=7)
    add('too-small-unit',request({0:b''},unit=1),status=9)
    add('empty-space',request({0:block()},blocks=0),status=7)
    for blocks,count in ((100,99),(4294967296,4294967295),(18446744073709551615,4294967295)):
        add('protective-'+str(blocks),request({0:block([entry(0xee,1,count,first=b'\0\x02\0',last=b'\xff'*3)])},blocks=blocks),mbr_issues=0)
    pmbr=block([entry(0xee,1,99,first=b'\0\x02\0',last=b'\xff'*3)])
    add('hybrid',request({0:block([entry(0xee,1,99,first=b'\0\x02\0'),entry(7,10,5)])}),mbr_issues=PROTECTIVE|HYBRID|OVERLAP)
    add('protective-wrong-size',request({0:block([entry(0xee,1,98,first=b'\0\x02\0')])}),mbr_issues=PROTECTIVE)
    add('inactive-protective-is-not-hybrid',request({0:block([entry(0xee,1,0,first=b'\0\x02\0')])}),mbr_issues=INACTIVE|PROTECTIVE)
    add('inactive-protective-with-data-is-hybrid',request({0:block([entry(0xee,1,0,first=b'\0\x02\0'),entry(7,10,5)])}),mbr_issues=INACTIVE|PROTECTIVE|HYBRID)
    altered=bytearray(pmbr);altered[440]=1
    add('protective-reserved',request({0:altered}),mbr_issues=PROTECTIVE)
    add('protective-reserved-tail',request({0:pmbr+b'\0'*7+b'\x01'},unit=520),mbr_issues=PROTECTIVE)
    add('chs-correct',request({0:block([entry(7,10,10,first=chs(10),last=chs(19))])},heads=16,sectors=63),mbr_issues=0,chs_compared=2)
    add('chs-disagrees',request({0:block([entry(7,10,10,first=chs(11),last=chs(19))])},heads=16,sectors=63),mbr_issues=CHS,chs_compared=2)
    add('chs-unknown-geometry',request({0:block([entry(7,10,10,first=chs(11),last=chs(19))])}),mbr_issues=0,chs_compared=0)
    add('chs-saturated',request({0:block([entry(7,10,10,first=b'\xfe\xff\xff',last=b'\xff'*3)])},heads=16,sectors=63),mbr_issues=0,chs_compared=0)
    add('chs-malformed',request({0:block([entry(7,10,10,first=b'\x01\0\0')])},heads=16,sectors=63),mbr_issues=CHS)
    add('incomplete-geometry',request({0:block()},heads=16),status=1)

    def chain(kind=15,unit=512):
        return {0:block([entry(kind,10,80)],unit,True),
                10:block([entry(7,1,5),entry(kind,20,60)],unit,True),
                30:block([entry(0x83,1,9)],unit,True)}
    for kind in (5,15,0x85):
        for unit in (512,520,4096):
            add('two-bases-'+str(kind)+'-'+str(unit),request(chain(kind,unit),unit=unit),mbr_issues=0,
                requests=['10','30'],complete=True,walk_issues=0,logical=[['11','16'],['31','40']])
    three=chain();three[30]=block([entry(7,1,9),entry(15,50,30)]);three[60]=block([entry(7,3,5)])
    add('third-link-original-base',request(three),requests=['10','30','60'],complete=True,walk_issues=0,
        logical=[['11','16'],['31','40'],['63','68']])
    for rel,addresses in ((0,['10','30']),(20,['10','30'])):
        cycle=chain();cycle[30]=block([entry(7,1,9),entry(15,rel,80-rel)])
        add('cycle-'+str(rel),request(cycle),requests=addresses,complete=False,walk_issues=CYCLE)
    add('budget',request(chain(),limit=1),requests=['10'],complete=False,walk_issues=BUDGET)
    add('zero-budget',request(chain(),limit=0),walk_status=1)
    for variation,record in [('logical-out',entry(7,79,2)),('link-out',entry(15,79,2))]:
        bad=chain();bad[10]=block([record] if variation=='logical-out' else [entry(7,1,5),record])
        add(variation,request(bad),requests=['10'],complete=False,walk_issues=RANGE)
    overlap=chain();overlap[10]=block([entry(7,1,25),entry(15,20,60)])
    add('logical-and-later-metadata-overlap',request(overlap),requests=['10','30'],complete=True,walk_issues=OVERLAP|METADATA)
    bad_metadata={k:bytearray(v) for k,v in overlap.items()};bad_metadata[30][511]=0
    add('bad-metadata-still-overlaps',request(bad_metadata),requests=['10','30'],complete=False,walk_issues=SIGNATURE|METADATA)
    own=chain();own[30]=block([entry(7,0,5)])
    add('own-ebr-overlap',request(own),complete=True,walk_issues=METADATA)
    reverse=chain();reverse[10]=block([entry(7,40,10),entry(15,20,60)]);reverse[30]=block([entry(7,0,30)])
    add('earlier-data-later-overlap',request(reverse),complete=True,walk_issues=METADATA|OVERLAP)
    adjacent={0:block([entry(15,10,190)]),10:block([entry(7,100,10),entry(15,20,170)]),30:block([entry(7,90,10)])}
    add('adjacent-logical',request(adjacent,blocks=200),complete=True,walk_issues=0,logical=[['110','120'],['120','130']])
    for size in (0,200,511):
        truncated=chain();truncated[30]=truncated[30][:size]
        add('short-ebr-'+str(size),request(truncated),requests=['10','30'],complete=False,walk_issues=TRUNCATED)
    missing=chain();del missing[30]
    add('unavailable-ebr',request(missing),requests=['10','30'],complete=False,walk_issues=UNAVAILABLE)
    bad=chain();bad[30][511]=0
    add('ebr-signature',request(bad),complete=False,walk_issues=SIGNATURE)
    for name,entries in [('link-slot-zero',[entry(15,20,60)]),('data-slot-one',[entry(7,1,5),entry(7,20,5)]),
                         ('extra-active',[entry(7,1,5),entry(),entry(7,20,5)]),('inactive-link',[entry(7,1,5),entry(15,20,0)])]:
        bad=chain();bad[10]=block(entries)
        add(name,request(bad),requests=['10'],complete=False,walk_issues=LAYOUT|(INACTIVE if name=='inactive-link' else 0))
    empty=chain();empty[10]=block([entry(),entry(15,20,60)])
    add('empty-data-link',request(empty),requests=['10','30'],complete=True,walk_issues=0,logical=[['31','40']])
    inactive=chain();inactive[30]=block([entry(7,1,9),entry(),entry(0,99,0)])
    add('preserve-unused-record',request(inactive),complete=True,walk_issues=INACTIVE)
    high={0:block([entry(15,0xffffffff,0xffffffff)]),
          0xffffffff:block([entry(7,1,4),entry(15,0x80000000,0x7fffffff)]),
          0x17fffffff:block([entry(7,1,5)])}
    add('ebr-addresses-widened',request(high,blocks=8589934590),requests=['4294967295','6442450943'],
        complete=True,walk_issues=0,logical=[['4294967296','4294967300'],['6442450944','6442450949']])
    many={0:block([entry(15,10,2000)])}
    for n in range(129):
        many[10+2*n]=block([entry(7,500+n,1)]+([entry(15,2*(n+1),2000-2*(n+1))] if n<128 else []))
    add('absolute-budget-128',request(many,blocks=2010),requests=[str(10+2*n) for n in range(128)],
        complete=False,walk_issues=BUDGET)
    # Construct layouts from absolute coordinates, then encode each of the two bases.
    rng=random.Random(210021)
    for i in range(220):
        count=128 if i==0 else rng.randint(1,20)
        base=rng.randint(1,100);end=base+2000;unit=rng.choice([512,520,4096]);kind=rng.choice([5,15,0x85])
        image={0:block([entry(kind,base,2000)],unit)};logical=[];addresses=[]
        for n in range(count):
            current=base+2*n;start=base+500+3*n;size=rng.randint(1,3)
            entries=[entry(7,start-current,size)];logical.append([str(start),str(start+size)]);addresses.append(str(current))
            if n+1<count:entries.append(entry(kind,2*(n+1),end-(base+2*(n+1))))
            image[current]=block(entries,unit,True)
        add('generated-chain-'+str(i),request(image,blocks=end,unit=unit),mbr_issues=0,requests=addresses,
            logical=logical,complete=True,walk_issues=0)
    # Deterministic mutations test bounded requests, opaque retention, and source immutability.
    for i in range(1000):
        image=chain();key=rng.choice(list(image));data=image[key]
        for _ in range(rng.randint(1,12)):data[rng.randrange(len(data))]=rng.randrange(256)
        if i%7==0:image[key]=data[:rng.randrange(512)]
        add('mutation-'+str(i),request(image,limit=rng.randint(1,8)))
    return cases


class Mbr(unittest.TestCase):
    def test_constructed_and_mutated_images(self):
        global RECORDS
        cases=corpus();wire=''.join(json.dumps(c['input'],separators=(',',':'))+'\n' for c in cases)
        run=subprocess.run([ARGS.probe],input=wire,text=True,capture_output=True,timeout=55)
        self.assertEqual(run.returncode,0,run.stderr)
        observations=[json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(observations),len(cases));records=[]
        for case,out in zip(cases,observations):
            with self.subTest(case=case['name']):
                expect=case['expected'];inp=case['input'];self.assertEqual(out['status'],expect.get('status',0))
                if not out['status']:
                    root=out['mbr'];self.assertEqual(root['raw'],inp['image']['0'])
                    if 'mbr_issues' in expect:self.assertEqual(root['issues'],expect['mbr_issues'])
                    actual_extents=[[e['start'],e['end']] for e in root['entries'] if e['range_valid']]
                    if 'root_extents' in expect:self.assertEqual(actual_extents,expect['root_extents'])
                    if 'chs_compared' in expect:self.assertEqual(root['entries'][0]['chs_compared'],expect['chs_compared'])
                    if any(k in expect for k in ('requests','complete','walk_issues','logical','walk_status')):
                        self.assertEqual(len(out['walks']),1);walk=out['walks'][0]
                        self.assertEqual(walk['status'],expect.get('walk_status',0))
                        for key in ('requests','complete'):
                            if key in expect:self.assertEqual(walk[key],expect[key])
                        if 'walk_issues' in expect:self.assertEqual(walk['issues'],expect['walk_issues'])
                        if 'logical' in expect:self.assertEqual([[e['start'],e['end']] for n in walk['nodes'] for e in n['entries'][:1] if e['range_valid']],expect['logical'])
                    for walk in out['walks']:
                        seen=walk['requests'];self.assertLessEqual(len(seen),int(inp['limit']))
                        self.assertEqual(len(seen),len(set(seen)))
                        parent=root['entries'][walk['slot']]
                        for lba in seen:self.assertTrue(int(parent['start'])<=int(lba)<int(parent['end']))
                        for node in walk['nodes']:self.assertEqual(node['raw'],inp['image'][node['lba']])
                    if out['walks'] and not any(k in expect for k in ('requests','complete','walk_issues','logical','walk_status')):
                        # Mutation results must still have an explicit terminal state.
                        for walk in out['walks']:
                            if not walk['complete']:self.assertTrue(walk['issues'] or walk['status'])
                    for t in [root]+[n for w in out['walks'] for n in w['nodes']]:
                        for i,e in enumerate(t['entries']):
                            if t['signature']:self.assertEqual(e['raw'],t['raw'][892+32*i:924+32*i])
                            if e['range_valid']:self.assertTrue(0<=int(e['start'])<int(e['end'])<=int(inp['blocks']))
                records.append(dict(name=case['name'],input_sha256=hashlib.sha256(json.dumps(inp,sort_keys=True).encode()).hexdigest(),
                                    output_sha256=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest(),expected=expect))
        RECORDS=records
        print('Checked',len(cases),'independently constructed/mutated synthetic image cases.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--probe',required=True);parser.add_argument('--evidence')
    ARGS=parser.parse_args();RECORDS=[]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mbr))
    if ARGS.evidence:
        Path(ARGS.evidence).write_text(json.dumps(dict(cases=len(RECORDS),passed=result.wasSuccessful(),observations=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
