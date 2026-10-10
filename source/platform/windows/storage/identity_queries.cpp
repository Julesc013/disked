#include "storage_queries.h"
#include "volume_inventory.h"
#include <cstddef>
#include <limits>
#include <map>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;using Bytes=std::vector<unsigned char>;
static_assert(sizeof(STORAGE_DEVICE_ID_DESCRIPTOR)==16 && offsetof(STORAGE_DEVICE_ID_DESCRIPTOR,Identifiers)==12,"selected ID descriptor ABI");
static_assert(sizeof(STORAGE_IDENTIFIER)==20 && offsetof(STORAGE_IDENTIFIER,Identifier)==16 && offsetof(STORAGE_IDENTIFIER,Association)==12,"selected identifier ABI");
static_assert(sizeof(STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR)==28,"selected alignment ABI");
static_assert(sizeof(PARTITION_INFORMATION_EX)==144 && offsetof(PARTITION_INFORMATION_EX,StartingOffset)==8 && offsetof(PARTITION_INFORMATION_EX,Mbr)==32,"selected partition ABI");
static_assert(offsetof(PARTITION_INFORMATION_GPT,Name)==40 && sizeof(PARTITION_INFORMATION_GPT)==112,"selected GPT union ABI");
static_assert(offsetof(DRIVE_LAYOUT_INFORMATION_EX,PartitionEntry)==48 && sizeof(DRIVE_LAYOUT_INFORMATION_EX)==192,"selected layout ABI");
void require(bool ok){if(!ok)throw std::invalid_argument("nt_identity_reply_shape");}
std::uint64_t load(const Bytes& b,std::size_t at,unsigned n){require(at<=b.size() && n<=b.size()-at);std::uint64_t out=0;for(unsigned i=0;i<n;++i)out|=static_cast<std::uint64_t>(b[at+i])<<(8*i);return out;}
V num(std::uint64_t n){return V::string(std::to_string(n));}
std::string hex(const Bytes& b,std::size_t at,std::size_t n){require(at<=b.size() && n<=b.size()-at);const char* h="0123456789abcdef";std::string out;out.reserve(n*2);for(std::size_t i=0;i<n;++i){out+=h[b[at+i]>>4];out+=h[b[at+i]&15];}return out;}
bool zero(const Bytes& b,std::size_t at,std::size_t n){require(at<=b.size() && n<=b.size()-at);for(std::size_t i=0;i<n;++i)if(b[at+i])return false;return true;}
bool growth(DWORD e){return e==ERROR_MORE_DATA || e==ERROR_INSUFFICIENT_BUFFER;}
const auto signed_max=(std::numeric_limits<std::uint64_t>::max)()>>1;
V claims(){return V::object().put("identity_scope",V::string("reported-evidence-only")).put("physical_identity",V::string("unknown"))
    .put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false)).put("capture_consistency",V::string("sequential-not-atomic"));}
}
V StorageQueryPort::identifiers(){
    begin(5);std::vector<Packet> packets;
    try{
        packets.push_back(call(IOCTL_STORAGE_QUERY_PROPERTY,8,true,StorageDeviceIdProperty));const auto& h=packets.back();
        if(h.state!="observed" && !(growth(h.error) && h.returned==8))return result("identifiers",h.state,packets);
        require(h.returned==8);const auto version=load(h.bytes,0,4),size=load(h.bytes,4,4);require(size>=16);
        if(version!=16)return result("identifiers","unsupported_version",packets);if(size>4096)return result("identifiers","budget_exhausted",packets);
        packets.push_back(call(IOCTL_STORAGE_QUERY_PROPERTY,static_cast<DWORD>(size),true,StorageDeviceIdProperty));const auto& b=packets.back();
        if(b.state!="observed")return result("identifiers",growth(b.error)?"changed":b.state,packets);
        require(b.returned>=16);if(load(b.bytes,0,4)!=version || load(b.bytes,4,4)!=size)return result("identifiers","changed",packets);require(b.returned>=size);
        const auto count=load(b.bytes,8,4);if(count>policy_.identifiers)return result("identifiers","budget_exhausted",packets);
        auto rows=V::array();std::size_t at=12;std::map<std::string,unsigned> duplicates;
        for(std::uint64_t i=0;i<count;++i){
            require(at<=size && size-at>=16);const auto code=load(b.bytes,at,4),type=load(b.bytes,at+4,4),length=load(b.bytes,at+8,2),next=load(b.bytes,at+10,2),association=load(b.bytes,at+12,4);
            require(length<=size-at-16);if(length>256)return result("identifiers","budget_exhausted",packets);
            const auto original=hex(b.bytes,at+16,static_cast<std::size_t>(length));auto row=V::object().put("ordinal",num(i+1)).put("code_set",num(code)).put("type",num(type)).put("association",num(association))
                .put("original_hex",V::string(original)).put("next_offset",num(next)).put("interpretation",V::string(code>=1 && code<=3 && type<=8 && association<=2?"reported":"unsupported-enumeration"));
            const auto key=std::to_string(code)+":"+std::to_string(type)+":"+std::to_string(association)+":"+original;++duplicates[key];row.put("comparison_key",V::string(key));rows.items.push_back(std::move(row));
            if(i+1<count){require(next>=16+length && next<=size-at && size-at-next>=16);at+=static_cast<std::size_t>(next);}else require(next==0);
        }
        for(auto& row:rows.items)row.put("duplicate_in_reply",V::boolean_value(duplicates[row.find("comparison_key")->text]>1));
        auto data=claims();data.put("version",num(version)).put("size_bytes",num(size)).put("identifiers",std::move(rows));return result("identifiers","observed",packets,std::move(data));
    }catch(const std::invalid_argument&){if(unresolved_)throw;return result("identifiers","malformed",packets);}
}
V StorageQueryPort::alignment(){
    begin(6);std::vector<Packet> packets;
    try{
        packets.push_back(call(IOCTL_STORAGE_QUERY_PROPERTY,28,true,StorageAccessAlignmentProperty));const auto& b=packets.back();if(b.state!="observed")return result("alignment",b.state,packets);require(b.returned>=28);
        const auto version=load(b.bytes,0,4),size=load(b.bytes,4,4);if(version!=28)return result("alignment","unsupported_version",packets);require(size==28);
        const auto cache=load(b.bytes,8,4),cache_offset=load(b.bytes,12,4),logical=load(b.bytes,16,4),physical=load(b.bytes,20,4),offset=load(b.bytes,24,4);
        require(logical && logical<=65536 && physical && physical<=1048576 && physical%logical==0 && offset<physical && offset%logical==0 && (cache?cache_offset<cache:cache_offset==0));
        auto data=claims();data.put("logical_sector_bytes",num(logical)).put("physical_sector_bytes",num(physical)).put("sector_alignment_offset_bytes",num(offset)).put("cache_line_bytes",num(cache)).put("cache_alignment_offset_bytes",num(cache_offset));
        return result("alignment","observed",packets,std::move(data));
    }catch(const std::invalid_argument&){if(unresolved_)throw;return result("alignment","malformed",packets);}
}
V StorageQueryPort::layout(){
    begin(7);std::vector<Packet> packets;
    try{
        DWORD bytes=192;
        for(;;){packets.push_back(call(IOCTL_DISK_GET_DRIVE_LAYOUT_EX,bytes));const auto& b=packets.back();
            if(b.state=="observed")break;
            if(b.state=="malformed" || b.state=="unresolved" || !growth(b.error))return result("layout",b.state,packets);
            if(bytes==12288)return result("layout","budget_exhausted",packets);bytes*=2;
        }
        const auto& b=packets.back();require(b.returned>=48);const auto style=load(b.bytes,0,4),count=load(b.bytes,4,4);
        if(style>2)return result("layout","unsupported_style",packets);if(count>policy_.partitions)return result("layout","budget_exhausted",packets);require(48+144*count<=b.returned);
        require(style==0?count%4==0:style==2?count==0:true);
        auto data=claims(),rows=V::array(),issues=V::array();data.put("partition_style",num(style)).put("partition_count",num(count)).put("raw_metadata_independently_verified",V::boolean_value(false));
        std::uint64_t usable_start=0,usable_end=0;std::map<std::string,unsigned> ids;std::map<std::uint64_t,unsigned> numbers;
        if(style==0)data.put("mbr_signature_raw",num(load(b.bytes,8,4)));
        if(style==1){usable_start=load(b.bytes,24,8);const auto length=load(b.bytes,32,8),max=load(b.bytes,40,4);require(usable_start<=signed_max && length<=signed_max-usable_start);usable_end=usable_start+length;
            data.put("gpt_disk_guid_hex",V::string(hex(b.bytes,8,16))).put("usable_start_bytes",num(usable_start)).put("usable_length_bytes",num(length)).put("max_partition_count",num(max));
            if(zero(b.bytes,8,16))issues.items.push_back(V::string("zero_disk_guid"));if(count>max)issues.items.push_back(V::string("count_exceeds_reported_max"));}
        for(std::uint64_t i=0;i<count;++i){
            const auto at=static_cast<std::size_t>(48+144*i);const auto entry_style=load(b.bytes,at,4),start=load(b.bytes,at+8,8),length=load(b.bytes,at+16,8),number=load(b.bytes,at+24,4);
            require(entry_style==style && start<=signed_max && length<=signed_max-start);const bool active=style==0?b.bytes[at+32]!=0:!zero(b.bytes,at+32,16);
            auto row=V::object().put("ordinal",num(i+1)).put("partition_number_hint",num(number)).put("offset_bytes",num(start)).put("length_bytes",num(length)).put("end_bytes",num(start+length))
                .put("active",V::boolean_value(active)).put("rewrite_flag_raw",num(b.bytes[at+28])).put("entry_hex",V::string(hex(b.bytes,at,144))).put("issues",V::array());
            if(active){++numbers[number];if(!length)row.fields["issues"].items.push_back(V::string("empty_active_range"));if(!number)row.fields["issues"].items.push_back(V::string("zero_partition_number"));}
            if(style==0)row.put("mbr_type",num(b.bytes[at+32])).put("boot_flag_raw",num(b.bytes[at+33])).put("recognized_flag_raw",num(b.bytes[at+34])).put("hidden_sectors",num(load(b.bytes,at+36,4)));
            else{
                const auto id=hex(b.bytes,at+48,16);row.put("gpt_type_guid_hex",V::string(hex(b.bytes,at+32,16))).put("gpt_partition_guid_hex",V::string(id)).put("gpt_attributes",num(load(b.bytes,at+64,8)));
                std::wstring name;for(unsigned j=0;j<36;++j)name+=static_cast<wchar_t>(load(b.bytes,at+72+j*2,2));row.put("gpt_name",lossless_name(name));
                if(active){++ids[id];if(zero(b.bytes,at+48,16))row.fields["issues"].items.push_back(V::string("zero_partition_guid"));if(start<usable_start || start+length>usable_end)row.fields["issues"].items.push_back(V::string("outside_reported_usable_range"));}
            }rows.items.push_back(std::move(row));
        }
        for(auto& row:rows.items){if(!row.find("active")->boolean)continue;auto& notes=row.fields["issues"].items;
            if(numbers[std::stoull(row.find("partition_number_hint")->text)]>1)notes.push_back(V::string("duplicate_partition_number"));
            if(style==1 && ids[row.find("gpt_partition_guid_hex")->text]>1)notes.push_back(V::string("duplicate_partition_guid"));
            for(const auto& other:rows.items){if(&row==&other || !other.find("active")->boolean)continue;
                const auto a=std::stoull(row.find("offset_bytes")->text),end=std::stoull(row.find("end_bytes")->text),c=std::stoull(other.find("offset_bytes")->text),d=std::stoull(other.find("end_bytes")->text);
                if(a<d && c<end){notes.push_back(V::string("reported_range_overlap"));break;}}
        }
        data.put("partitions",std::move(rows)).put("issues",std::move(issues));return result("layout","observed",packets,std::move(data));
    }catch(const std::invalid_argument&){if(unresolved_)throw;return result("layout","malformed",packets);}
}
}}
