// Private reference observer: one parent-bound read-only virtual-disk handle.
// No path selection, enumeration, attachment, repair or product/provider admission.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <virtdisk.h>
#include "runtime/command/json.h"
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using V = disked::json::Value;
namespace {
void require(bool value) { if (!value) throw std::runtime_error("reference invariant"); }
V number(unsigned long long value) { return V::number(std::to_string(value)); }
std::string hex(const unsigned char* data, std::size_t count) {
    const char* digits = "0123456789abcdef"; std::string result; result.reserve(count*2);
    for (std::size_t i=0;i<count;++i) { result+=digits[data[i]>>4]; result+=digits[data[i]&15]; }
    return result;
}
std::string guid(const GUID& value) {
    char text[37]{};
    const int count=std::snprintf(text,sizeof(text),"%08lx-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        static_cast<unsigned long>(value.Data1),value.Data2,value.Data3,value.Data4[0],value.Data4[1],
        value.Data4[2],value.Data4[3],value.Data4[4],value.Data4[5],value.Data4[6],value.Data4[7]);
    require(count==36); return text;
}
std::string text(const V& input,const char* key) {
    const V* value=input.find(key); require(value && value->kind==V::Kind::string); return value->text;
}
unsigned long long integer(const std::string& value) {
    require(disked::json::decimal_u64(value)); return std::stoull(value);
}
struct Query {
    DWORD control, error=0, returned=0; bool success=false;
    std::vector<unsigned char> bytes;
    Query(HANDLE handle,DWORD code,DWORD bound):control(code),bytes(bound) {
        SetLastError(ERROR_SUCCESS);
        success=DeviceIoControl(handle,code,nullptr,0,bytes.data(),bound,&returned,nullptr)!=FALSE;
        error=success?ERROR_SUCCESS:GetLastError();
        bytes.resize(std::min(returned,bound));
    }
    V record() const {
        V value=V::object();value.put("control",number(control));value.put("success",V::boolean_value(success));
        value.put("winerror",number(error));value.put("returned_bytes",number(returned));
        value.put("capture_truncated",V::boolean_value(returned>bytes.size()));
        value.put("raw_hex",V::string(hex(bytes.data(),bytes.size())));return value;
    }
};
template<class T> T decode(const Query& query) {
    require(query.success && query.bytes.size()>=sizeof(T));T result{};
    std::memcpy(&result,query.bytes.data(),sizeof(T));return result;
}
V abi() {
    V result=V::object();
    result.put("pointer_bytes",number(sizeof(void*)));
    result.put("create_v1_offset",number(offsetof(CREATE_VIRTUAL_DISK_PARAMETERS,Version1)));
    result.put("create_v1_bytes",number(sizeof(CREATE_VIRTUAL_DISK_PARAMETERS{}.Version1)));
    result.put("get_info_union_offset",number(offsetof(GET_VIRTUAL_DISK_INFO,Identifier)));
    result.put("layout_entries_offset",number(offsetof(DRIVE_LAYOUT_INFORMATION_EX,PartitionEntry)));
    result.put("partition_bytes",number(sizeof(PARTITION_INFORMATION_EX)));
    result.put("attach_flags",number(ATTACH_VIRTUAL_DISK_FLAG_READ_ONLY|ATTACH_VIRTUAL_DISK_FLAG_NO_DRIVE_LETTER));
    result.put("create_access",number(VIRTUAL_DISK_ACCESS_CREATE|VIRTUAL_DISK_ACCESS_GET_INFO));
    result.put("open_access",number(VIRTUAL_DISK_ACCESS_READ));
    result.put("create_flags",number(CREATE_VIRTUAL_DISK_FLAG_FULL_PHYSICAL_ALLOCATION));
    V controls=V::object();controls.put("length",number(IOCTL_DISK_GET_LENGTH_INFO));
    controls.put("geometry",number(IOCTL_DISK_GET_DRIVE_GEOMETRY_EX));
    controls.put("device",number(IOCTL_STORAGE_GET_DEVICE_NUMBER));controls.put("layout",number(IOCTL_DISK_GET_DRIVE_LAYOUT_EX));
    result.put("query_controls",std::move(controls));return result;
}
V observe(const V& input) {
    require(input.kind==V::Kind::object && input.fields.size()==4);
    const auto raw=integer(text(input,"handle"));
    require(raw!=0 && raw<=std::numeric_limits<std::uintptr_t>::max() && raw!=std::numeric_limits<std::uintptr_t>::max());
    require(integer(text(input,"expected_bytes"))==4194304);
    const std::string id=text(input,"attachment_uuid"), nonce=text(input,"nonce");
    require(id.size()==36 && nonce.size()==32);
    HANDLE handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(raw));DWORD flags=0;
    require(GetHandleInformation(handle,&flags)!=FALSE && !(flags&HANDLE_FLAG_INHERIT));
    V result=V::object();result.put("attachment_uuid",V::string(id));result.put("nonce",V::string(nonce));
    result.put("handle_inheritable",V::boolean_value(false));
    // A real one-byte negative control against the owned disposable read-only
    // capability. Any unexpected write is retained as failure, never concealed.
    const unsigned char byte=0x55;DWORD written=0;SetLastError(ERROR_SUCCESS);
    const BOOL wrote=WriteFile(handle,&byte,1,&written,nullptr);const DWORD write_error=wrote?0:GetLastError();
    result.put("write_denied",V::boolean_value(!wrote && written==0 && (write_error==ERROR_ACCESS_DENIED || write_error==ERROR_WRITE_PROTECT)));
    result.put("write_success",V::boolean_value(wrote!=FALSE));result.put("write_bytes",number(written));
    result.put("write_winerror",number(write_error));
    Query length(handle,IOCTL_DISK_GET_LENGTH_INFO,sizeof(GET_LENGTH_INFORMATION));
    Query geometry(handle,IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,4096);
    Query device(handle,IOCTL_STORAGE_GET_DEVICE_NUMBER,sizeof(STORAGE_DEVICE_NUMBER));
    Query layout(handle,IOCTL_DISK_GET_DRIVE_LAYOUT_EX,65536);
    V queries=V::object();queries.put("length",length.record());queries.put("geometry",geometry.record());
    queries.put("device",device.record());queries.put("layout",layout.record());result.put("queries",std::move(queries));
    try {
    if (length.success) {const auto value=decode<GET_LENGTH_INFORMATION>(length);result.put("disk_bytes",V::string(std::to_string(value.Length.QuadPart)));}
    if (device.success) {
        const auto value=decode<STORAGE_DEVICE_NUMBER>(device);result.put("device_type",number(value.DeviceType));
        result.put("device_number",number(value.DeviceNumber));result.put("partition_number",number(value.PartitionNumber));
    }
    if (geometry.success) {
        require(geometry.bytes.size()>=offsetof(DISK_GEOMETRY_EX,Data));DISK_GEOMETRY_EX value{};
        std::memcpy(&value,geometry.bytes.data(),offsetof(DISK_GEOMETRY_EX,Data));
        result.put("sector_bytes",number(value.Geometry.BytesPerSector));
        result.put("geometry_disk_bytes",V::string(std::to_string(value.DiskSize.QuadPart)));
    }
    if (layout.success) {
        const auto offset=offsetof(DRIVE_LAYOUT_INFORMATION_EX,PartitionEntry);
        require(layout.bytes.size()>=offset);DRIVE_LAYOUT_INFORMATION_EX value{};
        std::memcpy(&value,layout.bytes.data(),offset);
        require(value.PartitionCount<=128 && layout.bytes.size()>=offset+value.PartitionCount*sizeof(PARTITION_INFORMATION_EX));
        result.put("style",number(value.PartitionStyle));result.put("partition_count",number(value.PartitionCount));
        if(value.PartitionStyle==PARTITION_STYLE_GPT)result.put("disk_guid",V::string(guid(value.Gpt.DiskId)));
        if(value.PartitionStyle==PARTITION_STYLE_MBR)result.put("disk_signature",number(value.Mbr.Signature));
        V rows=V::array();
        for (DWORD i=0;i<value.PartitionCount;++i) {
            PARTITION_INFORMATION_EX part{};std::memcpy(&part,layout.bytes.data()+offset+i*sizeof(part),sizeof(part));
            V row=V::object();row.put("index",number(i));row.put("style",number(part.PartitionStyle));
            row.put("number",number(part.PartitionNumber));row.put("offset_bytes",V::string(std::to_string(part.StartingOffset.QuadPart)));
            row.put("length_bytes",V::string(std::to_string(part.PartitionLength.QuadPart)));
            row.put("rewrite_partition",V::boolean_value(part.RewritePartition!=FALSE));
            if(part.PartitionStyle==PARTITION_STYLE_MBR) {
                row.put("type",number(part.Mbr.PartitionType));row.put("boot_indicator",V::boolean_value(part.Mbr.BootIndicator!=FALSE));
                row.put("recognized",V::boolean_value(part.Mbr.RecognizedPartition!=FALSE));row.put("hidden_sectors",number(part.Mbr.HiddenSectors));
            } else if(part.PartitionStyle==PARTITION_STYLE_GPT) {
                row.put("type_guid",V::string(guid(part.Gpt.PartitionType)));row.put("unique_guid",V::string(guid(part.Gpt.PartitionId)));
                row.put("attributes",V::string(std::to_string(part.Gpt.Attributes)));
                static_assert(sizeof(wchar_t)==2,"Windows UTF-16 required");
                row.put("name_utf16le_hex",V::string(hex(reinterpret_cast<const unsigned char*>(part.Gpt.Name),sizeof(part.Gpt.Name))));
            }
            rows.items.push_back(std::move(row));
        }
        result.put("partitions",std::move(rows));
    }
    } catch(const std::exception&) {result.put("decode_error",V::string("contradictory or unsupported raw layout"));}
    require(CloseHandle(handle)!=FALSE);return result;
}
}

int main(int argc,char** argv) {
    try {
        V result;
        if(argc==2 && std::string(argv[1])=="--abi")result=abi();
        else {
            require(argc==1);std::string input;char byte;
            while(std::cin.get(byte)){require(input.size()<32768);input+=byte;}
            result=observe(disked::json::parse(input));
        }
        disked::json::Limits limits;limits.bytes=524288;limits.string_bytes=262144;limits.values=16384;
        std::cout<<disked::json::dump(result,limits)<<'\n';return 0;
    } catch(const std::exception&) {std::cerr<<"Invalid or contradictory private reference observation\n";return 2;}
}
