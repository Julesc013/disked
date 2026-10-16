#include "commands.h"
#include "pipeline.h"
#include "portable/hash/sha256.h"
#include <utility>

namespace disked {
namespace {
using V=json::Value;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw AcquisitionCommandError("acquisition_command_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw AcquisitionCommandError("acquisition_command_shape");return p.text;}
std::string digest(const V& v) {
    const auto bytes=json::dump(v);unsigned char hash[32];disked::sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),hash);
    const char alphabet[]="0123456789abcdef";std::string result="sha256:";for(const auto b:hash) {result+=alphabet[b>>4];result+=alphabet[b&15];}return result;
}
bool operation_id(const V& v) {return v.kind==V::Kind::string && v.text.size()==41 && v.text.compare(0,9,"image-op:")==0 && v.text.find_first_not_of("0123456789abcdef",9)==std::string::npos;}
const char* scope(bool logical) {
    return logical ? "ordinary-local-fat-file-extraction" : "ordinary-local-raw-file-acquisition";
}
bool logical_definition(const V& definition) {
    return text(definition,"schema")=="org.disked.acquisition-worker-definition/2";
}
Outcome translate(const std::string& request,const V& reply,bool observation,bool logical=false) {
    if(reply.kind!=V::Kind::object || reply.fields.size()!=6 || text(reply,"schema")!="org.disked.acquisition-admission-prototype/1")throw AcquisitionCommandError("acquisition_reply_shape");
    const auto status=text(reply,"status"),code=text(reply,"diagnostic");const auto& id=get(reply,"operation_id");
    const auto platform=text(reply,"platform_code");if(!json::decimal_u64(platform) || std::stoull(platform)>0xffffffffULL)throw AcquisitionCommandError("acquisition_reply_shape");
    if(id.kind!=V::Kind::null && !operation_id(id))throw AcquisitionCommandError("acquisition_reply_identity");
    if(status=="accepted_running" && !operation_id(id))throw AcquisitionCommandError("acquisition_reply_identity");
    auto value=get(reply,"value");if(value.kind!=V::Kind::object)throw AcquisitionCommandError("acquisition_reply_shape");
    if(const auto d=value.find("definition"))logical=logical_definition(*d);
    value.put("scope",V::string(observation && !value.find("definition") ? "ordinary-local-file-acquisition" : scope(logical))).put("request_kind",V::string(observation?"operation-observation":"acquisition-execution"));
    auto out=completed(request,value);out.response.put("operation_id",id);
    if(status=="accepted_running") {
        const auto& state=get(value,"state");
        if(text(state,"phase")!="active" || get(state,"quiescent").kind!=V::Kind::boolean || get(state,"quiescent").boolean ||
           get(state,"outcome").kind!=V::Kind::null || json::dump(get(get(state,"binding"),"operation_id"))!=json::dump(id))
            throw AcquisitionCommandError("acquisition_reply_state");
        out.response.put("status",V::string(status));out.exit_code=5;
    }
    else if(status=="unknown") {out.response.put("status",V::string(status));out.exit_code=6;}
    else if(status=="refused") {
        if(id.kind!=V::Kind::null || value.find("state"))throw AcquisitionCommandError("acquisition_reply_state");
        out.response.put("status",V::string(status));out.exit_code=3;
    }
    else if(status!="completed")throw AcquisitionCommandError("acquisition_reply_status");
    else if(!observation) {
        const auto& state=get(value,"state");const auto completion_status=text(get(state,"outcome"),"status");
        if(text(state,"phase")!="finished" || get(state,"quiescent").kind!=V::Kind::boolean || !get(state,"quiescent").boolean)throw AcquisitionCommandError("acquisition_reply_state");
        const auto& binding=get(state,"binding");const auto& reviewed=get(value,"definition");const auto& outcome=get(state,"outcome");
        if(json::dump(get(binding,"operation_id"))!=json::dump(id) || text(binding,"definition_digest")!=digest(reviewed) ||
           text(value,"definition_digest")!=digest(reviewed))throw AcquisitionCommandError("acquisition_reply_identity");
        if(text(binding,"image_digest")!=text(reviewed,"image_digest") || text(binding,"host_id")!=text(reviewed,"host_id") ||
           text(binding,"capture_epoch")!=text(get(reviewed,"plan"),"capture_epoch"))throw AcquisitionCommandError("acquisition_reply_identity");
        for(const auto name:{"checkpoint_bytes","source_bytes","substituted_bytes"})
            if(text(state,name)!=text(outcome,name))throw AcquisitionCommandError("acquisition_reply_coverage");
        const auto plan=acquisition::prepare(get(reviewed,"plan"));
        if(completion_status=="completed" || completion_status=="completed_with_substitution") {
            const auto covered=text(outcome,"checkpoint_bytes"),source=text(outcome,"source_bytes"),zeros=text(outcome,"substituted_bytes");
            if(!json::decimal_u64(covered) || !json::decimal_u64(source) || !json::decimal_u64(zeros) ||
               std::stoull(covered)!=plan.bytes || std::stoull(source)>plan.bytes || std::stoull(zeros)!=plan.bytes-std::stoull(source) ||
               (completion_status=="completed")!=(std::stoull(zeros)==0) || get(outcome,"uncertain_effect").kind!=V::Kind::boolean || get(outcome,"uncertain_effect").boolean)
                throw AcquisitionCommandError("acquisition_reply_coverage");
        }
        if(completion_status!="completed" && completion_status!="completed_with_substitution") {
            out.response.put("status",V::string("failed"));out.exit_code=4;
            out.response.fields["diagnostics"].items.push_back(diagnostic(completion_status=="paused"?"acquisition_incomplete_paused":"acquisition_execution_not_completed"));
        }
    }
    if(!code.empty())out.response.fields["diagnostics"].items.push_back(diagnostic(code));
    if(platform!="0" && !out.response.fields["diagnostics"].items.empty())out.response.fields["diagnostics"].items.back().put("platform_code",V::string(platform));
    json::dump(out.response);return out;
}
void definition(const Registry& registry,const V& value,bool logical) {
    auto descriptor=V::object().put("syntax_status",V::string("defined")).put("parameter_schema",V::string(logical?"urn:disked:schema:acquisition-worker-definition:2":"urn:disked:schema:acquisition-worker-definition:1"));
    const auto error=validate_parameters(registry,descriptor,value);if(!error.empty())throw AcquisitionCommandError("acquisition_definition_shape");
    acquisition::prepare(get(value,"plan"));
    const auto& request=get(value,"request");const auto& plan=get(value,"plan");
    if(logical && json::dump(get(request,"logical_source"))!=json::dump(get(plan,"logical_source")))
        throw AcquisitionCommandError("acquisition_definition_selection");
    if(text(request,"chunk_bytes")!=text(plan,"chunk_bytes") || text(request,"retry_limit")!=text(plan,"retry_limit") ||
       text(request,"read_policy")!=text(plan,"read_policy") || text(request,"substitution")!=text(plan,"substitution"))
        throw AcquisitionCommandError("acquisition_definition_options");
}
}
Outcome acquisition_observation(const std::string& request,const V& reply) {
    try {return translate(request,reply,true);}
    catch(const std::exception&) {
        auto out=refused(request,"acquisition_observation_unresolved",4);out.exit_code=6;out.response.put("status",V::string("unknown"));
        if(const auto id=reply.find("operation_id"))if(operation_id(*id))out.response.put("operation_id",*id);
        return out;
    }
}
Outcome acquisition_unresolved_request(const Registry& registry,const std::string& request,
    const V& parameters,const std::string& command) {
    auto value=V::object().put("request_state",V::string("unresolved"));
    const auto phase=parameters.find("phase"),id=parameters.find("operation_id");
    const bool observing=(command=="operation.inspect" || command=="operation.cancel.request" || command=="operation.watch") && id && operation_id(*id);
    const bool acquiring=command=="image.acquire" || command=="filesystem.extract";
    const bool preparing=acquiring && phase && phase->kind==V::Kind::string && phase->text=="prepare";
    const bool executing=acquiring && phase && phase->kind==V::Kind::string && phase->text=="execute";
    value.put("request_kind",V::string(observing?"operation-observation":preparing?"acquisition-preparation":executing?"acquisition-execution":"acquisition-request"));
    const auto keep_path=[&](const V& path) {
        if(path.kind!=V::Kind::string || path.text.empty() || path.text.size()>1024 || path.text.find('\0')!=std::string::npos || !json::valid_utf8(path.text))throw AcquisitionCommandError("acquisition_unresolved_path");
        value.put("state_directory",path);
    };
    try {
        json::Limits bounds;bounds.bytes=65535;json::dump(parameters,bounds);
        const auto descriptor=registry.command(command);
        if(!descriptor || !validate_parameters(registry,*descriptor,parameters).empty())throw AcquisitionCommandError("acquisition_unresolved_shape");
        if(observing || preparing) {
            if(const auto path=parameters.find("state_directory"))keep_path(*path);
        } else if(executing) {
            const auto& reviewed=get(parameters,"definition");definition(registry,reviewed,command=="filesystem.extract");
            const auto hash=digest(reviewed);
            if(text(parameters,"definition_digest")!=hash)throw AcquisitionCommandError("acquisition_unresolved_digest");
            keep_path(get(get(reviewed,"store"),"path"));value.put("definition_digest",V::string(hash));
        }
    } catch(const std::exception&) {} // No I/O, no guessed reviewed routing.
    auto out=completed(request,std::move(value));out.exit_code=6;out.response.put("status",V::string("unknown"));
    if(observing)out.response.put("operation_id",*id);
    out.response.fields["diagnostics"].items.push_back(diagnostic("request_wait_expired"));return out;
}
Outcome dispatch_acquisition(const Registry& registry,const std::string& request,const V& parameters,const AcquisitionActions& actions,const std::string& command) {
    bool execution_invoked=false;V worker_reply;
    try {
        if(command!="image.acquire" && command!="filesystem.extract")return refused(request,"command_unavailable",3);
        const bool logical=command=="filesystem.extract";
        const auto descriptor=registry.command(command);if(!descriptor)return refused(request,"command_unavailable",3);
        const auto error=validate_parameters(registry,*descriptor,parameters);if(!error.empty())return refused(request,error);
        if(text(parameters,"phase")=="prepare") {
            if(!actions.prepare)return refused(request,"acquisition_provider_unavailable",3);
            const auto prepared=actions.prepare(parameters);if(prepared.kind!=V::Kind::object || prepared.fields.size()!=2)throw AcquisitionCommandError("acquisition_preparation_shape");
            definition(registry,get(prepared,"definition"),logical);if(text(prepared,"definition_digest")!=digest(get(prepared,"definition")))throw AcquisitionCommandError("acquisition_preparation_digest");
            auto report=prepared;report.put("phase",V::string("prepare")).put("execution_admitted",V::boolean_value(false))
                .put("scope",V::string(scope(logical))).put("source_consistency",V::string("live-uncoordinated"));
            return completed(request,report);
        }
        const auto& reviewed=get(parameters,"definition");definition(registry,reviewed,logical);
        if(text(parameters,"definition_digest")!=digest(reviewed))return refused(request,"acquisition_worker_grant",3);
        auto grant=V::object().put("definition_digest",get(parameters,"definition_digest"));
        for(const auto name:{"source_read","destination_write","map_write","host_effects"}) {
            const auto& allowed=get(parameters,(std::string("allow_")+name).c_str());
            if(allowed.kind!=V::Kind::boolean || !allowed.boolean)return refused(request,"acquisition_worker_grant",3);
            grant.put(name,allowed);
        }
        if(!actions.execute)return refused(request,"acquisition_provider_unavailable",3);
        execution_invoked=true;worker_reply=actions.execute(reviewed,grant);
        if(const auto value=worker_reply.find("value")) {
            if(const auto returned=value->find("definition"))if(json::dump(*returned)!=json::dump(reviewed))throw AcquisitionCommandError("acquisition_reply_definition");
            if(const auto hash=value->find("definition_digest"))if(hash->kind!=V::Kind::string || hash->text!=digest(reviewed))throw AcquisitionCommandError("acquisition_reply_definition");
        }
        return translate(request,worker_reply,false,logical);
    } catch(const std::exception& error) {
        if(execution_invoked) {
            auto recovery=V::object().put("request_state",V::string("unresolved"));
            recovery.put("state_directory",get(get(get(parameters,"definition"),"store"),"path")).put("definition_digest",get(parameters,"definition_digest"));
            auto out=completed(request,recovery);
            if(const auto id=worker_reply.find("operation_id"))if(operation_id(*id))out.response.put("operation_id",*id);
            out.response.put("status",V::string("unknown"));out.exit_code=6;out.response.fields["diagnostics"].items.push_back(diagnostic("acquisition_execution_unresolved"));return out;
        }
        const auto native=dynamic_cast<const AcquisitionCommandError*>(&error);
        auto out=refused(request,native?native->what():"acquisition_preparation_refused",3);
        if(native && native->platform_code)out.response.fields["diagnostics"].items.back().put("platform_code",V::string(std::to_string(native->platform_code)));
        return out;
    }
}
}
