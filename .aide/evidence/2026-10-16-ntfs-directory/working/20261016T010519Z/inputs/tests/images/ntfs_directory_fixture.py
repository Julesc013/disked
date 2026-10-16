"""Independent sparse directory layouts and physical/read/hash expectations."""
import copy
import hashlib
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'property'))
from test_ntfs_index import filename, entry as index_entry, root as index_root
from test_ntfs_block import block as index_block
from test_ntfs_stream import resident, nonresident, record, entry as list_entry, ref
from test_ntfs_capture import Volume, bytes_at
from ntfs_closure_fixture import ClosureVolume, parts

I30 = '$I30'.encode('utf-16le')
def sha(raw):return 'sha256:' + hashlib.sha256(raw).hexdigest()

class DirectoryVolume:
    def __init__(self, kind='siblings', cluster=4096, index=4096, size=1024,
                 minor=1, offset=0, bitmap_form='resident', list_form='none',
                 split_allocation=False, fragmented_allocation=False,
                 mft_closure=False, reverse_list=False, number=5, sequence=3,
                 parent=None, namespace=1, name=None, usa=48):
        assert kind in {'leaf','empty','siblings','single','deep','mixed','preallocated','orphan'}
        self.cluster,self.index,self.size,self.offset=cluster,index,size,offset
        self.number,self.sequence=number,sequence
        self.reference=ref(number,sequence)
        self.kind=kind;self.bitmap_form=bitmap_form;self.list_form=list_form
        self.usa=usa
        self.mft_closure=mft_closure
        if mft_closure:
            volume=ClosureVolume(cluster=cluster,size=size,offset=offset,minor=minor,
                                 nonresident_list=True,volume_nonresident=True,usa=usa)
            self.mft_runs=volume.full_runs
        else:
            clusters=(64*size+cluster-1)//cluster
            first=min(clusters-1,max((size+cluster-1)//cluster,(number*size)//cluster+1))
            self.mft_runs=[(first,8),(clusters-first,100)]
            payload=nonresident(runs=self.mft_runs,allocated=clusters*cluster,
                                data=clusters*cluster,initialized=clusters*cluster,high=clusters-1)
            volume=Volume(spc=cluster//512,size=size,offset=offset,minor=minor,
                          runs=self.mft_runs,data_payload=payload,usa=usa)
        self.input=copy.deepcopy(volume.input)
        self.input['directory']={}
        self.bootstrap_reads=list(volume.initial_reads)
        self.record_regions={}
        self.child_unit=512 if index<cluster else cluster
        self.vbn=lambda ordinal:ordinal*(index//self.child_unit)
        self.base_sequence=sequence
        parent=self.reference if parent is None else parent
        def named(label,child=None,target=ref(14,9)):
            raw_name=(label.encode('utf-16le') if name is None else name)
            return index_entry(key=filename(raw_name,namespace=namespace,parent=parent),target=target,child=child)
        terminal=lambda child=None:index_entry(end=True,child=child)
        self.block_recipes={}
        if kind in {'leaf','empty','preallocated','orphan'}:
            root_rows=[terminal()] if kind=='empty' else [named('middle'),terminal()]
            root_children=False
        elif kind=='single':
            root_rows=[terminal(self.vbn(0))];root_children=True
            self.block_recipes[0]=([named('alpha'),terminal()],False)
        elif kind=='siblings':
            root_rows=[named('middle',self.vbn(0)),terminal(self.vbn(1))];root_children=True
            self.block_recipes[0]=([named('alpha'),terminal()],False)
            self.block_recipes[1]=([named('zeta'),terminal()],False)
        elif kind=='deep':
            root_rows=[terminal(self.vbn(0))];root_children=True
            self.block_recipes[0]=([named('middle',self.vbn(1)),terminal(self.vbn(2))],True)
            self.block_recipes[1]=([named('alpha'),terminal()],False)
            self.block_recipes[2]=([named('zeta'),terminal()],False)
        else:
            root_rows=[named('middle',self.vbn(0)),terminal(self.vbn(1))];root_children=True
            self.block_recipes[0]=([named('alpha'),terminal()],False)
            self.block_recipes[1]=([terminal(self.vbn(2))],True)
            self.block_recipes[2]=([named('zeta'),terminal()],False)
        self.root_rows=root_rows
        self.root_value,self.root_expected=index_root(root_rows,cluster=cluster,index=index,children=root_children)
        self.blocks={}
        for ordinal,(rows,children) in self.block_recipes.items():
            raw,logical,facts,items=index_block(size=index,rows=rows,children=children,vbn=self.vbn(ordinal))
            self.blocks[ordinal]=(bytes(raw),logical,facts,items)
        self.with_allocation=kind not in {'leaf','empty'}
        self.data_blocks=max(self.blocks,default=1)+1 if self.with_allocation else 0
        self.allocation_bytes=self.data_blocks*index
        count=(self.allocation_bytes+cluster-1)//cluster
        if count:
            self.allocation_runs=[(1,1000),(count-1,1100)] if fragmented_allocation and count>1 else [(count,1000)]
        else:self.allocation_runs=[]
        bits=sum(1<<n for n in self.blocks)
        if kind=='orphan':bits=1
        self.bitmap_value=bits.to_bytes(max(1,(self.data_blocks+7)//8),'little') if self.with_allocation else b''
        self.bitmap_runs=[(1,1300)]
        self.list_runs=[(1,1200)]
        self.directory_reads=[]
        self.root_attribute=resident(self.root_value,name=I30,kind=0x90,instance=11)
        self.allocation_attributes=[]
        if self.with_allocation:
            self.allocation_attributes.append(nonresident(runs=self.allocation_runs,
                allocated=count*cluster,data=self.allocation_bytes,initialized=self.allocation_bytes,
                name=I30,kind=0xa0,instance=13,high=count-1))
            self.bitmap_attribute=(resident(self.bitmap_value,name=I30,kind=0xb0,instance=17)
                if bitmap_form=='resident' else nonresident(runs=self.bitmap_runs,allocated=cluster,
                    data=len(self.bitmap_value),initialized=len(self.bitmap_value),name=I30,kind=0xb0,instance=17,high=0))
        else:self.bitmap_attribute=None
        if split_allocation:
            assert count>=2 and list_form!='none'
            first_runs=[self.allocation_runs[0]]
            # A split must have an actual logical extent boundary.
            if len(self.allocation_runs)==1:
                first_runs=[(1,1000)];second_runs=[(count-1,1001)]
            else:second_runs=self.allocation_runs[1:]
            first_count=sum(n for n,_ in first_runs)
            self.allocation_attributes=[
                nonresident(runs=first_runs,allocated=count*cluster,data=self.allocation_bytes,
                    initialized=self.allocation_bytes,name=I30,kind=0xa0,instance=13,high=first_count-1),
                nonresident(low=first_count,runs=second_runs,name=I30,kind=0xa0,instance=19,
                    high=count-1,allocated=(1<<64)-1,data=(1<<64)-1,initialized=(1<<64)-1)]
        self.ext_refs={12:ref(12,8),13:ref(13,9)}
        self.descriptors=[]
        self.base_attributes=[self.root_attribute]
        self.extension_attributes={}
        if list_form=='none':
            self.base_attributes+=self.allocation_attributes
            if self.bitmap_attribute is not None:self.base_attributes.append(self.bitmap_attribute)
        else:
            self.descriptors.append((0x90,self.reference,11,0))
            for i,a in enumerate(self.allocation_attributes):
                ordinal=12+i
                self.extension_attributes.setdefault(ordinal,[]).append(a)
                self.descriptors.append((0xa0,self.ext_refs[ordinal],13 if i==0 else 19,0 if i==0 else first_count))
            if self.bitmap_attribute is not None:
                self.extension_attributes.setdefault(12,[]).append(self.bitmap_attribute)
                self.descriptors.append((0xb0,self.ext_refs[12],17,0))
            if reverse_list:self.descriptors.reverse()
            self.list_value=b''.join(list_entry(reference=r,instance=i,low=low,name=I30,kind=kind)
                                     for kind,r,i,low in self.descriptors)
            value=(resident(self.list_value,kind=0x20,instance=1) if list_form=='resident'
                else nonresident(runs=self.list_runs,allocated=cluster,data=len(self.list_value),
                    initialized=len(self.list_value),kind=0x20,instance=1,high=0))
            self.base_attributes.append(value)
        self.place_record(number,record(self.base_attributes,number=number,sequence=sequence,flags=3,size=size,usa=usa))
        self.directory_reads+=self.record_regions[number]
        for ordinal,attributes in self.extension_attributes.items():
            self.place_record(ordinal,record(attributes,number=ordinal,sequence=self.ext_refs[ordinal]>>48,
                                             base=self.reference,size=size,usa=usa))
        if list_form=='nonresident':self.directory_reads+=self.place_logical(self.list_runs,0,self.list_value)
        loaded=set()
        for kind in (0x90,0xa0,0xb0):
            for entry_kind,r,_,_ in self.descriptors:
                ordinal=r&((1<<48)-1)
                if entry_kind==kind and ordinal!=number and ordinal not in loaded:
                    self.directory_reads+=self.record_regions[ordinal];loaded.add(ordinal)
        self.metadata_reads=self.bootstrap_reads+self.directory_reads.copy()
        self.bitmap_reads=[]
        if self.with_allocation and bitmap_form=='nonresident':
            self.bitmap_reads=self.place_logical(self.bitmap_runs,0,self.bitmap_value)
            self.directory_reads+=self.bitmap_reads
        self.block_reads={}
        for ordinal,(raw,_,_,_) in self.blocks.items():
            spans=self.place_logical(self.allocation_runs,ordinal*index,raw)
            self.block_reads[ordinal]=spans
            self.directory_reads+=spans
        # The existing boot fixture uses a4KiB index by default; bind the chosen
        # index explicitly without a checksum claim (its checksum field is zero).
        boot=self.input['regions'][0];raw=bytearray.fromhex(boot['hex'])
        raw[68]=(256-(index.bit_length()-1))&255;boot['hex']=raw.hex()
        self.initial_reads=self.bootstrap_reads+self.directory_reads
        self.expected_rows=[(None,row) for row in root_rows]
        for ordinal,(rows,_) in self.block_recipes.items():
            self.expected_rows += [(self.vbn(ordinal),row) for row in rows]

    def place(self,relative,value):
        for n in range(0,len(value),49152):
            self.input['regions'].append(dict(offset=str(self.offset+relative+n),hex=bytes(value[n:n+49152]).hex()))

    def place_logical(self,runs,start,value):
        spans=parts(runs,self.cluster,start,len(value));at=0
        for first,count in spans:self.place(first,value[at:at+count]);at+=count
        return [(self.offset+first,count) for first,count in spans]

    def place_record(self,number,value):
        self.record_regions[number]=self.place_logical(self.mft_runs,number*self.size,value)

    def bytes(self,at,length):return bytes_at(self.input,at,length)
    def regions(self):
        return [dict(offset=str(at),bytes=str(n),sha256=sha(self.bytes(at,n))) for at,n in self.initial_reads]
    def requests(self,reread=True):
        rows=self.initial_reads*(2 if reread else 1)
        return [dict(offset=str(at),bytes=str(n)) for at,n in rows]
    def mutate_record(self,number,at,raw):
        positions=[]
        for first,n in self.record_regions[number]:positions+=list(range(first,first+n))
        for offset,value in enumerate(raw):
            target=positions[at+offset]
            for region in self.input['regions']:
                start=int(region['offset']);data=bytearray.fromhex(region['hex'])
                if start<=target<start+len(data):data[target-start]=value;region['hex']=data.hex()

    def render_records(self):
        self.place_record(self.number,record(self.base_attributes,number=self.number,sequence=self.sequence,
                                            flags=3,size=self.size,usa=self.usa))
        for number,attributes in self.extension_attributes.items():
            self.place_record(number,record(attributes,number=number,sequence=self.ext_refs[number]>>48,
                                            base=self.reference,size=self.size,usa=self.usa))

    def replace_attribute(self,kind,transform):
        for attributes in [self.base_attributes,*self.extension_attributes.values()]:
            for i,a in enumerate(attributes):
                if struct.unpack_from('<I',a)[0]==kind:
                    attributes[i]=bytearray(transform(bytearray(a)))
        self.render_records()

    def replace_root(self,rows=None,value=None,children=None):
        if value is None:
            value,_=index_root(rows,cluster=self.cluster,index=self.index,
                               children=(self.kind not in {'leaf','empty','preallocated','orphan'}) if children is None else children)
        self.root_value=bytes(value)
        self.replace_attribute(0x90,lambda _:resident(value,name=I30,kind=0x90,instance=11))

    def replace_bitmap(self,value):
        self.bitmap_value=bytes(value)
        if self.bitmap_form=='resident':
            self.replace_attribute(0xb0,lambda _:resident(value,name=I30,kind=0xb0,instance=17))
        else:
            clusters=(len(value)+self.cluster-1)//self.cluster
            self.bitmap_runs=[(clusters,1300)] if clusters else []
            self.replace_attribute(0xb0,lambda _:nonresident(runs=self.bitmap_runs,allocated=clusters*self.cluster,
                data=len(value),initialized=len(value),name=I30,kind=0xb0,instance=17,
                high=clusters-1 if clusters else (1<<64)-1))
            self.bitmap_reads=self.place_logical(self.bitmap_runs,0,value)
            self.initial_reads=self.metadata_reads+self.bitmap_reads+[span for spans in self.block_reads.values() for span in spans]

    def replace_block(self,ordinal,rows,children=False):
        raw,logical,facts,items=index_block(size=self.index,rows=rows,children=children,vbn=self.vbn(ordinal))
        self.blocks[ordinal]=(bytes(raw),logical,facts,items)
        self.place_logical(self.allocation_runs,ordinal*self.index,raw)

    def mutate_block(self,ordinal,at,value):
        raw,logical,facts,items=self.blocks[ordinal];raw=bytearray(raw);raw[at:at+len(value)]=value
        self.blocks[ordinal]=(bytes(raw),logical,facts,items)
        self.place_logical(self.allocation_runs,ordinal*self.index,raw)
