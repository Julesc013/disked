#include "file_verification.h"
#include "local_file.h"
#include "sha256.h"
#include <algorithm>
namespace disked {
namespace {
using V=json::Value;using local_file::Handle;
std::string hash(const std::string& data) {unsigned char out[32];sha256(reinterpret_cast<const unsigned char*>(data.data()),data.size(),out);const char* hex="0123456789abcdef";std::string s="sha256:";for(auto b:out) {s+=hex[b>>4];s+=hex[b&15];}return s;}
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw FileVerificationError("verification_file_shape");return *p;}
struct Input {
    std::wstring path;std::vector<Handle> parents;V ancestors,metadata;Handle file;std::uint64_t bytes=0;
    explicit Input(const std::string& value):path(local_file::path_for(value)),parents(local_file::pin_parents(path)) {
        ancestors=local_file::parent_generations(parents);
        file=Handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_RANDOM_ACCESS,nullptr));
        if(file.value==INVALID_HANDLE_VALUE)throw FileVerificationError("verification_file_open",GetLastError());
        local_file::bind_path(file.value,path);const auto current=local_file::metadata(file.value);metadata=current.value;bytes=current.size;check();
    }
    void check() const {
        local_file::check_parents(path,parents,ancestors);local_file::bind_path(file.value,path);
        if(json::dump(local_file::metadata(file.value).value)!=json::dump(metadata))throw FileVerificationError("verification_file_changed");
    }
    V binding() const {check();return V::object().put("path",V::string(local_file::utf8(path))).put("metadata",metadata).put("ancestors",ancestors).put("access",V::string("read"));}
    V resource() const {
        const auto value=binding();const auto id=V::object().put("volume_id",get(metadata,"volume_id")).put("file_id",get(metadata,"file_id"));
        return V::object().put("identity",V::string("file:"+hash(json::dump(id)))).put("epoch",V::string(hash(json::dump(value))))
            .put("recorded_epoch",V::string(hash(json::dump(local_file::generation(file.value,false)))))
            .put("access",V::string("read")).put("bytes",V::string(std::to_string(bytes)));
    }
};
}
class FileImageVerification::Impl final:public evidence::proposal::VerificationPorts {
    Input image_,map_;std::string buffer_;std::uint64_t cursor_=0;bool used_=false;
    evidence::proposal::VerificationDefinition definition_;
    std::function<bool()> stop_;std::function<void(const evidence::proposal::VerificationOutcome&)> progress_;
public:
    Impl(const acquisition::Plan& plan,const std::string& image,const std::string& map):image_(image),map_(map) {
        definition_=evidence::proposal::prepare_verification(plan,observe());
    }
    const evidence::proposal::VerificationDefinition& definition() const {return definition_;}
    V binding() const {return V::object().put("image",image_.binding()).put("map",map_.binding()).put("provenance",V::string("observed-held-ordinary-file-resources"));}
    V observe() override {return V::object().put("image",image_.resource()).put("map",map_.resource());}
    acquisition::Record next_record() override {
        for(;;) {
            const auto newline=buffer_.find('\n');
            if(newline!=buffer_.npos) {auto body=buffer_.substr(0,newline);buffer_.erase(0,newline+1);return {body,true,false};}
            if(buffer_.size()>16384)return {buffer_.substr(0,16385),true,false};
            if(cursor_==map_.bytes) {if(buffer_.empty())return {{},true,true};auto body=std::move(buffer_);buffer_.clear();return {body,false,false};}
            const auto n=static_cast<DWORD>(std::min<std::uint64_t>(4096,map_.bytes-cursor_));char bytes[4096];DWORD got=0;
            if(!ReadFile(map_.file.value,bytes,n,&got,nullptr))throw FileVerificationError("verification_map_read",GetLastError());
            if(got!=n)throw FileVerificationError("verification_map_short_read");cursor_+=got;buffer_.append(bytes,got);
        }
    }
    acquisition::Read read_image(std::uint64_t offset,std::uint32_t n) override {
        acquisition::Read r;
        if(offset>image_.bytes || n>image_.bytes-offset) {r.error="verification_image_range";return r;}
        LARGE_INTEGER at{};at.QuadPart=static_cast<LONGLONG>(offset);
        if(!SetFilePointerEx(image_.file.value,at,nullptr,FILE_BEGIN))throw FileVerificationError("verification_image_seek",GetLastError());
        r.bytes.resize(n);DWORD got=0;
        if(n && !ReadFile(image_.file.value,r.bytes.data(),n,&got,nullptr)) {r.bytes.clear();r.error="verification_image_read";}
        else r.bytes.resize(got);return r;
    }
    bool stop_requested() override {return stop_ && stop_();}
    void progress(const evidence::proposal::VerificationOutcome& value) override {if(progress_)progress_(value);}
    evidence::proposal::VerificationOutcome execute(const evidence::proposal::VerificationGrant& grant,const std::function<bool()>& stop,const std::function<void(const evidence::proposal::VerificationOutcome&)>& progress) {
        if(used_)throw FileVerificationError("verification_session_consumed");used_=true;
        stop_=stop;progress_=progress;
        return evidence::proposal::verify_image(definition_,grant,*this);
    }
};
FileImageVerification::FileImageVerification(const acquisition::Plan& plan,const std::string& image,const std::string& map):impl_(new Impl(plan,image,map)) {}
FileImageVerification::~FileImageVerification()=default;
const evidence::proposal::VerificationDefinition& FileImageVerification::definition() const {return impl_->definition();}
V FileImageVerification::binding() const {return impl_->binding();}
evidence::proposal::VerificationOutcome FileImageVerification::execute(const evidence::proposal::VerificationGrant& grant,const std::function<bool()>& stop,const std::function<void(const evidence::proposal::VerificationOutcome&)>& progress) {return impl_->execute(grant,stop,progress);}
}
