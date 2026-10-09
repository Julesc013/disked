#include "volume_fixture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
namespace {using V=disked::json::Value;namespace n=disked::nt_inventory;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
DWORD number(const V& v) {if(v.kind!=V::Kind::string || !disked::json::decimal_u64(v.text) || std::stoull(v.text)>0xffffffffULL)throw std::invalid_argument("fixture_integer");return static_cast<DWORD>(std::stoul(v.text));}
bool flag(const V& v) {if(v.kind!=V::Kind::boolean)throw std::invalid_argument("fixture_boolean");return v.boolean;}
}
int main(int argc,char** argv) {
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc==2 && std::string(argv[1])=="--binding") {
        n::VolumeCursor cursor(n::native_volume_api());std::printf("{\"schema\":\"org.disked.nt-volume-binding-fixture/1\",\"native_table_bound\":true,\"queries\":0,\"pointer_bytes\":%u,\"live_namespace_qualified\":false}\n",static_cast<unsigned>(sizeof(void*)));return cursor.native_binding()?0:1;
    }
    if(argc!=1)return 2;
    try {
        char bytes[65536];const auto count=std::fread(bytes,1,sizeof(bytes),stdin);if(!count || count==sizeof(bytes) || std::ferror(stdin))return 2;
        auto fixture_limits=disked::json::Limits{};fixture_limits.bytes=65535;fixture_limits.values=16384;fixture_limits.depth=24;
        const auto value=disked::json::parse(std::string(bytes,count),fixture_limits);
        auto api=disked::nt_fixture::api(value);
        n::VolumeCursor cursor(api);n::InventoryPolicy policy;
        policy.volumes=number(get(value,"volume_limit"));policy.mounts=number(get(value,"mount_limit"));policy.mount_units=number(get(value,"unit_limit"));policy.include_mounts=flag(get(value,"include_mounts"));
        const auto epoch=get(value,"capture_epoch");if(epoch.kind!=V::Kind::string || !disked::json::decimal_u64(epoch.text))throw std::invalid_argument("fixture_epoch");
        const auto cancel_at=number(get(value,"cancel_after_calls"));
        const auto snapshot=n::collect_volume_namespace(cursor,std::stoull(epoch.text),policy,[cancel_at] {return cancel_at!=0xffffffffUL && disked::nt_fixture::call_count()>=cancel_at;});
        const auto closed_again=cursor.close();const auto before_reuse=disked::nt_fixture::call_count();bool reuse_refused=false;
        try {cursor.first();}catch(const std::invalid_argument&) {reuse_refused=true;}
        auto out=V::object().put("qualification",V::string("injected-win32-api-not-native-storage")).put("snapshot",snapshot).put("trace",disked::nt_fixture::calls_trace())
            .put("close_calls",V::string(std::to_string(disked::nt_fixture::close_count()))).put("repeat_close_state",V::string(closed_again.state)).put("reuse_refused",V::boolean_value(reuse_refused && disked::nt_fixture::call_count()==before_reuse));
        std::puts(disked::json::dump(out,n::volume_inventory_limits()).c_str());return 0;
    }catch(const std::exception& error) {
        const auto out=V::object().put("status",V::string("refused")).put("reason",V::string(error.what())).put("api_calls",V::string(std::to_string(disked::nt_fixture::call_count())));
        std::puts(disked::json::dump(out).c_str());return 3;
    }
}
