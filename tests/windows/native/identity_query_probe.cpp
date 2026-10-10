#include "storage_fixture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
#include <memory>
namespace {using V=disked::json::Value;namespace n=disked::nt_inventory;std::unique_ptr<n::StorageQueryPort> port;
void print(V value){value.put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count()))).put("error_calls",V::string(std::to_string(disked::nt_storage_fixture::error_count())))
    .put("unresolved",V::boolean_value(port && port->unresolved())).put("trace",disked::nt_storage_fixture::calls_trace());disked::json::Limits l;l.bytes=1048576;l.values=65536;l.depth=24;std::puts(disked::json::dump(value,l).c_str());}
}
int wmain(int argc,wchar_t**){
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try{char data[262145];const auto size=std::fread(data,1,sizeof(data),stdin);if(!size || size==sizeof(data) || std::ferror(stdin))return 2;
        disked::json::Limits limits;limits.bytes=262144;limits.values=32768;limits.depth=24;const auto input=disked::json::parse(std::string(data,size),limits);
        const auto profile=input.find("profile");if(!profile || profile->text!="identity-layout")throw std::invalid_argument("fixture_profile");
        auto api=disked::nt_storage_fixture::api(input);if(const auto kind=input.find("api")){if(kind->text=="native")api=n::native_storage_query_api();if(kind->text=="mixed-io")api.ioctl=&DeviceIoControl;if(kind->text=="mixed-error")api.error=&GetLastError;}
        const auto stop=input.find("cancel_after_io");const auto count=stop?std::stoull(stop->text):0xffffffffULL;
        auto handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(123));if(input.find("invalid_handle"))handle=INVALID_HANDLE_VALUE;
        port.reset(new n::StorageQueryPort(api,handle,{},[&]{return disked::nt_storage_fixture::call_count()>=count;}));
        const auto mode=input.find("mode");if(mode && mode->text=="construction"){print(V::object());return 0;}
        auto result=V::object();
        result.put("identifiers",port->identifiers());
        result.put("alignment",port->alignment());
        result.put("layout",port->layout());
        if(mode && mode->text=="reuse")port->identifiers();print(std::move(result));return 0;
    }catch(const std::exception& error){print(V::object().put("status",V::string("refused")).put("reason",V::string(error.what())));return 3;}
}
