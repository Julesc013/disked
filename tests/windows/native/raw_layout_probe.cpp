#include "storage_layout.h"
#include "storage_frame_reader.h"
#include "storage_fixture.h"
#include "local_file.h"
#include "memory_budget.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;namespace f=disked::local_file;
const V& get(const V& v,const char* k) {const auto* p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* k) {const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return p.text;}
std::uint64_t integer(const V& v,const char* k) {const auto s=text(v,k);if(!disked::json::decimal_u64(s))throw std::invalid_argument("fixture_integer");return std::stoull(s);}
void print(V v) {v.put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
    disked::json::Limits l;l.bytes=2097152;l.values=131072;l.depth=24;std::puts(disked::json::dump(v,l).c_str());}
std::vector<unsigned char> read(const V& input,V& facts) {
    const auto path=f::path_for(text(input,"image"));auto parents=f::pin_parents(path);const auto ancestor=f::parent_generations(parents);
    f::Handle h(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_RANDOM_ACCESS,nullptr));
    if(h.value==INVALID_HANDLE_VALUE)throw f::Error("fixture_open",GetLastError());
    f::ordinary(h.value,false);f::bind_path(h.value,path);f::check_parents(path,parents,ancestor);
    const auto before=f::metadata(h.value);if(before.size>16U*1024U*1024U)throw std::invalid_argument("fixture_image_budget");
    std::vector<unsigned char> bytes(static_cast<std::size_t>(before.size));DWORD got=0;
    if(!bytes.empty() && (!ReadFile(h.value,bytes.data(),static_cast<DWORD>(bytes.size()),&got,nullptr) || got!=bytes.size()))throw f::Error("fixture_read",GetLastError());
    const auto after=f::metadata(h.value);f::bind_path(h.value,path);f::check_parents(path,parents,ancestor);
    if(disked::json::dump(before.value)!=disked::json::dump(after.value))throw std::invalid_argument("fixture_changed");
    facts=V::object().put("before",before.value).put("after",after.value).put("bytes",V::string(std::to_string(bytes.size())));
    return bytes;
}
}
int wmain(int argc,wchar_t**) {
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try {
        disked::WindowsMemoryBudget memory;if(!memory.ready())throw std::runtime_error(memory.error());
        std::vector<char> b(524289);const auto count=std::fread(b.data(),1,b.size(),stdin);if(!count || count==b.size() || std::ferror(stdin))return 2;
        auto l=n::storage_observation_limits();l.bytes=524288;l.depth=24;l.values=65536;l.string_bytes=32768;
        const auto input=disked::json::parse(std::string(b.data(),count),l);const auto& fixture=get(input,"fixture");
        if(text(fixture,"profile")!="identity-layout")throw std::invalid_argument("fixture_profile");
        const auto subjects=n::storage_fixture_subjects(fixture);auto api=disked::nt_storage_fixture::api(fixture);
        if(const auto* p=input.find("api")) {if(p->text=="native")api=n::native_storage_query_api();if(p->text=="mixed-io")api.ioctl=&DeviceIoControl;if(p->text=="mixed-error")api.error=&GetLastError;}
        // Constructor validates the injected dispatch table before reading a file.
        n::StorageQueryPort validation(api,subjects[0].handle,{});
        if(const auto* p=input.find("mode"))if(p->text=="construction") {print(V::object().put("status",V::string("constructed")));return 0;}
        const auto block_text=text(input,"blocks");de_u64 blocks{};
        if(de_u64_parse(block_text.c_str(),block_text.size(),&blocks)!=DE_OK)throw std::invalid_argument("fixture_blocks");
        const auto unit=integer(input,"unit");if(unit>0xffffffffULL)throw std::invalid_argument("fixture_unit");
        disked::RawLayoutPolicy policy;if(const auto* p=input.find("policy")) {const auto parts=integer(*p,"partitions"),nodes=integer(*p,"ebr_nodes");
            if(parts>64 || nodes>128)throw std::invalid_argument("fixture_policy");policy.partitions=static_cast<unsigned>(parts);policy.ebr_nodes=static_cast<unsigned>(nodes);}
        V facts;const auto bytes=read(input,facts);const auto raw=disked::decode_raw_layout(bytes,blocks,static_cast<de_u32>(unit),policy);
        if(text(get(raw->value(),"source"),"sha256")!=text(input,"expected_image_digest"))throw std::invalid_argument("fixture_image_digest");
        const auto epoch=integer(input,"capture"),worker=integer(input,"worker");
        const auto frame=n::collect_storage_frame(api,subjects,epoch,{}, {},n::StorageFrameProfile::IdentityLayout);
        n::LayoutBinding binding{{text(input,"source"),epoch,worker},text(input,"subject"),n::storage_layout_frame_digest(*frame),n::raw_layout_digest(*raw)};
        if(const auto* p=input.find("binding")) {
            if(p->find("source"))binding.capture.source=text(*p,"source");if(p->find("capture"))binding.capture.capture=integer(*p,"capture");
            if(p->find("worker"))binding.capture.worker=integer(*p,"worker");if(p->find("subject"))binding.subject=text(*p,"subject");
            if(p->find("frame_digest"))binding.frame_digest=text(*p,"frame_digest");if(p->find("raw_digest"))binding.raw_digest=text(*p,"raw_digest");
        }
        const auto calls=disked::nt_storage_fixture::call_count();const auto compared=n::compare_storage_layout(*frame,*raw,binding);
        if(calls!=disked::nt_storage_fixture::call_count() || binding.frame_digest!=n::storage_layout_frame_digest(*frame) || binding.raw_digest!=n::raw_layout_digest(*raw))throw std::runtime_error("fixture_comparison_effect");
        print(V::object().put("raw",raw->value()).put("comparison",compared).put("frame",frame->value()).put("file",facts)
            .put("trace",disked::nt_storage_fixture::calls_trace()).put("comparison_api_calls",V::string("0"))
            .put("memory_limit_bytes",V::string(std::to_string(memory.limit_bytes()))));return 0;
    }catch(const std::exception& e) {print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
