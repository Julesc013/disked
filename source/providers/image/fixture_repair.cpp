#ifndef DISKED_GPT_OWNED_FIXTURE
#error The create-only GPT file adapter is a private test experiment, not a product provider.
#endif
#include "fixture_repair.h"
#include "local_file.h"
#include "sha256.h"
#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <map>

namespace disked { namespace image { namespace fixture {
namespace {
using V=json::Value;using Bytes=execution::proposal::Bytes;using local_file::Handle;using execution::proposal::FixtureError;
[[noreturn]] void fail(const char* code) {throw FixtureError(code);}
void require(bool ok,const char* code) {if(!ok)fail(code);}
std::string text(const V& v,const char* key) {const auto x=v.find(key);require(x && x->kind==V::Kind::string,"fixture_files_shape");return x->text;}
V exact(std::uint64_t n) {return V::string(std::to_string(n));}
std::string hash(const Bytes& bytes) {unsigned char d[32];sha256(bytes.data(),bytes.size(),d);const char digits[]="0123456789abcdef";std::string s="sha256:";for(const auto b:d){s+=digits[b>>4];s+=digits[b&15];}return s;}
std::string hash(const std::string& s) {return hash(Bytes(s.begin(),s.end()));}
std::string token(HANDLE h,bool directory=false) {return hash(json::dump(local_file::generation(h,directory)));}
std::uint64_t size(HANDLE h) {LARGE_INTEGER n{};require(GetFileSizeEx(h,&n) && n.QuadPart>=0,"fixture_file_size");return static_cast<std::uint64_t>(n.QuadPart);}
void seek(HANDLE h,std::uint64_t offset) {require(offset<=8388608,"fixture_io_extent");LARGE_INTEGER position{};position.QuadPart=static_cast<LONGLONG>(offset);require(SetFilePointerEx(h,position,nullptr,FILE_BEGIN)!=FALSE,"fixture_seek");}
Handle open(const std::wstring& path,bool create,bool directory=false) {
    Handle h(CreateFileW(path.c_str(),directory || !create?GENERIC_READ:GENERIC_READ|GENERIC_WRITE,
        directory?FILE_SHARE_READ:0,nullptr,create?CREATE_NEW:OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT|(directory?FILE_FLAG_BACKUP_SEMANTICS:FILE_FLAG_RANDOM_ACCESS),nullptr));
    require(h.value!=INVALID_HANDLE_VALUE,"fixture_open");local_file::ordinary(h.value,directory);local_file::bind_path(h.value,path);return h;
}
Bytes raw_read(HANDLE h,std::uint64_t start,std::size_t count) {
    seek(h,start);Bytes b(count);std::size_t at=0;
    while(at<count) {const auto amount=static_cast<DWORD>(std::min<std::size_t>(65536,count-at));DWORD got=0;require(ReadFile(h,b.data()+at,amount,&got,nullptr)!=FALSE && got==amount,"fixture_read");at+=got;}return b;
}
std::string executable_digest() {
    wchar_t path[241];const auto count=GetModuleFileNameW(nullptr,path,241);require(count && count<241,"fixture_executable_path");const auto name=local_file::path_for(local_file::utf8(std::wstring(path,count)));
    Handle h(CreateFileW(name.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));require(h.value!=INVALID_HANDLE_VALUE,"fixture_executable_open");local_file::ordinary(h.value,false);local_file::bind_path(h.value,name);
    const auto count_bytes=size(h.value);require(count_bytes>0 && count_bytes<=8388608,"fixture_executable_budget");return hash(raw_read(h.value,0,static_cast<std::size_t>(count_bytes)));
}
std::uint64_t created_time() {FILETIME created{},exited{},kernel{},user{};require(GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user)!=FALSE,"fixture_process_identity");return (std::uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime;}
void fault_shape(const Fault& f) {
    require((f.stage.empty() && f.action.empty()) || (!f.stage.empty() && f.stage.size()<=80 && f.stage.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789.-")==f.stage.npos),"fixture_fault_shape");
    require(f.action.empty() || f.action=="before_error" || f.action=="after_error" || f.action=="partial_error" || f.action=="crash_before" || f.action=="crash_after" || f.action=="short_read" || f.action=="alter_read","fixture_fault_shape");
}
}
struct GptFiles::Impl {
    std::wstring directory;std::vector<Handle> parents;V parent_generations;Handle root,image,backup,journal;V metadata,trace=V::array();
    std::map<std::string,std::size_t> calls;Fault fault;bool fired=false,readonly=false;std::uint64_t image_bytes=0;
    Impl(const Fault& f):fault(f) {fault_shape(f);}
    std::wstring path(const wchar_t* name) const {return directory+L"\\"+name;}
    void check(bool check_size=true) {
        local_file::check_parents(path(L"image.bin"),parents,parent_generations);local_file::ordinary(root.value,true);local_file::bind_path(root.value,directory);
        require(token(root.value,true)==text(metadata,"root_identity"),"fixture_root_changed");
        const std::vector<std::pair<HANDLE,const wchar_t*>> files{{image.value,L"image.bin"},{backup.value,L"backup.bin"},{journal.value,L"journal.bin"}};const char* names[]={"image_identity","backup_identity","journal_identity"};
        for(std::size_t i=0;i<files.size();++i) {local_file::ordinary(files[i].first,false);local_file::bind_path(files[i].first,path(files[i].second));require(token(files[i].first)==text(metadata,names[i]),"fixture_file_changed");}
        if(check_size)require(size(image.value)==image_bytes,"fixture_image_size_changed");
    }
    std::string begin(const std::string& operation,std::uint64_t offset,std::size_t count,bool setup=false) {
        check(!setup);const auto stage=operation+"."+std::to_string(++calls[operation]);require(trace.items.size()<2048,"fixture_trace_budget");
        trace.items.push_back(V::object().put("stage",V::string(stage)).put("offset",exact(offset)).put("bytes",exact(count)).put("setup",V::boolean_value(setup)).put("returned",V::boolean_value(false)));
        if(stage==fault.stage) {fired=true;if(fault.action=="crash_before")std::_Exit(112);if(fault.action=="before_error")fail("fixture_injected_before");}return stage;
    }
    void finish(const std::string& stage,std::size_t actual) {
        trace.items.back().put("actual_bytes",exact(actual)).put("returned",V::boolean_value(true));
        if(stage==fault.stage) {if(fault.action=="crash_after")std::_Exit(112);if(fault.action=="after_error")fail("fixture_injected_after");}
    }
    Bytes read(HANDLE h,const std::string& label,std::uint64_t start,std::size_t count) {
        require(count<=8388608 && start<=size(h) && count<=size(h)-start,"fixture_read_extent");Bytes result(count);seek(h,start);std::size_t at=0;
        while(at<count) {
            const auto amount=std::min<std::size_t>(65536,count-at);const auto stage=begin(label+".read",start+at,amount);DWORD got=0;
            const bool ok=ReadFile(h,result.data()+at,static_cast<DWORD>(amount),&got,nullptr)!=FALSE;require(ok && got==amount,"fixture_read");
            if(stage==fault.stage && fault.action=="short_read")fail("fixture_injected_short_read");
            if(stage==fault.stage && fault.action=="alter_read" && amount)result[at]^=1;
            finish(stage,got);at+=got;
        }return result;
    }
    void write(HANDLE h,const std::string& label,std::uint64_t start,const Bytes& data,bool setup=false) {
        require(!readonly,"fixture_read_only");require(start<=8388608 && data.size()<=8388608-start,"fixture_write_extent");seek(h,start);std::size_t at=0;
        while(at<data.size()) {
            const auto amount=std::min<std::size_t>(65536,data.size()-at);const auto stage=begin(label+".write",start+at,amount,setup);
            const bool partial=stage==fault.stage && fault.action=="partial_error";const auto requested=partial?amount/2:amount;DWORD got=0;
            const bool ok=WriteFile(h,data.data()+at,static_cast<DWORD>(requested),&got,nullptr)!=FALSE;require(ok && got==requested,"fixture_write");finish(stage,got);if(partial)fail("fixture_injected_partial_write");at+=got;
        }
    }
    void flush(HANDLE h,const std::string& label,bool setup=false) {
        require(!readonly,"fixture_read_only");const auto stage=begin(label+".flush",0,0,setup);require(FlushFileBuffers(h)!=FALSE,"fixture_flush");finish(stage,0);
    }
};
GptFiles::GptFiles(std::unique_ptr<Impl> impl):impl_(std::move(impl)) {}
GptFiles::~GptFiles()=default;
std::unique_ptr<GptFiles> GptFiles::create(const std::string& parent,const Bytes& seed,const std::string& revision,const Fault& fault) {
    require(seed.size()>0 && seed.size()<=8388608,"fixture_seed_budget");auto owned=std::unique_ptr<Impl>(new Impl(fault));const auto parent_path=local_file::path_for(parent);const auto exe=executable_digest();
    // Pin the supplied ordinary parent before creating a new private child.
    const auto marker=parent_path+L"\\.gptfixture-placeholder";owned->parents=local_file::pin_parents(marker);owned->parent_generations=local_file::parent_generations(owned->parents);const auto epoch=created_time();
    static std::atomic<std::uint64_t> sequence{0};bool made=false;
    for(unsigned attempt=0;attempt<32;++attempt) {
        const auto suffix=hash(std::to_string(GetCurrentProcessId())+":"+std::to_string(epoch)+":"+std::to_string(++sequence));const auto name="gptfx-"+suffix.substr(7,24);owned->directory=local_file::path_for(local_file::utf8(parent_path)+"\\"+name);
        if(CreateDirectoryW(owned->directory.c_str(),nullptr)) {made=true;break;}require(GetLastError()==ERROR_ALREADY_EXISTS,"fixture_create_directory");
    }
    require(made,"fixture_directory_collision");owned->root=open(owned->directory,false,true);
    owned->image=open(owned->path(L"image.bin"),true);owned->backup=open(owned->path(L"backup.bin"),true);owned->journal=open(owned->path(L"journal.bin"),true);
    owned->parents=local_file::pin_parents(owned->path(L"image.bin"));owned->parent_generations=local_file::parent_generations(owned->parents);owned->image_bytes=seed.size();
    const auto publisher=hash(std::to_string(GetCurrentProcessId())+":"+std::to_string(epoch)+":"+token(owned->root.value,true));
    owned->metadata=V::object().put("schema",V::string("org.disked.gpt-fixture-files/1")).put("scope",V::string("owned-file-fixture")).put("directory",V::string(local_file::utf8(owned->directory)))
        .put("root_identity",V::string(token(owned->root.value,true))).put("image_identity",V::string(token(owned->image.value))).put("backup_identity",V::string(token(owned->backup.value))).put("journal_identity",V::string(token(owned->journal.value)))
        .put("image_bytes",exact(seed.size())).put("provider_id",V::string("provider.image.gpt-owned-fixture/1")).put("executor_digest",V::string(exe)).put("publisher_identity",V::string(publisher.substr(7,32))).put("publisher_epoch",exact(epoch))
        .put("image_before_sha256",V::string(hash(seed))).put("source_revision",V::string(revision)).put("storage_independent",V::boolean_value(false));
    owned->write(owned->image.value,"image.seed",0,seed,true);owned->flush(owned->image.value,"image.seed",true);owned->check();require(raw_read(owned->image.value,0,seed.size())==seed,"fixture_seed_reread");
    return std::unique_ptr<GptFiles>(new GptFiles(std::move(owned)));
}
std::unique_ptr<GptFiles> GptFiles::reopen_readonly(const V& expected,const Fault& fault) {
    require(text(expected,"schema")=="org.disked.gpt-fixture-files/1" && text(expected,"scope")=="owned-file-fixture","fixture_files_shape");
    auto owned=std::unique_ptr<Impl>(new Impl(fault));owned->readonly=true;owned->metadata=expected;owned->directory=local_file::path_for(text(expected,"directory"));
    const auto base=owned->directory.substr(owned->directory.find_last_of(L'\\')+1);require(base.size()==30 && base.compare(0,6,L"gptfx-")==0,"fixture_directory_scope");
    const auto n=text(expected,"image_bytes");require(json::decimal_u64(n) && std::stoull(n)<=8388608,"fixture_image_budget");owned->image_bytes=std::stoull(n);
    owned->parents=local_file::pin_parents(owned->path(L"image.bin"));owned->parent_generations=local_file::parent_generations(owned->parents);owned->root=open(owned->directory,false,true);
    owned->image=open(owned->path(L"image.bin"),false);owned->backup=open(owned->path(L"backup.bin"),false);owned->journal=open(owned->path(L"journal.bin"),false);owned->check();
    require(text(expected,"executor_digest")==executable_digest(),"fixture_executor_generation");return std::unique_ptr<GptFiles>(new GptFiles(std::move(owned)));
}
const V& GptFiles::manifest() const {return impl_->metadata;}
V GptFiles::events() const {return impl_->trace;}
bool GptFiles::fault_fired() const {return impl_->fired;}
void GptFiles::check_ownership() {impl_->check();}
Bytes GptFiles::read_image(std::uint64_t offset,std::size_t count) {require(offset<=impl_->image_bytes && count<=impl_->image_bytes-offset,"fixture_image_extent");return impl_->read(impl_->image.value,"image",offset,count);}
void GptFiles::write_image(std::uint64_t offset,const Bytes& value) {require(offset<=impl_->image_bytes && value.size()<=impl_->image_bytes-offset,"fixture_image_extent");impl_->write(impl_->image.value,"image",offset,value);}
void GptFiles::flush_image() {impl_->flush(impl_->image.value,"image");}
Bytes GptFiles::read_backup() {const auto count=size(impl_->backup.value);require(count<=2117632,"fixture_backup_budget");return impl_->read(impl_->backup.value,"backup",0,static_cast<std::size_t>(count));}
void GptFiles::write_backup(const Bytes& value) {require(value.size()<=2117632 && size(impl_->backup.value)==0,"fixture_backup_not_empty");impl_->write(impl_->backup.value,"backup",0,value);}
void GptFiles::flush_backup() {impl_->flush(impl_->backup.value,"backup");}
Bytes GptFiles::read_journal() {const auto count=size(impl_->journal.value);require(count<=1048576,"fixture_journal_budget");return impl_->read(impl_->journal.value,"journal",0,static_cast<std::size_t>(count));}
void GptFiles::append_journal(const Bytes& value) {const auto count=size(impl_->journal.value);require(count<=1048576 && value.size()<=1048576-count,"fixture_journal_budget");impl_->write(impl_->journal.value,"journal",count,value);}
void GptFiles::flush_journal() {impl_->flush(impl_->journal.value,"journal");}
}}}
