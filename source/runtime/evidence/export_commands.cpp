#include "export_commands.h"
#include "report_operation.h"
#include <set>
namespace disked {
namespace {
using V=json::Value;namespace r=report_operation;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("export_reply_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw std::invalid_argument("export_reply_shape");return p.text;}
bool flag(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::boolean)throw std::invalid_argument("export_reply_shape");return p.boolean;}
bool operation(const V& id) {return id.kind==V::Kind::string && id.text.size()==42 && id.text.compare(0,10,"report-op:")==0 && id.text.find_first_not_of("0123456789abcdef",10)==std::string::npos;}
void digest(const std::string& s,bool prefix=true) {
    const std::size_t offset=prefix?7:0;if(s.size()!=offset+64 || (prefix && s.compare(0,7,"sha256:")) || s.find_first_not_of("0123456789abcdef",offset)!=s.npos)throw std::invalid_argument("export_reply_digest");
}
V annotate(V value,bool observation,const V* definition=nullptr) {
    if(definition)value=export_claims(std::move(value),*definition);
    return value.put("request_kind",V::string(observation?"operation-observation":"export-execution"));
}
Outcome translate(const std::string& request,const V& reply,bool observation,const V* expected=nullptr) {
    if(reply.kind!=V::Kind::object || reply.fields.size()!=6 || text(reply,"schema")!="org.disked.report-admission-prototype/1")throw std::invalid_argument("export_reply_shape");
    const auto status=text(reply,"status"),code=text(reply,"diagnostic"),platform=text(reply,"platform_code");const auto& id=get(reply,"operation_id");
    if(!json::decimal_u64(platform) || std::stoull(platform)>0xffffffffULL || code.size()>256)throw std::invalid_argument("export_reply_shape");
    if(id.kind!=V::Kind::null && !operation(id))throw std::invalid_argument("export_reply_identity");
    auto value=get(reply,"value");if(value.kind!=V::Kind::object)throw std::invalid_argument("export_reply_shape");
    const std::set<std::string> keys={"definition","definition_digest","state","last_digest","history_complete","worker_observation","cancellation_request","admission"};
    for(const auto& pair:value.fields)if(!keys.count(pair.first))throw std::invalid_argument("export_reply_shape");
    const auto reviewed=value.find("definition"),hash=value.find("definition_digest"),state=value.find("state");
    if(reviewed) {
        r::validate_definition(*reviewed);if(!hash || hash->kind!=V::Kind::string || hash->text!=r::digest(*reviewed))throw std::invalid_argument("export_reply_digest");
        if(expected && json::dump(*reviewed,r::definition_limits())!=json::dump(*expected,r::definition_limits()))throw std::invalid_argument("export_reply_definition");
        value.put("state_directory",get(get(*reviewed,"store"),"path"));
    } else if(hash)throw std::invalid_argument("export_reply_shape");
    if(state && state->kind!=V::Kind::null) {if(!reviewed || !operation(id))throw std::invalid_argument("export_reply_identity");r::validate_observation(*state,*reviewed,id.text);}
    if(value.find("last_digest"))digest(text(value,"last_digest"),false);
    if(value.find("history_complete"))flag(value,"history_complete");
    if(value.find("worker_observation")) {
        const auto observed=text(value,"worker_observation");if(observed!="running" && observed!="exited" && observed!="unavailable" && observed!="reused_identity" && observed!="changed_image_path")throw std::invalid_argument("export_reply_state");
    }
    if(value.find("admission") && text(value,"admission")!="unresolved")throw std::invalid_argument("export_reply_state");
    if(value.find("cancellation_request")) {
        const auto cancel=text(value,"cancellation_request");if(!observation || (cancel!="requested" && cancel!="too_late") || !state || state->kind==V::Kind::null ||
            (cancel=="too_late")!=(text(*state,"phase")=="finished"))throw std::invalid_argument("export_reply_state");
    }
    if(status=="completed" || status=="accepted_running") {
        if(!reviewed || !state || state->kind==V::Kind::null || !operation(id) || !flag(value,"history_complete") || !value.find("last_digest") || !value.find("worker_observation"))throw std::invalid_argument("export_reply_state");
        const bool finished=text(*state,"phase")=="finished";
        if(!finished && text(value,"worker_observation")!="running")throw std::invalid_argument("export_reply_state");
        if(status=="accepted_running" && (observation || finished))throw std::invalid_argument("export_reply_state");
        if(status=="completed" && !observation && !finished)throw std::invalid_argument("export_reply_state");
    } else if(status=="refused") {
        if(id.kind!=V::Kind::null || !value.fields.empty())throw std::invalid_argument("export_reply_state");
    } else if(status!="unknown")throw std::invalid_argument("export_reply_status");
    auto out=completed(request,annotate(value,observation,reviewed?reviewed:expected));out.response.put("operation_id",id);
    if(status=="accepted_running") {out.response.put("status",V::string(status));out.exit_code=5;}
    else if(status=="unknown") {out.response.put("status",V::string(status));out.exit_code=6;}
    else if(status=="refused") {out.response.put("status",V::string(status));out.exit_code=3;out.response.fields["diagnostics"].items.push_back(diagnostic("export_provider_refused"));}
    else if(!observation) {
        const auto logical=text(get(*state,"outcome"),"status");
        if(logical=="unknown") {out.response.put("status",V::string("unknown"));out.exit_code=6;}
        else if(logical!="completed") {out.response.put("status",V::string("failed"));out.exit_code=4;out.response.fields["diagnostics"].items.push_back(diagnostic("export_execution_not_completed"));}
    }
    if(!code.empty())out.response.fields["diagnostics"].items.push_back(diagnostic(code));
    if(platform!="0" && !out.response.fields["diagnostics"].items.empty())out.response.fields["diagnostics"].items.back().put("platform_code",V::string(platform));
    json::dump(out.response,response_limits(out.response));return out;
}
}
V export_claims(V value,const V& definition) {
    r::validate_definition(definition);const bool joined=r::joined_definition(definition);
    value.put("scope",V::string(joined?"recorded-acquisition-verification-support-export":"recorded-acquisition-case-support-export")).put("authenticity",V::string("not_established"));
    if(joined)return value.put("custody_authentication",V::string("not_established")).put("current_image_state",V::string("not_established")).put("power_loss_persistence",V::string("not_established"));
    return value.put("current_image_verification",V::string("not_performed"));
}
Outcome export_observation(const std::string& request,const V& reply) {
    try {return translate(request,reply,true);}catch(const std::exception&) {
        auto out=completed(request,annotate(V::object().put("request_state",V::string("unresolved")),true));out.response.put("status",V::string("unknown"));out.exit_code=6;
        if(const auto id=reply.find("operation_id"))if(operation(*id))out.response.put("operation_id",*id);
        out.response.fields["diagnostics"].items.push_back(diagnostic("export_observation_unresolved"));return out;
    }
}
Outcome export_unresolved_request(const std::string& request,const V& p) {
    const auto id=p.find("operation_id");const bool observing=id && operation(*id);auto value=V::object().put("request_state",V::string("unresolved"));
    if(const auto path=p.find("state_directory"))if(path->kind==V::Kind::string)value.put("state_directory",*path);
    if(const auto hash=p.find("definition_digest"))if(hash->kind==V::Kind::string)value.put("definition_digest",*hash);
    if(const auto d=p.find("definition")) {
        try {
            r::validate_definition(*d);
            if(text(p,"definition_digest")==r::digest(*d))value=export_claims(value,*d).put("state_directory",get(get(*d,"store"),"path"));
        }catch(const std::exception&) {} // Never guess a source profile.
    }
    value.put("request_kind",V::string(observing?"operation-observation":"export-execution"));
    auto out=completed(request,value);out.exit_code=6;out.response.put("status",V::string("unknown"));
    if(observing)out.response.put("operation_id",*id);out.response.fields["diagnostics"].items.push_back(diagnostic("request_wait_expired"));return out;
}
Outcome dispatch_export(const Registry& registry,const std::string& request,const V& parameters,const ExportActions& ports) {
    bool invoked=false;V reply;
    try {
        const auto descriptor=registry.command("evidence.export");if(!descriptor)return refused(request,"command_unavailable",3);
        const auto error=validate_parameters(registry,*descriptor,parameters);if(!error.empty())return refused(request,error);
        auto incoming=V::object().put("schema",V::string("org.disked.request/1")).put("request_id",V::string(request))
            .put("command",V::string("evidence.export")).put("parameters",parameters).put("required_features",V::array());
        json::Limits input_limits;input_limits.bytes=65535;json::dump(incoming,input_limits);
        if(text(parameters,"phase")=="prepare") {
            if(!ports.prepare)return refused(request,"export_provider_unavailable",3);const auto prepared=ports.prepare(parameters);
            if(prepared.kind!=V::Kind::object || prepared.fields.size()!=2)throw std::invalid_argument("export_preparation_shape");
            r::validate_definition(get(prepared,"definition"));if(text(prepared,"definition_digest")!=r::digest(get(prepared,"definition")))throw std::invalid_argument("export_preparation_digest");
            const auto& d=get(prepared,"definition");const auto& joint=get(d,"export");const auto& effect=get(joint,"effect");
            const bool joined=r::joined_definition(d);if(joined!=(parameters.find("collection_path")!=nullptr))throw std::invalid_argument("export_preparation_profile");
            const auto& source=joined?get(get(joint,"sources"),"case"):get(joint,"source");
            if((joined?text(get(joint,"report"),"case_operation_id"):text(get(joint,"case"),"operation_id"))!=text(parameters,"case_operation_id") || text(get(source,"store"),"path")!=text(parameters,"case_directory") ||
               text(get(get(effect,"resources"),"destination"),"location")!=text(parameters,"destination") || text(get(d,"store"),"path")!=text(parameters,"state_directory"))throw std::invalid_argument("export_preparation_inputs");
            if(joined && (text(get(get(joint,"sources"),"collection"),"path")!=text(parameters,"collection_path") ||
                          text(get(get(joint,"sources"),"collection"),"digest")!=text(parameters,"collection_digest")))throw std::invalid_argument("export_preparation_inputs");
            const auto& policy=get(get(effect,"artifact"),"policy");for(const auto n:{"identifiers","raw_values","interpretations","customer_data"}) {
                const auto selected=parameters.find(std::string("include_")+n);if(flag(policy,n)!=(selected && selected->kind==V::Kind::boolean && selected->boolean))throw std::invalid_argument("export_preparation_policy");
            }
            auto report=export_claims(prepared,d);report.put("phase",V::string("prepare")).put("execution_admitted",V::boolean_value(false));
            // Review must fit a subsequent complete execution request. The
            // projection has no execution port and creates no authority.
            auto projected=V::object().put("phase",V::string("execute")).put("definition",d).put("definition_digest",get(prepared,"definition_digest"));
            for(const auto n:{"case_read","report_write","store_write","host_effects"})projected.put(std::string("allow_")+n,V::boolean_value(true));
            if(joined)projected.put("allow_collection_read",V::boolean_value(true));
            auto frame=V::object().put("schema",V::string("org.disked.request/1")).put("request_id",V::string(std::string(128,'\1')))
                .put("command",V::string("evidence.export")).put("parameters",projected).put("required_features",V::array());
            json::Limits request_limits;request_limits.bytes=65535;json::dump(frame,request_limits);
            auto out=completed(request,report);json::dump(out.response,response_limits(out.response));return out;
        }
        const auto& reviewed=get(parameters,"definition");r::validate_definition(reviewed);
        if(text(parameters,"definition_digest")!=r::digest(reviewed))return refused(request,"export_definition_grant",3);
        auto grant=V::object().put("definition_digest",get(parameters,"definition_digest"));
        for(const auto n:{"case_read","report_write","store_write","host_effects"}) {
            if(!flag(parameters,(std::string("allow_")+n).c_str()))return refused(request,"export_definition_grant",3);
            grant.put(n,V::boolean_value(true));
        }
        if(r::joined_definition(reviewed)) {
            if(!flag(parameters,"allow_collection_read"))return refused(request,"export_definition_grant",3);
            grant.put("collection_read",V::boolean_value(true));
        }
        r::validate_grant(grant,reviewed);if(!ports.execute)return refused(request,"export_provider_unavailable",3);
        invoked=true;reply=ports.execute(reviewed,grant);
        if(const auto value=reply.find("value")) {
            if(const auto d=value->find("definition"))if(json::dump(*d,r::definition_limits())!=json::dump(reviewed,r::definition_limits()))throw std::invalid_argument("export_reply_definition");
            if(const auto h=value->find("definition_digest"))if(h->kind!=V::Kind::string || h->text!=r::digest(reviewed))throw std::invalid_argument("export_reply_definition");
        }
        auto out=translate(request,reply,false,&reviewed);
        out.response.fields["result"].put("state_directory",get(get(reviewed,"store"),"path")).put("definition_digest",get(parameters,"definition_digest"));json::dump(out.response,response_limits(out.response));return out;
    }catch(const std::exception&) {
        if(!invoked)return refused(request,"export_preparation_or_definition_refused",3);
        auto recovery=annotate(V::object().put("request_state",V::string("unresolved")),false,&get(parameters,"definition"))
            .put("state_directory",get(get(get(parameters,"definition"),"store"),"path")).put("definition_digest",get(parameters,"definition_digest"));
        auto out=completed(request,recovery);out.response.put("status",V::string("unknown"));out.exit_code=6;
        if(const auto id=reply.find("operation_id"))if(operation(*id))out.response.put("operation_id",*id);
        out.response.fields["diagnostics"].items.push_back(diagnostic("export_execution_unresolved"));return out;
    }
}
}
