#include "health.h"
#include <algorithm>
#include <initializer_list>
#include <limits>
#include <set>
#include <utility>

namespace disked { namespace health { namespace proposal {
using V=json::Value;
namespace {
void shape(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())throw Error("health_shape");
    for(const auto n:names)if(!v.find(n))throw Error("health_shape");
}
const V& get(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw Error("health_shape");return *p;}
std::string text(const V& v) {if(v.kind!=V::Kind::string || v.text.size()>256 || !json::valid_utf8(v.text))throw Error("health_text");return v.text;}
std::string id(const V& v) {
    const auto s=text(v);if(s.empty() || s.size()>128 || s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_.@-")!=s.npos)throw Error("health_id");return s;
}
std::uint64_t integer(const V& v,bool zero=false) {
    if(v.kind!=V::Kind::string || !json::decimal_u64(v.text) || (!zero && v.text=="0"))throw Error("health_integer");return std::stoull(v.text);
}
std::string digest(const V& v) {
    const auto s=text(v);if(s.size()!=71 || s.substr(0,7)!="sha256:" || s.find_first_not_of("0123456789abcdef",7)!=s.npos)throw Error("health_digest");return s;
}
std::string choice(const V& v,std::initializer_list<const char*> allowed) {const auto s=text(v);for(const auto a:allowed)if(s==a)return s;throw Error("health_enum");}
bool flag(const V& v) {if(v.kind!=V::Kind::boolean)throw Error("health_policy");return v.boolean;}
void array(const V& v,std::size_t maximum,bool empty=false) {if(v.kind!=V::Kind::array || v.items.size()>maximum || (!empty && v.items.empty()))throw Error("health_count");}
void input_budget(const V& v) {
    json::Limits limits;limits.bytes=65536;limits.depth=16;limits.values=16384;limits.string_bytes=8192;
    try {json::dump(v,limits);}catch(const json::Error&) {throw Error("health_input_limit");}
}
void target(const V& v) {shape(v,{"id","generation","identity_digest"});id(get(v,"id"));integer(get(v,"generation"));digest(get(v,"identity_digest"));}
V raw_unknown() {return V::object().put("availability",V::string("unknown")).put("hex",V{});}
V interpretation_unknown() {return V::object().put("availability",V::string("unknown")).put("text",V{}).put("rule_id",V{});}
V unknown_field(const V& declaration) {
    return V::object().put("id",get(declaration,"id")).put("sensitivity",get(declaration,"sensitivity"))
        .put("received",V::boolean_value(false)).put("raw",raw_unknown()).put("interpretation",interpretation_unknown());
}
std::size_t raw(const V& v) {
    shape(v,{"availability","hex"});const auto a=choice(get(v,"availability"),{"available","unavailable","denied","error","unknown"});const auto& h=get(v,"hex");
    if(a!="available") {if(h.kind!=V::Kind::null)throw Error("health_unavailable_value");return 0;}
    if(h.kind!=V::Kind::string || h.text.size()>2048 || h.text.size()%2 || h.text.find_first_not_of("0123456789abcdef")!=h.text.npos)throw Error("health_raw");return h.text.size()/2;
}
void interpretation(const V& v) {
    shape(v,{"availability","text","rule_id"});const auto a=choice(get(v,"availability"),{"available","unavailable","denied","error","unknown"});
    if(a=="available") {if(text(get(v,"text")).empty())throw Error("health_text");id(get(v,"rule_id"));}
    else if(get(v,"text").kind!=V::Kind::null || get(v,"rule_id").kind!=V::Kind::null)throw Error("health_unavailable_value");
}
bool equal(const V& a,const V& b) {return json::dump(a)==json::dump(b);}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
V claims() {return V::object().put("reliability",V::string("not_established")).put("mutation_authority",V::boolean_value(false)).put("physical_admission",V::boolean_value(false));}
V projection(V value) {
    json::Limits limits;limits.bytes=1048576;limits.depth=16;limits.values=16384;limits.string_bytes=8192;
    try {json::dump(value,limits);}catch(const json::Error&) {throw Error("health_projection_limit");}return value;
}
}
V ticket_value(const Ticket& key) {return V::object().put("source",V::string(key.source)).put("capture",number(key.capture)).put("worker",number(key.worker));}
Ticket read_ticket(const V& v) {shape(v,{"source","capture","worker"});return {id(get(v,"source")),integer(get(v,"capture")),integer(get(v,"worker"))};}
Capture::Capture(const V& request,std::uint64_t epoch,std::uint64_t seed):capture_(epoch) {
    input_budget(request);shape(request,{"target","sources"});target(get(request,"target"));target_=get(request,"target");
    if(!epoch)throw Error("health_integer");const auto& sources=get(request,"sources");array(sources,8);std::set<std::string> names;std::size_t fields=0;
    for(const auto& source:sources.items) {
        shape(source,{"id","provider_digest","capability","fields"});if(!names.insert(id(get(source,"id"))).second)throw Error("health_duplicate_source");
        digest(get(source,"provider_digest"));choice(get(source,"capability"),{"observe","unavailable"});const auto& requested=get(source,"fields");array(requested,32);fields+=requested.items.size();
        if(fields>128)throw Error("health_count");std::set<std::string> ids;
        for(const auto& f:requested.items) {shape(f,{"id","sensitivity"});if(!ids.insert(id(get(f,"id"))).second)throw Error("health_duplicate_field");choice(get(f,"sensitivity"),{"public","identifier","customer","secret"});}
        Slot s;s.declaration=source;s.worker=seed;reset(s);slots_.push_back(std::move(s));
    }
}
void Capture::reset(Slot& s) {
    s.state=get(s.declaration,"capability").text=="observe"?"not_started":"unavailable";s.diagnostic=s.state=="unavailable"?"observer_unavailable":"";
    s.started=s.open=s.live=false;s.fields=V::array();for(const auto& f:get(s.declaration,"fields").items)s.fields.items.push_back(unknown_field(f));
}
std::size_t Capture::slot(const std::string& source) const {for(std::size_t i=0;i<slots_.size();++i)if(get(slots_[i].declaration,"id").text==source)return i;throw Error("health_source_unknown");}
bool Capture::matches(const Slot& s,const Ticket& key) const {return key.capture==capture_ && key.worker==s.worker && s.started && get(s.declaration,"id").text==key.source;}
Ticket Capture::start(const std::string& source) {
    auto& s=slots_[slot(source)];if(cancelled_)throw Error("health_cancelled");if(get(s.declaration,"capability").text!="observe")throw Error("health_observer_unavailable");
    if(s.started)throw Error("health_already_started");if(s.worker==(std::numeric_limits<std::uint64_t>::max)())throw Error("health_counter_exhausted");
    ++s.worker;s.started=s.open=s.live=true;s.state="pending";return {source,capture_,s.worker};
}
bool Capture::finish(const Ticket& key,const V& response) {
    auto& s=slots_[slot(key.source)];if(!matches(s,key) || !s.open)throw Error("health_stale_result");
    try {
        input_budget(response);shape(response,{"ticket","target","provider_digest","outcome","fields"});
        if(!equal(ticket_value(key),get(response,"ticket")))throw Error("health_ticket_mismatch");target(get(response,"target"));
        if(!equal(target_,get(response,"target")))throw Error("health_target_mismatch");digest(get(response,"provider_digest"));
        if(!equal(get(s.declaration,"provider_digest"),get(response,"provider_digest")))throw Error("health_provider_mismatch");
        const auto outcome=choice(get(response,"outcome"),{"complete","partial","unavailable","denied","error"});const auto& fields=get(response,"fields");array(fields,32,true);
        if(outcome!="complete" && outcome!="partial" && !fields.items.empty())throw Error("health_outcome_fields");
        V accepted=s.fields;std::set<std::string> ids;std::size_t bytes=0;
        for(const auto& f:fields.items) {
            shape(f,{"id","raw","interpretation"});const auto name=id(get(f,"id"));if(!ids.insert(name).second)throw Error("health_duplicate_field");
            auto p=std::find_if(accepted.items.begin(),accepted.items.end(),[&](const V& x){return get(x,"id").text==name;});if(p==accepted.items.end())throw Error("health_unrequested_field");
            bytes+=raw(get(f,"raw"));if(bytes>4096)throw Error("health_raw_total");interpretation(get(f,"interpretation"));
            p->put("received",V::boolean_value(true)).put("raw",get(f,"raw")).put("interpretation",get(f,"interpretation"));
        }
        if(outcome=="complete" && ids.size()!=accepted.items.size())throw Error("health_incomplete_result");
        s.fields=std::move(accepted);s.state=outcome;s.diagnostic=outcome=="complete"?"":"observer_"+outcome;s.open=false;return true;
    }catch(const Error& error) {s.state="malformed";s.diagnostic=error.what();s.open=false;return false;}
}
bool Capture::timeout(const Ticket& key) {
    auto& s=slots_[slot(key.source)];if(!matches(s,key) || !s.open)return false;s.state="timed_out";s.diagnostic="observer_timeout";s.open=false;return true;
}
bool Capture::retire(const Ticket& key) {
    auto& s=slots_[slot(key.source)];if(!matches(s,key) || !s.live)return false;
    if(s.open) {s.state=cancelled_?"cancelled":"unavailable";s.diagnostic=cancelled_?"observer_cancelled":"observer_exited_without_result";s.open=false;}
    s.live=false;return true;
}
std::string Capture::state() const {
    bool unfinished=false,complete=true;for(const auto& s:slots_) {unfinished=unfinished || s.open || s.state=="not_started";complete=complete && s.state=="complete";}
    if(cancelled_)return unfinished?"cancel_requested":"cancelled";return unfinished?"collecting":complete?"complete":"partial";
}
bool Capture::cancel() {
    if(cancelled_ || state()=="complete" || state()=="partial")return false;cancelled_=true;
    for(auto& s:slots_)if(s.state=="not_started") {s.state="cancelled";s.diagnostic="observer_cancelled";}return true;
}
void Capture::next_capture() {
    for(const auto& s:slots_)if(s.live)throw Error("health_worker_outstanding");
    if(capture_==(std::numeric_limits<std::uint64_t>::max)())throw Error("health_counter_exhausted");
    ++capture_;cancelled_=false;for(auto& s:slots_)reset(s);
}
V Capture::view() const {
    V sources=V::array();bool coverage=true;std::uint64_t outstanding=0;
    for(const auto& s:slots_) {coverage=coverage && s.state=="complete";outstanding+=s.live?1:0;
        sources.items.push_back(V::object().put("id",get(s.declaration,"id")).put("provider_digest",get(s.declaration,"provider_digest"))
            .put("state",V::string(s.state)).put("diagnostic",V::string(s.diagnostic)).put("worker",number(s.worker))
            .put("request_open",V::boolean_value(s.open)).put("worker_outstanding",V::boolean_value(s.live)).put("fields",s.fields));
    }
    return projection(V::object().put("schema",V::string("org.disked.health-capture-prototype/1")).put("target",target_).put("capture",number(capture_))
        .put("state",V::string(state())).put("cancel_requested",V::boolean_value(cancelled_)).put("workers_outstanding",number(outstanding))
        .put("coverage_complete",V::boolean_value(coverage)).put("sources",sources).put("claims",claims()));
}
V Capture::support(const V& policy) const {
    shape(policy,{"identifiers","raw_values","interpretations","customer_data"});const bool identifiers=flag(get(policy,"identifiers")),raw_values=flag(get(policy,"raw_values")),interpretations=flag(get(policy,"interpretations")),customer=flag(get(policy,"customer_data"));
    V out=V::object().put("schema",V::string("org.disked.health-support-prototype/1")).put("state",V::string(state()))
        .put("cancel_requested",V::boolean_value(cancelled_)).put("policy",policy).put("claims",claims());
    if(identifiers)out.put("target",target_).put("capture",number(capture_));V sources=V::array();std::uint64_t index=0;
    for(const auto& s:slots_) {
        V source=V::object().put("label",V::string("observer"+std::to_string(++index))).put("state",V::string(s.state)).put("diagnostic",V::string(s.diagnostic))
            .put("request_open",V::boolean_value(s.open)).put("worker_outstanding",V::boolean_value(s.live));
        if(identifiers)source.put("id",get(s.declaration,"id")).put("provider_digest",get(s.declaration,"provider_digest")).put("worker",number(s.worker));
        V fields=V::array();std::uint64_t field_index=0;
        for(const auto& f:s.fields.items) {
            const auto classification=get(f,"sensitivity").text;const bool permitted=classification!="secret" && (classification!="identifier" || identifiers) && (classification!="customer" || customer);
            V field=V::object().put("label",V::string("observation"+std::to_string(++field_index))).put("received",get(f,"received"))
                .put("raw_availability",get(get(f,"raw"),"availability")).put("interpretation_availability",get(get(f,"interpretation"),"availability"));
            if(permitted && identifiers)field.put("id",get(f,"id"));
            if(permitted && raw_values)field.put("raw",get(f,"raw"));
            if(permitted && interpretations)field.put("interpretation",get(f,"interpretation"));
            fields.items.push_back(std::move(field));
        }
        source.put("fields",fields);sources.items.push_back(std::move(source));
    }
    return projection(out.put("sources",sources));
}
}}}
