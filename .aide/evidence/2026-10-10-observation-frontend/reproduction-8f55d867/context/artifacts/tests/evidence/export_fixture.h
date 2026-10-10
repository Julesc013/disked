#pragma once
#include "report_export.h"
namespace export_fixture {
using V=disked::json::Value;namespace e=disked::evidence::proposal;namespace h=disked::health::proposal;
inline const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("export_probe_input");return *p;}
inline std::string text(const V& v) {if(v.kind!=V::Kind::string)throw e::Error("export_probe_input");return v.text;}
inline V default_policy() {return V::object().put("identifiers",V::boolean_value(false)).put("raw_values",V::boolean_value(false)).put("interpretations",V::boolean_value(false)).put("customer_data",V::boolean_value(false));}
inline bool flag(const V& v,const char* key) {const auto p=v.find(key);if(!p)return false;if(p->kind!=V::Kind::boolean)throw e::Error("export_probe_input");return p->boolean;}
inline e::Case make_case(bool large,bool controls) {
    const auto target=V::object().put("id",V::string("fake:report@1")).put("generation",V::string("1")).put("identity_digest",V::string(e::export_digest("fixture-target")));
    V sources=V::array();const unsigned source_count=large?8:1,field_count=large?16:4;
    for(unsigned i=0;i<source_count;++i) {
        V fields=V::array();for(unsigned j=0;j<field_count;++j)fields.items.push_back(V::object().put("id",V::string("field"+std::to_string(j)))
            .put("sensitivity",V::string(large || !j?"public":j==1?"identifier":j==2?"customer":"secret")));
        sources.items.push_back(V::object().put("id",V::string("fake:source"+std::to_string(i))).put("provider_digest",V::string(e::export_digest("fixture-provider")))
            .put("capability",V::string("observe")).put("fields",fields));
    }
    h::Capture capture(V::object().put("target",target).put("sources",sources));
    for(unsigned i=0;i<source_count;++i) {
        const auto id="fake:source"+std::to_string(i);const auto ticket=capture.start(id);V fields=V::array();
        for(unsigned j=0;j<field_count;++j) {
            const std::string value=large?std::string(256,'\0'):!j?(controls?"35\n\t\x1b[31m\xe2\x80\xae":"35 Celsius"):j==1?"OWNED-SERIAL":j==2?"OWNED-CUSTOMER":"OWNED-SECRET";
            const auto raw=large?(j<3?std::string(2048,'0'):std::string("00")):std::string(j==0?"23":j==1?"53455249414c":j==2?"435553544f4d4552":"534543524554");
            fields.items.push_back(V::object().put("id",V::string("field"+std::to_string(j))).put("raw",V::object().put("availability",V::string("available")).put("hex",V::string(raw)))
                .put("interpretation",V::object().put("availability",V::string("available")).put("text",V::string(value)).put("rule_id",V::string("fixture.report@1"))));
        }
        const auto reply=V::object().put("ticket",h::ticket_value(ticket)).put("target",target).put("provider_digest",V::string(e::export_digest("fixture-provider")))
            .put("outcome",V::string("complete")).put("fields",fields);
        if(!capture.finish(ticket,reply) || !capture.retire(ticket))throw e::Error("export_fixture_invalid");
    }
    auto code=V::object().put("source_revision",V::string(std::string(40,'b'))).put("input_digest",V::string(e::export_digest("fixture-code-input")))
        .put("configuration_digest",V::string(e::export_digest("fixture-configuration")));
    e::Case report("case:export-fixture@1",code);report.append("before","compiled-fixture",e::export_digest("fixture-before"),capture);
    report.append("after","compiled-fixture",e::export_digest("fixture-after"),capture);return report;
}
inline e::ExportGrant grant(const V& input,const std::string& prepared) {
    const auto& v=field(input,"grant");if(v.kind!=V::Kind::object || v.fields.size()!=3 || field(v,"report_write").kind!=V::Kind::boolean || field(v,"host_effects").kind!=V::Kind::boolean)throw e::Error("export_probe_input");
    auto digest=text(field(v,"definition_digest"));if(digest=="$prepared")digest=prepared;
    return {digest,field(v,"report_write").boolean,field(v,"host_effects").boolean};
}
inline V preview(const e::SupportArtifact& artifact) {auto bytes=artifact.bytes();bytes.pop_back();return disked::json::parse(bytes,e::case_limits());}
}
