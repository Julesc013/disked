#include "namespace_worker.h"
#include "volume_fixture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !disked::json::decimal_u64(v.text))throw std::invalid_argument("fixture_integer");return std::stoull(v.text);}
void print(const V& v) {std::puts(disked::json::dump(v,n::namespace_worker_limits()).c_str());std::fflush(stdout);}
}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify) {
        const auto fault=v.find("worker_fault");if(fault && fault->kind==V::Kind::string && fault->text=="native_table")return n::native_volume_api();
        return disked::nt_fixture::api(v,notify);
    });
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc!=1)return 2;
    try {
        char buffer[65536];const auto size=std::fread(buffer,1,sizeof(buffer),stdin);if(!size || size==sizeof(buffer) || std::ferror(stdin))return 2;
        disked::json::Limits l;l.bytes=65535;l.values=16384;l.depth=24;const auto value=disked::json::parse(std::string(buffer,size),l);
        const auto& fixture=field(value,"fixture");n::NamespaceInput r;r.capture_epoch=integer(field(fixture,"capture_epoch"));r.provider_input=fixture;
        const auto v=integer(field(fixture,"volume_limit")),m=integer(field(fixture,"mount_limit")),u=integer(field(fixture,"unit_limit"));
        if(v>64 || m>64 || u>8192 || field(fixture,"include_mounts").kind!=V::Kind::boolean)throw std::invalid_argument("fixture_policy");
        r.policy.volumes=static_cast<std::uint32_t>(v);r.policy.mounts=static_cast<std::uint32_t>(m);r.policy.mount_units=static_cast<std::uint32_t>(u);r.policy.include_mounts=field(fixture,"include_mounts").boolean;
        const auto& scenario=field(value,"scenario");if(scenario.kind!=V::Kind::string)throw std::invalid_argument("fixture_scenario");
        const auto mode=scenario.text;if(mode!="normal" && mode!="late" && mode!="before" && mode!="during" && mode!="retire" && mode!="hold" && mode!="published" && mode!="invalid_wait" && mode!="stale")throw std::invalid_argument("fixture_scenario");
        auto session=n::NamespaceWorker::start(r);auto observations=V::array();observations.items.push_back(session->observe());
        if(mode=="before")session->cancel();session->release();
        if(mode=="late" || mode=="during" || mode=="retire" || mode=="hold") {
            const bool entered=session->wait_entered(1000);if(!entered)throw std::runtime_error("fixture_query_not_observed");observations.items.push_back(session->observe(1));
        }
        if(mode=="hold") {print(observations.items.back());Sleep(INFINITE);}
        if(mode=="during")session->cancel();
        if(mode=="retire")observations.items.push_back(session->retire());
        else if(mode=="invalid_wait") {bool refused=false;try {session->observe(1001);}catch(const std::invalid_argument&) {refused=true;}if(!refused)throw std::runtime_error("fixture_budget_not_enforced");observations.items.push_back(session->observe(1000));}
        else if(mode=="published") {
            const auto end=GetTickCount64()+1000;for(;;) {auto observed=session->observe();if(field(observed,"status").text=="completed") {observations.items.push_back(observed);break;}if(GetTickCount64()>=end)throw std::runtime_error("fixture_reply_not_observed");Sleep(1);}
            observations.items.push_back(session->observe(1000));
        }else observations.items.push_back(session->observe(1000));
        print(V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("observations",observations));return 0;
    }catch(const std::exception& error) {print(V::object().put("status",V::string("refused")).put("reason",V::string(error.what())));return 3;}
}
