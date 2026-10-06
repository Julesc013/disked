#include "fake_operation.h"
#include "sha256.h"
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace disked { namespace fake_operation {
using json::Value;
namespace {
[[noreturn]] void fail(const char* code) { throw std::invalid_argument(code); }
std::string text(const Value& value, const std::string& key) {
    const auto* p=value.find(key);
    if(!p || p->kind!=Value::Kind::string)fail("operation_record_shape");
    return p->text;
}
bool hex(const std::string& s, std::size_t size) {
    if(s.size()!=size)return false;
    for(const char c:s)if(!((c>='0' && c<='9') || (c>='a' && c<='f')))return false;
    return true;
}
bool prefixed_hex(const std::string& s, const std::string& prefix) {
    return s.compare(0,prefix.size(),prefix)==0 && hex(s.substr(prefix.size()),32);
}
void set(Value& value,const std::string& key,const std::string& s) {value.put(key,Value::string(s));}
json::Limits limits() {json::Limits l;l.bytes=record_limit;return l;}
std::string encoded(const Value& value) {return json::dump(value,limits());}
}
std::string hash(const std::string& bytes) {
    unsigned char digest[32];
    sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),digest);
    const char* digits="0123456789abcdef";std::string out;out.reserve(64);
    for(const auto b:digest) {out.push_back(digits[b>>4]);out.push_back(digits[b&15]);}
    return out;
}
bool fixture(const std::string& id) {
    return id=="fake:complete" || id=="fake:verification-failure" || id=="fake:cancel-checkpoint" || id=="fake:unknown";
}
void validate_binding(const Value& b) {
    if(b.kind!=Value::Kind::object || b.fields.size()!=12)fail("operation_binding_shape");
    const auto id=text(b,"operation_id");
    if(!prefixed_hex(id,"fake-op:") || text(b,"attempt_id")!=id+":attempt:1" ||
       !prefixed_hex(text(b,"worker_epoch"),"worker:") || !fixture(text(b,"fixture_id")) ||
       !hex(text(b,"host_id"),64) || !hex(text(b,"source_revision"),40) ||
       text(b,"input_digest").compare(0,7,"sha256:")!=0 || !hex(text(b,"input_digest").substr(7),64) || !hex(text(b,"image_digest"),64) ||
       text(b,"provider_id")!="provider.fake.bootstrap/1" || text(b,"target_profile")!="windows.nt10.x64.win32")fail("operation_binding_value");
    const auto pid=text(b,"process_id"),created=text(b,"process_created");
    if(!json::decimal_u64(pid) || pid=="0" || std::stoull(pid)>4294967295ULL ||
       !json::decimal_u64(created) || created=="0")fail("operation_process_identity");
}
Value origin(const Value& binding) {
    Value out=Value::object();
    for(const char* key:{"operation_id","attempt_id","worker_epoch"})set(out,key,text(binding,key));
    return out;
}
Operation::Operation(const Value& binding) {
    validate_binding(binding);state_=Value::object().put("binding",binding);
    set(state_,"schema","org.disked.fake-operation/1");set(state_,"scope","fake-only");
    set(state_,"sequence","1");set(state_,"phase","pending");set(state_,"logical_state","pending");
    set(state_,"attempt_state","prepared");set(state_,"effect_certainty","not_started");
    set(state_,"cancellation","not_requested");set(state_,"recovery","unnecessary");
    state_.put("outcome",Value{});set(state_,"synthetic_effect_count","0");set(state_,"last_event","initialized");
}
bool Operation::terminal() const {return text(state_,"phase")=="finished";}
bool Operation::advance(const std::string& action,const Value& observation_origin,const std::string& count) {
    if(encoded(observation_origin)!=encoded(origin(*state_.find("binding"))))fail("operation_epoch_mismatch");
    if(action!="observe" && !count.empty())fail("operation_unexpected_observation");
    auto next=state_;const auto phase=text(state_,"phase"),cancel=text(state_,"cancellation");
    std::string event;
    if(action=="cancel") {
        if(terminal() || cancel!="not_requested")return false;
        set(next,"cancellation","requested");event="cancel_requested";
    } else if(action=="checkpoint") {
        if(terminal() || cancel!="requested" || (phase!="pending" && phase!="prepared"))return false;
        set(next,"phase","finished");set(next,"logical_state","completed");set(next,"attempt_state","finished");
        set(next,"cancellation","acknowledged");set(next,"outcome","cancelled");event="cancel_acknowledged";
    } else if(action=="prepare") {
        if(phase!="pending")fail("operation_transition_refused");
        set(next,"phase","prepared");set(next,"logical_state","active");event="prepared";
    } else if(action=="dispatch") {
        if(phase!="prepared")fail("operation_transition_refused");
        if(cancel=="requested")fail("operation_checkpoint_required");
        set(next,"phase","in_flight");set(next,"attempt_state","dispatched");set(next,"effect_certainty","in_flight");
        next.put("synthetic_effect_count",Value{});event="effect_dispatched";
    } else if(action=="observe") {
        if(phase!="in_flight")fail("operation_transition_refused");
        if(count!="1")fail("operation_observation_refused");
        set(next,"phase","observed");set(next,"attempt_state","observing");set(next,"effect_certainty","observed");
        set(next,"synthetic_effect_count",count);event="effect_observed";
    } else if(action=="verify") {
        if(phase!="observed")fail("operation_transition_refused");
        const bool failed=text(*state_.find("binding"),"fixture_id")=="fake:verification-failure";
        set(next,"phase","finished");set(next,"logical_state",failed?"unresolved":"completed");set(next,"attempt_state","finished");
        set(next,"recovery",failed?"required":"unnecessary");set(next,"outcome",failed?"verification_failed":"succeeded");
        event=failed?"verification_failed":"verified";
    } else fail("operation_action_unknown");
    const auto sequence=std::stoull(text(state_,"sequence"));
    if(sequence==(std::numeric_limits<std::uint64_t>::max)())fail("operation_sequence_exhausted");
    set(next,"sequence",std::to_string(sequence+1));set(next,"last_event",event);
    state_=std::move(next);return true;
}
std::string record(const Value& state,const std::string& previous) {
    if(!hex(previous,64))fail("operation_chain_shape");
    auto out=Value::object().put("schema",Value::string("org.disked.fake-operation-record/1"))
        .put("state",state).put("previous",Value::string(previous));
    out.put("digest",Value::string(hash(encoded(out))));return encoded(out)+"\n";
}
History read_history(const std::string& bytes) {
    if(bytes.empty())fail("operation_history_empty");
    if(bytes.size()>history_limit)fail("operation_history_limit");
    if(bytes.back()!='\n')fail("operation_history_partial");
    History out;std::size_t start=0;
    // Reconstruct only from the immutable first binding. Every subsequent state
    // must equal the reducer's guarded transition; independently typed fields
    // alone would permit contradictory evidence.
    Value binding;std::vector<std::string> actions;
    while(start<bytes.size()) {
        if(++out.count>record_count_limit)fail("operation_history_count");
        const auto end=bytes.find('\n',start);const auto line=bytes.substr(start,end-start);start=end+1;
        if(line.size()>record_limit)fail("operation_record_limit");
        auto envelope=json::parse(line,limits());
        if(envelope.kind!=Value::Kind::object || envelope.fields.size()!=4 ||
           text(envelope,"schema")!="org.disked.fake-operation-record/1" || !envelope.find("state"))fail("operation_record_shape");
        if(text(envelope,"previous")!=out.digest)fail("operation_chain_mismatch");
        const auto digest=text(envelope,"digest");envelope.fields.erase("digest");
        if(!hex(digest,64) || hash(encoded(envelope))!=digest)fail("operation_digest_mismatch");
        const auto& state=*envelope.find("state");
        if(out.count==1) {
            if(!state.find("binding"))fail("operation_record_shape");binding=*state.find("binding");
        } else {
            const auto event=text(state,"last_event");
            if(event=="prepared")actions.push_back("prepare");
            else if(event=="effect_dispatched")actions.push_back("dispatch");
            else if(event=="effect_observed")actions.push_back("observe");
            else if(event=="verified" || event=="verification_failed")actions.push_back("verify");
            else if(event=="cancel_requested")actions.push_back("cancel");
            else if(event=="cancel_acknowledged")actions.push_back("checkpoint");
            else fail("operation_event_unknown");
        }
        Operation replay(binding);
        for(const auto& action:actions)if(!replay.advance(action,origin(binding),action=="observe"?"1":""))fail("operation_transition_noop");
        if(encoded(replay.state())!=encoded(state))fail("operation_state_mismatch");
        out.state=state;out.digest=digest;
    }
    return out;
}
}}
