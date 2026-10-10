#include "mbr.h"
#include "ebr.h"
#include "json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

using V = disked::json::Value;
static void require(bool value) { if(!value)throw std::runtime_error("probe invariant"); }
static V number(unsigned long value) { return V::number(std::to_string(value)); }
static std::string decimal(const de_u64& value) {
    char text[21]; require(de_u64_format(&value,text,sizeof(text))==DE_OK);return text;
}
static de_u64 exact(const V& value) {
    require(value.kind==V::Kind::string);de_u64 n{};
    require(de_u64_parse(value.text.data(),value.text.size(),&n)==DE_OK);return n;
}
static unsigned long small(const V& value) {
    auto n=exact(value);de_u32 result=0;require(de_u64_to_u32(&n,&result)==DE_OK);return result;
}
static const V& field(const V& value,const char* name) {
    auto* v=value.find(name);require(v!=nullptr);return *v;
}
static unsigned int digit(char ch) {
    if(ch>='0'&&ch<='9')return static_cast<unsigned>(ch-'0');
    if(ch>='a'&&ch<='f')return 10U+static_cast<unsigned>(ch-'a');
    throw std::runtime_error("hex");
}
static std::vector<unsigned char> unhex(const V& value) {
    require(value.kind==V::Kind::string&&value.text.size()%2==0);
    std::vector<unsigned char> result(value.text.size()/2);
    for(std::size_t i=0;i<result.size();++i)
        result[i]=static_cast<unsigned char>(digit(value.text[2*i])*16+digit(value.text[2*i+1]));
    return result;
}
static std::string hex(de_view bytes) {
    static const char chars[]="0123456789abcdef";std::string out;
    for(std::size_t i=0;i<bytes.size;++i){out+=chars[bytes.data[i]>>4];out+=chars[bytes.data[i]&15];}
    return out;
}
static V entry(const de_mbr_entry& e) {
    auto out=V::object();out.put("raw",V::string(hex({e.raw,16})));
    out.put("active",V::boolean_value(e.active!=0)).put("kind",number(static_cast<unsigned long>(e.kind)));
    out.put("relative",V::string(decimal(e.relative_start))).put("count",V::string(decimal(e.blocks)));
    out.put("range_valid",V::boolean_value(e.range_valid!=0)).put("issues",number(e.issues));
    out.put("chs_compared",number(e.chs_compared));
    if(e.range_valid)out.put("start",V::string(decimal(e.extent.start))).put("end",V::string(decimal(e.extent.end)));
    return out;
}
static V table(const de_mbr_table& t) {
    auto out=V::object();out.put("raw",V::string(hex(t.raw))).put("signature",V::boolean_value(t.signature!=0));
    out.put("issues",number(t.issues));auto entries=V::array();
    for(const auto& e:t.entries)entries.items.push_back(entry(e));
    out.put("entries",entries);return out;
}
static V observe(const V& input) {
    auto count=exact(field(input,"blocks"));auto unit=small(field(input,"unit"));
    auto heads=small(field(input,"heads")),sectors=small(field(input,"sectors"));
    require(heads<=256&&sectors<=63);
    de_mbr_geometry geometry{static_cast<unsigned short>(heads),static_cast<unsigned short>(sectors)};
    de_block_space space{};require(de_space_init("synthetic",9,&count,unit,&space)==DE_OK);
    const auto& blocks=field(input,"image");require(blocks.kind==V::Kind::object);
    std::map<std::string,std::vector<unsigned char>> image;
    for(const auto& item:blocks.fields)image.emplace(item.first,unhex(item.second));
    const auto before=image;auto found=image.find("0");require(found!=image.end());
    de_view bytes{found->second.data(),found->second.size()};de_mbr_table root{};
    auto status=de_mbr_read(&bytes,&space,&geometry,&root);
    auto output=V::object();output.put("status",number(static_cast<unsigned long>(status)));
    if(status){require(image==before);return output;}
    output.put("mbr",table(root));auto walks=V::array();
    auto limit=small(field(input,"limit"));require(limit<=DE_EBR_LIMIT);
    for(unsigned slot=0;slot<4;++slot) {
        const auto& e=root.entries[slot];if(e.kind!=DE_MBR_EXTENDED||!e.range_valid)continue;
        std::vector<de_ebr_node> nodes(DE_EBR_LIMIT);de_ebr_walk walk{};
        auto init=de_ebr_init(&root,slot,&geometry,nodes.data(),nodes.size(),limit,&walk);
        auto w=V::object();w.put("slot",number(slot)).put("status",number(static_cast<unsigned long>(init)));
        auto requests=V::array();
        if(!init)while(walk.needs_block) {
            require(walk.count<limit);auto lba=walk.pending;auto address=decimal(lba);
            requests.items.push_back(V::string(address));auto block=image.find(address);
            if(block==image.end()){require(de_ebr_unavailable(&walk)==DE_OK);break;}
            de_view next{block->second.data(),block->second.size()};
            // Refused wrong-address feeds must not consume a node or alter state.
            unsigned char saved[sizeof(walk)];std::memcpy(saved,&walk,sizeof(walk));
            auto wrong=de_u64_from_u32(0);
            if(!de_u64_compare(&wrong,&lba))wrong=de_u64_from_u32(1);
            require(de_ebr_feed(&walk,&wrong,&next)==DE_INVALID&&std::memcmp(saved,&walk,sizeof(walk))==0);
            require(de_ebr_feed(&walk,&lba,&next)==DE_OK);
        }
        w.put("requests",requests).put("complete",V::boolean_value(walk.complete!=0));
        w.put("issues",number(walk.issues));auto observations=V::array();
        for(std::size_t i=0;i<walk.count;++i) {
            auto n=table(nodes[i].table);n.put("lba",V::string(decimal(nodes[i].lba)));observations.items.push_back(n);
        }
        w.put("nodes",observations);walks.items.push_back(w);
    }
    output.put("walks",walks);require(image==before);return output;
}
static int guard() {
    SYSTEM_INFO info{};GetSystemInfo(&info);require(info.dwPageSize>=512);
    auto* pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,2*info.dwPageSize,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    require(pages!=nullptr);DWORD old=0;
    require(VirtualProtect(pages+info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old)!=0);
    auto* last=pages+info.dwPageSize-512;last[510]=0x55;last[511]=0xaa;
    last[450]=5;last[454]=1;last[458]=9;
    require(VirtualProtect(pages,info.dwPageSize,PAGE_READONLY,&old)!=0);
    de_block_space space{};auto blocks=de_u64_from_u32(10);
    require(de_space_init("guard",5,&blocks,512,&space)==DE_OK);
    de_mbr_geometry geometry{};de_view bytes{last,512};de_mbr_table root{};
    require(de_mbr_read(&bytes,&space,&geometry,&root)==DE_OK&&root.signature&&root.issues==0);
    require(root.raw.data==last&&root.entries[0].range_valid);
    de_ebr_node node{};de_ebr_walk walk{};
    require(de_ebr_init(&root,0,&geometry,&node,1,1,&walk)==DE_OK);
    auto pending=walk.pending;
    unsigned char saved_walk[sizeof(walk)];std::memcpy(saved_walk,&walk,sizeof(walk));
    de_view too_large{last,513};
    require(de_ebr_feed(&walk,&pending,&too_large)==DE_BOUNDS&&std::memcmp(saved_walk,&walk,sizeof(walk))==0);
    require(de_ebr_feed(&walk,&pending,&bytes)==DE_OK&&(walk.issues&DE_MBR_LAYOUT));
    // Every shorter block ends at the inaccessible boundary and must not decode.
    for(std::size_t n=0;n<512;++n) {
        de_view short_view{pages+info.dwPageSize-n,n};
        require(de_mbr_read(&short_view,&space,&geometry,&root)==DE_OK&&root.issues==DE_MBR_TRUNCATED);
    }
    unsigned char saved[sizeof(root)];std::memcpy(saved,&root,sizeof(root));
    de_view too_long{last,513};
    require(de_mbr_read(&too_long,&space,&geometry,&root)==DE_BOUNDS&&std::memcmp(saved,&root,sizeof(root))==0);
    require(VirtualFree(pages,0,MEM_RELEASE)!=0);std::puts("C MBR/EBR linkage, immutable pages and 512 truncated boundaries passed.");return 0;
}
int main(int argc,char** argv) {
    try {
        if(argc==2&&std::string(argv[1])=="--guard")return guard();
        require(argc==1);disked::json::Limits limits;limits.bytes=4*1024*1024;limits.string_bytes=3*1024*1024;limits.values=16384;
        std::string line;
        while(std::getline(std::cin,line)) {
            require(line.size()<=limits.bytes);
            std::cout<<disked::json::dump(observe(disked::json::parse(line,limits)),limits)<<'\n';
        }
        return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
