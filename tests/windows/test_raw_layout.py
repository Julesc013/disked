"""Independent generated image/OS-layout comparison; ordinary files and injected API only."""
import argparse,copy,hashlib,json,struct,subprocess,sys,time,uuid,zlib
from pathlib import Path
from test_storage_queries import disk,packet,digest
from test_identity_queries import identifiers,alignment
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus'))
from partition_images import recipes,table,mbr_entry,DISK,TYPE

def gpt_image(unit=512,count=2):
    blocks=256;slots=128;array_size=slots*128;array_blocks=(array_size+unit-1)//unit
    first=2+array_blocks;last=blocks-2-array_blocks;data=bytearray(blocks*unit)
    data[:512]=table([mbr_entry(0xee,1,blocks-1)]);rows=bytearray(array_size);facts=[]
    for i in range(count):
        start=first+i*2;end=start;name=(('A'+str(i)) if count!=1 else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345678').encode('utf-16-le').ljust(72,b'\0')
        unique=uuid.UUID(int=i+1).bytes_le;attrs=0x1000000000000001;at=i*128
        rows[at:at+16]=TYPE.bytes_le;rows[at+16:at+32]=unique
        struct.pack_into('<QQQ',rows,at+32,start,end,attrs);rows[at+56:at+128]=name
        facts.append(dict(start=start*unit,length=unit,type=TYPE.bytes_le,guid=unique,attrs=attrs,name=name))
    for my,other,lba in [(1,blocks-1,2),(blocks-1,1,blocks-1-array_blocks)]:
        data[lba*unit:lba*unit+array_size]=rows
        struct.pack_into('<8sIIIIQQQQ16sQIII',data,my*unit,b'EFI PART',0x10000,92,0,0,my,other,first,last,DISK.bytes_le,lba,slots,128,zlib.crc32(rows))
        struct.pack_into('<I',data,my*unit+16,zlib.crc32(data[my*unit:my*unit+92]))
    return bytes(data),dict(style=1,rows=facts,disk_guid=DISK.bytes_le,usable=(first*unit,(last-first+1)*unit))

def native_layout(facts):
    style=facts['style'];rows=facts['rows'];entries=[]
    for i,row in enumerate(rows):
        e=bytearray(144);struct.pack_into('<I4xqqIB',e,0,style,row['start'],row['length'],row.get('number',i+1),row.get('rewrite',0))
        if style==0:struct.pack_into('<BBB1xI',e,32,row['type'],row.get('boot',0),row.get('recognized',1),row.get('hidden',1))
        else:
            e[32:48]=row['type'];e[48:64]=row['guid'];struct.pack_into('<Q',e,64,row['attrs']);e[72:144]=row['name']
        entries.append(bytes(e))
    if style==0:
        while len(entries)%4:entries.append(bytes(144))
    header=bytearray(48);struct.pack_into('<II',header,0,style,len(entries))
    if style==0:struct.pack_into('<I',header,8,facts.get('signature',0))
    elif style==1:
        header[8:24]=facts['disk_guid'];struct.pack_into('<qqI',header,24,*facts['usable'],facts.get('maximum',128))
    return bytes(header)+b''.join(entries)

def fixture(facts,unit=512,blocks=256):
    d=disk(size=unit*blocks);d['replies']['geometry']=[packet(struct.pack('<QIIIIQ',0,12,0,0,unit,unit*blocks))]
    ids=identifiers();layout=native_layout(facts);growth=[];size=192
    while len(layout)>size:growth.append(packet(ok=False,error=122));size*=2
    d['replies'].update(identifiers=[packet(ids[:8]),packet(ids)],alignment=[packet(alignment(unit,max(unit,4096),0))],layout=growth+[packet(layout)])
    return dict(profile='identity-layout',subjects=[d])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();images=out/'images';images.mkdir();checks=[];runs=[];manifest=[]
    def check(label,ok):checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def image(name,data,unit=512,blocks=256):
        path=images/(name+'.img');path.write_bytes(data);sha='sha256:'+hashlib.sha256(data).hexdigest()
        manifest.append(dict(name=name,path=str(path),bytes=len(data),sha256=sha,unit=unit,blocks=blocks));return path,sha
    def request(name,data,facts,unit=512,blocks=256):
        path,sha=image(name,data,unit,blocks);return dict(image=str(path),expected_image_digest=sha,unit=str(unit),blocks=str(blocks),fixture=fixture(facts,unit,blocks),source='fixture-storage',capture='3',worker='7',subject='disk')
    def run(name,value,state='agree-within-scope',raw_state='complete',expected=0):
        payload=json.dumps(value,separators=(',',':')).encode();(out/(name+'.request.json')).write_bytes(payload);start=time.monotonic()
        r=subprocess.run([a.probe.absolute()],input=payload,capture_output=True,timeout=20)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,exit_code=r.returncode,expected_exit=expected,expected_state=state,expected_raw_state=raw_state,elapsed_seconds=round(time.monotonic()-start,3)))
        check(name+' exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout);check(name+' pointer',v['pointer_bytes']==str(a.pointer_bytes))
        if expected:check(name+' refused',v['status']=='refused');return v
        raw=v['raw'];c=v['comparison'];check(name+' raw state',raw['state']==raw_state);check(name+' comparison state',c['state']==state)
        check(name+' exact byte digest',raw['source']['sha256']==value['expected_image_digest'])
        check(name+' exact value binding',c['binding']['frame_digest']==digest(v['frame']) and c['binding']['raw_digest']==digest(raw))
        check(name+' no query in comparison',v['comparison_api_calls']=='0')
        check(name+' immutable provider claim',v['frame']['claims']['raw_metadata_independently_verified'] is False)
        check(name+' declared pairing only',c['claims']==dict(binding_scope='fixture-declared-pairing',physical_identity='unknown',physical_association='unproven',owned_reader_authenticated=False,mutation_authority=False))
        check(name+' no raw authority',raw['claims']['mutation_authority'] is False and raw['claims']['physical_identity']=='unknown')
        check(name+' source consistency unknown',raw['source']['consistency']=='unknown')
        check(name+' admitted bound',v['memory_limit_bytes']==str(256*1024*1024))
        check(name+' ordinary generation unchanged',v['file']['before']==v['file']['after'])
        if raw_state!='complete':check(name+' no partial canonical agreement',raw['entries']==[] and raw['links']==[])
        return v
    try:
        mbr_facts=dict(style=0,rows=[dict(start=512,length=31*512,type=7,boot=0),dict(start=40*512,length=60*512,type=0x83,boot=0)])
        ebr_facts=dict(style=0,rows=[dict(start=10*512,length=200*512,type=15),dict(start=11*512,length=9*512,type=7),dict(start=41*512,length=19*512,type=0x83)])
        corpus=recipes();valid_mbr=next(x['data'] for x in corpus if x['name']=='mbr-two');base=request('mbr-base',valid_mbr,mbr_facts);v=run('mbr-base',base)
        check('MBR all primary entries',len(v['raw']['entries'])==2 and len(v['comparison']['matches'])==2)
        for name,mutator in [
            ('signature',lambda f:f.update(signature=0x12345678)),('type',lambda f:f['rows'][0].update(type=0x0b)),
            ('boot',lambda f:f['rows'][0].update(boot=1)),('boot-noncanonical',lambda f:f['rows'][0].update(boot=2)),
            ('extent',lambda f:f['rows'][0].update(start=1024)),('extra',lambda f:f['rows'].append(dict(start=100*512,length=512,type=7))),
            ('missing',lambda f:f['rows'].pop()),('duplicate',lambda f:f['rows'].append(copy.deepcopy(f['rows'][0]))),
        ]:
            facts=copy.deepcopy(mbr_facts);mutator(facts);req=copy.deepcopy(base);req['fixture']=fixture(facts);run('mbr-'+name,req,'disagree')
        facts=copy.deepcopy(mbr_facts);facts['rows'].reverse()
        for i,r in enumerate(facts['rows']):r.update(number=90+i,recognized=0,hidden=999,rewrite=1)
        req=copy.deepcopy(base);req['fixture']=fixture(facts);run('mbr-permuted-host-fields',req)
        signed=bytearray(valid_mbr);struct.pack_into('<I',signed,440,0x12345678);facts=copy.deepcopy(mbr_facts);facts['signature']=0x12345678
        run('mbr-nonzero-signature',request('mbr-nonzero-signature',signed,facts))
        req=request('mbr-prefix',valid_mbr[:512],mbr_facts);v=run('mbr-complete-table-in-prefix',req);check('prefix completeness separate',not v['raw']['source']['complete'])
        ebr=next(x['data'] for x in corpus if x['name']=='ebr-two');ebase=request('ebr-base',ebr,ebr_facts);v=run('ebr-base',ebase)
        check('EBR current-node relative data',v['raw']['entries'][2]['offset_bytes']==str(41*512) and len(v['raw']['links'])==1)
        facts=copy.deepcopy(ebr_facts);facts['rows'].append(dict(start=40*512,length=170*512,type=15))
        req=copy.deepcopy(ebase);req['fixture']=fixture(facts);v=run('ebr-optional-structural-slot',req);check('link separate from partitions',len(v['comparison']['structural_matches'])==1)
        facts['rows'].append(copy.deepcopy(facts['rows'][-1]));req['fixture']=fixture(facts);v=run('ebr-duplicate-structural-slot',req,'disagree');check('link cannot match twice',len(v['comparison']['structural_matches'])==1 and len(v['comparison']['extra'])==1)
        req=copy.deepcopy(ebase);req['policy']=dict(partitions='64',ebr_nodes='1');run('ebr-walk-budget',req,'incomparable','budget_exhausted')
        for logical_count in (10,63,64):
            data=bytearray(256*512);data[:512]=table([mbr_entry(15,10,200)])
            rows=[dict(start=10*512,length=200*512,type=15)]
            for i in range(logical_count):
                lba=10+3*i;parts=[mbr_entry(7,1,1)]
                if i+1<logical_count:parts.append(mbr_entry(15,3*(i+1),200-3*(i+1)))
                data[lba*512:(lba+1)*512]=table(parts);rows.append(dict(start=(lba+1)*512,length=512,type=7))
            facts=dict(style=0,rows=rows[:64]);req=request('ebr-many-'+str(logical_count),data,facts)
            v=run('ebr-many-'+str(logical_count),req,'agree-within-scope' if logical_count<64 else 'incomparable','complete' if logical_count<64 else 'budget_exhausted')
            check('EBR complete pre-clear count '+str(logical_count),v['raw']['active_count']==str(logical_count+1))
        data=bytearray(256*4096);data[:512]=table([mbr_entry(7,1,31),mbr_entry(0x83,40,60)])
        facts=dict(style=0,rows=[dict(start=4096,length=31*4096,type=7),dict(start=40*4096,length=60*4096,type=0x83)])
        run('mbr-4096',request('mbr-4096',data,facts,4096))
        bootable=bytearray(valid_mbr);bootable[446]=0x80;facts=copy.deepcopy(mbr_facts);facts['rows'][0]['boot']=1
        run('mbr-bootable',request('mbr-bootable',bootable,facts))
        run('empty-byte-prefix',request('empty-byte-prefix',b'',mbr_facts),'incomparable','incomplete')
        run('unsigned-zero-media',request('unsigned-zero-media',bytes(256*512),mbr_facts),'incomparable','unrecognized')
        for unit,count in [(512,1),(4096,1),(512,10),(4096,10),(512,64),(4096,64)]:
            data,facts=gpt_image(unit,count);req=request('gpt-'+str(unit)+'-'+str(count),data,facts,unit);v=run('gpt-'+str(unit)+'-'+str(count),req)
            check('GPT complete active '+str(unit)+'/'+str(count),len(v['raw']['entries'])==count and len(v['comparison']['matches'])==count)
            if count==1:check('all36 UTF16 units '+str(unit),v['raw']['entries'][0]['gpt_name_hex']==facts['rows'][0]['name'].hex())
        data,facts=gpt_image();gbase=request('gpt-base',data,facts)
        run('gpt-primary-only-prefix',request('gpt-primary-only-prefix',data[:34*512],facts),'incomparable','incomparable')
        for name,change in [('hybrid-protective',lambda b:b.__setitem__(slice(462,478),mbr_entry(7,34,1))),('missing-protective',lambda b:b.__setitem__(slice(446,462),bytes(16))),('protective-signature',lambda b:b.__setitem__(511,0))]:
            altered=bytearray(data);change(altered);run(name,request(name,altered,facts),'incomparable','incomparable')
        over=bytearray(data);over[:512]=table([mbr_entry(0xee,1,9999)])
        struct.pack_into('<QQQQ',over,512+24,1,9999,259,9741);struct.pack_into('<I',over,512+80,1025)
        struct.pack_into('<I',over,512+16,0);struct.pack_into('<I',over,512+16,zlib.crc32(over[512:604]))
        req=request('gpt-workspace-count-budget',over,facts,blocks=10000);run('gpt-workspace-count-budget',req,'incomparable','budget_exhausted')
        invalid,valid_facts=gpt_image(count=1);invalid=bytearray(invalid)
        for header_lba,array_lba in [(1,2),(255,223)]:
            invalid[array_lba*512+126:array_lba*512+128]=b'X\0'
            struct.pack_into('<I',invalid,header_lba*512+88,zlib.crc32(invalid[array_lba*512:array_lba*512+16384]))
            struct.pack_into('<I',invalid,header_lba*512+16,0);struct.pack_into('<I',invalid,header_lba*512+16,zlib.crc32(invalid[header_lba*512:header_lba*512+92]))
        run('gpt-unterminated-all36-units',request('gpt-unterminated-all36-units',invalid,valid_facts),'incomparable','incomparable')
        changes=[('disk-guid',lambda f:f.update(disk_guid=uuid.UUID(int=88).bytes_le)),('usable-start',lambda f:f.update(usable=(f['usable'][0]+512,f['usable'][1]-512))),
                 ('type',lambda f:f['rows'][0].update(type=uuid.UUID(int=88).bytes_le)),('partition-guid',lambda f:f['rows'][0].update(guid=uuid.UUID(int=88).bytes_le)),
                 ('attributes',lambda f:f['rows'][0].update(attrs=2)),('name-first',lambda f:f['rows'][0].update(name=b'X\0'+f['rows'][0]['name'][2:])),
                 ('name-last-unit',lambda f:f['rows'][0].update(name=f['rows'][0]['name'][:-2]+b'X\0')),('extent',lambda f:f['rows'][0].update(start=f['rows'][0]['start']+512))]
        for name,change in changes:
            altered=copy.deepcopy(facts);change(altered);req=copy.deepcopy(gbase);req['fixture']=fixture(altered);v=run('gpt-'+name,req,'disagree')
            check('GPT difference explicit '+name,bool(v['comparison']['differences'] or v['comparison']['missing']))
        altered=copy.deepcopy(facts);altered['rows'].reverse();altered['maximum']=256
        for i,r in enumerate(altered['rows']):r['number']=87+i
        req=copy.deepcopy(gbase);req['fixture']=fixture(altered);run('gpt-permuted-advisory-maximum',req)
        data,facts=gpt_image(count=65);req=request('gpt-over-64',data,dict(facts,rows=facts['rows'][:64]));v=run('gpt-over-64',req,'incomparable','budget_exhausted');check('pre-clear count retained',v['raw']['active_count']=='65')
        req=copy.deepcopy(gbase);req['policy']=dict(partitions='1',ebr_nodes='128');run('gpt-selected-lower-budget',req,'incomparable','budget_exhausted')
        # Existing independently authored corrupt recipes preserve their known diagnostics.
        for item in corpus:
            name=item['name'];common=item['common_projection'];facts=ebr_facts if name.startswith('ebr-') else mbr_facts if name.startswith('mbr-') else dict(style=1,rows=[],disk_guid=DISK.bytes_le,usable=(34*512,189*512))
            if name=='mbr-empty':facts=dict(style=0,rows=[])
            if name=='gpt-valid':
                facts=dict(style=1,rows=[dict(start=34*512,length=27*512,type=TYPE.bytes_le,guid=uuid.UUID(int=1).bytes_le,attrs=0,name='Alpha'.encode('utf-16-le').ljust(72,b'\0')),dict(start=70*512,length=21*512,type=TYPE.bytes_le,guid=uuid.UUID(int=2).bytes_le,attrs=0,name='Beta'.encode('utf-16-le').ljust(72,b'\0'))],disk_guid=DISK.bytes_le,usable=(34*512,189*512))
            raw_state='complete' if common else 'incomplete' if name=='mbr-truncated' else 'unrecognized' if name=='mbr-signature' else 'incomparable'
            req=request('corpus-'+name,item['data'],facts);v=run('corpus-'+name,req,'agree-within-scope' if common else 'incomparable',raw_state)
            for key,wanted in item['checks'].items():
                if key=='mbr.issues':check(name+' independent MBR diagnostic',int(v['raw']['mbr']['issues'])==wanted)
                elif key=='comparison':check(name+' independent GPT relation',int(v['raw']['copy_relation'])==wanted)
        for name,components in [('capacity-unavailable',('geometry','length')),('sector-unavailable',('geometry','alignment')),('layout-unavailable',('layout',))]:
            req=copy.deepcopy(gbase)
            for c in components:req['fixture']['subjects'][0]['replies'][c]=[packet(ok=False,error=5)]
            v=run(name,req,'incomparable');check(name+' coverage explicit',bool(v['comparison']['coverage']))
        for name,component in [('geometry-capacity','geometry'),('length-capacity','length'),('alignment-sector','alignment')]:
            req=copy.deepcopy(gbase)
            data=struct.pack('<QIIIIQ',0,12,0,0,512,131584) if component=='geometry' else struct.pack('<Q',131584) if component=='length' else alignment(4096,4096,0)
            req['fixture']['subjects'][0]['replies'][component]=[packet(data)];run(name,req,'disagree')
        req=copy.deepcopy(gbase);req['fixture']['subjects'][0]['replies']['geometry']=[packet(ok=False,error=5)];run('capacity-from-length-unit-from-alignment',req)
        req=copy.deepcopy(gbase);req['fixture']=fixture(dict(style=2,rows=[]));run('native-raw-style',req,'disagree')
        req=copy.deepcopy(gbase);req['fixture']['subjects'][0]['replies']['layout']=[packet(b'\0'*47)];run('malformed-native-layout',req,'incomparable')
        for field,value in [('capture','4'),('worker','0'),('subject','other'),('source',''),('frame_digest','sha256:'+'0'*64),('raw_digest','sha256:'+'0'*64)]:
            req=copy.deepcopy(base);req['binding']={field:value};v=run('binding-'+field,req,expected=3);check(field+' binding refused',v['reason']=='nt_layout_binding' if field!='subject' else v['reason']=='nt_layout_subject')
        for name,changes in [('zero-blocks',dict(blocks='0')),('overflow-capacity',dict(blocks=str(2**64-1))),('non-selected-unit',dict(unit='520')),('prefix-exceeds-capacity',dict(blocks='1')),('bad-digest',dict(expected_image_digest='sha256:'+'0'*64)),('zero-policy',dict(policy=dict(partitions='0',ebr_nodes='128')))]:
            req=copy.deepcopy(base);req.update(changes);run(name,req,expected=3)
        for api in ('native','mixed-io','mixed-error'):
            req=copy.deepcopy(base);req['api']=api;v=run('refuse-'+api,req,expected=3);check(api+' no dispatch',v['api_calls']=='0')
        for name,path in [('physical-path',r'\\.\PhysicalDrive0'),('device-namespace',r'\\?\GLOBALROOT\Device\Harddisk0\DR0'),('directory',str(images))]:
            req=copy.deepcopy(base);req['image']=path;v=run(name,req,expected=3);check(name+' no fixture dispatch',v['api_calls']=='0')
        huge,sha=image('over-image-budget',b'\0'*(16*1024*1024+1));req=copy.deepcopy(base);req.update(image=str(huge),expected_image_digest=sha);v=run('image-byte-budget',req,expected=3);check('budget refusal before query',v['api_calls']=='0')
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,processes=len(runs),assertions=len(checks),checks=checks,executions=runs)
    except BaseException as error:
        result=dict(status='fail',pointer_bytes=a.pointer_bytes,processes=len(runs),assertions=len(checks),checks=checks,executions=runs,error=str(error));raise
    finally:
        (out/'image-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        if 'result' in locals():(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],processes=len(runs),assertions=len(checks))))

if __name__=='__main__':main()
