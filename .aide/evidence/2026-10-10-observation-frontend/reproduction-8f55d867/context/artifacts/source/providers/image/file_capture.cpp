#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "file_capture.h"
#include "local_file.h"
#include "map_observation.h"
#include "sha256.h"
#include <algorithm>
#include <atomic>
#include <deque>
#include <vector>

namespace disked {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code,DWORD platform=0) {throw ImageCaptureError(code,platform);}
void checked(int status) {if(status!=DE_OK)fail("image_capture_internal");}
using local_file::Handle;
std::string hex(const unsigned char* p,std::size_t size) {
    static const char alphabet[]="0123456789abcdef";std::string out;out.reserve(size*2);
    for(std::size_t i=0;i<size;++i) {out+=alphabet[p[i]>>4];out+=alphabet[p[i]&15];}return out;
}
std::string hash(const unsigned char* p,std::size_t size) {
    unsigned char digest[32];sha256(p,size,digest);return "sha256:"+hex(digest,32);
}
std::string hash(const std::string& bytes) {return hash(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size());}
V exact(std::uint64_t n) {return V::string(std::to_string(n));}
std::uint64_t filetime(const FILETIME& value) {return (static_cast<std::uint64_t>(value.dwHighDateTime)<<32)|value.dwLowDateTime;}
std::uint64_t now() {FILETIME value{};GetSystemTimeAsFileTime(&value);return filetime(value);}
std::string epoch(const V& source,std::uint64_t started) {
    static std::atomic<std::uint64_t> sequence{0};FILETIME created{},exited{},kernel{},user{};
    if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user))fail("image_capture_epoch",GetLastError());
    auto origin=V::object().put("source",source).put("process_id",exact(GetCurrentProcessId()))
        .put("process_created",exact(filetime(created))).put("capture_started",exact(started)).put("sequence",exact(++sequence));
    return hash(json::dump(origin));
}
using local_file::utf8;using local_file::path_for;using local_file::ordinary;using local_file::bind_path;
class Source {
    std::vector<Handle> ancestors_;
    V parent_generations_;
public:
    std::wstring path;
    Handle file;
    explicit Source(const std::string& input):path(path_for(input)) {
#ifdef DISKED_IMAGE_CAPTURE_TESTING
        if(GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_OPEN_GUARD",nullptr,0))fail("image_test_open_guard");
#endif
        ancestors_=local_file::pin_parents(path);
        parent_generations_=local_file::parent_generations(ancestors_);
        file=Handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_RANDOM_ACCESS,nullptr));
        if(file.value==INVALID_HANDLE_VALUE)fail("image_source_open",GetLastError());ordinary(file.value,false);bind_path(file.value,path);
        check();
    }
    void check() const {local_file::check_parents(path,ancestors_,parent_generations_);ordinary(file.value,false);bind_path(file.value,path);}
};
using local_file::Metadata;
Metadata metadata(HANDLE h) {
    try {return local_file::metadata(h);}catch(const local_file::Error& e) {throw ImageCaptureError(e.what(),e.platform_code);}
}
std::uint64_t native(const de_u64& n) {
    char out[21];checked(de_u64_format(&n,out,sizeof(out)));return std::stoull(out);
}
de_u64 portable(std::uint64_t n) {de_u64 value{};const auto text=std::to_string(n);checked(de_u64_parse(text.data(),text.size(),&value));return value;}
struct Read {
    std::vector<unsigned char> bytes;
    DWORD error=0;
};
Read read(HANDLE h,std::uint64_t start,std::size_t length) {
    Read out;
    if(start>static_cast<std::uint64_t>(MAXLONGLONG)) {out.error=ERROR_INVALID_PARAMETER;return out;}
    LARGE_INTEGER position{};position.QuadPart=static_cast<LONGLONG>(start);
    if(!SetFilePointerEx(h,position,nullptr,FILE_BEGIN)) {out.error=GetLastError();return out;}
    out.bytes.resize(length);DWORD got=0;
    if(length && !ReadFile(h,out.bytes.data(),static_cast<DWORD>(length),&got,nullptr))out.error=GetLastError();
    // Bytes from a failed ReadFile are not established; never parse its buffer.
    out.bytes.resize(out.error?0:static_cast<std::size_t>(got));return out;
}
struct Region {
    std::uint64_t start=0,end=0;
    Read first,second;
};
class Capture {
    HANDLE file_;
    std::deque<Region> regions_;
    bool overlap_equal_=true;
    std::size_t requests_=0,request_bytes_=0;
public:
    explicit Capture(HANDLE h):file_(h) {}
    de_view region(const de_byte_extent& extent) {
        ++requests_;const auto start=native(extent.start),end=native(extent.end);request_bytes_+=static_cast<std::size_t>(end-start);
        for(const auto& r:regions_)if(r.start==start && r.end==end)return {r.first.bytes.data(),r.first.bytes.size()};
        Region item;item.start=start;item.end=end;item.first=read(file_,start,static_cast<std::size_t>(end-start));
#ifdef DISKED_IMAGE_CAPTURE_TESTING
        // Test-only process environment, absent from the product/library build.
        if(regions_.empty() && GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_READ_ERROR",nullptr,0)) {item.first.bytes.clear();item.first.error=ERROR_READ_FAULT;}
        if(regions_.empty() && GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_SHORT_READ",nullptr,0) && !item.first.bytes.empty())item.first.bytes.pop_back();
        if(GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_OVERLAP_CHANGED",nullptr,0))for(const auto& r:regions_) {
            const auto begin=std::max(start,r.start),finish=std::min(start+item.first.bytes.size(),r.start+r.first.bytes.size());
            if(begin<finish)item.first.bytes[static_cast<std::size_t>(begin-start)]^=1;
        }
#endif
        for(const auto& r:regions_) {
            const auto begin=std::max(start,r.start),finish=std::min(start+item.first.bytes.size(),r.start+r.first.bytes.size());
            if(begin<finish && !std::equal(item.first.bytes.begin()+static_cast<std::size_t>(begin-start),
                item.first.bytes.begin()+static_cast<std::size_t>(finish-start),r.first.bytes.begin()+static_cast<std::size_t>(begin-r.start)))overlap_equal_=false;
        }
        regions_.push_back(std::move(item));const auto& result=regions_.back().first.bytes;return {result.data(),result.size()};
    }
    V verify(V& summary) {
        auto manifest=V::array(),details=V::array();std::size_t requested=0,captured=0,short_regions=0,reread_short=0,errors=0;bool equal=overlap_equal_;
        for(auto& r:regions_) {
            const auto length=static_cast<std::size_t>(r.end-r.start);r.second=read(file_,r.start,length);
#ifdef DISKED_IMAGE_CAPTURE_TESTING
            if(&r==&regions_.front() && GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_CHANGED",nullptr,0) && !r.second.bytes.empty())r.second.bytes[0]^=1;
            if(&r==&regions_.front() && GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_VERIFY_ERROR",nullptr,0)) {r.second.bytes.clear();r.second.error=ERROR_READ_FAULT;}
#endif
            const bool same=!r.first.error && !r.second.error && r.first.bytes==r.second.bytes;
            equal=equal && same;requested+=length;captured+=r.first.bytes.size();if(r.first.bytes.size()!=length)++short_regions;
            if(r.second.bytes.size()!=length)++reread_short;
            if(r.first.error || r.second.error)++errors;
            auto value=V::object().put("start",exact(r.start)).put("end",exact(r.end)).put("bytes",exact(r.first.bytes.size()))
                .put("sha256",V::string(hash(r.first.bytes.data(),r.first.bytes.size())))
                .put("read_error",r.first.error?exact(r.first.error):V{}).put("reread_bytes",exact(r.second.bytes.size()))
                .put("reread_sha256",V::string(hash(r.second.bytes.data(),r.second.bytes.size())))
                .put("reread_error",r.second.error?exact(r.second.error):V{}).put("equal",V::boolean_value(same));
            if(details.items.size()<8)details.items.push_back(value);manifest.items.push_back(std::move(value));
        }
        json::Limits limits;limits.bytes=256*1024;limits.depth=8;limits.values=16384;limits.string_bytes=128;
        const auto bytes=json::dump(manifest,limits);const auto omitted=regions_.size()-details.items.size();
        summary.put("requests",exact(requests_)).put("unique_regions",exact(regions_.size())).put("requested_bytes",exact(requested))
            .put("requested_bytes_with_reuse",exact(request_bytes_))
            .put("captured_bytes",exact(captured)).put("short_regions",exact(short_regions)).put("error_regions",exact(errors))
            .put("regions_complete",V::boolean_value(short_regions==0 && errors==0)).put("overlap_equal",V::boolean_value(overlap_equal_))
            .put("reread_short_regions",exact(reread_short)).put("reread_regions_complete",V::boolean_value(reread_short==0 && errors==0))
            .put("reread_equal",V::boolean_value(equal)).put("region_manifest_sha256",V::string(hash(bytes)))
            .put("omitted_regions",exact(omitted)).put("regions",std::move(details));
        return manifest;
    }
};
}
CapturedImage capture_raw_image(const std::string& input,std::uint32_t unit) {
    try {
    if(unit!=512 && unit!=4096)fail("image_geometry");
    const auto started=now(),ticks=GetTickCount64();Source source(input);const auto before=metadata(source.file.value);
    const auto blocks=before.size/unit+(before.size%unit?1:0);Capture capture(source.file.value);
    CapturedImage out;out.report=observe_partition_regions(portable(blocks),unit,[&capture](const de_byte_extent& extent) {return capture.region(extent);});
    auto receipt=V::object().put("source_consistency",V::string("live-uncoordinated"))
        .put("whole_file_hashed",V::boolean_value(false)).put("atomic_snapshot",V::boolean_value(false))
        .put("capture_epoch",V::string(epoch(before.value,started))).put("started_filetime",exact(started))
        .put("source_before",before.value).put("path",V::string(input)).put("resolved_path",V::string(utf8(source.path)))
        .put("partial_final_block",V::boolean_value(before.size%unit!=0));
    source.check();out.region_manifest=capture.verify(receipt);source.check();
    try {
        auto after=metadata(source.file.value);
#ifdef DISKED_IMAGE_CAPTURE_TESTING
        if(GetEnvironmentVariableW(L"DISKED_IMAGE_TEST_METADATA_CHANGED",nullptr,0))after.value.put("changed",V::string("test-only"));
#endif
        const bool same=json::dump(before.value)==json::dump(after.value);
        receipt.put("source_after",std::move(after.value)).put("metadata_equal",V::boolean_value(same));
        receipt.put("observed_stable",V::boolean_value(same && receipt.find("reread_equal")->boolean));
    } catch(const ImageCaptureError& error) {
        receipt.put("source_after",V{}).put("metadata_equal",V::boolean_value(false)).put("observed_stable",V::boolean_value(false))
            .put("metadata_error",V::string(error.what())).put("metadata_platform_code",exact(error.platform_code));
    }
    receipt.put("finished_filetime",exact(now())).put("elapsed_ms",exact(GetTickCount64()-ticks));
    out.report.put("capture",std::move(receipt));
    json::Limits bounds;bounds.bytes=60*1024;bounds.depth=16;bounds.values=8192;bounds.string_bytes=1024;
    try {json::dump(out.report,bounds);}catch(const json::Error&) {fail("image_report_limit");}
    return out;
    }catch(const local_file::Error& e) {throw ImageCaptureError(e.what(),e.platform_code);}
}
}
