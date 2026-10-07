// Test-only deterministic mutation driver over unmodified private C readers.
#include "mbr.h"
#include "ebr.h"
#include "gpt.h"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using Bytes = std::vector<unsigned char>;
static void require(bool v) { if (!v) throw std::runtime_error("campaign invariant"); }
struct Counts {
    std::size_t cases=0, mbr=0, ebr=0, headers=0, arrays=0, agree=0, disagree=0;
} counts;
static de_u64 exact(std::size_t n) { require(n<=2097152); return de_u64_from_u32(static_cast<de_u32>(n)); }
static std::size_t native(const de_u64& n) { std::size_t out=0; require(!de_u64_to_size(&n,&out)); return out; }
static de_view slice(const Bytes& data, std::size_t start, std::size_t length) {
    if (start>=data.size()) return {nullptr,0};
    return {data.data()+start,std::min(length,data.size()-start)};
}
static void extent(const de_block_extent& e, const de_block_space& space) {
    require(e.space==&space && de_u64_compare(&e.start,&e.end)<=0 && de_u64_compare(&e.end,&space.blocks)<=0);
}
static void observe(const Bytes& data, std::size_t blocks) {
    require(data.size()<=2097152 && blocks>=2 && blocks<=4096);
    const auto before=data; auto n=exact(blocks); de_block_space space{};
    require(!de_space_init("campaign",8,&n,512,&space)); de_mbr_geometry geometry{};
    de_mbr_table root{}; auto mbr=slice(data,0,512);
    require(!de_mbr_read(&mbr,&space,&geometry,&root));
    if(root.signature)++counts.mbr;
    for(unsigned slot=0;slot<4;++slot) {
        const auto& entry=root.entries[slot];
        if(entry.range_valid)extent(entry.extent,space);
        if(entry.kind!=DE_MBR_EXTENDED || !entry.range_valid)continue;
        std::vector<de_ebr_node> nodes(DE_EBR_LIMIT); de_ebr_walk walk{};
        if(de_ebr_init(&root,slot,&geometry,nodes.data(),nodes.size(),DE_EBR_LIMIT,&walk))continue;
        std::size_t feeds=0;
        while(walk.needs_block) {
            require(feeds++<DE_EBR_LIMIT && walk.count<DE_EBR_LIMIT);
            auto pending=walk.pending; auto start=native(pending); require(start<blocks);
            auto bytes=slice(data,start*512,512); auto previous=walk.count;
            if(!bytes.size)require(!de_ebr_unavailable(&walk));
            else { require(!de_ebr_feed(&walk,&pending,&bytes)); ++counts.ebr; }
            require(!walk.needs_block || walk.count>previous);
        }
        for(std::size_t i=0;i<walk.count;++i)
            for(const auto& entry2:nodes[i].table.entries)
                if(entry2.range_valid)extent(entry2.extent,space);
    }
    de_gpt_header header[2]{}; de_gpt_candidate candidate[2]{};
    std::vector<de_gpt_entry> rows[2]; de_gpt_limits limits{1024,4096,1048576};
    for(unsigned side=0;side<2;++side) {
        auto lba=exact(side?blocks-1:1); auto bytes=slice(data,native(lba)*512,512);
        require(!de_gpt_header_read(&bytes,&space,&lba,side?DE_GPT_BACKUP:DE_GPT_PRIMARY,&header[side]));
        candidate[side].header=&header[side]; if(header[side].consistent)++counts.headers;
        de_block_extent request{};
        if(de_gpt_request_array(&header[side],&limits,&request))continue;
        extent(request,space); auto begin=native(request.start),end=native(request.end);
        rows[side].resize(header[side].count); bytes=slice(data,begin*512,(end-begin)*512);
        require(!de_gpt_array_read(&header[side],&limits,&bytes,rows[side].data(),rows[side].size(),&candidate[side]));
        if(candidate[side].complete)++counts.arrays;
        require(candidate[side].count<=rows[side].size());
        for(std::size_t i=0;i<candidate[side].count;++i) {
            const auto& e=candidate[side].entries[i]; if(e.range_valid)extent(e.extent,space);
            require(e.raw.size==header[side].entry_size);
        }
    }
    int comparison=-1; require(!de_gpt_compare(&candidate[0],&candidate[1],&comparison));
    if(comparison==DE_GPT_AGREE) {
        ++counts.agree; require(candidate[0].consistent && candidate[1].consistent);
        const auto bytes=native(header[0].array_bytes); require(bytes==native(header[1].array_bytes));
        require(std::equal(candidate[0].raw_array.data,candidate[0].raw_array.data+bytes,candidate[1].raw_array.data));
    }
    if(comparison==DE_GPT_DISAGREE) { ++counts.disagree; require(candidate[0].consistent && candidate[1].consistent); }
    // Exercise encoding publication with independently selected output capacities.
    if(data.size()>=72) {
        auto name=slice(data,0,72); char text[109]; std::fill(text,text+109,'X'); int term=19;
        auto status=de_gpt_name_utf8(&name,text,data[0]%110,&term);
        if(status) { require(term==19); for(char ch:text)require(ch=='X'); }
    }
    require(data==before); ++counts.cases;
}
static std::uint32_t random_word(std::uint32_t& state) {
    state^=state<<13; state^=state>>17; state^=state<<5; return state;
}
static std::uint64_t little(const Bytes& b,std::size_t pos,unsigned width) {
    require(pos<=b.size() && width<=b.size()-pos); std::uint64_t out=0;
    for(unsigned i=0;i<width;++i)out|=static_cast<std::uint64_t>(b[pos+i])<<(i*8);
    return out;
}
static void put32(Bytes& b,std::size_t pos,std::uint32_t value) {
    require(pos+4<=b.size()); for(unsigned i=0;i<4;++i)b[pos+i]=static_cast<unsigned char>(value>>(i*8));
}
static std::uint32_t crc(const unsigned char* p,std::size_t size) {
    std::uint32_t v=0xffffffffU;
    for(std::size_t i=0;i<size;++i) { v^=p[i]; for(unsigned bit=0;bit<8;++bit)v=(v>>1)^((v&1)?0xedb88320U:0); }
    return v^0xffffffffU;
}
static void repair_test_crc(Bytes& data,std::size_t blocks) {
    for(auto lba:{std::size_t(1),blocks-1}) {
        auto h=lba*512; if(h>data.size() || data.size()-h<512)continue;
        auto size=little(data,h+12,4); if(size<92 || size>512)continue;
        auto start=little(data,h+72,8), count=little(data,h+80,4), width=little(data,h+84,4);
        auto bytes=count*width; // u32*u32 always fits this test harness's uint64_t.
        if(start<=data.size()/512 && bytes<=data.size()-static_cast<std::size_t>(start)*512)
            put32(data,h+88,crc(data.data()+static_cast<std::size_t>(start)*512,static_cast<std::size_t>(bytes)));
        put32(data,h+16,0); put32(data,h+16,crc(data.data()+h,static_cast<std::size_t>(size)));
    }
}
static Bytes load(const char* path) {
    std::ifstream in(path,std::ios::binary|std::ios::ate); require(static_cast<bool>(in));
    auto n=in.tellg(); require(n>=0 && n<=2097152); Bytes out(static_cast<std::size_t>(n));
    in.seekg(0); if(n)require(static_cast<bool>(in.read(reinterpret_cast<char*>(out.data()),n))); return out;
}
static void save(const char* path,const Bytes& bytes) {
    std::ofstream out(path,std::ios::binary); require(static_cast<bool>(out));
    if(!bytes.empty())out.write(reinterpret_cast<const char*>(bytes.data()),static_cast<std::streamsize>(bytes.size()));
    out.close(); require(static_cast<bool>(out));
}
static Bytes mutate(const Bytes& seed,std::uint32_t& state,std::size_t iteration,std::size_t blocks) {
    auto data=seed;
    for(unsigned change=0,limit=1+random_word(state)%8;change<limit && !data.empty();++change) {
        auto pos=static_cast<std::size_t>(random_word(state))%data.size();
        if(iteration%3==0)pos%=std::min(std::size_t(17408),data.size());
        if(iteration%3==1 && data.size()>=16896)pos=data.size()-16896+(pos%16896);
        data[pos]^=static_cast<unsigned char>(1+random_word(state)%255);
    }
    if(iteration%4==0)repair_test_crc(data,blocks);
    if(iteration%7==0 && !data.empty())data.resize(random_word(state)%data.size());
    return data;
}
int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--control-failure")require(false);
        require(argc>=6); const std::string mode=argv[1]; require(mode=="--run" || mode=="--emit" || mode=="--control");
        auto iterations=std::stoul(argv[2]); require(iterations<=1000000);
        auto seed=std::stoul(argv[3]); require(seed>0 && seed<=0xffffffffUL);
        const auto blocks=std::stoul(argv[4]); require(blocks>=2 && blocks<=4096);
        int first=5; const char* output=nullptr;
        if(mode=="--emit") { require(argc>=7); output=argv[first++]; }
        std::vector<Bytes> seeds; for(int i=first;i<argc;++i)seeds.push_back(load(argv[i]));
        require(!seeds.empty() && seeds.size()<=128); std::uint32_t state=static_cast<std::uint32_t>(seed);
        const auto total=mode=="--emit"?iterations+1:iterations+seeds.size();
        for(std::size_t i=0;i<total;++i) {
            const auto index=i<seeds.size()?i:random_word(state)%seeds.size();
            auto data=i<seeds.size()?seeds[index]:mutate(seeds[index],state,i,blocks);
            if(mode=="--emit") { if(i==iterations)save(output,data); continue; }
            std::cout<<"case "<<i<<" seed "<<index<<" bytes "<<data.size()<<" crc32 "<<crc(data.data(),data.size())<<std::endl;
            if(mode=="--control" && i==seeds.size())require(false);
            observe(data,blocks);
        }
        if(mode=="--run")std::cout<<"{\"cases\":"<<counts.cases<<",\"mbr_signatures\":"<<counts.mbr
            <<",\"ebr_feeds\":"<<counts.ebr<<",\"consistent_headers\":"<<counts.headers
            <<",\"complete_arrays\":"<<counts.arrays<<",\"agree\":"<<counts.agree<<",\"disagree\":"<<counts.disagree<<"}"<<std::endl;
        return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
