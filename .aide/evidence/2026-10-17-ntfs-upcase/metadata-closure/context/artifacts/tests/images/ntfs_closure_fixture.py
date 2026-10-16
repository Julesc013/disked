"""Independent sparse NTFS image layout and exact physical closure read oracle."""
import copy
import hashlib
import struct

from test_ntfs_capture import Volume, mapping
from test_ntfs_stream import entry, nonresident, record, ref, resident

MAX_READ=49152


def parts(runs,cluster,start,length):
    end=start+length;next_byte=start;vcn=0;out=[]
    for count,lcn in runs:
        first,last=vcn*cluster,(vcn+count)*cluster;vcn+=count
        if next_byte>=last:continue
        if next_byte<first:break
        size=min(end-next_byte,last-next_byte)
        assert lcn is not None
        at=lcn*cluster+next_byte-first
        while size:
            chunk=min(size,MAX_READ);out.append((at,chunk));at+=chunk;next_byte+=chunk;size-=chunk
        if next_byte==end:break
    assert next_byte==end,(runs,cluster,start,length)
    return out


class ClosureVolume(Volume):
    def __init__(self,offset=0,minor=1,cluster=4096,size=1024,nonresident_list=False,
                 volume_list=True,volume_nonresident=False,reverse=True,padding=0,
                 same_extension=False,usa=48):
        assert cluster in (512,4096) and size in (512,1024,2048,4096)
        first=(32*size+cluster-1)//cluster;second=first;third=(16*size+cluster-1)//cluster
        seed=7 if cluster==512 else 1
        assert first>seed
        first_runs=[(seed,8),(first-seed,40)]
        layout=[*first_runs,(second,100),(third,200)]
        super().__init__(sector=512,spc=cluster//512,size=size,offset=offset,minor=minor,runs=layout,usa=usa)
        self.full_runs=layout;self.cluster=cluster;self.offset=offset;self.size=size
        self.total_clusters=first+second+third;self.allocated=self.total_clusters*cluster
        assert self.allocated%size==0
        self.base_reference=ref(0,3);self.volume_reference=ref(3,3)
        first_slots=first*cluster//size
        self.first_extension=first_slots-1
        assert self.first_extension not in (0,3)
        self.second_extension=first_slots+1
        if self.second_extension==3:self.second_extension+=1
        self.volume_extension=self.allocated//size-1
        assert len({0,3,self.first_extension,self.second_extension,self.volume_extension})==5
        self.first_reference=ref(self.first_extension,9)
        self.second_reference=ref(self.second_extension,12)
        self.info_reference=ref(self.volume_extension,8)
        if same_extension:self.second_reference=self.first_reference
        data0=nonresident(runs=first_runs,high=first-1,allocated=self.allocated,data=self.allocated,initialized=self.allocated,instance=11)
        data1=nonresident(low=first,runs=((second,100),),high=first+second-1,allocated=(1<<64)-1,data=(1<<64)-1,initialized=(1<<64)-1,instance=13)
        data2=nonresident(low=first+second,runs=((third,200),),high=self.total_clusters-1,allocated=(1<<64)-1,data=(1<<64)-1,initialized=(1<<64)-1,instance=17)
        descriptors=[entry(self.base_reference,11),entry(self.first_reference,13,first),entry(self.second_reference,17,first+second)]
        if reverse:descriptors.reverse()
        descriptors += [entry(self.base_reference,99,kind=0x110) for _ in range(padding)]
        self.mft_list_value=b''.join(descriptors)
        list_clusters=(len(self.mft_list_value)+cluster-1)//cluster
        self.list_runs=[(1,300)]+([(list_clusters-1,500)] if list_clusters>1 else [])
        if nonresident_list:
            list_attribute=nonresident(kind=0x20,instance=1,runs=self.list_runs,high=list_clusters-1,allocated=list_clusters*cluster,data=len(self.mft_list_value),initialized=len(self.mft_list_value))
        else:list_attribute=resident(self.mft_list_value,kind=0x20,instance=1)
        primary=record([data0,list_attribute],number=0,sequence=3,size=size,usa=usa)
        extension1=record([data1,data2] if same_extension else [data1],number=self.first_extension,sequence=9,base=self.base_reference,size=size,usa=usa)
        extension2=record([data2],number=self.second_extension,sequence=12,base=self.base_reference,size=size,usa=usa)
        info=b'\0'*8+bytes([3,minor])+b'\0\0'
        info_attribute=resident(info,kind=0x70,instance=7)
        self.info=bytes(info_attribute);self.data=bytes(data0)
        volume_descriptors=entry(self.info_reference,7,kind=0x70)
        self.volume_list_value=bytes(volume_descriptors)
        self.volume_list_runs=[(1,700)]
        if volume_list:
            if volume_nonresident:
                volume_attribute=nonresident(kind=0x20,instance=1,runs=self.volume_list_runs,high=0,allocated=cluster,data=len(volume_descriptors),initialized=len(volume_descriptors))
            else:volume_attribute=resident(volume_descriptors,kind=0x20,instance=1)
            volume=record([volume_attribute],number=3,sequence=3,size=size,usa=usa)
        else:volume=record([info_attribute],number=3,sequence=3,size=size,usa=usa)
        info_record=record([info_attribute],number=self.volume_extension,sequence=8,base=self.volume_reference,size=size,usa=usa)
        self.input['regions']=self.input['regions'][:1]
        self.initial_reads=[(offset,512),(offset+8*cluster,size),(offset+5000*cluster,size)]
        self.record_regions={}
        def place(at,value):
            for n in range(0,len(value),MAX_READ):self.input['regions'].append(dict(offset=str(offset+at+n),hex=bytes(value[n:n+MAX_READ]).hex()))
        def logical(runs,start,value):
            position=0;spans=parts(runs,cluster,start,len(value))
            for at,count in spans:place(at,value[position:position+count]);position+=count
            return [(offset+at,count) for at,count in spans]
        place(8*cluster,primary);place(5000*cluster,primary)
        self.record_regions[0]=[(offset+8*cluster,size)]
        ext1_spans=logical(layout,self.first_extension*size,extension1)
        self.record_regions[self.first_extension]=ext1_spans
        if not same_extension:
            ext2_spans=logical(layout,self.second_extension*size,extension2)
            self.record_regions[self.second_extension]=ext2_spans
        else:ext2_spans=[]
        volume_spans=logical(layout,3*size,volume);self.record_regions[3]=volume_spans
        info_spans=logical(layout,self.volume_extension*size,info_record);self.record_regions[self.volume_extension]=info_spans
        if nonresident_list:self.initial_reads+=logical(self.list_runs,0,self.mft_list_value)
        self.initial_reads+=ext1_spans+ext2_spans+volume_spans
        if volume_list:
            if volume_nonresident:self.initial_reads+=logical(self.volume_list_runs,0,self.volume_list_value)
            self.initial_reads+=info_spans
        self.expected=dict(mft_runs='4',allocated=str(self.allocated),initialized=str(self.allocated),mft_extensions=1 if same_extension else 2,volume_extensions=1 if volume_list else 0,
                           mft_list_bytes=str(len(self.mft_list_value)),volume_list_bytes=str(len(self.volume_list_value)),first=self.first_reference,second=self.second_reference,info=self.info_reference)
        self.nonresident_list=nonresident_list;self.volume_list=volume_list;self.volume_nonresident=volume_nonresident

    def bytes(self,at,length):
        out=bytearray(length)
        for region in self.input['regions']:
            begin=int(region['offset']);raw=bytes.fromhex(region['hex']);first=max(begin,at);last=min(begin+len(raw),at+length)
            if first<last:out[first-at:last-at]=raw[first-begin:last-begin]
        return bytes(out)

    def mutate_record(self,number,relative,value):
        spans=self.record_regions[number];position=0
        for start,length in spans:
            if position<=relative<position+length:
                target=start+relative-position
                for region in self.input['regions']:
                    first=int(region['offset']);raw=bytearray.fromhex(region['hex'])
                    if first<=target<first+len(raw):raw[target-first]=value;region['hex']=raw.hex()
                return
            position+=length
        raise ValueError((number,relative))

    def independent_regions(self):
        return [dict(offset=str(at),bytes=str(length),sha256='sha256:'+hashlib.sha256(self.bytes(at,length)).hexdigest()) for at,length in self.initial_reads]
