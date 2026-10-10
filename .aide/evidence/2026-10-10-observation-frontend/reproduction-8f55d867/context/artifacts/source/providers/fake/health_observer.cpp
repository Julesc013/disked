#include "health_observer.h"
#include "health.h"
#include "snapshot.h"

namespace disked {
namespace {
using json::Value;
struct Fixture {const char* id;const char* identity;const char* kind;int temperature,errors;};
const Fixture fixtures[]={
    {"fake:alpha@1","fixture:controller-A:lun0","block-device",35,0},
    {"fake:clone@1","fixture:controller-B:lun0","block-device",42,3},
    {"fake:denied@1","fixture:controller-A:lun1","block-device",0,0},
    {"fake:stale@1","fixture:controller-A:lun2","block-device",0,0},
    {"fake:unknown@1","fixture:controller-A:lun3","block-device",0,0},
    {"fake:table@1","fixture:table-A","gpt",0,0},
    {"fake:volume@1","fixture:volume-A","volume",0,0}
};
std::string hex(const std::string& bytes) {
    const char* digits="0123456789abcdef";std::string out;out.reserve(bytes.size()*2);
    for(unsigned char byte:bytes) {out+=digits[byte>>4];out+=digits[byte&15];}return out;
}
Value field(const char* id,const std::string& raw,const std::string& text,const char* rule) {
    const bool raw_ok=raw.size()<=1024,text_ok=text.size()<=256;
    return Value::object().put("id",Value::string(id))
        .put("raw",Value::object().put("availability",Value::string(raw_ok?"available":"error")).put("hex",raw_ok?Value::string(hex(raw)):Value{}))
        .put("interpretation",Value::object().put("availability",Value::string(text_ok?"available":"error"))
            .put("text",text_ok?Value::string(text):Value{}).put("rule_id",text_ok?Value::string(rule):Value{}));
}
}
Outcome fake_health_observation(const std::string& request,const Value& node,const std::string& revision,const Value& policy) {
    const auto& id=node.find("id")->text;const auto& p=*node.find("properties");const Fixture* fixture=nullptr;
    for(const auto& f:fixtures)if(id==f.id)fixture=&f;
    // Graph target IDs alone cannot substitute for the declared fixture identity.
    if(!fixture || p.find("identity")->text!=fixture->identity || p.find("media_generation")->text!="1" || node.find("kind")->text!=fixture->kind)
        return refused(request,"health_observer_unavailable",3);
    const auto& state=p.find("state")->text;
    if(state=="stale")return refused(request,"health_observation_stale");
    if(state=="denied")return refused(request,"health_observation_denied",3);
    try {
        Value binding=Value::object().put("id",Value::string(id)).put("identity",*p.find("identity")).put("generation",*p.find("media_generation"));
        const auto target=Value::object().put("id",Value::string(id)).put("generation",*p.find("media_generation"))
            .put("identity_digest",Value::string(digest_sha256(json::dump(binding))));
        const auto provider=Value::string(digest_sha256("provider.fake.health.fixture/1"));
        const bool observe=node.find("kind")->text=="block-device";
        Value fields=Value::array();
        for(const auto& item:std::vector<std::pair<const char*,const char*>>{{"temperature","public"},{"media_errors","public"},{"serial","identifier"},{"label","customer"},{"debug","secret"}})
            fields.items.push_back(Value::object().put("id",Value::string(item.first)).put("sensitivity",Value::string(item.second)));
        Value source=Value::object().put("id",Value::string("fake:health.fixture@1")).put("provider_digest",provider)
            .put("capability",Value::string(observe?"observe":"unavailable")).put("fields",fields);
        Value sources=Value::array();sources.items.push_back(source);
        health::proposal::Capture capture(Value::object().put("target",target).put("sources",sources));
        if(observe) {
            const auto ticket=capture.start("fake:health.fixture@1");Value observed=Value::array();
            // Unknown captures never replace absent values with fixture zeros.
            const bool known=state=="current" && (id=="fake:alpha@1" || id=="fake:clone@1");
            if(known) {
                observed.items.push_back(field("temperature",std::string(1,static_cast<char>(fixture->temperature)),std::to_string(fixture->temperature)+" Celsius","fixture.celsius@1"));
                observed.items.push_back(field("media_errors",std::string(1,static_cast<char>(fixture->errors)),std::to_string(fixture->errors)+" media errors","fixture.count@1"));
                observed.items.push_back(field("serial","CLONED","CLONED","fixture.utf8@1"));
                observed.items.push_back(field("label",p.find("label")->text,p.find("label")->text,"fixture.utf8@1"));
                observed.items.push_back(field("debug","fixture-secret-do-not-export","fixture-secret-do-not-export","fixture.utf8@1"));
            }
            const auto response=Value::object().put("ticket",health::proposal::ticket_value(ticket)).put("target",target).put("provider_digest",provider)
                .put("outcome",Value::string(known?"complete":"partial")).put("fields",observed);
            if(!capture.finish(ticket,response))return refused(request,"health_observation_invalid",4);
            // The lookup has already returned; no asynchronous worker exists.
            if(!capture.retire(ticket))return refused(request,"health_observation_invalid",4);
        }
        return completed(request,Value::object().put("schema",Value::string("org.disked.fake-health-result/1"))
            .put("scope",Value::string("fake-only")).put("target_id",Value::string(id)).put("basis_revision",Value::string(revision))
            .put("observation_kind",Value::string("compiled-fixture")).put("observed_at",Value{}).put("support_report",capture.support(policy)));
    } catch(const health::proposal::Error&) {return refused(request,"health_observation_invalid",4);}
}
}
