#include "storage_queries.h"
#include "snapshot.h"
#include <algorithm>
#include <cstddef>
#include <limits>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;using Bytes=std::vector<unsigned char>;
static_assert(sizeof(STORAGE_PROPERTY_QUERY)==12 && sizeof(STORAGE_DEVICE_DESCRIPTOR)==40 && offsetof(STORAGE_DEVICE_DESCRIPTOR,RawDeviceProperties)==36,"selected descriptor ABI");
static_assert(sizeof(STORAGE_DEVICE_NUMBER)==12 && sizeof(DISK_GEOMETRY)==24 && offsetof(DISK_GEOMETRY_EX,DiskSize)==24,"selected fixed query ABI");
static_assert(sizeof(DISK_EXTENT)==24 && offsetof(VOLUME_DISK_EXTENTS,Extents)==8 && offsetof(DISK_EXTENT,StartingOffset)==8 && offsetof(DISK_EXTENT,ExtentLength)==16,"selected extent ABI");
void require(bool ok) {if(!ok)throw std::invalid_argument("nt_storage_reply_shape");}
std::uint64_t load(const Bytes& b,std::size_t at,unsigned size) {require(at<=b.size() && size<=b.size()-at);std::uint64_t v=0;for(unsigned i=0;i<size;++i)v|=static_cast<std::uint64_t>(b[at+i])<<(8*i);return v;}
V num(std::uint64_t n) {return V::string(std::to_string(n));}
std::string hex(const Bytes& b,std::size_t at,std::size_t size) {require(at<=b.size() && size<=b.size()-at);const char* h="0123456789abcdef";std::string s;for(std::size_t i=0;i<size;++i) {s+=h[b[at+i]>>4];s+=h[b[at+i]&15];}return s;}
V name(const Bytes& b,std::size_t at,DWORD limit) {
    auto v=V::object().put("original_encoding",V::string("device-descriptor-ascii-bytes")).put("display_encoding",V::string("ascii-with-byte-escapes"));
    if(!at)return v.put("state",V::string("absent")).put("original_hex",V::string("")).put("display",V::string("")).put("ascii_conformant",V::boolean_value(true));
    require(at>=36 && at<b.size());std::size_t end=at;while(end<b.size() && b[end] && end-at<=limit)++end;
    require(end<b.size() && !b[end] && end-at<=limit);std::string display;bool ascii=true;const char* h="0123456789abcdef";
    for(auto i=at;i<end;++i) {const auto c=b[i];ascii=ascii && c<128;if(c>=32 && c<=126)display+=static_cast<char>(c);else {display+="\\x";display+=h[c>>4];display+=h[c&15];}}
    return v.put("state",V::string(end==at?"empty":"present")).put("original_hex",V::string(hex(b,at,end-at)))
        .put("display",V::string(display)).put("ascii_conformant",V::boolean_value(ascii));
}
bool growth_error(DWORD e) {return e==ERROR_MORE_DATA || e==ERROR_INSUFFICIENT_BUFFER;}
const auto signed_max=(std::numeric_limits<std::uint64_t>::max)()>>1;
}
json::Limits storage_observation_limits() {json::Limits l;l.bytes=524288;l.values=32768;l.depth=24;return l;}
StorageQueryApi native_storage_query_api() {StorageQueryApi a;a.ioctl=&DeviceIoControl;a.error=&GetLastError;return a;}
StorageQueryPort::StorageQueryPort(const StorageQueryApi& api,HANDLE handle,const StorageQueryPolicy& p,std::function<bool()> stop):
    api_(api),handle_(handle),policy_(p),stop_(std::move(stop)) {
    if(!api.ioctl || !api.error || handle==nullptr || handle==INVALID_HANDLE_VALUE || p.descriptor_bytes<40 || p.descriptor_bytes>4096 || !p.string_bytes || p.string_bytes>256 || !p.extents || p.extents>64)throw std::invalid_argument("nt_storage_request");
    const auto native=native_storage_query_api();if(api.ioctl==native.ioctl || api.error==native.error)throw std::invalid_argument("nt_storage_native_port_not_admitted");
}
void StorageQueryPort::begin(unsigned i) {if(used_[i])throw std::invalid_argument("nt_storage_query_reused");used_[i]=true;}
StorageQueryPort::Packet StorageQueryPort::call(DWORD code,DWORD bytes,bool property,STORAGE_PROPERTY_ID id) {
    Packet p;p.code=code;p.property=property;p.property_id=id;if(unresolved_) {p.state="unresolved";return p;}if(stop_ && stop_()) {p.state="cancelled";return p;}
    p.bytes.assign(bytes,0xcc);STORAGE_PROPERTY_QUERY query{};query.PropertyId=id;query.QueryType=PropertyStandardQuery;
    try {
        p.ok=api_.ioctl(handle_,code,property?&query:nullptr,property?sizeof(query):0,p.bytes.data(),bytes,&p.returned,nullptr)!=FALSE;
        if(!p.ok)p.error=api_.error(); // immediate transport error, before allocation/formatting
    }catch(...) {unresolved_=true;throw;}
    // A pending transport remains unresolved even if its byte count is invalid.
    if(!p.ok && p.error==ERROR_IO_PENDING) {unresolved_=true;p.state="unresolved";return p;}
    if(p.returned>bytes) {p.state="malformed";return p;}
    if(p.ok)p.state="observed";
    else p.state=p.error==ERROR_ACCESS_DENIED?"denied":p.error==ERROR_INVALID_FUNCTION || p.error==ERROR_NOT_SUPPORTED?"unsupported":"unavailable";
    return p;
}
V StorageQueryPort::result(const char* component,const std::string& state,const std::vector<Packet>& packets,V data) const {
    auto receipts=V::array();DWORD error=0;
    for(const auto& p:packets) {
        error=p.error;const bool known=p.returned<=p.bytes.size() && (p.ok || (growth_error(p.error) && p.returned));
        auto receipt=V::object().put("control",num(p.code)).put("buffer_bytes",num(p.bytes.size())).put("returned_bytes",num(p.returned))
            .put("ok",V::boolean_value(p.ok)).put("platform_code",num(p.error)).put("state",V::string(p.state));
        if(p.property && p.property_id!=StorageDeviceProperty)receipt.put("property_id",num(p.property_id));
        receipt.put("returned_hex",known?V::string(hex(p.bytes,0,p.returned)):V{});
        receipt.put("returned_sha256",known?V::string(digest_sha256(std::string(p.bytes.begin(),p.bytes.begin()+p.returned))):V{});receipts.items.push_back(std::move(receipt));
    }
    return V::object().put("component",V::string(component)).put("state",V::string(state)).put("platform_code",num(error)).put("data",std::move(data)).put("receipts",std::move(receipts));
}
V StorageQueryPort::descriptor() {
    begin(0);std::vector<Packet> p;
    try {
        p.push_back(call(IOCTL_STORAGE_QUERY_PROPERTY,8,true));const auto& header=p.back();
        if(header.state!="observed" && !(growth_error(header.error) && header.returned==8))return result("descriptor",header.state,p);
        require(header.returned==8);const auto version=load(header.bytes,0,4),size=load(header.bytes,4,4);
        require(size>=40);if(version!=40)return result("descriptor","unsupported_version",p);if(size>policy_.descriptor_bytes)return result("descriptor","budget_exhausted",p);
        p.push_back(call(IOCTL_STORAGE_QUERY_PROPERTY,static_cast<DWORD>(size),true));const auto& body=p.back();
        if(body.state!="observed")return result("descriptor",growth_error(body.error)?"changed":body.state,p);
        require(body.returned>=40);if(load(body.bytes,0,4)!=version || load(body.bytes,4,4)!=size)return result("descriptor","changed",p);
        require(body.returned>=size);const auto raw=load(body.bytes,32,4);require(raw<=size-36);
        auto data=V::object().put("version",num(version)).put("size_bytes",num(size)).put("device_type",num(body.bytes[8])).put("device_type_modifier",num(body.bytes[9]))
            .put("removable_raw",num(body.bytes[10])).put("queueing_raw",num(body.bytes[11])).put("bus_type",num(load(body.bytes,28,4)))
            .put("raw_properties_bytes",num(raw)).put("raw_properties_hex",V::string(hex(body.bytes,36,static_cast<std::size_t>(raw))))
            .put("raw_properties_sha256",V::string(digest_sha256(std::string(body.bytes.begin()+36,body.bytes.begin()+36+static_cast<std::size_t>(raw)))));
        const char* keys[]={"vendor","product","revision","serial"};for(unsigned i=0;i<4;++i)data.put(keys[i],name(body.bytes,static_cast<std::size_t>(load(body.bytes,12+4*i,4)),policy_.string_bytes));
        return result("descriptor","observed",p,data);
    }catch(const std::invalid_argument&) {return result("descriptor","malformed",p);}
}
V StorageQueryPort::device_number() {
    begin(1);std::vector<Packet> p;
    try {p.push_back(call(IOCTL_STORAGE_GET_DEVICE_NUMBER,12));const auto& b=p.back();if(b.state!="observed")return result("number",b.state,p);require(b.returned==12);
        const auto type=load(b.bytes,0,4),number=load(b.bytes,4,4),partition=load(b.bytes,8,4);require(type<=65535);
        return result("number","observed",p,V::object().put("device_type",num(type)).put("device_number",num(number)).put("partition_raw",num(partition))
            .put("partition_number",partition==0xffffffffU?V{}:num(partition)).put("identity_scope",V::string("transient-lookup-only")));
    }catch(const std::invalid_argument&) {return result("number","malformed",p);}
}
V StorageQueryPort::geometry() {
    begin(2);std::vector<Packet> p;
    try {p.push_back(call(IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,32));const auto& b=p.back();if(b.state!="observed")return result("geometry",b.state,p);require(b.returned==32);
        const auto cylinders=load(b.bytes,0,8),bytes=load(b.bytes,20,4),size=load(b.bytes,24,8);require(cylinders<=signed_max && size<=signed_max && bytes && bytes<=65536);
        return result("geometry","observed",p,V::object().put("cylinders",num(cylinders)).put("media_type",num(load(b.bytes,8,4))).put("tracks_per_cylinder",num(load(b.bytes,12,4)))
            .put("sectors_per_track",num(load(b.bytes,16,4))).put("logical_sector_bytes",num(bytes)).put("disk_size_bytes",num(size)).put("physical_sector_bytes",V{}));
    }catch(const std::invalid_argument&) {return result("geometry","malformed",p);}
}
V StorageQueryPort::length() {
    begin(3);std::vector<Packet> p;
    try {p.push_back(call(IOCTL_DISK_GET_LENGTH_INFO,8));const auto& b=p.back();if(b.state!="observed")return result("length",b.state,p);require(b.returned==8);
        const auto length=load(b.bytes,0,8);require(length<=signed_max);return result("length","observed",p,V::object().put("length_bytes",num(length)));
    }catch(const std::invalid_argument&) {return result("length","malformed",p);}
}
V StorageQueryPort::extents() {
    begin(4);std::vector<Packet> p;
    try {
        p.push_back(call(IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,32));std::uint64_t expected=0;
        if(!p.back().ok) {
            if(p.back().error!=ERROR_MORE_DATA || p.back().state=="malformed")return result("extents",p.back().state,p);
            require(p.back().returned>=4);expected=load(p.back().bytes,0,4);require(expected>1);if(expected>policy_.extents)return result("extents","budget_exhausted",p);
            p.push_back(call(IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,static_cast<DWORD>(8+24*expected)));
            if(!p.back().ok)return result("extents",p.back().error==ERROR_MORE_DATA?"changed":p.back().state,p);
        }
        const auto& b=p.back();if(b.state!="observed")return result("extents",b.state,p);require(b.returned>=8);const auto count=load(b.bytes,0,4);
        if(count>policy_.extents)return result("extents","budget_exhausted",p);if(expected && count!=expected)return result("extents","changed",p);require(8+24*count<=b.returned);
        auto data=V::array();for(std::uint64_t i=0;i<count;++i) {
            const auto at=static_cast<std::size_t>(8+24*i);const auto offset=load(b.bytes,at+8,8),length=load(b.bytes,at+16,8);
            require(offset<=signed_max && length && length<=signed_max-offset);
            data.items.push_back(V::object().put("ordinal",num(i+1)).put("disk_number",num(load(b.bytes,at,4))).put("offset_bytes",num(offset)).put("length_bytes",num(length)).put("end_bytes",num(offset+length)));
        }return result("extents","observed",p,data);
    }catch(const std::invalid_argument&) {return result("extents","malformed",p);}
}
}}
