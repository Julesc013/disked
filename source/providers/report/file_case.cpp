#include "file_case.h"
#include "worker_files.h"
#include "local_file.h"

namespace disked {
namespace {
using namespace worker_files;
using V=json::Value;
[[noreturn]] void reject(const char* code) {throw evidence::proposal::Error(code);}
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)reject("case_source_shape");return *p;}
std::string digest(const std::string& bytes) {return "sha256:"+hash(bytes);}
json::Limits request_limits() {auto l=acquisition_operation::row_limits();l.bytes=32768;l.depth=24;l.values=4096;return l;}
V store(const Directory& directory) {
    directory.check();auto children=V::array();for(const auto key:{"acquisition.request","acquisition.records","acquisition.cancel","acquisition.admission"})children.items.push_back(V::string(key));
    const auto generation=local_file::generation(directory.pinned.back().value,true);
    return V::object().put("path",V::string(narrow(directory.path))).put("generation",generation).put("children",children)
        .put("access",V::string("create-owned-metadata")).put("failure_domain",V::string("observed-file-volume:"+text(generation,"volume_id")));
}
}
class FileAcquisitionCase::Impl {
public:
    Directory directory;Handle header_file,records_file;V header_metadata,records_metadata,header;std::string header_bytes,records_bytes;
    std::unique_ptr<evidence::proposal::AcquisitionCase> snapshot;
    explicit Impl(const std::string& operation,const std::string& path):directory(path) {
        header_file=directory.open(L"acquisition.request",GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);
        if(!header_file.valid())worker_files::fail("case_source_request_unavailable");
        records_file=directory.open(L"acquisition.records",GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);
        if(!records_file.valid())worker_files::fail("case_source_history_unavailable");
        header_metadata=local_file::metadata(header_file.value).value;records_metadata=local_file::metadata(records_file.value).value;
        header_bytes=read_file(header_file.value,32768);records_bytes=read_file(records_file.value,acquisition_operation::history_limit);
        header=json::parse(header_bytes,request_limits());
        snapshot.reset(new evidence::proposal::AcquisitionCase(header,records_bytes));
        const auto& definition=field(header,"definition");Security security;
        if(text(header,"operation_id")!=operation || text(definition,"host_id")!=security.host_id ||
            json::dump(field(definition,"store"))!=json::dump(store(directory)) || file_identity(records_file.value)!=text(header,"records_id"))reject("case_source_binding");
        check();
    }
    void check() const {
        directory.check();
        for(const auto item:{std::make_pair(header_file.value,&header_metadata),std::make_pair(records_file.value,&records_metadata)})
            if(json::dump(local_file::metadata(item.first).value)!=json::dump(*item.second))reject("case_source_changed");
        local_file::bind_path(header_file.value,directory.child(L"acquisition.request"));local_file::bind_path(records_file.value,directory.child(L"acquisition.records"));
        if(read_file(header_file.value,32768)!=header_bytes || read_file(records_file.value,acquisition_operation::history_limit)!=records_bytes)reject("case_source_changed");
        directory.check();
        for(const auto item:{std::make_pair(header_file.value,&header_metadata),std::make_pair(records_file.value,&records_metadata)})
            if(json::dump(local_file::metadata(item.first).value)!=json::dump(*item.second))reject("case_source_changed");
    }
    V binding() const {
        check();auto files=V::array();
        files.items.push_back(V::object().put("name",V::string("acquisition.request")).put("metadata",header_metadata).put("digest",V::string(digest(header_bytes))));
        files.items.push_back(V::object().put("name",V::string("acquisition.records")).put("metadata",records_metadata).put("digest",V::string(digest(records_bytes))));
        return V::object().put("schema",V::string("org.disked.file-acquisition-case-source-prototype/1"))
            .put("access",V::string("read")).put("store",store(directory)).put("ancestors",directory.generations)
            .put("files",files).put("case_revision",V::string(snapshot->revision()))
            .put("provenance",V::string("ordinary-file-read-and-record-validation")).put("authenticity",V::string("not_established"));
    }
};
FileAcquisitionCase::FileAcquisitionCase(const std::string& operation,const std::string& path):impl_(new Impl(operation,path)) {}
FileAcquisitionCase::~FileAcquisitionCase()=default;
const evidence::proposal::AcquisitionCase& FileAcquisitionCase::report() const {impl_->check();return *impl_->snapshot;}
const std::string& FileAcquisitionCase::request_bytes() const {impl_->check();return impl_->header_bytes;}
const std::string& FileAcquisitionCase::history_bytes() const {impl_->check();return impl_->records_bytes;}
json::Value FileAcquisitionCase::binding() const {return impl_->binding();}
void FileAcquisitionCase::check() const {impl_->check();}
}
