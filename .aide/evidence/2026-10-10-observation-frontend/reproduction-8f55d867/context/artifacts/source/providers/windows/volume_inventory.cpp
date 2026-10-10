#include "volume_inventory.h"
#include <algorithm>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
std::wstring folded(std::wstring value) {for(auto& c:value)if(c>=L'A' && c<=L'Z')c=static_cast<wchar_t>(c-L'A'+L'a');return value;}
bool volume_name(const std::wstring& name) {
    if(name.size()!=49 || folded(name).substr(0,11)!=L"\\\\?\\volume{" || name.substr(47)!=L"}\\")return false;
    for(std::size_t at=11;at<47;++at) {
        const auto c=name[at];if(at==19 || at==24 || at==29 || at==34) {if(c!=L'-')return false;}
        else if(!((c>=L'0' && c<=L'9') || (c>=L'a' && c<=L'f') || (c>=L'A' && c<=L'F')))return false;
    }return true;
}
V claims() {return V::object().put("physical_identity",V::string("unknown")).put("full_topology",V::string("not_observed"))
    .put("media_preservation",V::string("not_established")).put("physical_admission",V::boolean_value(false))
    .put("mutation_authority",V::boolean_value(false)).put("complete_alias_proof",V::boolean_value(false));}
std::string lookup(std::string hex) {
    const char* digits="0123456789abcdef";
    for(std::size_t at=0;at<hex.size();at+=4)if(hex[at+2]=='0' && hex[at+3]=='0') {
        auto nibble=[](char c) {return c>='a'?c-'a'+10:c-'0';};
        const unsigned n=static_cast<unsigned>((nibble(hex[at])<<4)|nibble(hex[at+1]));
        if(n>=65 && n<=90) {const unsigned lower=n+32;hex[at]=digits[lower>>4];hex[at+1]=digits[lower&15];}
    }return hex;
}
}
json::Limits volume_inventory_limits() {json::Limits l;l.bytes=262144;l.values=16384;l.depth=24;return l;}
V lossless_name(const std::wstring& name) {
    if(name.size()>256)throw std::invalid_argument("nt_volume_name_limit");
    const char* digits="0123456789abcdef";std::string original,display;
    for(wchar_t unit:name) {
        const auto n=static_cast<unsigned>(unit);original+=digits[(n>>4)&15];original+=digits[n&15];original+=digits[(n>>12)&15];original+=digits[(n>>8)&15];
        if(n>=0x20 && n<=0x7e)display+=static_cast<char>(n);
        else {display+="\\u";for(int shift=12;shift>=0;shift-=4)display+=digits[(n>>shift)&15];}
    }
    return V::object().put("original_encoding",V::string("utf16le-code-units")).put("original_hex",V::string(original))
        .put("display_encoding",V::string("ascii-with-utf16-unit-escapes")).put("display",V::string(display));
}
V collect_volume_namespace(VolumeCursor& cursor,std::uint64_t epoch,const InventoryPolicy& p,const std::function<bool()>& stop) {
    if(!epoch || !p.volumes || p.volumes>64 || !p.mounts || p.mounts>64 || !p.mount_units || p.mount_units>8192)throw std::invalid_argument("nt_volume_policy");
    V records=V::array();std::string state="not_started";DWORD error=0;std::size_t mounts=0,units=0;bool complete=false,partial=false;
    try {
        if(stop && stop())state="cancelled";
        else {
            auto name=cursor.first();
            for(;;) {
                error=name.error;
                if(name.state!="present") {state=name.state;complete=state=="exhausted";break;}
                auto row=V::object().put("observation_id",V::string("nt-volume-observation:"+std::to_string(epoch)+":"+std::to_string(records.items.size()+1)))
                    .put("volume_path",lossless_name(name.name)).put("state",V::string("present"))
                    .put("conflicts",V::object().put("duplicate_volume_name",V::boolean_value(false)).put("duplicate_mount_alias",V::boolean_value(false)));
                auto paths=V::array();std::string mount_state="not_selected";DWORD mount_error=0;
                if(!volume_name(name.name)) {row.put("state",V::string("malformed"));mount_state="not_queried";partial=true;}
                else if(p.include_mounts) {
                    if(stop && stop()) {mount_state="cancelled";partial=true;}
                    else if(mounts==p.mounts || units==p.mount_units) {mount_state="budget_exhausted";partial=true;}
                    else {
                        try {
                            const auto observed=cursor.mounts(std::min<std::size_t>(4096,p.mount_units-units),std::min<std::size_t>(32,p.mounts-mounts));
                            mount_state=observed.state;mount_error=observed.error;
                            if(mount_state=="observed") {for(const auto& path:observed.paths)paths.items.push_back(lossless_name(path));mounts+=observed.paths.size();units+=observed.units;}
                            else partial=true;
                        }catch(const std::exception&) {mount_state="adapter_exception";partial=true;}
                    }
                }
                row.put("mounts",V::object().put("state",V::string(mount_state)).put("platform_code",V::string(std::to_string(mount_error))).put("paths",paths));
                records.items.push_back(std::move(row));
                if(mount_state=="adapter_exception") {state="adapter_exception";break;}
                if(stop && stop()) {state="cancelled";break;}
                if(records.items.size()==p.volumes) {state="budget_exhausted";break;}
                name=cursor.next();
            }
        }
    }catch(const std::exception&) {state="adapter_exception";complete=false;partial=true;}
    const auto close=cursor.close();if(close.state=="uncertain")partial=true;
    // No merging. Even observed alias/name equality cannot establish media ID.
    for(std::size_t i=0;i<records.items.size();++i)for(std::size_t j=0;j<i;++j) {
        auto& a=records.items[i];auto& b=records.items[j];
        if(lookup(a.fields["volume_path"].fields["original_hex"].text)==lookup(b.fields["volume_path"].fields["original_hex"].text)) {
            partial=true;a.fields["conflicts"].put("duplicate_volume_name",V::boolean_value(true));b.fields["conflicts"].put("duplicate_volume_name",V::boolean_value(true));
        }
        const auto& aa=a.fields["mounts"].fields["paths"].items;const auto& bb=b.fields["mounts"].fields["paths"].items;
        for(const auto& first:aa)for(const auto& second:bb)if(lookup(first.fields.at("original_hex").text)==lookup(second.fields.at("original_hex").text)) {
            partial=true;a.fields["conflicts"].put("duplicate_mount_alias",V::boolean_value(true));b.fields["conflicts"].put("duplicate_mount_alias",V::boolean_value(true));
        }
    }
    for(auto& row:records.items) {const auto& paths=row.fields["mounts"].fields["paths"].items;
        for(std::size_t i=0;i<paths.size();++i)for(std::size_t j=0;j<i;++j)if(lookup(paths[i].fields.at("original_hex").text)==lookup(paths[j].fields.at("original_hex").text)) {
            partial=true;row.fields["conflicts"].put("duplicate_mount_alias",V::boolean_value(true));
        }
    }
    const auto status=complete && !partial?"complete":state=="cancelled"?"cancelled":records.items.empty() && (state=="denied" || state=="unavailable")?state.c_str():"partial";
    auto value=V::object().put("schema",V::string("org.disked.nt-volume-namespace-prototype/1")).put("provider",V::string("windows.volume-namespace.prototype"))
        .put("capture_epoch",V::string(std::to_string(epoch))).put("status",V::string(status)).put("scope",V::string("volume-namespace-only"))
        .put("api_binding",V::string(cursor.native_binding()?"native-win32-table":"injected-win32-table"))
        .put("policy",V::object().put("volumes",V::string(std::to_string(p.volumes))).put("mounts",V::string(std::to_string(p.mounts))).put("mount_units",V::string(std::to_string(p.mount_units))).put("include_mounts",V::boolean_value(p.include_mounts)))
        .put("enumeration",V::object().put("state",V::string(state)).put("platform_code",V::string(std::to_string(error))).put("exhausted",V::boolean_value(complete)))
        .put("close",V::object().put("state",V::string(close.state)).put("platform_code",V::string(std::to_string(close.error))))
        .put("records",records).put("claims",claims());
    json::dump(value,volume_inventory_limits());return value;
}
}}
