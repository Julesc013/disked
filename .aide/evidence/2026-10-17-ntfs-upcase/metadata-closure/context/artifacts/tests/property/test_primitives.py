"""Independent integer/byte oracle for the actual C portable implementation."""
import argparse,json,random,subprocess,unittest
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--probe',type=Path,required=True);P.add_argument('--evidence',type=Path)
A,REST=P.parse_known_args();A.probe=A.probe.resolve();OBS=[];MAX=(1<<64)-1
profile=subprocess.run([str(A.probe),'profile'],capture_output=True,text=True,timeout=5)
if profile.returncode or profile.stderr:raise RuntimeError('Native profile failed: '+repr(profile))
PROFILE=profile.stdout.strip();FIELDS={k:int(v) for k,v in (x.split('=') for x in PROFILE.split()[1:])}
SIZE_MAX=(1<<FIELDS['size'])-1

def extent(n,unit,start,length,inclusive=False):
    if unit>0xffffffff:return 'refused width'
    if not 1<=unit<=1048576:return 'refused unit'
    if inclusive:
        if length<start:return 'refused underflow'
        if length==MAX:return 'refused overflow'
        length=length-start+1
    if not length:return 'refused empty'
    end=start+length
    if end>MAX:return 'refused overflow'
    if end>n:return 'refused bounds'
    if end*unit>MAX:return f'block {end} bytes_refused overflow'
    return f'ok {end} {start*unit} {end*unit} {length}'

