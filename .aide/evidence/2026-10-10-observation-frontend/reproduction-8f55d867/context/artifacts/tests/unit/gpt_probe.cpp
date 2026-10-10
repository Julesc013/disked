#include "gpt.h"
#include "json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using V=disked::json::Value;
static void require(bool v){if(!v)throw std::runtime_error("probe invariant");}
static V number(unsigned long n){return V::number(std::to_string(n));}
static std::string decimal(const de_u64& n){char s[21];require(!de_u64_format(&n,s,sizeof(s)));return s;}
static const V& field(const V& v,const char* key){auto* p=v.find(key);require(p!=nullptr);return *p;}
static de_u64 exact(const V& v){de_u64 n{};require(v.kind==V::Kind::string&&!de_u64_parse(v.text.data(),v.text.size(),&n));return n;}
static de_u32 small(const V& v){auto n=exact(v);de_u32 out=0;require(!de_u64_to_u32(&n,&out));return out;}
static unsigned digit(char ch){if(ch>='0'&&ch<='9')return static_cast<unsigned>(ch-'0');if(ch>='a'&&ch<='f')return 10+static_cast<unsigned>(ch-'a');throw std::runtime_error("hex");}
static std::vector<unsigned char> unhex(const V& v){
    require(v.kind==V::Kind::string&&v.text.size()%2==0);std::vector<unsigned char> out(v.text.size()/2);
    for(std::size_t i=0;i<out.size();++i)out[i]=static_cast<unsigned char>(digit(v.text[2*i])*16+digit(v.text[2*i+1]));
    return out;
}
static std::string hex(de_view v){
    static const char chars[]="0123456789abcdef";std::string out;
    for(std::size_t i=0;i<v.size;++i){out+=chars[v.data[i]>>4];out+=chars[v.data[i]&15];}return out;
}
static std::string guid(const unsigned char* bytes){char out[37];de_view v{bytes,16};require(!de_gpt_guid_text(&v,out,sizeof(out)));return out;}
static V header(const de_gpt_header& h){
    auto v=V::object();v.put("raw",V::string(hex(h.raw))).put("consistent",V::boolean_value(h.consistent!=0));
    v.put("issues",number(h.issues)).put("revision",number(h.revision)).put("header_size",number(h.header_size));
    v.put("my_lba",V::string(decimal(h.my_lba))).put("alternate",V::string(decimal(h.alternate_lba)));
    v.put("first",V::string(decimal(h.first_usable))).put("last",V::string(decimal(h.last_usable)));
    v.put("array_lba",V::string(decimal(h.array_lba))).put("array_bytes",V::string(decimal(h.array_bytes)));
    v.put("array_blocks",V::string(decimal(h.array_blocks))).put("count",number(h.count)).put("entry_size",number(h.entry_size));
    v.put("disk_guid",V::string(guid(h.disk_guid)));return v;
}
static V candidate(const de_gpt_candidate& c){
    auto v=V::object();v.put("raw",V::string(hex(c.raw_array))).put("complete",V::boolean_value(c.complete!=0));
    v.put("consistent",V::boolean_value(c.consistent!=0)).put("issues",number(c.issues));auto rows=V::array();
    for(std::size_t i=0;i<c.count;++i){
        const auto& e=c.entries[i];auto row=V::object();row.put("raw",V::string(hex(e.raw)));
        row.put("active",V::boolean_value(e.active!=0)).put("issues",number(e.issues));
        row.put("range_valid",V::boolean_value(e.range_valid!=0)).put("first",V::string(decimal(e.first))).put("last",V::string(decimal(e.last)));
        row.put("attributes",V::string(decimal(e.attributes)));
        if(e.range_valid)row.put("end",V::string(decimal(e.extent.end)));
        if(e.active){
            row.put("type_guid",V::string(guid(e.raw.data))).put("unique_guid",V::string(guid(e.raw.data+16)));
            char text[109];int terminated=0;de_view name{e.raw.data+56,72};
            auto status=de_gpt_name_utf8(&name,text,sizeof(text),&terminated);
            row.put("name_status",number(static_cast<unsigned long>(status))).put("terminated",V::boolean_value(e.name_terminated!=0));
            if(!status)row.put("name",V::string(text));
        }
        rows.items.push_back(row);
    }
    v.put("entries",rows);return v;
}
static V observe(const V& in){
    if(auto* encoding=in.find("encoding")){
        auto data=unhex(*encoding);de_view view{data.data(),data.size()};de_u32 crc=0;
        require(!de_gpt_crc32(&view,&crc));auto out=V::object();out.put("crc",number(crc));
        if(data.size()==16)out.put("guid",V::string(guid(data.data())));
        if(data.size()==72){
            char text[109];std::memset(text,'X',sizeof(text));int term=19;
            auto capacity=in.find("capacity")?small(field(in,"capacity")):109;require(capacity<=109);
            auto status=de_gpt_name_utf8(&view,text,capacity,&term);out.put("status",number(static_cast<unsigned long>(status)));
            if(!status)out.put("name",V::string(text)).put("terminated",V::boolean_value(term!=0));
            else {require(term==19);for(char ch:text)require(ch=='X');}
        }
        return out;
    }
    auto blocks=exact(field(in,"blocks"));auto unit=small(field(in,"unit"));
    de_block_space space{};require(!de_space_init("synthetic",9,&blocks,unit,&space));auto other=space;
    de_gpt_limits limits{small(field(in,"max_entries")),small(field(in,"max_entry_size")),small(field(in,"max_bytes"))};
    auto one=de_u64_from_u32(1),last=blocks;require(!de_u64_sub(&blocks,&one,&last));
    std::vector<unsigned char> data[2]={unhex(field(in,"primary")),unhex(field(in,"backup"))};
    std::vector<unsigned char> arrays[2]={unhex(field(in,"primary_array")),unhex(field(in,"backup_array"))};
    auto before0=data[0],before1=data[1],array0=arrays[0],array1=arrays[1];
    de_gpt_header h[2]{};de_gpt_candidate c[2]{};std::vector<de_gpt_entry> rows[2];
    auto results=V::array();
    for(unsigned i=0;i<2;++i){
        de_view bytes{data[i].data(),data[i].size()};auto lba=i?last:one;
        const bool separate=in.find("separate_space")&&field(in,"separate_space").boolean;
        auto status=de_gpt_header_read(&bytes,(i&&separate)?&other:&space,&lba,i?DE_GPT_BACKUP:DE_GPT_PRIMARY,&h[i]);
        auto v=V::object();v.put("status",number(static_cast<unsigned long>(status)));c[i].header=&h[i];
        if(!status){
            v.put("header",header(h[i]));de_block_extent request{};
            auto rs=de_gpt_request_array(&h[i],&limits,&request);v.put("request_status",number(static_cast<unsigned long>(rs)));
            if(!rs){
                v.put("request_start",V::string(decimal(request.start))).put("request_end",V::string(decimal(request.end)));
                rows[i].resize(h[i].count);de_view a{arrays[i].data(),arrays[i].size()};
                auto as=de_gpt_array_read(&h[i],&limits,&a,rows[i].data(),rows[i].size(),&c[i]);
                v.put("array_status",number(static_cast<unsigned long>(as)));
                if(!as)v.put("candidate",candidate(c[i]));
            }
        }
        results.items.push_back(v);
    }
    int comparison=-1;auto status=de_gpt_compare(&c[0],&c[1],&comparison);
    auto out=V::object();out.put("copies",results).put("compare_status",number(static_cast<unsigned long>(status)));
    if(!status)out.put("comparison",number(static_cast<unsigned long>(comparison)));
    require(data[0]==before0&&data[1]==before1&&arrays[0]==array0&&arrays[1]==array1);return out;
}
static void store(unsigned char* p,std::size_t offset,unsigned long n,unsigned width){
    for(unsigned i=0;i<width;++i){p[offset+i]=static_cast<unsigned char>(n&255);n>>=8;}
}
static int guard(){
    SYSTEM_INFO info{};GetSystemInfo(&info);require(info.dwPageSize>=512);
    auto* hp=static_cast<unsigned char*>(VirtualAlloc(nullptr,2*info.dwPageSize,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));require(hp!=nullptr);
    auto pages=(16384U+info.dwPageSize-1)/info.dwPageSize;
    auto* ap=static_cast<unsigned char*>(VirtualAlloc(nullptr,(pages+1)*info.dwPageSize,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));require(ap!=nullptr);
    auto* hbytes=hp+info.dwPageSize-512;auto* abytes=ap+pages*info.dwPageSize-16384;DWORD old=0;
    std::memcpy(hbytes,"EFI PART",8);store(hbytes,8,0x10000,4);store(hbytes,12,92,4);
    store(hbytes,24,1,8);store(hbytes,32,99,8);store(hbytes,40,34,8);store(hbytes,48,66,8);hbytes[56]=1;
    store(hbytes,72,2,8);store(hbytes,80,128,4);store(hbytes,84,128,4);
    de_view aview{abytes,16384},hview{hbytes,92};de_u32 crc=0;
    require(!de_gpt_crc32(&aview,&crc));store(hbytes,88,crc,4);
    require(!de_gpt_crc32(&hview,&crc));store(hbytes,16,crc,4);hview.size=512;
    require(VirtualProtect(hp,info.dwPageSize,PAGE_READONLY,&old)!=0&&VirtualProtect(hp+info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old)!=0);
    require(VirtualProtect(ap,pages*info.dwPageSize,PAGE_READONLY,&old)!=0&&VirtualProtect(ap+pages*info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old)!=0);
    auto blocks=de_u64_from_u32(100),lba=de_u64_from_u32(1);de_block_space space{};
    require(!de_space_init("guard",5,&blocks,512,&space));de_gpt_header h{};
    require(!de_gpt_header_read(&hview,&space,&lba,DE_GPT_PRIMARY,&h)&&h.consistent);
    de_gpt_limits limits{128,128,16384};std::vector<de_gpt_entry> rows(128);de_gpt_candidate c{};
    require(!de_gpt_array_read(&h,&limits,&aview,rows.data(),rows.size(),&c)&&c.consistent&&c.complete);
    unsigned char saved[sizeof(c)];std::memcpy(saved,&c,sizeof(c));de_view too_long{abytes,16385};
    require(de_gpt_array_read(&h,&limits,&too_long,rows.data(),rows.size(),&c)==DE_BOUNDS&&std::memcmp(saved,&c,sizeof(c))==0);
    de_view inaccessible{ap+pages*info.dwPageSize,16384};auto tight=limits;tight.entries=127;
    require(de_gpt_array_read(&h,&tight,&inaccessible,rows.data(),rows.size(),&c)==DE_BUFFER&&std::memcmp(saved,&c,sizeof(c))==0);
    require(de_gpt_array_read(&h,&limits,&inaccessible,rows.data(),127,&c)==DE_BUFFER&&std::memcmp(saved,&c,sizeof(c))==0);
    unsigned char saved_header[sizeof(h)];std::memcpy(saved_header,&h,sizeof(h));de_view long_header{hbytes,513};
    require(de_gpt_header_read(&long_header,&space,&lba,DE_GPT_PRIMARY,&h)==DE_BOUNDS&&std::memcmp(saved_header,&h,sizeof(h))==0);
    for(auto n:{0U,1U,127U,128U,511U,512U,16383U}){
        de_view short_view{ap+pages*info.dwPageSize-n,n};
        require(!de_gpt_array_read(&h,&limits,&short_view,rows.data(),rows.size(),&c)&&!c.complete&&c.issues==DE_GPT_TRUNCATED);
    }
    for(std::size_t n=0;n<512;++n){
        de_view short_view{hp+info.dwPageSize-n,n};
        require(!de_gpt_header_read(&short_view,&space,&lba,DE_GPT_PRIMARY,&h)&&h.issues==DE_GPT_TRUNCATED);
    }
    require(VirtualFree(hp,0,MEM_RELEASE)!=0&&VirtualFree(ap,0,MEM_RELEASE)!=0);
    std::puts("GPT C/C++ linkage and protected header/array boundaries passed.");return 0;
}
int main(int argc,char** argv){
    try{
        if(argc==2&&std::string(argv[1])=="--guard")return guard();
        require(argc==1);disked::json::Limits limits;limits.bytes=32*1024*1024;limits.string_bytes=24*1024*1024;limits.values=65536;
        std::string line;while(std::getline(std::cin,line)){require(line.size()<=limits.bytes);std::cout<<disked::json::dump(observe(disked::json::parse(line,limits)),limits)<<'\n';}
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
