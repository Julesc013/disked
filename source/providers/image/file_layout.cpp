#include "file_layout.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <set>

namespace disked {
namespace {
using V=json::Value;namespace f=local_file;
const V& get(const V& v,const char* k){auto p=v.find(k);if(!p)throw std::invalid_argument("file_layout_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("file_layout_shape");return p.text;}
V number(std::uint64_t n){return V::string(std::to_string(n));}
std::uint64_t integer(const V& v,const char* k){const auto s=text(v,k);if(!json::decimal_u64(s))throw std::invalid_argument("file_layout_integer");return std::stoull(s);}
void exact(const V& v,const std::set<std::string>& keys){if(v.kind!=V::Kind::object || v.fields.size()!=keys.size())throw std::invalid_argument("file_layout_shape");for(const auto& x:v.fields)if(!keys.count(x.first))throw std::invalid_argument("file_layout_shape");}
bool same(const V& a,const V& b){return json::dump(a,file_layout_snapshot_limits())==json::dump(b,file_layout_snapshot_limits());}
bool digest(const std::string& s){return s.size()==71 && s.substr(0,7)=="sha256:" && s.find_first_not_of("0123456789abcdef",7)==std::string::npos;}
std::string hash(const unsigned char* bytes,std::size_t size){unsigned char out[32];sha256(bytes,size,out);const char* chars="0123456789abcdef";std::string s="sha256:";for(auto n:out){s+=chars[n>>4];s+=chars[n&15];}return s;}
void metadata(const V& v){
    exact(v,{"volume_id","file_id","bytes","created","written","changed","attributes","hardlinks"});
    integer(v,"volume_id");integer(v,"bytes");if(integer(v,"attributes")>0xffffffffULL || integer(v,"hardlinks")!=1)throw std::invalid_argument("file_layout_metadata");
    const auto id=text(v,"file_id");if(id.size()!=32 || id.find_first_not_of("0123456789abcdef")!=id.npos)throw std::invalid_argument("file_layout_metadata");
    for(const auto k:{"created","written","changed"}){const auto s=text(v,k);if(s.size()>20 || std::to_string(std::stoll(s))!=s)throw std::invalid_argument("file_layout_metadata");}
}
V claims(){return V::object().put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false))
    .put("atomic_snapshot",V::boolean_value(false)).put("source_consistency",V::string("live-uncoordinated")).put("source_read_only",V::boolean_value(true));}
std::string hook(const FileLayoutInput& r){const auto p=r.fixture.find("capture_fault");return p?p->text:"";}
class Source {
    std::vector<f::Handle> parents_;V generations_;
public:
    const std::wstring path;f::Handle file;
    explicit Source(const std::string& input):path(f::path_for(input)){
        parents_=f::pin_parents(path);generations_=f::parent_generations(parents_);
        file=f::Handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_RANDOM_ACCESS,nullptr));
        if(file.value==INVALID_HANDLE_VALUE)throw f::Error("file_layout_source_open",GetLastError());check();
    }
    void check()const{f::ordinary(file.value,false);f::bind_path(file.value,path);f::check_parents(path,parents_,generations_);}
};
struct Read {std::vector<unsigned char> bytes;DWORD error=0;};
Read read(HANDLE h,std::size_t size,const std::function<bool()>& stop){
    Read out;out.bytes.resize(size);LARGE_INTEGER zero{};if(!SetFilePointerEx(h,zero,nullptr,FILE_BEGIN)){out.error=GetLastError();out.bytes.clear();return out;}
    std::size_t at=0;
    while(at<size){if(stop && stop())throw std::invalid_argument("file_layout_cancelled");const auto want=static_cast<DWORD>(std::min<std::size_t>(65536,size-at));DWORD got=0;
        if(!ReadFile(h,out.bytes.data()+at,want,&got,nullptr)){out.error=GetLastError();out.bytes.clear();return out;}if(got>want)throw std::invalid_argument("file_layout_read_shape");at+=got;if(got!=want)break;}
    out.bytes.resize(at);return out;
}
de_u64 blocks(std::size_t size,std::uint32_t unit){const auto n=size/unit+(size%unit?1:0);de_u64 out{};const auto s=std::to_string(n);if(de_u64_parse(s.data(),s.size(),&out)!=DE_OK)throw std::invalid_argument("file_layout_geometry");return out;}
bool boolean(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::boolean)throw std::invalid_argument("file_layout_shape");return p.boolean;}
}
json::Limits file_layout_snapshot_limits(){json::Limits l;l.bytes=786432;l.values=40000;l.depth=24;l.string_bytes=1024;return l;}
V file_layout_unavailable(const std::string& code,std::uint32_t platform){return V::object().put("schema",V::string("org.disked.file-layout-snapshot-prototype/1"))
    .put("status",V::string("unavailable")).put("receipt",V{}).put("layout",V{}).put("diagnostic",V::object().put("code",V::string(code)).put("platform_code",number(platform))).put("claims",claims());}
