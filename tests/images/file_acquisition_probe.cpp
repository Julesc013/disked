#include "file_acquisition.h"
#include <cstdio>

namespace {
using V=disked::json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw disked::FileAcquisitionError("acquisition_probe_input");return *p;}
std::string text(const V& v) {if(v.kind!=V::Kind::string)throw disked::FileAcquisitionError("acquisition_probe_input");return v.text;}
std::uint32_t number(const V& v) {
    const auto s=text(v);if(!disked::json::decimal_u64(s) || std::stoull(s)>0xffffffffULL)throw disked::FileAcquisitionError("acquisition_probe_input");return static_cast<std::uint32_t>(std::stoull(s));
}
}
int main() {
    try {
        std::string input;char block[4096];for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>65536)return 2;if(n<sizeof(block))break;}
        const auto value=disked::json::parse(input);if(value.kind!=V::Kind::object)throw disked::FileAcquisitionError("acquisition_probe_input");
        for(const auto& f:value.fields)if(f.first!="source" && f.first!="destination" && f.first!="map" && f.first!="mode" && f.first!="options" && f.first!="grant")throw disked::FileAcquisitionError("acquisition_probe_input");
        const auto mode=text(field(value,"mode"));if(mode!="prepare" && mode!="start" && mode!="resume")throw disked::FileAcquisitionError("acquisition_probe_input");
        disked::FileAcquisitionRequest r;r.source=text(field(value,"source"));r.destination=text(field(value,"destination"));r.map=text(field(value,"map"));r.resume=mode=="resume";
        if(const auto options=value.find("options")) {
            if(options->kind!=V::Kind::object || options->fields.size()!=4)throw disked::FileAcquisitionError("acquisition_probe_input");r.explicit_options=true;
            r.chunk_bytes=number(field(*options,"chunk_bytes"));r.retries=number(field(*options,"retry_limit"));r.read_policy=text(field(*options,"read_policy"));r.substitution=text(field(*options,"substitution"));
        }
        disked::FileAcquisition session(r);auto result=V::object().put("plan",session.plan().definition).put("plan_digest",V::string(session.plan().digest));
        if(mode!="prepare") {
            disked::acquisition::Grant grant{session.plan().digest,true,true,true,true};
            if(const auto g=value.find("grant")) {
                if(g->kind!=V::Kind::object || g->fields.size()!=5)throw disked::FileAcquisitionError("acquisition_probe_input");grant.plan_digest=text(field(*g,"plan_digest"));
                // Probe-only convenience binds explicit flag tests to this preparation.
                if(grant.plan_digest=="$prepared")grant.plan_digest=session.plan().digest;
                for(const char* name:{"source_read","destination_write","map_write","host_effects"})if(field(*g,name).kind!=V::Kind::boolean)throw disked::FileAcquisitionError("acquisition_probe_input");
                grant.source_read=field(*g,"source_read").boolean;grant.destination_write=field(*g,"destination_write").boolean;grant.map_write=field(*g,"map_write").boolean;grant.host_effects=field(*g,"host_effects").boolean;
            }
            const auto outcome=session.execute(grant);result.put("outcome",outcome.outcome.report()).put("receipt",outcome.receipt);
        }
        std::puts(disked::json::dump(result).c_str());return 0;
    } catch(const disked::FileAcquisitionError& e) {
        const auto result=V::object().put("refusal",V::string(e.what())).put("platform_code",V::string(std::to_string(e.platform_code)));std::puts(disked::json::dump(result).c_str());return 3;
    } catch(const std::exception& e) {
        std::puts(disked::json::dump(V::object().put("refusal",V::string(e.what()))).c_str());return 3;
    }
}
