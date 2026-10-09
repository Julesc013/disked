#include "file_image_collection.h"
#include "local_file.h"
#include "report_export.h"
#include <algorithm>
namespace disked {
namespace {using V=json::Value;namespace e=evidence::proposal;
[[noreturn]] void fail(const char* code) {throw e::Error(code);}
std::string encode(const V& v) {return json::dump(v,e::image_collection_limits());}
}
class FileImageVerificationCollection::Impl final {
public:
    std::wstring path;std::vector<local_file::Handle> parents;local_file::Handle file;V ancestors,metadata;
    std::string bytes,digest;std::unique_ptr<e::ImageVerificationCollection> report;
    Impl(const std::string& selected,const std::string& expected):path(local_file::path_for(selected)),parents(local_file::pin_parents(path)),ancestors(local_file::parent_generations(parents)) {
        if(expected.size()!=71 || expected.substr(0,7)!="sha256:" || expected.find_first_not_of("0123456789abcdef",7)!=expected.npos)fail("image_collection_file_digest");
        file=local_file::Handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS,nullptr));
        if(file.value==INVALID_HANDLE_VALUE)throw local_file::Error("image_collection_file_open",GetLastError());
        local_file::ordinary(file.value,false);local_file::bind_path(file.value,path);const auto observed=local_file::metadata(file.value);
        if(!observed.size || observed.size>1048577)fail("image_collection_file_limit");metadata=observed.value;
        bytes=read(observed.size);digest=e::export_digest(bytes);if(digest!=expected)fail("image_collection_file_digest");
        report.reset(new e::ImageVerificationCollection(e::ImageVerificationCollection::restore(bytes)));check();
    }
    std::string read(std::uint64_t count) const {
        if(!count || count>1048577)fail("image_collection_file_limit");LARGE_INTEGER zero{};
        if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))throw local_file::Error("image_collection_file_seek",GetLastError());
        std::string result;result.reserve(static_cast<std::size_t>(count));
        while(result.size()<count) {const auto n=static_cast<DWORD>(std::min<std::uint64_t>(65536,count-result.size()));char chunk[65536];DWORD got=0;
            if(!ReadFile(file.value,chunk,n,&got,nullptr))throw local_file::Error("image_collection_file_read",GetLastError());
            if(got!=n)fail("image_collection_file_short_read");result.append(chunk,got);}
        return result;
    }
    void check_metadata() const {
        local_file::check_parents(path,parents,ancestors);local_file::ordinary(file.value,false);local_file::bind_path(file.value,path);
        if(encode(local_file::metadata(file.value).value)!=encode(metadata))fail("image_collection_file_changed");
    }
    void check() const {check_metadata();if(read(bytes.size())!=bytes)fail("image_collection_file_changed");check_metadata();}
    V binding() const {check();return V::object().put("schema",V::string("org.disked.file-image-verification-collection-source-prototype/1"))
        .put("path",V::string(local_file::utf8(path))).put("metadata",metadata).put("ancestors",ancestors).put("digest",V::string(digest))
        .put("collection_revision",V::string(report->revision())).put("access",V::string("read")).put("scope",V::string("historical-record-retention-only"));}
};
FileImageVerificationCollection::FileImageVerificationCollection(const std::string& path,const std::string& expected):impl_(new Impl(path,expected)) {}
FileImageVerificationCollection::~FileImageVerificationCollection()=default;
const e::ImageVerificationCollection& FileImageVerificationCollection::snapshot() const {impl_->check();return *impl_->report;}
json::Value FileImageVerificationCollection::binding() const {return impl_->binding();}
void FileImageVerificationCollection::check() const {impl_->check();}
}
