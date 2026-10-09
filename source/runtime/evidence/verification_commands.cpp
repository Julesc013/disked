#include "verification_commands.h"
#include "verification_operation.h"
#include <set>
namespace disked {
namespace {
using V=json::Value;namespace r=verification_operation;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("verification_reply_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw std::invalid_argument("verification_reply_shape");return p.text;}
bool flag(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::boolean)throw std::invalid_argument("verification_reply_shape");return p.boolean;}
bool operation(const V& v) {return v.kind==V::Kind::string && v.text.size()==42 && v.text.compare(0,10,"verify-op:")==0 && v.text.find_first_not_of("0123456789abcdef",10)==v.text.npos;}
void one(const std::string& s,std::initializer_list<const char*> values) {for(const auto v:values)if(s==v)return;throw std::invalid_argument("verification_reply_state");}
V annotate(V v) {return v.put("scope",V::string("recorded-acquired-image-verification")).put("authenticity",V::string("not_established"))
    .put("latest_image_state",V::string("not_established")).put("source_preservation",V::string("not_established"))
    .put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));}
V kind(V v,bool observing) {return annotate(v).put("request_kind",V::string(observing?"operation-observation":"verification-execution"));}
json::Limits public_definition_limits() {return json::Limits{};}
void public_request(const std::string& request,const V& parameters) {
    // A budget projection only. It neither dispatches a request nor grants effects.
    auto limits=json::Limits{};--limits.bytes; // Reserve the framing LF.
    json::dump(V::object().put("schema",V::string("org.disked.request/1")).put("request_id",V::string(request))
        .put("command",V::string("image.verify")).put("parameters",parameters).put("required_features",V::array()),limits);
}
void executable_review(const V& prepared) {
    auto parameters=V::object().put("phase",V::string("execute")).put("definition",get(prepared,"definition")).put("definition_digest",get(prepared,"definition_digest"));
    for(const auto n:{"case_read","image_read","map_read","store_write","host_effects","private_metadata"})parameters.put(std::string("allow_")+n,V::boolean_value(true));
    // The largest legal 128-byte request ID may require six JSON bytes per byte.
    // These flags are a nonexecuting budget projection, not an authority receipt.
    public_request(std::string(128,'\x01'),parameters);
}
void sized(const Outcome& out) {json::dump(out.response,response_limits(out.response));}
Outcome translate(const std::string& request,const V& reply,bool observing) {
    if(reply.kind!=V::Kind::object || reply.fields.size()!=6 || text(reply,"schema")!="org.disked.verification-admission-prototype/1")throw std::invalid_argument("verification_reply_shape");
    const auto status=text(reply,"status"),code=text(reply,"diagnostic"),platform=text(reply,"platform_code");const auto& id=get(reply,"operation_id");
    if(!json::decimal_u64(platform) || std::stoull(platform)>0xffffffffULL || code.size()>128 || code.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")!=code.npos ||
       (id.kind!=V::Kind::null && !operation(id)))throw std::invalid_argument("verification_reply_identity");
    auto value=get(reply,"value");if(value.kind!=V::Kind::object)throw std::invalid_argument("verification_reply_shape");
    const std::set<std::string> keys={"definition","definition_digest","state","request_binding","last_digest","history_complete","worker_observation","cancellation_request","admission","collection_validation","attachment_applicability"};
    for(const auto& p:value.fields)if(!keys.count(p.first))throw std::invalid_argument("verification_reply_shape");
    const auto d=value.find("definition"),digest=value.find("definition_digest"),state=value.find("state");
    if(d) {r::validate_definition(*d);if(!digest || digest->kind!=V::Kind::string || digest->text!=r::digest(*d))throw std::invalid_argument("verification_reply_digest");value.put("state_directory",get(get(*d,"store"),"path"));}
    else if(digest || state)throw std::invalid_argument("verification_reply_shape");
    if(state && state->kind!=V::Kind::null) {
        if(!operation(id))throw std::invalid_argument("verification_reply_identity");r::validate_observation(*state,*d,id.text);
        auto binding=get(*state,"binding");binding.fields.erase("process_id");binding.fields.erase("process_created");
        if(json::dump(binding)!=json::dump(get(value,"request_binding")))throw std::invalid_argument("verification_reply_binding");
    }else if(value.find("request_binding"))throw std::invalid_argument("verification_reply_binding");
    if(value.find("last_digest")) {const auto hash=text(value,"last_digest");if(hash.size()!=64 || hash.find_first_not_of("0123456789abcdef")!=hash.npos)throw std::invalid_argument("verification_reply_digest");}
    if(value.find("history_complete"))flag(value,"history_complete");
    if(value.find("worker_observation"))one(text(value,"worker_observation"),{"running","exited","unavailable","reused_identity","changed_image_path"});
    if(value.find("admission") && text(value,"admission")!="unresolved")throw std::invalid_argument("verification_reply_state");
    if(value.find("collection_validation")) {
        if(!state || state->kind==V::Kind::null || text(value,"collection_validation")!="passed" || text(get(*state,"retention"),"state")!="verified" || !value.find("attachment_applicability"))throw std::invalid_argument("verification_reply_retention");
    }else if(value.find("attachment_applicability"))throw std::invalid_argument("verification_reply_retention");
    if(value.find("attachment_applicability"))one(text(value,"attachment_applicability"),{"applicable","changed","unavailable"});
    if(value.find("cancellation_request")) {
        const auto cancel=text(value,"cancellation_request");one(cancel,{"requested","too_late"});
        if(!observing || !state || state->kind==V::Kind::null || (cancel=="too_late")!=(text(*state,"phase")=="finished"))throw std::invalid_argument("verification_reply_state");
    }
    if(status=="completed" || status=="accepted_running") {
        if(!d || !state || state->kind==V::Kind::null || !operation(id) || !flag(value,"history_complete") || !value.find("last_digest") || !value.find("worker_observation"))throw std::invalid_argument("verification_reply_state");
        const bool finished=text(*state,"phase")=="finished";
        if(!finished && text(value,"worker_observation")!="running")throw std::invalid_argument("verification_reply_state");
        if(status=="accepted_running" && (observing || finished))throw std::invalid_argument("verification_reply_state");
        if(status=="completed" && !observing && !finished)throw std::invalid_argument("verification_reply_state");
        if(finished && text(get(*state,"retention"),"state")=="verified" && !value.find("collection_validation"))throw std::invalid_argument("verification_reply_retention");
    }else if(status=="refused") {if(id.kind!=V::Kind::null || !value.fields.empty())throw std::invalid_argument("verification_reply_state");}
    else if(status!="unknown")throw std::invalid_argument("verification_reply_state");
    auto out=completed(request,kind(value,observing));out.response.put("operation_id",id);
    if(status=="accepted_running") {out.response.put("status",V::string(status));out.exit_code=5;}
    else if(status=="unknown") {out.response.put("status",V::string(status));out.exit_code=6;}
    else if(status=="refused") {out.response.put("status",V::string(status));out.exit_code=3;out.response.fields["diagnostics"].items.push_back(diagnostic("verification_provider_refused"));}
    else if(!observing) {
        const auto disposition=text(*state,"disposition");const auto& outcome=get(*state,"outcome");const auto& retention=get(*state,"retention");
        if(disposition=="unknown" || text(retention,"state")=="uncertain" || (outcome.kind!=V::Kind::null && text(outcome,"status")=="unknown") ||
           (value.find("attachment_applicability") && text(value,"attachment_applicability")!="applicable")) {out.response.put("status",V::string("unknown"));out.exit_code=6;}
        else if(disposition!="completed" || outcome.kind==V::Kind::null || text(outcome,"status")!="matched" || text(retention,"state")!="verified") {
            out.response.put("status",V::string("failed"));out.exit_code=4;out.response.fields["diagnostics"].items.push_back(diagnostic("verification_execution_not_matched"));
        }
    }
    if(!code.empty())out.response.fields["diagnostics"].items.push_back(diagnostic(code));
    if(platform!="0" && !out.response.fields["diagnostics"].items.empty())out.response.fields["diagnostics"].items.back().put("platform_code",V::string(platform));sized(out);return out;
}
Outcome unknown(const std::string& request,const V& reply,V retained,bool observing) {
    auto out=completed(request,kind(retained.put("request_state",V::string("unresolved")),observing));out.response.put("status",V::string("unknown"));out.exit_code=6;
    if(const auto id=reply.find("operation_id"))if(operation(*id))out.response.put("operation_id",*id);
    out.response.fields["diagnostics"].items.push_back(diagnostic(observing?"verification_observation_unresolved":"verification_execution_unresolved"));sized(out);return out;
}
}
Outcome verification_observation(const std::string& request,const V& reply) {
    try {return translate(request,reply,true);}catch(const std::exception&) {return unknown(request,reply,V::object(),true);}
}
Outcome verification_unresolved_request(const std::string& request,const V& p) {
    const auto id=p.find("operation_id");const bool observing=id && operation(*id);auto value=V::object().put("request_state",V::string("unresolved"));
    if(const auto path=p.find("state_directory"))if(path->kind==V::Kind::string)value.put("state_directory",*path);
    if(const auto d=p.find("definition"))if(const auto store=d->find("store"))if(const auto path=store->find("path"))if(path->kind==V::Kind::string)value.put("state_directory",*path);
    if(const auto digest=p.find("definition_digest"))if(digest->kind==V::Kind::string)value.put("definition_digest",*digest);
    auto out=completed(request,kind(value,observing));out.exit_code=6;out.response.put("status",V::string("unknown"));
    if(observing)out.response.put("operation_id",*id);out.response.fields["diagnostics"].items.push_back(diagnostic("request_wait_expired"));return out;
}
Outcome dispatch_verification(const Registry& registry,const std::string& request,const V& parameters,const VerificationActions& ports) {
    bool invoked=false;V reply;auto recovery=V::object();
    try {
        const auto descriptor=registry.command("image.verify");if(!descriptor)return refused(request,"command_unavailable",3);
        const auto error=validate_parameters(registry,*descriptor,parameters);if(!error.empty())return refused(request,error);
        try {public_request(request,parameters);}catch(const json::Error&) {return refused(request,"parameter_limit");}
        if(text(parameters,"phase")=="prepare") {
            if(!ports.prepare)return refused(request,"verification_provider_unavailable",3);const auto prepared=ports.prepare(parameters);
            if(prepared.kind!=V::Kind::object || prepared.fields.size()!=2)throw std::invalid_argument("verification_preparation_shape");const auto& d=get(prepared,"definition");
            r::validate_definition(d);json::dump(d,public_definition_limits());if(text(prepared,"definition_digest")!=r::digest(d))throw std::invalid_argument("verification_preparation_digest");
            executable_review(prepared);
            if(text(d,"case_operation_id")!=text(parameters,"case_operation_id") || text(get(get(d,"case_source"),"store"),"path")!=text(parameters,"case_directory") ||
               text(get(get(d,"image_binding"),"image"),"path")!=text(parameters,"image") || text(get(get(d,"image_binding"),"map"),"path")!=text(parameters,"map") ||
               text(get(d,"store"),"path")!=text(parameters,"state_directory"))throw std::invalid_argument("verification_preparation_inputs");
            auto result=annotate(prepared).put("phase",V::string("prepare")).put("execution_admitted",V::boolean_value(false));auto out=completed(request,result);sized(out);return out;
        }
        const auto& d=get(parameters,"definition");r::validate_definition(d);json::dump(d,public_definition_limits());
        if(text(parameters,"definition_digest")!=r::digest(d))return refused(request,"verification_definition_grant",3);
        auto grant=V::object().put("definition_digest",get(parameters,"definition_digest"));
        for(const auto n:{"case_read","image_read","map_read","store_write","host_effects","private_metadata"}) {
            if(!flag(parameters,(std::string("allow_")+n).c_str()))return refused(request,"verification_definition_grant",3);grant.put(n,V::boolean_value(true));
        }
        r::validate_grant(grant,d);if(!ports.execute)return refused(request,"verification_provider_unavailable",3);
        recovery.put("state_directory",get(get(d,"store"),"path")).put("definition_digest",get(parameters,"definition_digest"));invoked=true;reply=ports.execute(d,grant);
        if(const auto value=reply.find("value")) {
            if(const auto selected=value->find("definition"))if(json::dump(*selected,r::definition_limits())!=json::dump(d,r::definition_limits()))throw std::invalid_argument("verification_reply_definition");
            if(const auto hash=value->find("definition_digest"))if(hash->kind!=V::Kind::string || hash->text!=r::digest(d))throw std::invalid_argument("verification_reply_definition");
        }
        auto out=translate(request,reply,false);out.response.fields["result"].put("state_directory",get(get(d,"store"),"path")).put("definition_digest",get(parameters,"definition_digest"));sized(out);return out;
    }catch(const std::exception&) {if(!invoked)return refused(request,"verification_preparation_or_definition_refused",3);return unknown(request,reply,recovery,false);}
}
}
