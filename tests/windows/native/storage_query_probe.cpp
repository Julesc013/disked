#include "storage_inventory.h"
#include "storage_fixture.h"
#include <algorithm>
#include <cstdio>
#include <io.h>
#include <fcntl.h>
#include <map>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
V fixture;
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::uint64_t num(const V& v){if(v.kind!=V::Kind::string || !disked::json::decimal_u64(v.text))throw std::invalid_argument("fixture_integer");return std::stoull(v.text);}
DWORD word(const V& v){const auto n=num(v);if(n>0xffffffffULL)throw std::invalid_argument("fixture_integer");return static_cast<DWORD>(n);}
void print(V v) {v.put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count()))).put("error_calls",V::string(std::to_string(disked::nt_storage_fixture::error_count()))).put("trace",disked::nt_storage_fixture::calls_trace()).put("pointer_bytes",V::string(std::to_string(sizeof(void*))));
    disked::json::Limits l;l.bytes=2097152;l.values=131072;std::puts(disked::json::dump(v,l).c_str());std::fflush(stdout);}
}
int wmain(int argc,wchar_t**) {
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try {
        char b[262145];const auto size=std::fread(b,1,sizeof(b),stdin);if(!size || size==sizeof(b) || std::ferror(stdin))return 2;
        disked::json::Limits l;l.bytes=262144;l.values=32768;l.depth=24;fixture=disked::json::parse(std::string(b,size),l);
        auto api=disked::nt_storage_fixture::api(fixture);
        if(const auto p=fixture.find("api")) {if(p->text=="native")api=n::native_storage_query_api();if(p->text=="mixed-io")api.ioctl=&DeviceIoControl;if(p->text=="mixed-error")api.error=&GetLastError;}
        n::StorageQueryPolicy policy;if(const auto p=fixture.find("policy")) {policy.descriptor_bytes=word(get(*p,"descriptor_bytes"));policy.string_bytes=word(get(*p,"string_bytes"));policy.extents=word(get(*p,"extents"));}
        std::vector<n::StorageSubject> subjects;std::size_t i=0;
        for(const auto& s:get(fixture,"subjects").items) {
            n::StorageSubject subject;subject.key=get(s,"key").text;subject.kind=get(s,"kind").text=="disk"?n::StorageSubjectKind::Disk:get(s,"kind").text=="volume"?n::StorageSubjectKind::Volume:static_cast<n::StorageSubjectKind>(-1);
            subject.handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(123+i++));
            if(const auto p=s.find("label_units"))for(const auto& unit:p->items) {const auto n=num(unit);if(n>65535)throw std::invalid_argument("fixture_units");subject.label+=static_cast<wchar_t>(n);}else subject.label.assign(subject.key.begin(),subject.key.end());
            if(const auto p=s.find("invalid_handle"))if(p->boolean)subject.handle=INVALID_HANDLE_VALUE;subjects.push_back(std::move(subject));
        }
        if(const auto mode=fixture.find("mode")) {
            if(subjects.empty())throw std::invalid_argument("fixture_subjects");n::StorageQueryPort port(api,subjects[0].handle,policy);
            if(mode->text=="construction") {print(V::object().put("constructed",V::boolean_value(true)));return 0;}
            if(mode->text=="reuse") {port.descriptor();port.descriptor();}
        }
        const auto capture=fixture.find("capture")?num(get(fixture,"capture")):1;
        const auto stop=fixture.find("cancel_after_io")?num(get(fixture,"cancel_after_io")):0xffffffffULL;
        const auto frame=n::collect_storage_frame(api,subjects,capture,policy,[&] {return disked::nt_storage_fixture::call_count()>=stop;});
        const auto context=disked::digest_sha256(disked::json::dump(fixture,l));
        const auto graph=n::project_storage_frame(*frame,{"storage",capture,1},context);
        print(V::object().put("frame",frame->value()).put("fixture_context_digest",V::string(context)).put("graph",disked::GraphSnapshot::create(graph,capture)->value()));return 0;
    }catch(const std::exception& e) {print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
