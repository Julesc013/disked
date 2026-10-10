#include "storage_frame_reader.h"
#include <algorithm>
#include <cstring>
#include <set>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("storage_frame_shape");return *p;}
std::string text(const V& v,const char* k){const auto& x=get(v,k);if(x.kind!=V::Kind::string)throw std::invalid_argument("storage_frame_shape");return x.text;}
std::uint64_t integer(const V& v){if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))throw std::invalid_argument("storage_frame_integer");return std::stoull(v.text);}
DWORD word(const V& v){const auto n=integer(v);if(n>0xffffffffULL)throw std::invalid_argument("storage_frame_integer");return static_cast<DWORD>(n);}
void require(bool ok){if(!ok)throw std::invalid_argument("storage_frame_receipt");}
std::vector<unsigned char> unhex(const std::string& s,std::size_t limit=8192){
    require(s.size()%2==0 && s.size()<=limit);auto nibble=[](char c)->unsigned{if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);throw std::invalid_argument("storage_frame_hex");};
    std::vector<unsigned char> b;for(std::size_t i=0;i<s.size();i+=2)b.push_back(static_cast<unsigned char>(nibble(s[i])*16+nibble(s[i+1])));return b;
}
struct Token{const V* receipt=nullptr;std::size_t subject=0;DWORD control=0;int exception=0;STORAGE_PROPERTY_ID property=StorageDeviceProperty;};
struct Replay{std::vector<Token> tokens;std::size_t at=0;DWORD last_error=0;};
thread_local Replay* active=nullptr;
BOOL WINAPI control(HANDLE h,DWORD code,LPVOID input,DWORD input_bytes,LPVOID output,DWORD bytes,LPDWORD returned,LPOVERLAPPED overlapped){
    if(!active || active->at>=active->tokens.size())throw std::runtime_error("storage_frame_missing_receipt");const auto& t=active->tokens[active->at++];
    if(code!=t.control || reinterpret_cast<std::uintptr_t>(h)!=123+t.subject || overlapped || !output || !returned)throw std::runtime_error("storage_frame_receipt_order");
    if(t.exception==1)throw std::runtime_error("storage_frame_exception_receipt");if(t.exception==2)throw std::invalid_argument("storage_frame_exception_receipt");
    const auto& r=*t.receipt;if(word(get(r,"buffer_bytes"))!=bytes || (code==IOCTL_STORAGE_QUERY_PROPERTY?(!input || input_bytes!=12):(input || input_bytes)))throw std::runtime_error("storage_frame_receipt_buffer");
    if(code==IOCTL_STORAGE_QUERY_PROPERTY){const auto q=static_cast<const STORAGE_PROPERTY_QUERY*>(input);if(q->PropertyId!=t.property || q->QueryType!=PropertyStandardQuery || q->AdditionalParameters[0])throw std::runtime_error("storage_frame_property");}
    if(get(r,"returned_hex").kind==V::Kind::string){const auto b=unhex(text(r,"returned_hex"),t.control==IOCTL_DISK_GET_DRIVE_LAYOUT_EX?24576:8192);if(b.size()>bytes)throw std::runtime_error("storage_frame_receipt_buffer");std::copy(b.begin(),b.end(),static_cast<unsigned char*>(output));}
    *returned=word(get(r,"returned_bytes"));active->last_error=word(get(r,"platform_code"));return get(r,"ok").boolean?TRUE:FALSE;
}
DWORD WINAPI error(){return active->last_error;}
struct Guard{Replay* previous;explicit Guard(Replay& r):previous(active){active=&r;}~Guard(){active=previous;}};
}
std::vector<StorageSubject> storage_fixture_subjects(const V& fixture){
    const auto& rows=get(fixture,"subjects");require(rows.kind==V::Kind::array && !rows.items.empty() && rows.items.size()<=16);std::vector<StorageSubject> out;std::set<std::string> keys;
    for(const auto& row:rows.items){
        StorageSubject s;s.key=text(row,"key");const auto kind=text(row,"kind");require(kind=="disk" || kind=="volume");s.kind=kind=="disk"?StorageSubjectKind::Disk:StorageSubjectKind::Volume;
        require(!s.key.empty() && s.key.size()<=64 && s.key.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")==std::string::npos && keys.insert(s.key).second);
        if(const auto p=row.find("label_units")){require(p->kind==V::Kind::array && p->items.size()<=256);for(const auto& unit:p->items){const auto n=integer(unit);require(n<=65535);s.label+=static_cast<wchar_t>(n);}}
        else s.label.assign(s.key.begin(),s.key.end());
        if(const auto p=row.find("invalid_handle"))require(p->kind==V::Kind::boolean && !p->boolean);
        s.handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(123+out.size()));out.push_back(std::move(s));
    }return out;
}
std::shared_ptr<const StorageFrame> read_storage_frame(const V& value,const V& fixture,std::uint64_t capture,const StorageQueryPolicy& policy,StorageFrameProfile profile){
    require(profile==StorageFrameProfile::Metadata || profile==StorageFrameProfile::IdentityLayout);const bool identity=profile==StorageFrameProfile::IdentityLayout;
    if(identity)require(text(fixture,"profile")=="identity-layout");
    json::dump(value,storage_observation_limits());const auto subjects=storage_fixture_subjects(fixture);const auto& rows=get(value,"resources");require(rows.kind==V::Kind::array && rows.items.size()==subjects.size());Replay replay;
    struct Code{const char* name;DWORD control;unsigned receipts;STORAGE_PROPERTY_ID property;bool typed;};
    std::vector<Code> codes={{"descriptor",IOCTL_STORAGE_QUERY_PROPERTY,2,StorageDeviceProperty,false},{"number",IOCTL_STORAGE_GET_DEVICE_NUMBER,2,StorageDeviceProperty,false},
        {"geometry",IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,2,StorageDeviceProperty,false},{"length",IOCTL_DISK_GET_LENGTH_INFO,2,StorageDeviceProperty,false},{"extents",IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,2,StorageDeviceProperty,false}};
    if(identity)codes.insert(codes.end(),{{"identifiers",IOCTL_STORAGE_QUERY_PROPERTY,2,StorageDeviceIdProperty,true},{"alignment",IOCTL_STORAGE_QUERY_PROPERTY,1,StorageAccessAlignmentProperty,true},{"layout",IOCTL_DISK_GET_DRIVE_LAYOUT_EX,7,StorageDeviceProperty,false}});
    for(std::size_t i=0;i<rows.items.size();++i)for(const auto& p:codes){
        const auto& c=get(get(rows.items[i],"components"),p.name);const auto& receipts=get(c,"receipts");require(receipts.kind==V::Kind::array && receipts.items.size()<=p.receipts);
        for(const auto& receipt:receipts.items){
            require(receipt.kind==V::Kind::object && receipt.fields.size()==(p.typed?9U:8U) && get(receipt,"ok").kind==V::Kind::boolean && word(get(receipt,"control"))==p.control);
            if(p.typed)require(word(get(receipt,"property_id"))==static_cast<DWORD>(p.property));
            const auto size=word(get(receipt,"buffer_bytes")),returned=word(get(receipt,"returned_bytes"));const auto max=p.control==IOCTL_DISK_GET_DRIVE_LAYOUT_EX?12288U:4096U;require(size<=max);word(get(receipt,"platform_code"));text(receipt,"state");
            if(get(receipt,"returned_hex").kind==V::Kind::string){const auto b=unhex(text(receipt,"returned_hex"),max*2);require(b.size()==returned && b.size()<=size && text(receipt,"returned_sha256")==digest_sha256(std::string(b.begin(),b.end())));}
            else require(get(receipt,"returned_hex").kind==V::Kind::null && get(receipt,"returned_sha256").kind==V::Kind::null);
            replay.tokens.push_back({&receipt,i,p.control,0,p.property});
        }
        if(receipts.items.empty() && (text(c,"state")=="adapter_exception" || text(c,"state")=="malformed"))replay.tokens.push_back({nullptr,i,p.control,text(c,"state")=="adapter_exception"?1:2,p.property});
    }
    Guard guard(replay);StorageQueryApi api;api.ioctl=&control;api.error=&error;
    const auto reconstructed=collect_storage_frame(api,subjects,capture,policy,[&]{
        if(replay.at<replay.tokens.size()){const auto p=replay.tokens[replay.at].receipt;if(p && text(*p,"state")=="cancelled"){++replay.at;return true;}}return false;
    },profile);
    require(replay.at==replay.tokens.size());if(json::dump(reconstructed->value(),storage_observation_limits())!=json::dump(value,storage_observation_limits()))throw std::invalid_argument("storage_frame_conformance");return reconstructed;
}
}}
