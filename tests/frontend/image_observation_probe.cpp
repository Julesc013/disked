#include "map_observation.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <io.h>

int main(int argc,char** argv) {
    using disked::json::Value;
    try {
        if(argc!=3)return 2;de_u64 blocks{},unit64{};de_u32 unit=0;
        if(de_u64_parse(argv[1],std::strlen(argv[1]),&blocks) ||
           de_u64_parse(argv[2],std::strlen(argv[2]),&unit64) || de_u64_to_u32(&unit64,&unit))return 2;
        if(_setmode(_fileno(stdin),_O_BINARY)==-1)return 4;
        std::vector<unsigned char> bytes;unsigned char chunk[8192];
        constexpr std::size_t maximum=16U*1024U*1024U+1;
        while(bytes.size()<maximum) {
            const auto want=std::min<std::size_t>(sizeof(chunk),maximum-bytes.size());
            const auto got=std::fread(chunk,1,want,stdin);bytes.insert(bytes.end(),chunk,chunk+got);
            if(got<want) {if(std::ferror(stdin))return 4;break;}
        }
        auto before=bytes;auto result=disked::observe_partition_map(bytes,blocks,unit);
        if(before!=bytes)return 4;
        // Returned observations own their fields, including names and raw data.
        bytes.assign(bytes.size(),0xa5);bytes.clear();bytes.shrink_to_fit();
        const auto text=disked::json::dump(result);std::puts(text.c_str());return 0;
    } catch(const disked::MapObservationError& error) {
        const auto text=disked::json::dump(Value::object().put("refusal",Value::string(error.what())));
        std::puts(text.c_str());return 3;
    } catch(const std::exception&) {return 4;}
}
