#include "semantics.h"
#include <algorithm>
#include <limits>
#include <map>
#include <set>

namespace disked { namespace journal { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void bad(const char* code) {throw DefinitionError(code);}
const V& get(const V& v,const std::string& k) {const auto p=v.find(k);if(!p)bad("semantic_shape");return *p;}
std::string str(const V& v) {if(v.kind!=V::Kind::string)bad("semantic_string");return v.text;}
std::string str(const V& v,const char* k) {return str(get(v,k));}
void keys(const V& v,const std::vector<std::string>& names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())bad("semantic_shape");for(const auto& n:names)get(v,n);}
bool flag(const V& v,const char* k) {const auto& x=get(v,k);if(x.kind!=V::Kind::boolean)bad("semantic_boolean");return x.boolean;}
std::string id(const V& v,const char* k,bool empty=false) {
    const auto s=str(v,k);if((s.empty() && !empty) || s.size()>128 || s.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:/@+-")!=s.npos)bad("semantic_identifier");return s;
}
std::uint64_t num(const V& v,const char* k,bool positive=true) {const auto s=str(v,k);if(!json::decimal_u64(s))bad("semantic_integer");const auto n=std::stoull(s);if(positive && !n)bad("semantic_integer");return n;}
bool has(const std::vector<std::string>& a,const std::string& s) {return std::find(a.begin(),a.end(),s)!=a.end();}
V count(std::uint64_t n) {return V::string(std::to_string(n));}
V parse_payload(const Bytes& bytes) {
    json::Limits l;l.bytes=max_payload;l.string_bytes=max_payload;l.values=262144;
    try {const std::string s(bytes.begin(),bytes.end());auto v=json::parse(s,l);if(json::dump(v,l)!=s)bad("semantic_noncanonical");return v;}
    catch(const json::Error&) {bad("semantic_json");}
}
struct State {
    const Definition* definition;std::vector<V> receipts;std::vector<std::string> selected;
    std::set<std::string> ids,attempts,done;std::map<std::string,std::string> expected;
    std::string operation,attempt,worker,admission,basis,pending,last_completed,recovery_kind,recovery_step,recovery_digest,terminal;
    std::uint64_t epoch=0,event_sequence=0,capture_epoch=0,intention_capture=0,events=0,observations=0,retained_bytes=0;
    bool defined=false,cancelled=false,exited=false,bootstrap=false;
    explicit State(const Definition& d):definition(&d) {for(const auto& r:get(d.value(),"resources").items)expected[str(r,"id")]=str(r,"state_digest");}
    const V& step(const std::string& name) const {for(const auto& s:get(definition->value(),"steps").items)if(str(s,"id")==name)return s;bad("semantic_step");}
    void unique(const V& v) {if(!ids.insert(id(v,"id")).second)bad("semantic_id_reused");}
    bool all_done() const {return bootstrap && done.size()==selected.size();}
    bool checkpoint() const {return last_completed.empty() || flag(get(step(last_completed),"recovery"),"cancellable_at_checkpoint");}
    void ready(const std::string& name) const {
        if(!has(selected,name) || done.count(name))bad("semantic_step_scope");
        for(const auto& dep:get(step(name),"depends_on").items)if(!done.count(str(dep)))bad("semantic_predecessor");
    }
    void capture(const V& c,const std::string& name,const std::string& when) {
        keys(c,{"observer_id","capture_epoch","resources"});id(c,"observer_id");const auto n=num(c,"capture_epoch");if(n<=capture_epoch)bad("semantic_capture_order");
        const auto& rows=get(c,"resources");const auto& bound=get(definition->value(),"resources");if(rows.kind!=V::Kind::array || rows.items.size()!=bound.items.size())bad("semantic_capture_scope");
        auto wanted=expected;
        if(when!="terminal")for(const auto& e:get(step(name),"effects").items)wanted[str(e,"resource")]=str(e,when=="after" && str(e,"access")=="write"?"after_digest":"before_digest");
        for(std::size_t i=0;i<rows.items.size();++i) {
            const auto& r=rows.items[i];const auto& b=bound.items[i];keys(r,{"resource","identity_digest","state_digest","epoch","available"});
            if(id(r,"resource")!=str(b,"id") || str(r,"identity_digest")!=str(b,"identity_digest") || num(r,"epoch")!=num(b,"epoch") || !flag(r,"available") || str(r,"state_digest")!=wanted.at(str(b,"id")))bad("semantic_capture_mismatch");
        }capture_epoch=n;
    }
    void finish(const std::string& name) {
        done.insert(name);last_completed=name;for(const auto& e:get(step(name),"effects").items)if(str(e,"access")=="write")expected[str(e,"resource")]=str(e,"after_digest");pending.clear();
    }
    void claim_exit_flush(const V& details,const char* flush_key) const {
        if(!flag(details,"worker_exited") || !flag(details,"qualified_fake_flush"))bad("semantic_recovery_evidence");
        const auto exit=num(details,"exit_capture_epoch",false),flush=num(details,flush_key);
        if(exit<capture_epoch || flush<=exit || num(get(details,"capture"),"capture_epoch")<=flush)bad("semantic_recovery_order");
    }
    void accept(const Record& r) {
        if(r.kind>=32768) {++observations;return;}
        const auto v=parse_payload(r.payload);
        if(r.kind==1) {
            if(defined || !ids.empty())bad("semantic_definition_order");const Definition d(v);
            if(d.payload()!=definition->payload())bad("semantic_definition_mismatch");unique(v);defined=true;retained_bytes=r.payload.size();return;
        }
        if(!defined)bad("semantic_definition_missing");
        unique(v);
        if(r.kind==2 || r.kind==3 || (r.kind==4 && str(v,"schema")=="org.disked.plan-receipt-prototype/1")) {
            if(receipts.size()>=128 || r.payload.size()>1048576-retained_bytes)bad("semantic_receipt_budget");
            const auto expected_kind=r.kind==2?"review":r.kind==3?"grant":"admission";if(str(v,"kind")!=expected_kind)bad("semantic_receipt_kind");
            auto candidate=receipts;candidate.push_back(v);inspect_receipts(*definition,candidate);
            if(r.kind==4) {
                if(bootstrap)bad("semantic_initial_admission_repeated");
                for(const auto& s:get(v,"step_ids").items)selected.push_back(str(s));
                for(const auto& name:selected)for(const auto& dep:get(step(name),"depends_on").items)if(!has(selected,str(dep)))bad("semantic_admission_dependencies");
                operation=str(v,"operation_id");attempt=str(v,"attempt_id");worker=str(v,"worker_identity");epoch=num(v,"worker_epoch");basis=admission=digest_text(hash(r.payload));attempts.insert(attempt);bootstrap=true;
            }
            retained_bytes+=r.payload.size();receipts=std::move(candidate);return;
        }
        if(!bootstrap)bad("semantic_admission_missing");
        if(str(v,"plan_digest")!=digest_text(definition->digest()))bad("semantic_plan_mismatch");
        if(r.kind==4) {
            keys(v,{"schema","id","plan_digest","basis_admission_digest","operation_id","attempt_id","worker_identity","worker_epoch","recovery_record_digest","capture"});
            if(str(v,"schema")!="org.disked.journal-checkpoint-admission-prototype/1")bad("semantic_version");
            if(!exited || cancelled || all_done() || recovery_digest.empty() || (recovery_kind!="before" && recovery_kind!="after") || str(v,"recovery_record_digest")!=recovery_digest || str(v,"basis_admission_digest")!=basis || id(v,"operation_id")!=operation)bad("semantic_checkpoint_reference");
            if(!pending.empty() && !flag(get(step(pending),"recovery"),"replayable"))bad("semantic_replay_forbidden");
            const auto new_attempt=id(v,"attempt_id"),new_worker=id(v,"worker_identity");const auto new_epoch=num(v,"worker_epoch");
            if(attempts.size()>=4 || attempts.count(new_attempt) || new_epoch<=epoch)bad("semantic_attempt_reused_or_limit");
            capture(get(v,"capture"),"","terminal");attempt=new_attempt;worker=new_worker;epoch=new_epoch;attempts.insert(attempt);admission=digest_text(hash(r.payload));event_sequence=0;pending.clear();exited=false;recovery_digest.clear();recovery_kind.clear();return;
        }
        keys(v,{"schema","id","plan_digest","admission_digest","operation_id","attempt_id","worker_identity","worker_epoch","sequence","step_id","event","details"});
        if(str(v,"schema")!="org.disked.journal-effect-prototype/1")bad("semantic_version");
        if(str(v,"admission_digest")!=admission || id(v,"operation_id")!=operation || id(v,"attempt_id")!=attempt || id(v,"worker_identity")!=worker || num(v,"worker_epoch")!=epoch)bad("semantic_attempt_mismatch");
        const auto sequence=num(v,"sequence");if(event_sequence==(std::numeric_limits<std::uint64_t>::max)() || sequence!=event_sequence+1)bad("semantic_event_sequence");if(events>=1024)bad("semantic_event_budget");
        const auto name=id(v,"step_id",true),event=str(v,"event");const auto& details=get(v,"details");
        if(r.kind==5) {
            if(event!="intention")bad("semantic_event_kind");keys(details,{"capture"});
            if(exited || cancelled || !pending.empty())bad("semantic_intention_order");ready(name);capture(get(details,"capture"),name,"before");pending=name;intention_capture=capture_epoch;recovery_digest.clear();recovery_kind.clear();
        } else if(r.kind==6) {
            if(event!="verified_completion")bad("semantic_event_kind");keys(details,{"capture","target_flush_capture_epoch","qualified_fake_flush"});
            if(exited || pending.empty() || name!=pending)bad("semantic_completion_order");
            const auto flush=num(details,"target_flush_capture_epoch");if(!flag(details,"qualified_fake_flush") || flush<intention_capture || num(get(details,"capture"),"capture_epoch")<=flush)bad("semantic_completion_evidence");
            capture(get(details,"capture"),name,"after");finish(name);
        } else if(r.kind==7) {
            if(event!="cancellation_request")bad("semantic_event_kind");keys(details,{"requested"});
            if(cancelled || !flag(details,"requested") || name!=pending)bad("semantic_cancellation_order");cancelled=true;
        } else if(r.kind==8) {
            if(event!="recovery_observation")bad("semantic_event_kind");keys(details,{"capture","flush_capture_epoch","qualified_fake_flush","worker_exited","exit_capture_epoch","observed"});
            claim_exit_flush(details,"flush_capture_epoch");const auto observed=str(details,"observed");
            if(observed=="terminal") {if(!name.empty() || !pending.empty() || (!all_done() && (!cancelled || !checkpoint())))bad("semantic_recovery_scope");}
            else if(observed=="before" || observed=="after") {
                ready(name);if((!pending.empty() && name!=pending) || (observed=="after" && pending.empty()))bad("semantic_recovery_scope");
            } else bad("semantic_recovery_state");
            capture(get(details,"capture"),name,observed);exited=true;recovery_kind=observed;recovery_step=name;recovery_digest=digest_text(r.digest);if(observed=="after")finish(name);
        } else if(r.kind==9) {
            if(event!="seal")bad("semantic_event_kind");keys(details,{"capture","worker_exited","exit_capture_epoch","outcome","cancel_acknowledged"});
            const auto outcome=str(details,"outcome");const auto exit=num(details,"exit_capture_epoch",false);
            if(!name.empty() || !flag(details,"worker_exited") || exit<capture_epoch || num(get(details,"capture"),"capture_epoch")<=exit)bad("semantic_seal_evidence");
            if(outcome=="completed") {if(!all_done() || !pending.empty() || flag(details,"cancel_acknowledged"))bad("semantic_seal_scope");}
            else if(outcome=="cancelled") {if(!cancelled || !checkpoint() || !flag(details,"cancel_acknowledged") || (!pending.empty() && (recovery_kind!="before" || recovery_step!=pending)))bad("semantic_seal_scope");}
            else bad("semantic_seal_outcome");
            capture(get(details,"capture"),"","terminal");exited=true;terminal=outcome;
        } else bad("semantic_unknown_kind");
        event_sequence=sequence;++events;
    }
    V report() const {
        auto completed=V::array();for(const auto& name:done)completed.items.push_back(V::string(name));
        return V::object().put("scope",V::string("private-fake-binary-journal-declarations")).put("authenticated",V::boolean_value(false)).put("authorizes_effects",V::boolean_value(false))
            .put("qualifies_durability",V::boolean_value(false)).put("replay_authorized",V::boolean_value(false)).put("retirement_authorized",V::boolean_value(false)).put("requires_live_reconciliation",V::boolean_value(true))
            .put("definition_observed",V::boolean_value(defined)).put("bootstrap_complete",V::boolean_value(bootstrap)).put("receipts",count(receipts.size())).put("retained_payload_bytes",count(retained_bytes))
            .put("operation_id",V::string(operation)).put("attempt_id",V::string(attempt)).put("worker_identity",V::string(worker)).put("worker_epoch",count(epoch)).put("attempts",count(attempts.size()))
            .put("event_sequence",count(event_sequence)).put("events",count(events)).put("capture_epoch",count(capture_epoch)).put("observational_records",count(observations))
            .put("declared_completed_steps",completed).put("pending_intention",V::string(pending)).put("cancellation_declared",V::boolean_value(cancelled)).put("worker_exit_declared",V::boolean_value(exited))
            .put("recovery_declaration",V::string(recovery_kind)).put("declared_terminal_outcome",V::string(terminal));
    }
};
}
SemanticScan scan_semantics(Source& source,const Definition& definition,const Bindings& expected,const PublisherBinding& publisher) {
    SemanticScan result;State state(definition);
    if(expected.plan!=definition.digest() || expected.targets!=definition.resources_digest() || expected.providers!=definition.providers_digest()) {
        result.framing.diagnostic="journal_semantic_expected_binding";result.semantic_diagnostic="semantic_expected_binding";result.projection=state.report();return result;
    }
    if(!publisher.epoch || std::all_of(publisher.identity.begin(),publisher.identity.end(),[](unsigned char c){return c==0;})) {
        result.framing.diagnostic="journal_semantic_expected_publisher";result.semantic_diagnostic="semantic_expected_publisher";result.projection=state.report();return result;
    }
    result.framing=scan(source,expected,[&](const Record& r) {
        try {
            if(r.publisher!=publisher.identity || r.publisher_epoch!=publisher.epoch)bad("semantic_publisher_mismatch");
            auto next=state;next.accept(r);state=std::move(next);return true;
        }catch(const DefinitionError& error) {result.semantic_diagnostic=error.what();return false;}
    });
    result.projection=state.report();return result;
}
}}}
