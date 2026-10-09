#include "file_export.h"
#include "local_file.h"
#include <algorithm>
#include <cstdio>

namespace disked {
namespace {
using V=json::Value;using local_file::Handle;namespace e=evidence::proposal;
V number(std::uint64_t n) {return V::string(std::to_string(n));}
std::string encode(const V& v) {return json::dump(v,e::export_definition_limits());}
bool exists(const std::wstring& path) {
    if(GetFileAttributesW(path.c_str())!=INVALID_FILE_ATTRIBUTES)return true;
    const auto error=GetLastError();if(error==ERROR_FILE_NOT_FOUND || error==ERROR_PATH_NOT_FOUND)return false;
    throw FileReportExportError("export_path_observation",error);
}
Handle open_read(const std::wstring& path) {
    Handle h(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS,nullptr));
    if(h.value==INVALID_HANDLE_VALUE)throw FileReportExportError("export_producer_open",GetLastError());local_file::ordinary(h.value,false);local_file::bind_path(h.value,path);return h;
}
void seek(HANDLE h,std::uint64_t offset) {
    if(offset>1048577)throw FileReportExportError("export_file_range");LARGE_INTEGER n{};n.QuadPart=static_cast<LONGLONG>(offset);
    if(!SetFilePointerEx(h,n,nullptr,FILE_BEGIN))throw FileReportExportError("export_file_seek",GetLastError());
}
struct Path {
    std::wstring value,parent;std::vector<Handle> handles;V ancestors=V::array();
    explicit Path(const std::string& input):value(local_file::path_for(input)),handles(local_file::pin_parents(value)) {
        const auto slash=value.rfind(L'\\');if(value.size()<=3 || slash==value.size()-1)throw FileReportExportError("export_output_path");
        parent=slash==2?value.substr(0,3):value.substr(0,slash);
        ancestors=local_file::parent_generations(handles);
    }
    void check() const {
        local_file::check_parents(value,handles,ancestors);
    }
    V binding() const {
        auto leaf=value.substr(value.rfind(L'\\')+1);const auto n=LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_UPPERCASE,leaf.data(),static_cast<int>(leaf.size()),nullptr,0,nullptr,nullptr,0);
        if(n<=0)throw FileReportExportError("export_lookup_key",GetLastError());std::wstring folded(static_cast<std::size_t>(n),L'\0');
        if(LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_UPPERCASE,leaf.data(),static_cast<int>(leaf.size()),&folded[0],n,nullptr,nullptr,0)!=n)throw FileReportExportError("export_lookup_key",GetLastError());
        const auto identity=e::export_digest(encode(V::object().put("parent",ancestors.items.back()).put("leaf_lookup",V::string(local_file::utf8(folded)))));
        return V::object().put("identity",V::string("location:"+identity)).put("epoch",V::string(e::export_digest(encode(ancestors))))
            .put("location",V::string(local_file::utf8(value))).put("access",V::string("create-write")).put("verification",V::string("readback-sha256"));
    }
};
#ifdef DISKED_REPORT_EXPORT_TESTING
bool flag(const wchar_t* name) {return GetEnvironmentVariableW(name,nullptr,0)!=0;}
bool selected(const char* phase) {
    wchar_t b[80];const auto n=GetEnvironmentVariableW(L"DISKED_REPORT_TEST_EVENT",b,80);return n && n<80 && local_file::utf8(std::wstring(b,n))==phase;
}
void event(const char* phase) {
    if(!selected(phase))return;
    std::printf("{\"event\":\"%s\"}\n",phase);std::fflush(stdout);
    if(flag(L"DISKED_REPORT_TEST_PAUSE")) {
        const auto start=GetTickCount64();wchar_t path[241];const auto n=GetEnvironmentVariableW(L"DISKED_REPORT_TEST_RELEASE_FILE",path,241);
        if(!n || n>=241)throw FileReportExportError("export_test_release_path");
        while(GetFileAttributesW(path)==INVALID_FILE_ATTRIBUTES) {if(GetTickCount64()-start>15000)throw FileReportExportError("export_test_release_timeout");Sleep(10);}
    } else throw FileReportExportError("export_test_interrupt");
}
#else
void event(const char* phase) {(void)phase;}
#endif
}
class FileReportExport::Impl final:public e::ExportPorts {
    Path destination_;std::unique_ptr<Path> producer_path_;Handle producer_,output_;V producer_metadata_,bindings_;std::string producer_digest_;
    std::unique_ptr<e::ExportDefinition> definition_;bool used_=false,created_=false;std::uint32_t platform_=0;std::uint64_t written_=0;std::string phase_="prepared";std::function<bool()> stop_;
    template<typename F> auto guarded(F&& f)->decltype(f()) {
        try {return f();}catch(const FileReportExportError& error) {platform_=error.platform_code;throw;}
        catch(const local_file::Error& error) {platform_=error.platform_code;throw FileReportExportError(error.what(),error.platform_code);}
    }
    V producer_binding() const {
        return V::object().put("identity",V::string("file:"+e::export_digest(encode(local_file::generation(producer_.value,false)))))
            .put("epoch",V::string(e::export_digest(encode(producer_metadata_)))).put("location",V::string(local_file::utf8(producer_path_->value)))
            .put("access",V::string("read")).put("digest",V::string(producer_digest_));
    }
public:
    Impl(const e::SupportArtifact& artifact,const std::string& destination,const V* reviewed):destination_(destination) {
        wchar_t module[241];const auto length=GetModuleFileNameW(nullptr,module,241);if(!length || length>=241)throw FileReportExportError("export_producer_path",GetLastError());
        producer_path_.reset(new Path(local_file::utf8(std::wstring(module,length))));producer_=open_read(producer_path_->value);
        const auto metadata=local_file::metadata(producer_.value);producer_metadata_=metadata.value;if(!metadata.size || metadata.size>16777216)throw FileReportExportError("export_producer_limit");
        std::string bytes(static_cast<std::size_t>(metadata.size),'\0');DWORD read=0;
        if(!ReadFile(producer_.value,&bytes[0],static_cast<DWORD>(bytes.size()),&read,nullptr))throw FileReportExportError("export_producer_read",GetLastError());
        if(read!=bytes.size())throw FileReportExportError("export_producer_short_read");producer_digest_=e::export_digest(bytes);
        bindings_=observe();definition_.reset(new e::ExportDefinition(artifact,bindings_));
        if(reviewed && encode(*reviewed)!=encode(definition_->value()))throw FileReportExportError("export_reviewed_definition_changed");event("prepared");
    }
    const e::ExportDefinition& definition() const {return *definition_;}
    V observe() override {return guarded([&] {
        destination_.check();producer_path_->check();
        if(encode(local_file::metadata(producer_.value).value)!=encode(producer_metadata_))throw FileReportExportError("export_producer_changed");
        local_file::bind_path(producer_.value,producer_path_->value);
        if(created_) {local_file::ordinary(output_.value,false);local_file::bind_path(output_.value,destination_.value);}
        else if(exists(destination_.value))throw FileReportExportError("export_output_exists");
        return V::object().put("destination",destination_.binding()).put("producer",producer_binding());
    });}
    void create() override {guarded([&] {
        phase_="creation";ULARGE_INTEGER free{};if(!GetDiskFreeSpaceExW(destination_.parent.c_str(),&free,nullptr,nullptr)) {platform_=GetLastError();throw e::CreationRefusal("export_capacity_observation");}
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(flag(L"DISKED_REPORT_TEST_NO_CAPACITY"))throw e::CreationRefusal("export_capacity");
#endif
        if(free.QuadPart<definition_->artifact().bytes().size())throw e::CreationRefusal("export_capacity");event("before-create");
        output_=Handle(CreateFileW(destination_.value.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_RANDOM_ACCESS,nullptr));
        if(output_.value==INVALID_HANDLE_VALUE) {platform_=GetLastError();if(platform_==ERROR_FILE_EXISTS || platform_==ERROR_ALREADY_EXISTS)throw e::CreationRefusal("export_output_exists");throw FileReportExportError("export_output_create",platform_);}
        created_=true;event("created");local_file::ordinary(output_.value,false);local_file::bind_path(output_.value,destination_.value);
    });}
    std::uint32_t write(std::uint64_t offset,const char* bytes,std::uint32_t size) override {return guarded([&] {
        phase_="write";if(size>65536 || offset+size>1048577)throw FileReportExportError("export_file_range");seek(output_.value,offset);DWORD got=0;auto count=size;
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(flag(L"DISKED_REPORT_TEST_WRITE_ERROR"))throw FileReportExportError("export_file_write",ERROR_DISK_FULL);
        if(flag(L"DISKED_REPORT_TEST_SHORT_WRITE"))count/=2;
#endif
        if(!WriteFile(output_.value,bytes,count,&got,nullptr))throw FileReportExportError("export_file_write",GetLastError());written_+=got;event("written");
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(flag(L"DISKED_REPORT_TEST_LOST_WRITE_ACK"))throw FileReportExportError("export_write_ack_lost");
#endif
        return static_cast<std::uint32_t>(got);
    });}
    void flush() override {guarded([&] {
        phase_="flush";
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(flag(L"DISKED_REPORT_TEST_FLUSH_ERROR"))throw FileReportExportError("export_file_flush",ERROR_WRITE_FAULT);
#endif
        if(!FlushFileBuffers(output_.value))throw FileReportExportError("export_file_flush",GetLastError());event("flushed");
    });}
    std::string read(std::uint64_t offset,std::uint32_t size) override {return guarded([&] {
        phase_="readback";if(size>65536 || offset+size>1048577)throw FileReportExportError("export_file_range");seek(output_.value,offset);std::string bytes(size,'\0');DWORD got=0;
        if(!ReadFile(output_.value,&bytes[0],size,&got,nullptr))throw FileReportExportError("export_file_read",GetLastError());bytes.resize(got);
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(flag(L"DISKED_REPORT_TEST_SHORT_READ") && !bytes.empty())bytes.pop_back();
        if(flag(L"DISKED_REPORT_TEST_CORRUPT_READ") && !bytes.empty())bytes[0]^=1;
#endif
        event("read");return bytes;
    });}
    std::uint64_t size() override {return guarded([&] {return local_file::metadata(output_.value).size;});}
    bool stop_requested() override {
        if(stop_ && stop_())return true;
#ifdef DISKED_REPORT_EXPORT_TESTING
        if(selected("cancel-before-create") && !created_)return true;
        if(selected("cancel-after-create") && created_)return true;
        if(selected("cancel-after-write") && written_)return true;
        if(selected("cancel-after-flush") && phase_=="flush")return true;
#endif
        return false;
    }
    FileReportExportResult execute(const e::ExportGrant& grant,const std::function<bool()>& stop) {
        if(used_)throw FileReportExportError("export_session_used");used_=true;stop_=stop;const auto outcome=e::execute_export(*definition_,grant,*this);
        V output;try {if(created_)output=local_file::metadata(output_.value).value;}catch(const std::exception&) {}
        auto receipt=V::object().put("definition_digest",V::string(definition_->digest())).put("artifact_digest",V::string(definition_->artifact().digest()))
            .put("routing_metadata_is_support_export",V::boolean_value(false)).put("output_path",V::string(local_file::utf8(destination_.value)))
            .put("output_created_observed",V::boolean_value(created_)).put("output_metadata",output).put("producer",*bindings_.find("producer"))
            .put("platform_code",number(platform_)).put("flush_scope",V::string("per-file-FlushFileBuffers-API-only"));
        return {outcome,receipt};
    }
};
FileReportExport::FileReportExport(const e::SupportArtifact& artifact,const std::string& path,const V* reviewed) {
    try {impl_.reset(new Impl(artifact,path,reviewed));}catch(const local_file::Error& error) {throw FileReportExportError(error.what(),error.platform_code);}
}
FileReportExport::~FileReportExport()=default;
const e::ExportDefinition& FileReportExport::definition() const {return impl_->definition();}
FileReportExportResult FileReportExport::execute(const e::ExportGrant& grant,const std::function<bool()>& stop) {return impl_->execute(grant,stop);}
}