void validate_file_layout_input(const FileLayoutInput& r){
    if(!r.capture_epoch || (r.unit!=512 && r.unit!=4096) || !r.policy.partitions || r.policy.partitions>64 || !r.policy.ebr_nodes || r.policy.ebr_nodes>128)throw std::invalid_argument("file_layout_request");
    f::path_for(r.path);metadata(r.expected_source);if(!r.expected_content_digest.empty() && !digest(r.expected_content_digest))throw std::invalid_argument("file_layout_content_digest");
    if(r.fixture.kind!=V::Kind::object)throw std::invalid_argument("file_layout_fixture");
    for(const auto& x:r.fixture.fields){
#ifdef DISKED_FILE_LAYOUT_TESTING
        if(x.first!="capture_fault" && x.first!="worker_fault" && x.first!="startup_fault" && x.first!="reply_fault")throw std::invalid_argument("file_layout_fixture");
        if(x.second.kind!=V::Kind::string || x.second.text.empty() || x.second.text.size()>32)throw std::invalid_argument("file_layout_fixture");
        const std::set<std::string> captures={"read_error","short_read","reread_changed","reread_error","short_reread","metadata_changed","metadata_error"};
        const std::set<std::string> workers={"hang","late","corrupt_payload","corrupt_layout","corrupt_receipt","claims"};
        const std::set<std::string> startups={"before_spawn","after_spawn","after_spawn_alloc"},replies={"capture","worker","shape","status","claims","schema","digest","hold","code","request","scope","host","observer","attempt","pid","created"};
        const auto& choices=x.first=="capture_fault"?captures:x.first=="worker_fault"?workers:x.first=="startup_fault"?startups:replies;
        if(!choices.count(x.second.text))throw std::invalid_argument("file_layout_fixture");
#else
        (void)x;throw std::invalid_argument("file_layout_fixture");
#endif
    }
}
FileLayoutRead read_file_layout(const FileLayoutInput& r,const std::function<bool()>& stop){
    validate_file_layout_input(r);if(stop && stop())throw std::invalid_argument("file_layout_cancelled");Source source(r.path);const auto before=f::metadata(source.file.value);
    if(!same(before.value,r.expected_source))throw std::invalid_argument("file_layout_source_changed");
    if(!before.size || before.size>file_layout_payload_bytes)throw std::invalid_argument("file_layout_input_budget");
    auto first=read(source.file.value,static_cast<std::size_t>(before.size),stop);const auto fault=hook(r);(void)fault;
#ifdef DISKED_FILE_LAYOUT_TESTING
    if(fault=="read_error"){first.error=ERROR_READ_FAULT;first.bytes.clear();}if(fault=="short_read" && !first.bytes.empty())first.bytes.pop_back();
#endif
    if(first.error)throw f::Error("file_layout_read",first.error);if(first.bytes.size()!=before.size)throw std::invalid_argument("file_layout_short_read");
    const auto first_hash=hash(first.bytes.data(),first.bytes.size());if(!r.expected_content_digest.empty() && r.expected_content_digest!=first_hash)throw std::invalid_argument("file_layout_content_changed");
    source.check();auto second=read(source.file.value,static_cast<std::size_t>(before.size),stop);
#ifdef DISKED_FILE_LAYOUT_TESTING
    if(fault=="reread_changed" && !second.bytes.empty())second.bytes[0]^=1;
    if(fault=="reread_error"){second.error=ERROR_READ_FAULT;second.bytes.clear();}if(fault=="short_reread" && !second.bytes.empty())second.bytes.pop_back();
#endif
    V after;std::string metadata_error;DWORD metadata_platform=0;
    try{source.check();after=f::metadata(source.file.value).value;
#ifdef DISKED_FILE_LAYOUT_TESTING
        if(fault=="metadata_changed")after.put("changed",V::string(text(after,"changed")=="0"?"1":"0"));
        if(fault=="metadata_error")throw f::Error("file_layout_metadata",ERROR_READ_FAULT);
#endif
    }catch(const f::Error& e){after=V{};metadata_error=e.what();metadata_platform=e.platform_code;}
    const auto second_hash=hash(second.bytes.data(),second.bytes.size());const bool reread_equal=!second.error && first.bytes==second.bytes,metadata_equal=after.kind==V::Kind::object && same(before.value,after);
    auto receipt=V::object().put("schema",V::string("org.disked.file-layout-capture-prototype/1")).put("capture_epoch",number(r.capture_epoch))
        .put("path",V::string(r.path)).put("resolved_path",V::string(f::utf8(source.path))).put("logical_sector_bytes",number(r.unit))
        .put("source_before",before.value).put("source_after",after).put("captured_bytes",number(first.bytes.size())).put("sha256",V::string(first_hash))
        .put("reread_bytes",number(second.bytes.size())).put("reread_sha256",V::string(second_hash)).put("reread_error",second.error?number(second.error):V{})
        .put("metadata_equal",V::boolean_value(metadata_equal)).put("reread_equal",V::boolean_value(reread_equal)).put("observed_stable",V::boolean_value(metadata_equal && reread_equal))
        .put("metadata_error",metadata_error.empty()?V{}:V::object().put("code",V::string(metadata_error)).put("platform_code",number(metadata_platform)))
        .put("whole_file_hashed",V::boolean_value(true)).put("partial_final_block",V::boolean_value(before.size%r.unit!=0));
    const auto raw=decode_raw_layout(first.bytes,blocks(first.bytes.size(),r.unit),r.unit,r.policy);
    auto snapshot=V::object().put("schema",V::string("org.disked.file-layout-snapshot-prototype/1")).put("status",V::string("captured"))
        .put("receipt",std::move(receipt)).put("layout",raw->value()).put("diagnostic",V{}).put("claims",claims());
    json::dump(snapshot,file_layout_snapshot_limits());return {std::move(first.bytes),std::move(snapshot)};
}
std::shared_ptr<const RawPartitionLayout> verify_file_layout_snapshot(const V& snapshot,const FileLayoutInput& r,const std::vector<unsigned char>& bytes){
    validate_file_layout_input(r);exact(snapshot,{"schema","status","receipt","layout","diagnostic","claims"});
    if(text(snapshot,"schema")!="org.disked.file-layout-snapshot-prototype/1" || !same(get(snapshot,"claims"),claims()))throw std::invalid_argument("file_layout_claims");
    if(text(snapshot,"status")=="unavailable"){
        const auto& d=get(snapshot,"diagnostic");exact(d,{"code","platform_code"});const auto code=text(d,"code");if(code.empty() || code.size()>128 || integer(d,"platform_code")>0xffffffffULL || get(snapshot,"receipt").kind!=V::Kind::null || get(snapshot,"layout").kind!=V::Kind::null || !bytes.empty())throw std::invalid_argument("file_layout_failure");return {};
    }
    if(text(snapshot,"status")!="captured" || get(snapshot,"diagnostic").kind!=V::Kind::null)throw std::invalid_argument("file_layout_status");const auto& v=get(snapshot,"receipt");
    exact(v,{"schema","capture_epoch","path","resolved_path","logical_sector_bytes","source_before","source_after","captured_bytes","sha256","reread_bytes","reread_sha256","reread_error","metadata_equal","reread_equal","observed_stable","metadata_error","whole_file_hashed","partial_final_block"});
    metadata(get(v,"source_before"));if(!same(get(v,"source_before"),r.expected_source) || text(v,"schema")!="org.disked.file-layout-capture-prototype/1" || integer(v,"capture_epoch")!=r.capture_epoch || text(v,"path")!=r.path || text(v,"resolved_path")!=f::utf8(f::path_for(r.path)) || integer(v,"logical_sector_bytes")!=r.unit)throw std::invalid_argument("file_layout_binding");
    const auto size=integer(get(v,"source_before"),"bytes");if(!size || size>file_layout_payload_bytes || size!=bytes.size() || size!=integer(v,"captured_bytes") || text(v,"sha256")!=hash(bytes.data(),bytes.size()) || (!r.expected_content_digest.empty() && text(v,"sha256")!=r.expected_content_digest))throw std::invalid_argument("file_layout_content_binding");
    const auto& after=get(v,"source_after");const auto& error=get(v,"metadata_error");if(after.kind==V::Kind::object){metadata(after);if(error.kind!=V::Kind::null)throw std::invalid_argument("file_layout_metadata");}
    else{exact(error,{"code","platform_code"});if(after.kind!=V::Kind::null || text(error,"code").empty() || text(error,"code").size()>128 || integer(error,"platform_code")>0xffffffffULL)throw std::invalid_argument("file_layout_metadata");}
    const auto reread=integer(v,"reread_bytes");if(reread>size || !digest(text(v,"reread_sha256")))throw std::invalid_argument("file_layout_reread");const auto& read_error=get(v,"reread_error");
    if(read_error.kind!=V::Kind::null && (read_error.kind!=V::Kind::string || !json::decimal_u64(read_error.text) || !std::stoull(read_error.text) || std::stoull(read_error.text)>0xffffffffULL || reread))throw std::invalid_argument("file_layout_reread");
    const bool me=after.kind==V::Kind::object && same(get(v,"source_before"),after),re=read_error.kind==V::Kind::null && reread==size && text(v,"reread_sha256")==text(v,"sha256");
    if(boolean(v,"metadata_equal")!=me || boolean(v,"reread_equal")!=re || boolean(v,"observed_stable")!=(me && re) || !boolean(v,"whole_file_hashed") || boolean(v,"partial_final_block")!=(size%r.unit!=0))throw std::invalid_argument("file_layout_consistency");
    const auto raw=decode_raw_layout(bytes,blocks(bytes.size(),r.unit),r.unit,r.policy);if(!same(raw->value(),get(snapshot,"layout")))throw std::invalid_argument("file_layout_reconstruction");return raw;
}
}
