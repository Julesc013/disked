#include "guarded_model.h"
#include <algorithm>
#include <limits>
#include <map>
#include <set>

namespace disked { namespace journal { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void bad(const char* code) {throw DefinitionError(code);}
const V& get(const V& v,const std::string& k) {const auto p=v.find(k);if(!p)bad("model_shape");return *p;}
std::string str(const V& v) {if(v.kind!=V::Kind::string)bad("model_string");return v.text;}
std::string str(const V& v,const char* k) {return str(get(v,k));}
bool boolean(const V& v,const char* k) {const auto& x=get(v,k);if(x.kind!=V::Kind::boolean)bad("model_boolean");return x.boolean;}
void keys(const V& v,const std::vector<std::string>& ks) {if(v.kind!=V::Kind::object || v.fields.size()!=ks.size())bad("model_shape");for(const auto& k:ks)get(v,k);}
std::uint64_t number(const V& v,const char* k,bool positive=true) {
    const auto s=str(v,k);if(!json::decimal_u64(s))bad("model_integer");const auto n=std::stoull(s);if(positive && !n)bad("model_integer");return n;
}
std::string identifier(const V& v,const char* k) {
    const auto s=str(v,k);if(s.empty() || s.size()>128 || s.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:/@+-")!=s.npos)bad("model_identifier");return s;
}
void checked_digest(const std::string& s) {
    if(s.size()!=71 || s.compare(0,7,"sha256:") || s.find_first_not_of("0123456789abcdef",7)!=s.npos || s.substr(7)==std::string(64,'0'))bad("model_digest");
}
void option(const std::string& s,std::initializer_list<const char*> choices) {for(const auto c:choices)if(s==c)return;bad("model_enum");}
std::string encode(const V& v,std::size_t bytes=131072) {json::Limits l;l.bytes=bytes;l.values=262144;try{return json::dump(v,l);}catch(const json::Error&){bad("model_payload_limit");}}
std::string hashed(const std::string& s) {return digest_text(hash(Bytes(s.begin(),s.end())));}
V count(std::uint64_t n) {return V::string(std::to_string(n));}
const std::map<std::string,std::vector<std::string>> action_fields={
    {"capture",{"observer_id","capture_epoch","resources"}}, {"intention",{"step_id","fault"}}, {"journal_flush",{"fault"}},
    {"dispatch",{}}, {"effect_result",{"outcome"}}, {"target_flush",{"fault"}}, {"verify",{"capture_epoch"}}, {"completion",{"fault"}},
    {"cancel_request",{"fault"}}, {"cancel_checkpoint",{}}, {"client_disconnect",{}}, {"client_reconnect",{}}, {"timeout",{}}, {"worker_exit",{}},
    {"crash",{"prefix_entries","persist_after","torn_tail"}}, {"recovery_flush",{"fault"}}, {"reconcile",{"capture_epoch","observed","fault"}},
    {"replace",{"new_attempt_id","new_worker_identity","new_worker_epoch","fault"}}, {"fork_journal",{}}, {"seal",{"fault"}},
    {"change_resource",{"resource","identity_digest","state_digest","epoch","available"}}
};
struct Journal {std::vector<V> frames;std::string tail;std::size_t stable=0,bytes=0,baseline=0;bool failed=false;};
std::string journal_digest(const Journal& j) {std::string s;for(const auto& f:j.frames)s+=encode(f)+"\n";return hashed(s+j.tail);}
}
struct GuardedModel::Impl {
    Definition definition;V initial_admission;std::vector<std::string> selected;std::map<std::string,V> bound,actual;
    std::map<std::string,std::string> durable,expected;std::set<std::string> done,attempt_ids;
    Journal journal;std::vector<Journal> retained;
    std::string operation,attempt,worker_identity,worker="prepared",logical="pending",phase="admission_pending",effect="not_started",recovery="none",active,diagnostic,observer;
    std::uint64_t worker_epoch=0,capture_epoch=0,exit_capture=0,dispatch_capture=0,flush_capture=0,generation=0,captured_generation=0,actions=0,dispatches=0,writes=0,target_flushes=0,journal_flushes=0;
    std::size_t entries_limit=0,bytes_limit=0,attempts_limit=0;bool qualified=false,connected=true,captured=false,pending=false,intention_stable=false,target_flushed=false,recovery_flushed=false;
    bool cancellation=false,cancel_durable=false,cancel_ack=false,retry_observed=false,needs_recovery=false,unbound=false;
    std::string sealed_outcome,last_completed;
    bool result_observed=false;
    std::uint64_t model_generation=1;
    Impl(const Definition& d,const std::vector<V>& receipts,const V& config):definition(d) {
        keys(config,{"entries_limit","bytes_limit","attempts_limit","qualified_fake_flush"});
        const auto e=number(config,"entries_limit"),b=number(config,"bytes_limit"),a=number(config,"attempts_limit");
        if(e>512 || b>1048576 || a>4)bad("model_budget");entries_limit=static_cast<std::size_t>(e);bytes_limit=static_cast<std::size_t>(b);attempts_limit=static_cast<std::size_t>(a);qualified=boolean(config,"qualified_fake_flush");
        if(receipts.size()!=3 || str(receipts[0],"kind")!="review" || str(receipts[1],"kind")!="grant" || str(receipts[2],"kind")!="admission")bad("model_initial_receipts");
        inspect_receipts(d,receipts);initial_admission=receipts[2];operation=str(initial_admission,"operation_id");attempt=str(initial_admission,"attempt_id");worker_identity=str(initial_admission,"worker_identity");worker_epoch=number(initial_admission,"worker_epoch");
        for(const auto& s:get(initial_admission,"step_ids").items)selected.push_back(str(s));attempt_ids.insert(attempt);
        for(const auto& name:selected)for(const auto& dep:get(step(name),"depends_on").items)if(!has(selected,str(dep)))bad("model_admission_dependencies");
        for(const auto& r:get(d.value(),"resources").items) {
            const auto name=str(r,"id");bound.emplace(name,r);auto row=V::object().put("resource",V::string(name));
            for(const auto k:{"identity_digest","state_digest","epoch"})row.put(k,get(r,k));row.put("available",V::boolean_value(true));actual.emplace(name,row);durable[name]=expected[name]=str(r,"state_digest");
        }
        append("1",d.value(),"none");for(std::size_t i=0;i<receipts.size();++i)append(std::to_string(i+2),receipts[i],"none");if(journal.failed)bad("model_bootstrap_budget");
    }
    static bool has(const std::vector<std::string>& v,const std::string& s) {return std::find(v.begin(),v.end(),s)!=v.end();}
    const V& step(const std::string& name) const {for(const auto& s:get(definition.value(),"steps").items)if(str(s,"id")==name)return s;bad("model_step");}
    const V& current() const {if(active.empty())bad("model_no_step");return step(active);}
    bool all_done() const {for(const auto& s:selected)if(!done.count(s))return false;return true;}
    bool terminal() const {return logical=="completed" || logical=="cancelled";}
    std::string next_step() const {
        for(const auto& name:selected)if(!done.count(name)) {
            bool ready=true;for(const auto& dep:get(step(name),"depends_on").items)ready=ready && done.count(str(dep));if(ready)return name;
        }return "";
    }
    void running() const {if(worker!="running" || logical!="active" || needs_recovery || unbound)bad("model_worker_not_active");}
    void unresolved(const char* code) {
        diagnostic=code;logical="unresolved";needs_recovery=true;recovery="required";
        if(effect=="in_flight" || effect=="reported_after")effect="uncertain";
    }
    bool protected_resource(const std::string& name) const {const auto purpose=str(bound.at(name),"purpose");return purpose=="journal" || purpose=="backup" || purpose=="executable" || purpose=="provider";}
    void closure() const {
        for(const auto& pair:actual) {
            const auto& r=pair.second;const auto& original=bound.at(pair.first);
            if(!boolean(r,"available"))bad("model_resource_unavailable");
            if(str(r,"identity_digest")!=str(original,"identity_digest") || str(r,"epoch")!=str(original,"epoch"))bad("model_identity_mismatch");
            if(protected_resource(pair.first) && str(r,"state_digest")!=str(original,"state_digest"))bad("model_dependency_mismatch");
        }
    }
    void fresh(bool after_exit=false) const {
        if(!captured || captured_generation!=generation || (after_exit && capture_epoch<=exit_capture))bad("model_capture_stale");closure();
    }
    bool states(const std::string& when) const {
        auto wanted=expected;
        if(when!="terminal")for(const auto& e:get(current(),"effects").items) {
            const auto key=when=="after" && str(e,"access")=="write"?"after_digest":"before_digest";
            wanted[str(e,"resource")]=str(e,key);
        }
        for(const auto& p:wanted)if(str(actual.at(p.first),"state_digest")!=p.second)return false;return true;
    }
    bool journal_available() const {
        const auto name=str(definition.value(),"journal_resource");const auto& r=actual.at(name);const auto& original=bound.at(name);
        return boolean(r,"available") && str(r,"identity_digest")==str(original,"identity_digest") && str(r,"epoch")==str(original,"epoch") && str(r,"state_digest")==str(original,"state_digest");
    }
    void finish_step(const std::string& name) {
        done.insert(name);for(const auto& e:get(step(name),"effects").items)if(str(e,"access")=="write")expected[str(e,"resource")]=str(e,"after_digest");
        active=name;last_completed=name;pending=false;intention_stable=false;phase="idle";effect="verified_after";
    }
    V capture_rows() const {auto out=V::array();for(const auto& p:actual)out.items.push_back(p.second);return out;}
    V evidence(const std::string& observed="") const {
        return V::object().put("capture_epoch",count(capture_epoch)).put("observer_id",V::string(observer)).put("resources",capture_rows())
            .put("observed",V::string(observed)).put("qualified_fake_flush",V::boolean_value(qualified));
    }
    bool append(const std::string& kind,const V& data,const std::string& fault) {
        option(fault,{"none","before","torn"});
        if(!journal_available()) {journal.failed=true;unresolved("model_journal_dependency");return false;}
        if(journal.failed || !journal.tail.empty()) {unresolved("model_journal_unwritable");return false;}
        if(!journal.frames.empty() && str(journal.frames.back(),"kind")=="9") {unresolved("model_journal_sealed");return false;}
        const auto previous=journal.frames.empty()?digest_text(definition.digest()):str(journal.frames.back(),"digest");
        auto frame=V::object().put("kind",V::string(kind)).put("sequence",count(journal.frames.size()+1)).put("operation_id",V::string(operation))
            .put("attempt_id",V::string(attempt)).put("worker_identity",V::string(worker_identity)).put("worker_epoch",count(worker_epoch))
            .put("publisher_identity",V::string("fake:publisher")).put("publisher_epoch",count(model_generation)).put("step_id",V::string(active)).put("data",data);
        const auto encoded=encode(frame,131072);const auto digest=hashed("DiskEd.fake.guard.log/1\n"+previous+encoded);
        frame.put("previous",V::string(previous)).put("digest",V::string(digest));const auto bytes=encode(frame,131072);
        if(journal.frames.size()>=entries_limit || bytes.size()>bytes_limit-journal.bytes) {journal.failed=true;unresolved("model_journal_limit");return false;}
        if(fault=="before") {journal.failed=true;unresolved("model_append_before_failure");return false;}
        if(fault=="torn") {journal.tail=bytes.substr(0,bytes.size()/2);journal.bytes+=journal.tail.size();journal.failed=true;unresolved("model_append_torn");return false;}
        journal.bytes+=bytes.size();journal.frames.push_back(frame);return true;
    }
    void apply_stable(const V& frame,bool restoring=false) {
        const auto kind=str(frame,"kind");const auto& data=get(frame,"data");
        if(kind=="4") {
            attempt=str(frame,"attempt_id");worker_identity=str(frame,"worker_identity");worker_epoch=number(frame,"worker_epoch");
            if(!restoring) {worker="running";logical="active";phase="idle";needs_recovery=false;recovery="none";}
        }
        if(kind=="5") {active=str(frame,"step_id");pending=true;intention_stable=true;if(!restoring)phase="prepared";}
        if(kind=="6")finish_step(str(frame,"step_id"));
        if(kind=="7") {cancellation=true;cancel_durable=true;}
        if(kind=="8") {
            const auto observed=str(data,"observed");
            if(observed=="after") {finish_step(str(frame,"step_id"));if(!restoring) {logical="active";needs_recovery=false;recovery="after";}}
            if(observed=="before") {active=str(frame,"step_id");pending=false;retry_observed=true;phase="retry_proposed";effect="observed_before";recovery="before";}
            if(observed=="terminal" && !restoring) {logical="ready_to_seal";phase="idle";needs_recovery=false;recovery="observed_terminal";}
        }
        if(kind=="9") {sealed_outcome=str(data,"outcome");cancel_ack=boolean(data,"cancel_acknowledged");if(!restoring) {logical=sealed_outcome;phase="sealed";needs_recovery=false;recovery="none";}}
    }
    void flush(const std::string& fault) {
        option(fault,{"none","error","unqualified"});
        if(!journal_available()) {journal.failed=true;unresolved("model_journal_dependency");return;}
        if(journal.failed || !journal.tail.empty()) {unresolved("model_journal_unwritable");return;}
        if(fault!="none" || !qualified) {journal.failed=true;unresolved(fault=="error"?"model_journal_flush_failed":"model_journal_flush_unqualified");return;}
        ++journal_flushes;const auto old=journal.stable;journal.stable=journal.frames.size();
        for(std::size_t i=old;i<journal.stable;++i)if(i>=journal.baseline)apply_stable(journal.frames[i]);
    }
    void target_flush(const std::string& fault,bool recovering) {
        option(fault,{"none","error","unqualified"});
        if(recovering) {if(worker!="exited" || !needs_recovery || unbound)bad("model_recovery_guard");fresh(true);}
        else {running();if(phase!="effect_returned" || effect!="reported_after")bad("model_target_flush_order");closure();if(!states("after"))bad("model_postcondition_failed");}
        if(fault!="none" || !qualified) {unresolved(fault=="error"?"model_target_flush_failed":"model_target_flush_unqualified");return;}
        ++target_flushes;for(const auto& pair:actual)durable[pair.first]=str(pair.second,"state_digest");flush_capture=capture_epoch;
        if(recovering)recovery_flushed=true;else {target_flushed=true;phase="target_flushed";}
    }
    void recover_prefix() {
        expected.clear();done.clear();active.clear();last_completed.clear();pending=false;intention_stable=false;retry_observed=false;cancel_durable=false;cancellation=false;cancel_ack=false;sealed_outcome.clear();
        for(const auto& p:bound)expected[p.first]=str(p.second,"state_digest");
        for(std::size_t i=0;i<journal.stable;++i)apply_stable(journal.frames[i],true);
        unbound=journal.stable<4;
        if(active.empty() || (!pending && !all_done()))active=next_step();
        worker="exited";logical="unresolved";needs_recovery=true;recovery=unbound?"unbound":"required";phase="recovery";
        effect=pending?"uncertain":"not_started";target_flushed=false;recovery_flushed=false;captured=false;exit_capture=capture_epoch;
    }
    void perform(const V& action) {
        encode(action,65536);const auto op=str(action,"op");const auto found=action_fields.find(op);if(found==action_fields.end())bad("model_action_unknown");
        std::vector<std::string> fields={"op","operation_id","attempt_id","worker_identity","worker_epoch"};fields.insert(fields.end(),found->second.begin(),found->second.end());keys(action,fields);
        if(identifier(action,"operation_id")!=operation || identifier(action,"attempt_id")!=attempt || identifier(action,"worker_identity")!=worker_identity || number(action,"worker_epoch")!=worker_epoch)bad("model_context_mismatch");
        if(actions>=1024)bad("model_action_limit");diagnostic.clear();
        if(op=="capture") {
            const auto epoch=number(action,"capture_epoch");const auto id=identifier(action,"observer_id");if(epoch<=capture_epoch)bad("model_capture_epoch");
            const auto& rows=get(action,"resources");if(rows.kind!=V::Kind::array || rows.items.size()!=actual.size())bad("model_capture_scope");auto expected_row=actual.begin();
            for(const auto& row:rows.items) {
                keys(row,{"resource","identity_digest","state_digest","epoch","available"});identifier(row,"resource");number(row,"epoch");checked_digest(str(row,"identity_digest"));checked_digest(str(row,"state_digest"));boolean(row,"available");
                if(encode(row)!=encode(expected_row->second))bad("model_capture_mismatch");++expected_row;
            }
            closure();capture_epoch=epoch;observer=id;captured=true;captured_generation=generation;
        } else if(op=="intention") {
            running();fresh();if(phase!="idle" || pending || cancellation)bad("model_intention_order");const auto name=identifier(action,"step_id");
            if(!has(selected,name) || done.count(name))bad("model_step_scope");const auto& s=step(name);for(const auto& dep:get(s,"depends_on").items)if(!done.count(str(dep)))bad("model_predecessor_incomplete");
            active=name;if(!states("before"))bad("model_precondition");pending=true;intention_stable=false;target_flushed=false;result_observed=false;effect="not_started";phase="intention_pending";
            append("5",evidence("before"),str(action,"fault"));
        } else if(op=="journal_flush")flush(str(action,"fault"));
        else if(op=="dispatch") {
            running();fresh();if(!pending || phase!="prepared" || !intention_stable || cancellation)bad("model_dispatch_order");if(!states("before"))bad("model_precondition");
            ++dispatches;phase="dispatched";effect="in_flight";dispatch_capture=capture_epoch;
        } else if(op=="effect_result") {
            const auto outcome=str(action,"outcome");option(outcome,{"after","before","mixed"});
            if(worker=="exited" || !pending || result_observed || (phase!="dispatched" && effect!="uncertain"))bad("model_effect_result_order");result_observed=true;
            bool bound_target=true;
            for(const auto& e:get(current(),"effects").items)if(str(e,"access")=="write") {
                const auto name=str(e,"resource");const auto& live=actual.at(name);const auto& original=bound.at(name);
                bound_target=bound_target && boolean(live,"available") && str(live,"identity_digest")==str(original,"identity_digest") && str(live,"epoch")==str(original,"epoch");
            }
            if(!bound_target) {phase="effect_observed_unresolved";effect="uncertain";unresolved("model_effect_target_changed");}
            else {
                if(outcome!="before")for(const auto& e:get(current(),"effects").items)if(str(e,"access")=="write") {
                    actual.at(str(e,"resource")).put("state_digest",V::string(outcome=="after"?str(e,"after_digest"):hashed("fake:mixed:"+str(e,"resource"))));++writes;
                }
                ++generation;captured=false;
                if(worker=="stalled" || needs_recovery || outcome!="after") {phase="effect_observed_unresolved";effect="uncertain";unresolved("model_effect_requires_reconciliation");}
                else {phase="effect_returned";effect="reported_after";}
            }
        } else if(op=="target_flush")target_flush(str(action,"fault"),false);
        else if(op=="verify") {
            running();fresh();if(phase!="target_flushed" || !target_flushed || number(action,"capture_epoch")!=capture_epoch || capture_epoch<=dispatch_capture || capture_epoch<=flush_capture)bad("model_verification_order");
            if(!states("after"))unresolved("model_postcondition_failed");else {phase="verified";effect="verified_after";}
        } else if(op=="completion") {
            running();fresh();if(phase!="verified" || !target_flushed || effect!="verified_after")bad("model_completion_order");phase="completion_pending";append("6",evidence("after"),str(action,"fault"));
        } else if(op=="cancel_request") {
            if(terminal() || unbound)bad("model_cancellation_order");cancellation=true;if(!cancel_durable)append("7",V::object().put("requested",V::boolean_value(true)),str(action,"fault"));else option(str(action,"fault"),{"none","before","torn"});
        } else if(op=="cancel_checkpoint") {
            const bool recovered=worker=="exited" && retry_observed && phase=="retry_proposed";
            if(recovered)fresh(true);else running();
            const bool undispatched=pending && effect=="not_started" && phase=="prepared";
            if(!cancellation || !cancel_durable || (!recovered && !undispatched && (pending || phase!="idle")))bad("model_cancellation_order");
            if(!last_completed.empty() && !boolean(get(step(last_completed),"recovery"),"cancellable_at_checkpoint"))bad("model_cancellation_checkpoint");
            cancel_ack=true;pending=false;phase="idle";needs_recovery=false;if(recovered)logical="ready_to_seal";
        } else if(op=="client_disconnect" || op=="client_reconnect")connected=op=="client_reconnect";
        else if(op=="timeout") {if(worker!="running")bad("model_timeout_order");worker="stalled";unresolved("model_worker_stalled");}
        else if(op=="worker_exit") {
            if(worker=="exited")bad("model_exit_order");worker="exited";exit_capture=capture_epoch;
            if(pending || phase!="idle" || (!all_done() && !cancel_ack))unresolved("model_worker_exited_unresolved");
            if(!pending && !all_done() && !cancel_ack) {active=next_step();intention_stable=false;}
        } else if(op=="crash") {
            const auto prefix=number(action,"prefix_entries",false);if(prefix<journal.stable || prefix>journal.frames.size())bad("model_crash_prefix");const bool torn=boolean(action,"torn_tail");
            if(torn && prefix==journal.frames.size() && journal.tail.empty())bad("model_crash_tail");
            const auto& persisted=get(action,"persist_after");if(persisted.kind!=V::Kind::array || persisted.items.size()>32)bad("model_crash_resources");std::string previous;
            for(const auto& item:persisted.items) {
                const auto name=str(item);if(!previous.empty() && previous>=name)bad("model_crash_resources");previous=name;bool found_effect=false;
                if(!active.empty())for(const auto& e:get(current(),"effects").items)if(str(e,"resource")==name && str(e,"access")=="write" && pending && (effect!="not_started")) {durable[name]=str(e,"after_digest");found_effect=true;}
                if(!found_effect)bad("model_crash_resources");
            }
            std::string tail=torn?(prefix<journal.frames.size()?encode(journal.frames[static_cast<std::size_t>(prefix)]).substr(0,encode(journal.frames[static_cast<std::size_t>(prefix)]).size()/2):journal.tail):"";
            journal.frames.resize(static_cast<std::size_t>(prefix));journal.stable=journal.frames.size();journal.baseline=journal.stable;journal.tail=tail;journal.failed=!tail.empty();journal.bytes=tail.size();
            for(const auto& f:journal.frames)journal.bytes+=encode(f).size();for(auto& p:actual)p.second.put("state_digest",V::string(durable.at(p.first)));
            ++generation;connected=false;recover_prefix();diagnostic="model_crash_requires_observation";
        } else if(op=="recovery_flush")target_flush(str(action,"fault"),true);
        else if(op=="reconcile") {
            const auto observed=str(action,"observed");option(observed,{"before","after","terminal"});
            if(worker!="exited" || !needs_recovery || unbound)bad("model_recovery_guard");fresh(true);
            if(number(action,"capture_epoch")!=capture_epoch || !recovery_flushed || capture_epoch<=flush_capture)bad("model_recovery_capture");
            if(observed=="terminal") {if(pending || (!all_done() && !cancel_ack && sealed_outcome.empty()))bad("model_recovery_guard");}
            else if(active.empty() || done.count(active))bad("model_recovery_guard");
            if(!states(observed))bad("model_recovery_state");
            if(observed=="after" && !intention_stable)bad("model_recovery_intention");
            phase="reconciliation_pending";append("8",evidence(observed),str(action,"fault"));
        } else if(op=="replace") {
            if(worker!="exited" || unbound || cancellation || all_done())bad("model_replace_guard");fresh(true);
            if(retry_observed && phase=="retry_proposed") {
                if(!states("before") || (intention_stable && !boolean(get(current(),"recovery"),"replayable")))bad("model_replay_forbidden");
            }else {
                if(needs_recovery || phase!="idle")bad("model_replace_guard");active=next_step();if(active.empty() || !states("before"))bad("model_precondition");
            }
            const auto new_id=identifier(action,"new_attempt_id"),new_worker=identifier(action,"new_worker_identity");const auto epoch=number(action,"new_worker_epoch");
            if(attempt_ids.count(new_id) || attempt_ids.size()>=attempts_limit || epoch<=worker_epoch)bad("model_attempt_limit_or_reuse");
            const auto proof=evidence("before");attempt_ids.insert(new_id);attempt=new_id;worker_identity=new_worker;worker_epoch=epoch;worker="prepared";phase="admission_pending";effect="not_started";result_observed=false;retry_observed=false;pending=false;captured=false;target_flushed=false;recovery_flushed=false;
            append("4",V::object().put("basis_admission_digest",V::string(digest_text(Receipt(definition,initial_admission).digest()))).put("checkpoint",proof),str(action,"fault"));
        } else if(op=="fork_journal") {
            if(worker!="exited" || !needs_recovery || unbound || (!journal.failed && journal.tail.empty() && (journal.frames.empty() || str(journal.frames.back(),"kind")!="9")))bad("model_fork_guard");fresh(true);
            if(retained.size()>=3)bad("model_generation_limit");retained.push_back(journal);Journal next;
            next.frames.assign(journal.frames.begin(),journal.frames.begin()+journal.stable);if(!next.frames.empty() && str(next.frames.back(),"kind")=="9")next.frames.pop_back();
            next.baseline=next.frames.size();for(const auto& f:next.frames)next.bytes+=encode(f).size();journal=std::move(next);++model_generation;
        } else if(op=="seal") {
            if(worker!="exited" || needs_recovery || pending || phase!="idle" || (!all_done() && !cancel_ack))bad("model_seal_guard");fresh();if(!states("terminal"))bad("model_postcondition_failed");
            phase="seal_pending";append("9",V::object().put("outcome",V::string(cancel_ack?"cancelled":"completed")).put("cancel_acknowledged",V::boolean_value(cancel_ack)),str(action,"fault"));
        } else if(op=="change_resource") {
            const auto name=identifier(action,"resource");const auto found_resource=actual.find(name);if(found_resource==actual.end())bad("model_resource");
            checked_digest(str(action,"identity_digest"));checked_digest(str(action,"state_digest"));number(action,"epoch");boolean(action,"available");
            for(const auto k:{"identity_digest","state_digest","epoch","available"})found_resource->second.put(k,get(action,k));++generation;captured=false;
        }
        ++actions;
    }
    V report() const {
        auto history=V::array();for(std::size_t i=0;i<retained.size();++i)history.items.push_back(V::object().put("generation",count(i+1)).put("entries",count(retained[i].frames.size())).put("stable_entries",count(retained[i].stable))
            .put("tail_bytes",count(retained[i].tail.size())).put("tail_digest",V::string(hashed(retained[i].tail))).put("log_digest",V::string(journal_digest(retained[i]))));
        auto rows=capture_rows();for(auto& r:rows.items)r.put("durable_state_digest",V::string(durable.at(str(r,"resource"))));
        const bool fresh_exit=captured && captured_generation==generation && capture_epoch>exit_capture;
        bool retirement=false;if(terminal() && worker=="exited" && fresh_exit && !needs_recovery) {try {closure();retirement=states("terminal");}catch(const DefinitionError&) {}}
        return V::object().put("scope",V::string("closed-fake-memory-guarded-journal-model")).put("authenticated",V::boolean_value(false)).put("authorizes_effects",V::boolean_value(false)).put("physical_durability_qualified",V::boolean_value(false)).put("file_io",V::boolean_value(false))
            .put("operation_id",V::string(operation)).put("attempt_id",V::string(attempt)).put("worker_identity",V::string(worker_identity)).put("worker_epoch",count(worker_epoch))
            .put("operation_status",V::string(logical)).put("worker_status",V::string(worker)).put("phase",V::string(phase)).put("step_id",V::string(active)).put("effect_certainty",V::string(effect))
            .put("stable_intention",V::boolean_value(intention_stable))
            .put("recovery_status",V::string(recovery)).put("cancellation_requested",V::boolean_value(cancellation)).put("cancellation_durable",V::boolean_value(cancel_durable)).put("cancellation_acknowledged",V::boolean_value(cancel_ack))
            .put("client_connected",V::boolean_value(connected)).put("capture_epoch",count(capture_epoch)).put("capture_current",V::boolean_value(captured && captured_generation==generation)).put("dependencies_retained",V::boolean_value(true)).put("retirement_eligible",V::boolean_value(retirement))
            .put("completed_steps",count(done.size())).put("actions",count(actions)).put("dispatches",count(dispatches)).put("resource_writes",count(writes)).put("target_flushes",count(target_flushes)).put("journal_flushes",count(journal_flushes))
            .put("diagnostic",V::string(diagnostic)).put("journal",V::object().put("generation",count(model_generation)).put("publisher_identity",V::string("fake:publisher")).put("publisher_epoch",count(model_generation)).put("entries",count(journal.frames.size())).put("stable_entries",count(journal.stable))
            .put("bytes",count(journal.bytes)).put("tail_bytes",count(journal.tail.size())).put("tail_digest",V::string(hashed(journal.tail))).put("log_digest",V::string(journal_digest(journal))).put("failed",V::boolean_value(journal.failed)).put("retained_generations",history))
            .put("resources",rows);
    }
};
GuardedModel::GuardedModel(const Definition& d,const std::vector<V>& receipts,const V& configuration):state_(new Impl(d,receipts,configuration)) {}
GuardedModel::~GuardedModel()=default;
V GuardedModel::snapshot() const {return state_->report();}
V GuardedModel::history() const {
    auto journals=V::array();const auto add=[&](const Journal& j) {
        auto frames=V::array();frames.items=j.frames;journals.items.push_back(V::object().put("events",frames).put("tail",V::string(j.tail)).put("stable_entries",count(j.stable)).put("digest",V::string(journal_digest(j))));
    };for(const auto& j:state_->retained)add(j);add(state_->journal);return journals;
}
V GuardedModel::apply(const V& action) {std::unique_ptr<Impl> next(new Impl(*state_));next->perform(action);state_.swap(next);return state_->report();}
}}}