class Portable(unittest.TestCase):
    def batch(self,name,cases):
        text=''.join(' '.join(map(str,args))+'\n' for args,expected in cases)
        process=subprocess.run([str(A.probe)],input=text,capture_output=True,text=True,encoding='ascii',timeout=30)
        actual=process.stdout.splitlines();rows=[]
        for i,(args,expected) in enumerate(cases):
            got=actual[i] if i<len(actual) else None
            rows.append(dict(arguments=args,expected=expected,actual=got,passed=got==expected))
        OBS.append(dict(test=name,exit_code=process.returncode,stderr=process.stderr,lines=len(actual),cases=rows))
        self.assertEqual((0,''),(process.returncode,process.stderr),name)
        self.assertEqual(len(cases),len(actual),name)
        for row in rows:self.assertEqual(row['expected'],row['actual'],str(row['arguments']))

    def test_checked_arithmetic(self):
        r=random.Random(20201020);edge=sorted({0,1,2,MAX,*(min(MAX,(1<<b)+d) for b in [8,16,32,48,63] for d in [-1,0,1])})
        pairs=[(a,b) for a in edge for b in edge]+[(r.getrandbits(r.randrange(65)),r.getrandbits(r.randrange(65))) for _ in range(400)]
        cases=[]
        for a,b in pairs:
            cases.extend([(['add',a,b],f'ok {a+b}' if a+b<=MAX else 'refused overflow'),
                (['sub',a,b],f'ok {a-b}' if a>=b else 'refused underflow'),
                (['mul',a,b],f'ok {a*b}' if a*b<=MAX else 'refused overflow'),
                (['div',a,b],f'ok {a//b} {a%b}' if b else 'refused divzero')])
        cases.extend((['size',n],f'ok {n}' if n<=SIZE_MAX else 'refused width') for n in edge+[0xffffffff,0x100000000,MAX])
        self.batch('checked arithmetic and target size',cases)

    def test_extents_and_units(self):
        r=random.Random(31020);cases=[]
        for unit in [0,1,3,512,520,4096,1048576,1048577,0xffffffff,0x100000000]:
            for n,s,length in [(0,0,0),(0,0,1),(10,0,10),(10,9,1),(10,10,1),(10,10,0),(10,11,1),(MAX,0,MAX),(MAX,MAX,1),(MAX,MAX-1,1),(MAX,MAX-1,2),(MAX,1,MAX)]:
                cases.append((['extent',n,unit,s,length],extent(n,unit,s,length)))
            for n,s,last in [(10,0,9),(10,9,9),(10,0,10),(10,5,4),(MAX,MAX-1,MAX-1),(MAX,0,MAX),(0,0,0)]:
                cases.append((['inclusive',n,unit,s,last],extent(n,unit,s,last,True)))
        for _ in range(500):
            n=r.getrandbits(r.randrange(65));s=r.randrange(n+1);length=r.randrange(n-s+2);unit=r.choice([1,3,520,4096,1048576])
            cases.append((['extent',n,unit,s,length],extent(n,unit,s,length)))
            cases.append((['inclusive',n,unit,s,min(MAX,s+length)],extent(n,unit,s,min(MAX,s+length),True)))
        self.batch('half-open extents, inclusive conversion and byte projection',cases)

    def test_space_geometry_and_overlap(self):
        cases=[]
        for unit in [0,1,3,520,1048576,1048577,0x100000000]:
            for n in [0,1,3,519,520,521,MAX]:
                expected='refused width' if unit>0xffffffff else 'refused unit' if not 1<=unit<=1048576 else 'refused alignment' if n%unit else f'ok {n//unit}'
                cases.append((['spacebytes',n,unit],expected))
        r=random.Random(881)
        pairs=[(0,1,1,1),(0,10,1,8),(0,1,0,1),(9,1,0,9),(0,0,0,1)]
        pairs += [(r.randrange(50),r.randrange(51),r.randrange(50),r.randrange(51)) for _ in range(300)]
        for s1,l1,s2,l2 in pairs:
            for same in [0,1]:
                expected='refused empty' if not l1 or not l2 else 'refused space' if not same else f'ok {int(s1<s2+l2 and s2<s1+l1)} {int(s1<=s2 and s1+l1>=s2+l2)}'
                cases.append((['overlap',100,520,s1,l1,s2,l2,same],expected))
        self.batch('exact units and immutable space separation',cases)

    def test_bounded_views(self):
        cases=[];data=bytes(range(64))
        for size in [0,1,7,8,9,32,64]:
            for offset in [0,1,7,8,size,max(0,size-1),size+1,MAX,0x100000000]:
                for length in [0,1,2,8,64,MAX]:
                    expected='refused width' if offset>SIZE_MAX or length>SIZE_MAX else 'refused bounds' if offset>size or length>size-offset else f'ok {length} '+data[offset:offset+length].hex()
                    cases.append((['slice',offset,length,size],expected))
        self.batch('native-size conversion and bounded empty/unaligned views',cases)

    def test_endian_reads_writes(self):
        cases=[];data=bytes(range(64))
        for size in [0,1,7,8,9,64]:
            for offset in [0,1,2,7,8,63,64,MAX]:
                for width in [0,1,2,3,4,8,16]:
                    for order in [0,1,2]:
                        failure='width' if offset>SIZE_MAX else 'invalid' if width not in [1,2,4,8] or order not in [0,1] else 'bounds' if offset>size or width>size-offset else None
                        expected='refused '+failure if failure else 'ok '+str(int.from_bytes(data[offset:offset+width],'little' if order==0 else 'big'))
                        cases.append((['read',offset,width,order,size],expected))
                        n=min(MAX,(1<<(8*min(width,8)))-1) if width else 1
                        for value in [0,n,min(MAX,n+1),MAX]:
                            error=failure or ('width' if value >= (1<<(width*8)) else None)
                            if error:expected='refused '+error
                            else:
                                out=bytearray(data);out[offset:offset+width]=value.to_bytes(width,'little' if order==0 else 'big');expected='ok '+out.hex()
                            cases.append((['write',offset,width,order,value,size],expected))
        self.batch('unaligned endian read/write and unchanged refusal buffers',cases)

    def test_aliases_and_invalid_internal_objects(self):
        self.batch('native output sentinels and invalid internal object checks', [(['selftest'],'ok unchanged_outputs_aliases_invalid_objects')])

if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    record=dict(passed=result.result.wasSuccessful(),tests=result.result.testsRun,cases=sum(len(x['cases']) for x in OBS),profile=PROFILE,observations=OBS)
    if A.evidence:A.evidence.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not record['passed'])
