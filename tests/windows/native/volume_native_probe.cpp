#include "providers/windows/volume_inventory.h"
#include <sddl.h>
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <stdexcept>
#include <vector>

namespace {
using V=disked::json::Value;
namespace n=disked::nt_inventory;
V identity() {
    HANDLE token=nullptr;
    if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token))throw std::runtime_error("token_open");
    struct Close {HANDLE value;~Close(){CloseHandle(value);}} close{token};
    DWORD size=0;GetTokenInformation(token,TokenUser,nullptr,0,&size);
    if(!size || size>4096)throw std::runtime_error("token_user_size");
    std::vector<unsigned char> bytes(size);
    if(!GetTokenInformation(token,TokenUser,bytes.data(),size,&size))throw std::runtime_error("token_user");
    wchar_t* text=nullptr;
    if(!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(bytes.data())->User.Sid,&text))throw std::runtime_error("token_sid");
    char sid[256]{};
    const bool converted=WideCharToMultiByte(CP_UTF8,0,text,-1,sid,sizeof(sid),nullptr,nullptr)!=0;
    LocalFree(text);if(!converted)throw std::runtime_error("token_sid_encoding");
    TOKEN_ELEVATION elevation{};DWORD app=1;BOOL job=FALSE;
    if(!GetTokenInformation(token,TokenElevation,&elevation,sizeof(elevation),&size) ||
       !GetTokenInformation(token,TokenIsAppContainer,&app,sizeof(app),&size) ||
       !IsProcessInJob(GetCurrentProcess(),nullptr,&job))throw std::runtime_error("token_properties");
    return V::object().put("sid",V::string(sid)).put("pid",V::string(std::to_string(GetCurrentProcessId())))
        .put("restricted",V::boolean_value(IsTokenRestricted(token)!=FALSE))
        .put("elevated",V::boolean_value(elevation.TokenIsElevated!=0))
        .put("appcontainer",V::boolean_value(app!=0)).put("in_job",V::boolean_value(job!=FALSE));
}
}

int main(int argc,char** argv) {
    if(_setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc!=2)return 2;
    const std::string mode=argv[1];
    if(mode!="--binding" && mode!="--observe" && mode!="--no-mounts" &&
       mode!="--limit-one" && mode!="--cancelled" && mode!="--invalid-policy")return 2;
    try {
        auto out=V::object().put("schema",V::string("org.disked.nt-volume-native-test/1"))
            .put("mode",V::string(mode)).put("identity",identity());
        n::VolumeCursor cursor(n::native_volume_api());
        out.put("native_table_bound",V::boolean_value(cursor.native_binding()));
        if(mode=="--binding") {
            out.put("dispatch_requested",V::boolean_value(false)).put("close",V::string(cursor.close().state));
        }else {
            n::InventoryPolicy policy;
            if(mode=="--no-mounts")policy.include_mounts=false;
            if(mode=="--limit-one")policy.volumes=1;
            if(mode=="--invalid-policy")policy.volumes=0;
            try {
                const auto snapshot=n::collect_volume_namespace(cursor,7,policy,[&mode]{return mode=="--cancelled";});
                out.put("dispatch_requested",V::boolean_value(true)).put("snapshot",snapshot);
                const auto repeated=cursor.close();bool refused=false;
                try {cursor.first();}catch(const std::invalid_argument&) {refused=true;}
                out.put("repeat_close",V::string(repeated.state)).put("reuse_refused",V::boolean_value(refused));
            }catch(const std::invalid_argument& error) {
                out.put("status",V::string("refused")).put("reason",V::string(error.what()))
                    .put("close",V::string(cursor.close().state));
                std::puts(disked::json::dump(out,n::volume_inventory_limits()).c_str());return 3;
            }
        }
        std::puts(disked::json::dump(out,n::volume_inventory_limits()).c_str());return 0;
    }catch(const std::exception& error) {
        std::fprintf(stderr,"native_volume_test: %s\n",error.what());return 4;
    }
}
