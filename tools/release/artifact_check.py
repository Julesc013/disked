"""Independent staging inventory and bounded ZIP completeness verification.

Never extracts or executes archive content. Quiescent reviewed staging is required;
stat checks detect changes but are not a hostile filesystem isolation boundary.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import unicodedata
import zipfile
import zlib

SCHEMA='org.disked.artifact-inventory-prototype/1'
MAX_FILES=4096
MAX_JSON=4*1024*1024
MAX_CENTRAL=8*1024*1024
MAX_FILE=512*1024*1024
MAX_TOTAL=1024*1024*1024
MAX_ARCHIVE=512*1024*1024
CHUNK=65536

class Rejected(Exception):
    pass

def reject(code):raise Rejected(code)
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')

def safe_path(value):
    if not isinstance(value,str) or not value or len(value.encode('utf-8',errors='surrogatepass'))>1024:reject('unsafe_path')
    if unicodedata.normalize('NFC',value)!=value or any(unicodedata.category(c).startswith('C') or c in '\\<>:"|?*' for c in value):reject('unsafe_path')
    parts=value.split('/')
    for part in parts:
        if not part or part in ('.','..') or part.endswith((' ','.')) or len(part.encode('utf-8'))>255:reject('unsafe_path')
        stem=part.split('.')[0].upper()
        if stem in ('CON','PRN','AUX','NUL','CONIN$','CONOUT$') or re.fullmatch(r'(COM|LPT)[0-9¹²³]',stem):reject('unsafe_path')
    return value

def closure(paths):
    names=set();folded=set();parents=set()
    for path in paths:
        safe_path(path)
        if path in names or path.casefold() in folded:reject('duplicate_path')
        names.add(path);folded.add(path.casefold());parts=path.split('/')
        parents.update('/'.join(parts[:i]) for i in range(1,len(parts)))
        if len(parents)>MAX_FILES:reject('directory_budget')
    if folded.intersection(p.casefold() for p in parents):reject('file_directory_collision')
    # Directory components must also agree in case across distinct file paths.
    spellings={}
    for p in names|parents:
        old=spellings.setdefault(p.casefold(),p)
        if old!=p:reject('case_collision')
    return names,parents

def fingerprint(s):return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns
def identity(s):return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns
def local_source(path):
    value=str(path).replace('\\','/');folded=value.casefold()
    if folded.startswith(('//','/??/','/device/','/global??/')) or any(c==':' and (i!=1 or not value[0].isalpha()) for i,c in enumerate(value)):reject('unsupported_source_path')
def no_link(path,directory=False):
    s=path.lstat()
    if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):reject('link_rejected')
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):reject('file_type')
    if not directory and s.st_nlink!=1:reject('link_rejected')
    return s

@contextmanager
def pinned(path):
    local_source(path);path=Path(path).absolute();before=no_link(path)
    for ancestor in path.parents:no_link(ancestor,True)
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
    with os.fdopen(os.open(path,flags),'rb') as file:
        opened=os.fstat(file.fileno())
        # Windows path/descriptor APIs can give different legacy ctime values.
        # Compare shared identity fields across APIs, then each API to itself.
        if identity(before)!=identity(opened) or not stat.S_ISREG(opened.st_mode):reject('file_changed')
        yield file,opened
        if fingerprint(opened)!=fingerprint(os.fstat(file.fileno())) or fingerprint(before)!=fingerprint(no_link(path)):reject('file_changed')

def hash_file(file,size):
    file.seek(0);h=hashlib.sha256();n=0
    while True:
        chunk=file.read(CHUNK)
        if not chunk:break
        n+=len(chunk)
        if n>size:reject('file_changed')
        h.update(chunk)
    if n!=size:reject('file_changed')
    return 'sha256:'+h.hexdigest()

def validate_inventory(value):
    if not isinstance(value,dict) or set(value)!={'schema','required_entrypoints','files'} or value['schema']!=SCHEMA:reject('inventory_shape')
    files=value['files'];required=value['required_entrypoints']
    if not isinstance(files,list) or not 1<=len(files)<=MAX_FILES or not isinstance(required,list) or not 1<=len(required)<=MAX_FILES:reject('inventory_empty_or_budget')
    closure(required);rows={};total=0;paths=[]
    for row in files:
        if not isinstance(row,dict) or set(row)!={'path','type','bytes','sha256'} or row['type']!='regular':reject('inventory_shape')
        path=safe_path(row['path']);size=row['bytes'];sha=row['sha256']
        if not isinstance(size,str) or not re.fullmatch(r'0|[1-9][0-9]{0,19}',size) or int(size)>MAX_FILE:reject('inventory_size')
        if not isinstance(sha,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',sha):reject('inventory_digest')
        total+=int(size)
        if total>MAX_TOTAL:reject('inventory_total')
        rows[path]=row;paths.append(path)
    closure(paths)
    if paths!=sorted(paths) or required!=sorted(required):reject('inventory_order')
    if any(p not in rows or int(rows[p]['bytes'])==0 for p in required):reject('required_entrypoint')
    return rows

def inventory(staging,required):
    local_source(staging);root=Path(staging).absolute();no_link(root,True)
    for ancestor in root.parents:no_link(ancestor,True)
    rows=[];directories=[];directories_seen=[];files_seen=[];total=0
    def walk(directory):
        nonlocal total
        before=no_link(directory,True);directories_seen.append((directory,fingerprint(before)))
        with os.scandir(directory) as scan:entries=sorted(scan,key=lambda x:x.name)
        for entry in entries:
            path=Path(entry.path);name=path.relative_to(root).as_posix();safe_path(name);s=path.lstat()
            if stat.S_ISDIR(s.st_mode):
                no_link(path,True);directories.append(name)
                if len(directories)>MAX_FILES:reject('staging_budget')
                walk(path)
            else:
                no_link(path)
                if len(rows)>=MAX_FILES or s.st_size>MAX_FILE:reject('staging_budget')
                total+=s.st_size
                if total>MAX_TOTAL:reject('staging_budget')
                with pinned(path) as (file,opened):sha=hash_file(file,opened.st_size)
                if fingerprint(s)!=fingerprint(no_link(path)):reject('staging_changed')
                files_seen.append((path,fingerprint(s)))
                rows.append(dict(path=name,type='regular',bytes=str(s.st_size),sha256=sha))
        if fingerprint(before)!=fingerprint(no_link(directory,True)):reject('staging_changed')
    walk(root)
    rows.sort(key=lambda x:x['path']);value=dict(schema=SCHEMA,required_entrypoints=sorted(required),files=rows);validate_inventory(value)
    _,parents=closure(x['path'] for x in rows)
    if set(directories)!=parents:reject('empty_staging_directory')
    if any(expected!=fingerprint(no_link(p,True)) for p,expected in directories_seen):reject('staging_changed')
    if any(expected!=fingerprint(no_link(p)) for p,expected in files_seen):reject('staging_changed')
    return value

def load_inventory(path):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:reject('inventory_duplicate_key')
            out[k]=v
        return out
    with pinned(path) as (file,s):
        if s.st_size>MAX_JSON:reject('inventory_budget')
        data=file.read(MAX_JSON+1)
    if len(data)>MAX_JSON:reject('inventory_budget')
    try:value=json.loads(data.decode('utf-8'),object_pairs_hook=pairs)
    except (ValueError,UnicodeError,RecursionError):reject('inventory_json')
    validate_inventory(value);return value,digest(data)

def preflight(file,size):
    if size>MAX_ARCHIVE or size<22:reject('archive_budget_or_format')
    n=min(size,65557);file.seek(size-n);tail=file.read(n);index=tail.rfind(b'PK\x05\x06')
    if index<0 or len(tail)-index<22:reject('archive_end')
    _,disk,central_disk,on_disk,count,central_size,offset,comment=struct.unpack_from('<4s4H2IH',tail,index)
    end=size-n+index
    if end+22+comment!=size or disk or central_disk or on_disk!=count:reject('archive_end')
    boundary=end
    if count==65535 or central_size==0xffffffff or offset==0xffffffff:
        if end<20:reject('archive_zip64')
        file.seek(end-20);locator=file.read(20)
        if len(locator)!=20:reject('archive_zip64')
        sig,which,record_offset,disks=struct.unpack('<4sIQI',locator)
        if sig!=b'PK\x06\x07' or which or disks!=1 or record_offset>end-76:reject('archive_zip64')
        file.seek(record_offset);record=file.read(56)
        if len(record)!=56:reject('archive_zip64')
        sig,length,_,_,disk,central_disk,on_disk,count,central_size,offset=struct.unpack('<4sQ2H2I4Q',record)
        if sig!=b'PK\x06\x06' or length<44 or length>4096 or record_offset+12+length!=end-20 or disk or central_disk or on_disk!=count:reject('archive_zip64')
        boundary=record_offset
    if count>MAX_FILES*2 or central_size>MAX_CENTRAL or offset+central_size!=boundary:reject('archive_metadata_budget')
    return count,offset

def extra_fields(data):
    offset=0;seen={}
    while offset<len(data):
        if len(data)-offset<4:reject('archive_extra_field')
        tag,n=struct.unpack_from('<HH',data,offset);offset+=4
        if tag!=1 or tag in seen or (n%8 and n!=28) or n>28 or n>len(data)-offset:reject('archive_extra_field')
        if n==28 and struct.unpack_from('<I',data,offset+24)[0]:reject('archive_extra_field')
        seen[tag]=data[offset:offset+n];offset+=n
    return seen

def local_header(file,info,central):
    file.seek(info.header_offset);data=file.read(30)
    if len(data)!=30:reject('archive_local_header')
    sig,_,flags,method,_,_,crc,compressed,size,n,extra=struct.unpack('<4s5H3I2H',data)
    if sig!=b'PK\x03\x04' or flags!=info.flag_bits or method!=info.compress_type or n>1024 or info.header_offset+30+n+extra+info.compress_size>central:reject('archive_local_header')
    name=file.read(n);fields=file.read(extra)
    try:decoded=name.decode('utf-8' if flags&0x800 else 'cp437')
    except UnicodeError:reject('archive_local_name')
    if decoded!=info.orig_filename or len(fields)!=extra:reject('archive_local_name')
    fields=extra_fields(fields);wide=size==0xffffffff or compressed==0xffffffff
    if wide or 1 in fields:
        if size!=0xffffffff or compressed!=0xffffffff or len(fields.get(1,b''))!=16:reject('archive_local_size')
        size,compressed=struct.unpack('<QQ',fields[1])
    if flags&8:
        if crc not in (0,info.CRC) or compressed not in (0,info.compress_size) or size not in (0,info.file_size):reject('archive_local_size')
    elif crc!=info.CRC or compressed!=info.compress_size or size!=info.file_size:reject('archive_local_size')
    return file.tell(),wide

def content_extent(file,info,start,wide,central):
    """Consume actual raw content, including bytes beyond declared output size.

    ZipExtFile bounds its output by central file_size. That is insufficient for
    completeness: a forged size/CRC can hide an expanded suffix. Decode the full
    raw extent ourselves with a bounded output buffer and require exact EOF.
    """
    file.seek(start);remaining=info.compress_size;n=0;crc=0;h=hashlib.sha256()
    def observe(chunk):
        nonlocal n,crc
        n+=len(chunk)
        if n>info.file_size:reject('archive_size')
        h.update(chunk);crc=zlib.crc32(chunk,crc)
    if info.compress_type==zipfile.ZIP_STORED:
        if remaining!=info.file_size:reject('archive_size')
        while remaining:
            chunk=file.read(min(CHUNK,remaining))
            if not chunk:reject('archive_content')
            remaining-=len(chunk);observe(chunk)
    else:
        decoder=zlib.decompressobj(-15);pending=b''
        while True:
            if not pending and remaining:
                pending=file.read(min(CHUNK,remaining))
                if not pending:reject('archive_content')
                remaining-=len(pending)
            chunk=decoder.decompress(pending,CHUNK);pending=decoder.unconsumed_tail;observe(chunk)
            if decoder.eof:
                if pending or decoder.unused_data or remaining:reject('archive_compressed_tail')
                break
            if not pending and not remaining and not chunk:reject('archive_deflate_incomplete')
    if n!=info.file_size or crc!=info.CRC:reject('archive_content')
    end=start+info.compress_size
    if info.flag_bits&8:
        count=16 if wide else 8
        file.seek(end);data=file.read(min(8+count,central-end));matches=[]
        for prefix in (0,4):
            if prefix and data[:4]!=b'PK\x07\x08':continue
            value=data[prefix:prefix+4+count]
            if len(value)==4+count and struct.unpack('<IQQ' if wide else '<III',value)==(info.CRC,info.compress_size,info.file_size):matches.append(end+prefix+4+count)
        # A signature-shaped CRC may belong to an unsigned descriptor. Accept
        # only an unambiguous exact match, then check physical record continuity.
        if len(matches)!=1:reject('archive_descriptor')
        end=matches[0]
    return end,'sha256:'+h.hexdigest()

def verify_zip(expected,archive):
    rows=validate_inventory(expected);names,parents=closure(rows);observed=set();seen=set();folded=set();total=0;extents=[]
    try:
        with pinned(archive) as (file,s):
            count,central_offset=preflight(file,s.st_size)
            file.seek(0)
            with zipfile.ZipFile(file) as z:
                infos=z.infolist()
                if len(infos)!=count:reject('archive_count')
                if infos and min(x.header_offset for x in infos)!=0:reject('archive_prefix')
                for info in infos:
                    original=info.orig_filename;directory=original.endswith('/');path=safe_path(original[:-1] if directory else original)
                    if info.filename!=original or path in seen or path.casefold() in folded:reject('archive_duplicate_or_name')
                    seen.add(path);folded.add(path.casefold());mode=info.external_attr>>16;kind=stat.S_IFMT(mode)
                    if kind not in ((0,stat.S_IFDIR) if directory else (0,stat.S_IFREG)) or info.external_attr&0x400 or info.external_attr&0x10 and not directory:reject('archive_file_type')
                    if info.flag_bits&~(0x800|8|6) or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):reject('archive_encoding')
                    if info.header_offset<0 or info.header_offset>=central_offset:reject('archive_offset')
                    extra_fields(info.extra);start,wide=local_header(file,info,central_offset)
                    if directory:
                        if path not in parents or info.file_size:reject('archive_extra_directory')
                        end,_=content_extent(file,info,start,wide,central_offset);extents.append((info.header_offset,end))
                        continue
                    if path not in names:reject('archive_extra')
                    row=rows[path];size=int(row['bytes']);total+=size
                    if info.file_size!=size or info.file_size>MAX_FILE or total>MAX_TOTAL:reject('archive_size')
                    end,content_sha=content_extent(file,info,start,wide,central_offset);extents.append((info.header_offset,end))
                    if content_sha!=row['sha256']:reject('archive_content')
                    observed.add(path)
                if observed!=names:reject('archive_missing')
                position=0
                for start,end in sorted(extents):
                    if start!=position:reject('archive_record_layout')
                    position=end
                if position!=central_offset:reject('archive_record_layout')
            sha=hash_file(file,s.st_size)
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError,struct.error,zlib.error):reject('archive_format')
    return dict(schema='org.disked.artifact-check-prototype/1',status='pass',archive_sha256=sha,inventory_sha256=digest(canonical(expected)),files=str(len(rows)),bytes=str(total),completeness=True,authenticity='not_run',publication='not_run',runtime='not_run',extraction='not_run')

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inventory');p.add_argument('--staging',type=Path,required=True);p.add_argument('--required',action='append',required=True);p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('verify');p.add_argument('--inventory',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='inventory':
            local_source(args.output)
            parent=args.output.absolute().parent
            for directory in (parent,*parent.parents):no_link(directory,True)
            if args.output.absolute().is_relative_to(args.staging.absolute()):reject('inventory_output_inside_staging')
            value=inventory(args.staging,args.required);data=canonical(value)+b'\n'
            if len(data)>MAX_JSON:reject('inventory_budget')
            with args.output.open('xb') as file:file.write(data)
            result=dict(status='pass',inventory_sha256=digest(data),files=str(len(value['files'])),owner_review='not_run')
        else:
            value,identity=load_inventory(args.inventory);result=verify_zip(value,args.archive);result['inventory_file_sha256']=identity
        print(json.dumps(result,sort_keys=True));return 0
    except Rejected as error:code=str(error)
    except (OSError,UnicodeError,ValueError):code='source_io_or_value'
    print(json.dumps(dict(status='fail',diagnostic=code),sort_keys=True));return 1
if __name__=='__main__':sys.exit(main())
