#include "file_acquisition.h"
#include "local_file.h"
#include "sha256.h"
#include <algorithm>
#include <atomic>
#include <functional>
#include <cstdio>

namespace disked {
namespace {
using V=json::Value;using local_file::Handle;
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw FileAcquisitionError("acquisition_file_header");return *p;}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
std::string hash(const unsigned char* data,std::size_t size) {
    unsigned char digest[32];sha256(data,size,digest);const char alphabet[]="0123456789abcdef";std::string out="sha256:";
    for(const auto b:digest) {out+=alphabet[b>>4];out+=alphabet[b&15];}return out;
}
std::string hash(const std::string& s) {return hash(reinterpret_cast<const unsigned char*>(s.data()),s.size());}
std::string file_id(const V& v) {
    return "file:"+hash(json::dump(V::object().put("volume_id",field(v,"volume_id")).put("file_id",field(v,"file_id"))));
}
std::string domain(const V& v) {return "observed-file-volume:"+field(v,"volume_id").text;}
V binding(const char* role,const std::string& id,const std::string& epoch,const std::string& failure,std::uint64_t size,const std::string& location="") {
    auto aliases=V::array();aliases.items.push_back(V::string(id));if(!location.empty() && location!=id)aliases.items.push_back(V::string(location));
    const std::string r=role;
    return V::object().put("identity",V::string(id)).put("epoch",V::string(epoch)).put("access",V::string(r=="source" || r=="executable"?"read":r=="destination"?"create-write":r=="map"?"create-append":"observe"))
        .put("start",number(0)).put("end",number(r=="source" || r=="destination"?size:0)).put("aliases",aliases).put("failure_domain",V::string(failure))
        .put("verification",V::string(r=="destination"?"readback-sha256":r=="map"?"ordered-hash-chain":"identity-epoch"));
}
bool exists(const std::wstring& path) {
    if(GetFileAttributesW(path.c_str())!=INVALID_FILE_ATTRIBUTES)return true;
    const auto code=GetLastError();if(code==ERROR_FILE_NOT_FOUND || code==ERROR_PATH_NOT_FOUND)return false;
    throw FileAcquisitionError("acquisition_path_observation",code);
}
Handle open(const std::wstring& path,DWORD access,DWORD sharing,DWORD creation,const char* error) {
    Handle h(CreateFileW(path.c_str(),access,sharing,nullptr,creation,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_RANDOM_ACCESS,nullptr));
    if(h.value==INVALID_HANDLE_VALUE)throw FileAcquisitionError(error,GetLastError());
    local_file::ordinary(h.value,false);local_file::bind_path(h.value,path);return h;
}
struct Path {
    std::wstring value,parent;std::vector<Handle> ancestors;V generation,ancestor_generations;
    explicit Path(const std::string& input):value(local_file::path_for(input)),ancestors(local_file::pin_parents(value)) {
        const auto slash=value.rfind(L'\\');if(value.size()<=3 || slash==value.size()-1)throw FileAcquisitionError("acquisition_output_path");
        parent=slash==2?value.substr(0,3):value.substr(0,slash);ancestor_generations=local_file::parent_generations(ancestors);generation=ancestor_generations.items.back();
    }
    std::string location() const {
        auto leaf=value.substr(value.rfind(L'\\')+1);
        const auto n=LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_UPPERCASE,leaf.data(),static_cast<int>(leaf.size()),nullptr,0,nullptr,nullptr,0);
        if(n<=0)throw FileAcquisitionError("acquisition_lookup_key",GetLastError());std::wstring folded(static_cast<std::size_t>(n),L'\0');
        if(LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_UPPERCASE,leaf.data(),static_cast<int>(leaf.size()),&folded[0],n,nullptr,nullptr,0)!=n)throw FileAcquisitionError("acquisition_lookup_key",GetLastError());
        return "location:"+hash(json::dump(V::object().put("parent",generation).put("leaf_lookup",V::string(local_file::utf8(folded)))));
    }
    void check() const {
        local_file::check_parents(value,ancestors,ancestor_generations);
    }
};
void seek(HANDLE h,std::uint64_t offset) {
    if(offset>static_cast<std::uint64_t>(MAXLONGLONG))throw FileAcquisitionError("acquisition_file_range");
    LARGE_INTEGER p{};p.QuadPart=static_cast<LONGLONG>(offset);if(!SetFilePointerEx(h,p,nullptr,FILE_BEGIN))throw FileAcquisitionError("acquisition_file_seek",GetLastError());
}
acquisition::Read read(HANDLE h,std::uint64_t offset,std::uint32_t size) {
    seek(h,offset);acquisition::Read r;r.bytes.resize(size);DWORD got=0;
    if(size && !ReadFile(h,r.bytes.data(),size,&got,nullptr)) {r.bytes.clear();r.error="win32-read:"+std::to_string(GetLastError());}
    else r.bytes.resize(got);return r;
}
void write(HANDLE h,const unsigned char* bytes,std::size_t size) {
    DWORD got=0;if(!WriteFile(h,bytes,static_cast<DWORD>(size),&got,nullptr))throw FileAcquisitionError("acquisition_file_write",GetLastError());
    if(got!=size)throw FileAcquisitionError("acquisition_file_short_write");
}
json::Limits record_limits() {json::Limits l;l.bytes=16384;l.depth=10;l.values=512;l.string_bytes=512;return l;}
}
class FileAcquisition::Impl final:public acquisition::Ports {
    FileAcquisitionRequest request_;Path source_path_,destination_path_,map_path_;
    Handle source_,code_,destination_,map_;std::unique_ptr<Path> code_path_;
    V source_metadata_,code_metadata_,base_,active_;std::string code_hash_;
    std::uint64_t source_size_=0,map_size_=0,cursor_=0,last_complete_=0,checkpoint_=0;
    bool executed_=false,opened_=false,creation_attempted_=false;std::uint32_t platform_=0;
    acquisition::Plan plan_;
    FileAcquisitionHooks hooks_;V original_capture_;std::uint64_t started_=0,ticks_=0;
    template<typename F> auto guarded(F&& f)->decltype(f()) {
        try {return f();}catch(const FileAcquisitionError& e) {platform_=e.platform_code;throw;}
        catch(const local_file::Error& e) {platform_=e.platform_code;throw FileAcquisitionError(e.what(),e.platform_code);}
    }
    std::string host() const {
        wchar_t value[MAX_COMPUTERNAME_LENGTH+1];DWORD size=MAX_COMPUTERNAME_LENGTH+1;
        if(!GetComputerNameW(value,&size))throw FileAcquisitionError("acquisition_host_observation",GetLastError());
        return "observed-local-host:"+hash(local_file::utf8(std::wstring(value,size)));
    }
    V prospective(const char* role,const Path& p) const {
        return binding(role,p.location(),hash(json::dump(p.ancestor_generations)+":absence"),domain(p.generation),source_size_);
    }
    V owned(const char* role,const Path& path,HANDLE file) const {
        local_file::bind_path(file,path.value);
        const auto g=local_file::generation(file,false);return binding(role,file_id(g),hash(json::dump(g)),domain(g),source_size_,path.location());
    }
    V observe_base() const {
        source_path_.check();destination_path_.check();map_path_.check();code_path_->check();
        local_file::bind_path(source_.value,source_path_.value);local_file::bind_path(code_.value,code_path_->value);
        const auto source=local_file::metadata(source_.value),code=local_file::metadata(code_.value);
        return V::object().put("source",binding("source",file_id(source.value),hash(json::dump(source.value)),domain(source.value),source.size))
            .put("host",binding("host",host(),"windows.nt10.x64.local-file-profile/1","host-observation",0))
            .put("executable",binding("executable",file_id(code.value),hash(json::dump(code.value)+code_hash_),domain(code.value),0))
            .put("provider",binding("provider","provider.image.acquire.raw.prototype/1",code_hash_,"linked-executable-generation",0));
    }
    void capacity(std::uint64_t data_remaining,std::uint64_t map_remaining) const {
        ULARGE_INTEGER data{},records{};
        if(!GetDiskFreeSpaceExW(destination_path_.parent.c_str(),&data,nullptr,nullptr) ||
           !GetDiskFreeSpaceExW(map_path_.parent.c_str(),&records,nullptr,nullptr))throw FileAcquisitionError("acquisition_capacity_observation",GetLastError());
#ifdef DISKED_FILE_ACQUISITION_TESTING
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_NO_CAPACITY",nullptr,0))throw acquisition::CreationRefusal("acquisition_capacity");
#endif
        if(domain(destination_path_.generation)==domain(map_path_.generation)) {
            if(data_remaining>MAXULONGLONG-map_remaining || data.QuadPart<data_remaining+map_remaining)throw acquisition::CreationRefusal("acquisition_capacity");
        } else if(data.QuadPart<data_remaining || records.QuadPart<map_remaining)throw acquisition::CreationRefusal("acquisition_capacity");
    }
    void event(const char* name) {
#ifdef DISKED_FILE_ACQUISITION_TESTING
        wchar_t wanted[80];const auto n=GetEnvironmentVariableW(L"DISKED_ACQ_TEST_EVENT",wanted,80);
        const auto match=n && n<80 && local_file::utf8(std::wstring(wanted,n))==name;
        if(match) {
            const auto message=json::dump(V::object().put("event",V::string(name)).put("checkpoint_bytes",number(checkpoint_)).put("pid",number(GetCurrentProcessId())));
            std::fputs(message.c_str(),stdout);std::fputc('\n',stdout);std::fflush(stdout);
            if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_PAUSE",nullptr,0)) {
                wchar_t release[241];const auto count=GetEnvironmentVariableW(L"DISKED_ACQ_TEST_RELEASE_FILE",release,241);
                if(count && count<241) {
                    const auto start=GetTickCount64();
                    while(GetFileAttributesW(release)==INVALID_FILE_ATTRIBUTES) {
                        if(GetTickCount64()-start>15000)throw FileAcquisitionError("acquisition_test_release_timeout");Sleep(10);
                    }
                    return; // Test-only controlled continuation of the same worker.
                }
                Sleep(INFINITE);
            }
            throw FileAcquisitionError("acquisition_test_interrupt");
        }
#else
        (void)name;
#endif
    }
    acquisition::Record row() {
        if(cursor_==map_size_)return {"",true,true};std::string bytes;const auto start=cursor_;
        // Read windows, never the full map. Cursor stops at the physical LF.
        while(cursor_<map_size_) {
            const auto want=static_cast<std::uint32_t>(std::min<std::uint64_t>(4096,map_size_-cursor_));auto block=read(map_.value,cursor_,want);
            if(!block.error.empty() || block.bytes.size()!=want)throw FileAcquisitionError("acquisition_map_read");
            const auto end=std::find(block.bytes.begin(),block.bytes.end(),static_cast<unsigned char>('\n'));
            const auto count=static_cast<std::size_t>(end-block.bytes.begin());if(bytes.size()+count>16384)throw FileAcquisitionError("acquisition_map_record_limit");
            bytes.append(reinterpret_cast<const char*>(block.bytes.data()),count);cursor_+=count;
            if(end!=block.bytes.end()) {++cursor_;last_complete_=cursor_;return {bytes,true,false};}
        }
        if(cursor_-start>16384)throw FileAcquisitionError("acquisition_map_record_limit");return {bytes,false,false};
    }
    void prepare_resume() {
        destination_=open(destination_path_.value,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING,"acquisition_destination_open");
        map_=open(map_path_.value,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING,"acquisition_map_open");map_size_=local_file::metadata(map_.value).size;
        const auto r=row();if(r.end || !r.complete)throw FileAcquisitionError("acquisition_file_header");const auto h=json::parse(r.bytes,record_limits());
        if(field(h,"type").text!="header")throw FileAcquisitionError("acquisition_file_header");
        const auto& payload=field(h,"payload");plan_=acquisition::prepare(field(payload,"plan"));
        if(field(payload,"plan_digest").text!=plan_.digest)throw FileAcquisitionError("acquisition_file_header");
        auto expected=observe_base();expected.put("destination",prospective("destination",destination_path_)).put("map",prospective("map",map_path_));
        if(plan_.bytes!=source_size_ || json::dump(field(plan_.definition,"resources"))!=json::dump(expected))throw FileAcquisitionError("acquisition_resume_binding");
        if(request_.explicit_options && (request_.chunk_bytes!=plan_.chunk_bytes || request_.retries!=plan_.retries ||
            request_.read_policy!=field(plan_.definition,"read_policy").text || request_.substitution!=field(plan_.definition,"substitution").text))throw FileAcquisitionError("acquisition_resume_options");
        active_=observe_base();active_.put("destination",owned("destination",destination_path_,destination_.value)).put("map",owned("map",map_path_,map_.value));
        if(json::dump(active_)!=json::dump(field(payload,"resources")))throw FileAcquisitionError("acquisition_resume_binding");
        if(local_file::metadata(destination_.value).size>plan_.bytes)throw FileAcquisitionError("acquisition_destination_extent");
        base_=expected;cursor_=last_complete_=0;
    }
public:
    explicit Impl(const FileAcquisitionRequest& request,const acquisition::Plan* reviewed):request_(request),source_path_(request.source),destination_path_(request.destination),map_path_(request.map) {
        if(destination_path_.location()==map_path_.location())throw FileAcquisitionError("acquisition_file_alias");
        source_=open(source_path_.value,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING,"image_source_open");
        source_metadata_=local_file::metadata(source_.value).value;source_size_=local_file::metadata(source_.value).size;
        wchar_t module[241];const auto length=GetModuleFileNameW(nullptr,module,241);if(!length || length>=241)throw FileAcquisitionError("acquisition_executable_path",GetLastError());
        code_path_.reset(new Path(local_file::utf8(std::wstring(module,length))));code_=open(code_path_->value,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING,"acquisition_executable_open");
        const auto info=local_file::metadata(code_.value);code_metadata_=info.value;
        if(info.size>16*1024*1024)throw FileAcquisitionError("acquisition_executable_budget");const auto bytes=read(code_.value,0,static_cast<std::uint32_t>(info.size));
        if(!bytes.error.empty() || bytes.bytes.size()!=info.size)throw FileAcquisitionError("acquisition_executable_read");code_hash_=hash(bytes.bytes.data(),bytes.bytes.size());
        if(request.resume)prepare_resume();
        else {
            if(exists(destination_path_.value) || exists(map_path_.value))throw FileAcquisitionError("acquisition_output_exists");
            base_=observe_base();base_.put("destination",prospective("destination",destination_path_)).put("map",prospective("map",map_path_));
            FILETIME timestamp{};GetSystemTimeAsFileTime(&timestamp);static std::atomic<std::uint64_t> sequence{0};
            const auto origin=json::dump(source_metadata_)+std::to_string(timestamp.dwHighDateTime)+":"+std::to_string(timestamp.dwLowDateTime)+":"+std::to_string(GetCurrentProcessId())+":"+std::to_string(++sequence);
            plan_=acquisition::prepare(V::object().put("schema",V::string("org.disked.acquisition-plan-prototype/1")).put("capture_epoch",reviewed?field(reviewed->definition,"capture_epoch"):V::string(hash(origin)))
                .put("resources",base_).put("bytes",number(source_size_)).put("chunk_bytes",number(request.chunk_bytes)).put("read_policy",V::string(request.read_policy))
                .put("retry_limit",number(request.retries)).put("substitution",V::string(request.substitution)));
        }
        if(reviewed && plan_.digest!=reviewed->digest)throw FileAcquisitionError("acquisition_reviewed_definition_changed");
    }
    const acquisition::Plan& plan() const {return plan_;}
    V observe() override { return guarded([&] {
        auto b=observe_base();
        if(opened_) {
            if(local_file::metadata(destination_.value).size>source_size_ || local_file::metadata(map_.value).size!=map_size_)throw FileAcquisitionError("acquisition_output_state");
            b.put("destination",owned("destination",destination_path_,destination_.value)).put("map",owned("map",map_path_,map_.value));
        } else {
            if(exists(destination_path_.value) || exists(map_path_.value))throw acquisition::CreationRefusal("acquisition_output_exists");
            b.put("destination",prospective("destination",destination_path_)).put("map",prospective("map",map_path_));
        }
        return b;
    }); }
    V create_outputs(const acquisition::Plan& p) override { return guarded([&] {
        const auto chunks=p.bytes/p.chunk_bytes+(p.bytes%p.chunk_bytes?1:0);capacity(p.bytes,(chunks*2+2)*16385+1048576);
        // CREATE_NEW is the final no-clobber check; no output is erased on failure.
        event("before-create");
        creation_attempted_=true;
        try {map_=open(map_path_.value,GENERIC_READ|GENERIC_WRITE,0,CREATE_NEW,"acquisition_map_create");}
        catch(const FileAcquisitionError& e) {platform_=e.platform_code;throw acquisition::CreationRefusal(e.what());}
        map_size_=0;event("map-created");destination_=open(destination_path_.value,GENERIC_READ|GENERIC_WRITE,0,CREATE_NEW,"acquisition_destination_create");
        opened_=true;active_=observe();event("outputs-created");return active_;
    }); }
    void open_resume() override { guarded([&] {
        // Release read-only preparation handles, reopen with effect authority,
        // then reidentify under exclusive normal-file sharing before mutation.
        destination_=Handle();map_=Handle();
        destination_=open(destination_path_.value,GENERIC_READ|GENERIC_WRITE,0,OPEN_EXISTING,"acquisition_destination_open");
        map_=open(map_path_.value,GENERIC_READ|GENERIC_WRITE,0,OPEN_EXISTING,"acquisition_map_open");
        opened_=true;cursor_=last_complete_=0;
        if(json::dump(observe())!=json::dump(active_))throw FileAcquisitionError("acquisition_resume_binding");
    }); }
    acquisition::Record next_record() override { return guarded([&] {return row();}); }
    void validate_output_coverage(std::uint64_t checkpoint,std::uint64_t pending) override { guarded([&] {
        const auto size=local_file::metadata(destination_.value).size;
        if(size<checkpoint || size>pending)throw FileAcquisitionError("acquisition_unexplained_output");
    }); }
    void discard_incomplete_tail() override { guarded([&] {
        seek(map_.value,last_complete_);if(!SetEndOfFile(map_.value))throw FileAcquisitionError("acquisition_map_truncate",GetLastError());
        map_size_=cursor_=last_complete_;flush_map();event("tail-repaired");
    }); }
    void append_record(const std::string& bytes) override { guarded([&] {
        if(bytes.size()>16384 || bytes.find('\n')!=std::string::npos || map_size_>17180917760ULL-bytes.size()-1)throw FileAcquisitionError("acquisition_map_limit");
        capacity(0,bytes.size()+1);seek(map_.value,map_size_);const auto row_bytes=bytes+'\n';
#ifdef DISKED_FILE_ACQUISITION_TESTING
        wchar_t torn_type[32];const auto torn_count=GetEnvironmentVariableW(L"DISKED_ACQ_TEST_TORN_MAP_TYPE",torn_type,32);
        const auto selected=torn_count && torn_count<32 && local_file::utf8(std::wstring(torn_type,torn_count))==field(json::parse(bytes,record_limits()),"type").text;
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_TORN_MAP",nullptr,0) || selected) {write(map_.value,reinterpret_cast<const unsigned char*>(row_bytes.data()),row_bytes.size()/2);map_size_+=row_bytes.size()/2;throw FileAcquisitionError("acquisition_test_torn_map");}
#endif
        write(map_.value,reinterpret_cast<const unsigned char*>(row_bytes.data()),row_bytes.size());map_size_+=row_bytes.size();
        const auto record=json::parse(bytes,record_limits());const auto type=field(record,"type").text;
        if(type=="checkpoint") {const auto& c=field(record,"payload");checkpoint_=std::stoull(field(c,"offset").text)+std::stoull(field(c,"length").text);}
        event(("append-"+type).c_str());
    }); }
    void flush_map() override { guarded([&] {
#ifdef DISKED_FILE_ACQUISITION_TESTING
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_MAP_FLUSH_ERROR",nullptr,0))throw FileAcquisitionError("acquisition_map_flush",ERROR_WRITE_FAULT);
#endif
        if(!FlushFileBuffers(map_.value))throw FileAcquisitionError("acquisition_map_flush",GetLastError());event("map-flushed");
    }); }
    acquisition::Read read_source(std::uint64_t offset,std::uint32_t size) override { return guarded([&] {
        auto out=read(source_.value,offset,size);
#ifdef DISKED_FILE_ACQUISITION_TESTING
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_READ_ERROR",nullptr,0)) {out.bytes.clear();out.error="win32-read:30";}
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_SHORT_READ",nullptr,0) && !out.bytes.empty())out.bytes.pop_back();
#endif
        event("source-read");return out;
    }); }
    void write_destination(std::uint64_t offset,const std::vector<unsigned char>& bytes) override { guarded([&] {
        if(offset>source_size_ || bytes.size()>source_size_-offset)throw FileAcquisitionError("acquisition_file_range");capacity(bytes.size(),16385*2);seek(destination_.value,offset);
#ifdef DISKED_FILE_ACQUISITION_TESTING
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_WRITE_ERROR",nullptr,0))throw FileAcquisitionError("acquisition_file_write",ERROR_DISK_FULL);
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_PARTIAL_WRITE",nullptr,0)) {write(destination_.value,bytes.data(),bytes.size()/2);throw FileAcquisitionError("acquisition_test_partial_write");}
#endif
        write(destination_.value,bytes.data(),bytes.size());event("destination-written");
    }); }
    void flush_destination() override { guarded([&] {
#ifdef DISKED_FILE_ACQUISITION_TESTING
        if(GetEnvironmentVariableW(L"DISKED_ACQ_TEST_DESTINATION_FLUSH_ERROR",nullptr,0))throw FileAcquisitionError("acquisition_destination_flush",ERROR_WRITE_FAULT);
#endif
        if(!FlushFileBuffers(destination_.value))throw FileAcquisitionError("acquisition_destination_flush",GetLastError());event("destination-flushed");
    }); }
    acquisition::Read read_destination(std::uint64_t offset,std::uint32_t size) override { return guarded([&] {return read(destination_.value,offset,size);}); }
    bool stop_requested() override { return guarded([&] {
        if(hooks_.stop && hooks_.stop())return true;
#ifdef DISKED_FILE_ACQUISITION_TESTING
        wchar_t value[24];const auto n=GetEnvironmentVariableW(L"DISKED_ACQ_TEST_STOP_AFTER",value,24);
        if(n && n<24)return checkpoint_>=std::stoull(local_file::utf8(std::wstring(value,n)));
#endif
        return false;
    }); }
    V capture_evidence() override {return V::object().put("clock",V::string("windows-filetime-wall")).put("started",number(started_)).put("attempt_id",V::string(hooks_.attempt_id));}
    void original_capture(const V& v) override {original_capture_=v;}
    void checkpoint_observed(const acquisition::Outcome& out) override {if(hooks_.checkpoint)hooks_.checkpoint(out);}
    FileAcquisitionResult run(const acquisition::Grant& grant,const FileAcquisitionHooks& hooks) {
        if(executed_)throw FileAcquisitionError("acquisition_session_consumed");executed_=true;
        hooks_=hooks;FILETIME stamp{};GetSystemTimeAsFileTime(&stamp);started_=(static_cast<std::uint64_t>(stamp.dwHighDateTime)<<32)|stamp.dwLowDateTime;ticks_=GetTickCount64();
        if(hooks_.attempt_id.empty())hooks_.attempt_id="file-attempt:"+std::to_string(GetCurrentProcessId())+":"+std::to_string(started_);
        auto outcome=acquisition::execute(plan_,grant,*this,request_.resume);
        GetSystemTimeAsFileTime(&stamp);const auto finished=(static_cast<std::uint64_t>(stamp.dwHighDateTime)<<32)|stamp.dwLowDateTime;
        V map_bytes,destination_bytes;auto observations=V::array();
        const auto size=[&observations](HANDLE handle,const char* role,V& result) {
            if(handle==INVALID_HANDLE_VALUE)return;
            try {result=number(local_file::metadata(handle).size);}
            catch(const local_file::Error& e) {observations.items.push_back(V::object().put("role",V::string(role)).put("diagnostic",V::string(e.what())).put("platform_code",number(e.platform_code)));}
        };
        size(map_.value,"map",map_bytes);size(destination_.value,"destination",destination_bytes);
        auto receipt=V::object().put("profile",V::string("ordinary-windows-raw-file-prototype/1")).put("source_metadata",source_metadata_)
            .put("source_path",V::string(local_file::utf8(source_path_.value))).put("destination_path",V::string(local_file::utf8(destination_path_.value)))
            .put("map_path",V::string(local_file::utf8(map_path_.value))).put("map_bytes",map_bytes).put("expected_map_bytes",number(map_size_))
            .put("destination_bytes",destination_bytes).put("size_observation_errors",observations).put("opened_outputs",V::boolean_value(opened_))
            .put("output_creation_attempted",V::boolean_value(creation_attempted_))
            .put("resources",opened_?active_:base_).put("resources_kind",V::string(opened_?"effect-owned":"prepared-plan")).put("source_consistency",V::string("live-uncoordinated"))
            .put("flush_scope",V::string("per-file-FlushFileBuffers-API-only")).put("physical_backing_qualified",V::boolean_value(false))
            .put("platform_code",number(platform_));
        receipt.put("original_capture",original_capture_).put("attempt_id",V::string(hooks_.attempt_id)).put("started_filetime",number(started_))
            .put("finished_filetime",number(finished)).put("elapsed_ms",number(GetTickCount64()-ticks_)).put("wall_clock_regressed",V::boolean_value(finished<started_));
        return {outcome,receipt};
    }
};
FileAcquisition::FileAcquisition(const FileAcquisitionRequest& request,const V* reviewed_definition) {
    if((!request.resume || request.explicit_options) &&
       ((request.chunk_bytes!=4096 && request.chunk_bytes!=65536 && request.chunk_bytes!=1048576) || request.retries>3 ||
        (request.read_policy!="ordinary" && request.read_policy!="failing-read-mostly") ||
        (request.substitution!="stop" && request.substitution!="zero-fill") || (request.read_policy=="failing-read-mostly" && request.retries)))
        throw FileAcquisitionError("acquisition_file_options");
    acquisition::Plan reviewed;if(reviewed_definition)reviewed=acquisition::prepare(*reviewed_definition);
    try {impl_.reset(new Impl(request,reviewed_definition?&reviewed:nullptr));}catch(const local_file::Error& e) {throw FileAcquisitionError(e.what(),e.platform_code);}
}
FileAcquisition::~FileAcquisition()=default;
const acquisition::Plan& FileAcquisition::plan() const {return impl_->plan();}
FileAcquisitionResult FileAcquisition::execute(const acquisition::Grant& grant,const FileAcquisitionHooks& hooks) {return impl_->run(grant,hooks);}
}
