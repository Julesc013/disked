#include "protocol.h"
#include <algorithm>
#include <set>

namespace disked {
using json::Value;
namespace {
bool string(const Value* v,bool nonempty=true) {
    return v && v->kind==Value::Kind::string && (!nonempty || !v->text.empty()) &&
        json::valid_utf8(v->text) && v->text.find('\0')==std::string::npos;
}
bool kind(const Value* v,Value::Kind k) {return v && v->kind==k;}
bool strings(const Value* v) {
    if(!kind(v,Value::Kind::array))return false;
    for(const auto& item:v->items)if(!string(&item))return false;
    return true;
}
Value envelope(const std::string& id,const std::string& status) {
    return Value::object().put("schema",Value::string("org.disked.response/1"))
        .put("request_id",Value::string(id)).put("status",Value::string(status))
        .put("operation_id",Value{}).put("result",Value{})
        .put("diagnostics",Value::array()).put("evidence",Value::array());
}
bool resource_failure(const std::string& code) {
    return code=="message_too_large" || code=="frame_limit_exceeded" || code=="depth_limit_exceeded" ||
        code=="value_limit_exceeded" || code=="string_limit_exceeded";
}
}
Value diagnostic(const std::string& code,Value parameters) {
    return Value::object().put("code",Value::string(code)).put("severity",Value::string("error"))
        .put("message_key",Value::string("disked."+code)).put("parameters",std::move(parameters))
        .put("platform_code",Value{}).put("remediation",Value::array());
}
Outcome completed(const std::string& id,Value result) {
    Outcome out;out.response=envelope(id,"completed").put("result",std::move(result));return out;
}
Outcome refused(const std::string& id,const std::string& code,int exit_code) {
    Outcome out;out.exit_code=exit_code;out.response=envelope(id,exit_code==4?"failed":"refused");
    out.response.fields["diagnostics"].items.push_back(diagnostic(code));return out;
}
Outcome process_request(const Registry& registry,const std::string& frame,const Handler& handler,const Handler& events) {
    Value value;
    try {value=json::parse(frame);}
    catch(const json::Error& e) {return refused("@unparsed",e.code);}
    const std::set<std::string> keys={"schema","request_id","command","parameters","required_features",
        "plan_digest","expected_revision","idempotency_key"};
    if(value.kind!=Value::Kind::object)return refused("@unparsed","invalid_request");
    for(const auto& pair:value.fields)if(!keys.count(pair.first))return refused("@unparsed","invalid_request");
    const auto* id=value.find("request_id"), *schema=value.find("schema"), *command=value.find("command");
    if(!string(id) || id->text.size()>128 || !string(schema) || !string(command) ||
        !kind(value.find("parameters"),Value::Kind::object) || !strings(value.find("required_features")))
        return refused("@unparsed","invalid_request");
    for(const auto* field:{"plan_digest","expected_revision"})if(const auto* hash=value.find(field)) {
        if(!string(hash) || hash->text.size()!=71 || hash->text.substr(0,7)!="sha256:" ||
            hash->text.find_first_not_of("0123456789abcdef",7)!=std::string::npos)return refused("@unparsed","invalid_request");
    }
    if(value.find("idempotency_key") && !string(value.find("idempotency_key")))return refused("@unparsed","invalid_request");
    if(schema->text!="org.disked.request/1")return refused(id->text,"incompatible_schema");
    const auto& features=value.find("required_features")->items;
    const auto* operation=value.find("parameters")->find("operation_id");
    const bool matching_profile=features.size()==1 && operation && operation->kind==Value::Kind::string &&
        ((features.front().text=="org.disked.fake-operation-events/1" && operation->text.compare(0,8,"fake-op:")==0) ||
         (features.front().text=="org.disked.acquisition-operation-events/1" && operation->text.compare(0,9,"image-op:")==0) ||
         (features.front().text=="org.disked.report-operation-events/1" && operation->text.compare(0,10,"report-op:")==0) ||
         (features.front().text=="org.disked.verification-operation-events/1" && operation->text.compare(0,10,"verify-op:")==0));
    const bool streaming=matching_profile && command->text=="operation.watch" && events;
    if(!features.empty() && !streaming)return refused(id->text,"unsupported_feature",3);
    const auto* descriptor=registry.command(command->text);
    if(!descriptor || command->text=="protocol.serve")return refused(id->text,"command_unavailable",3);
    // Revision-bound cached observation does not admit mutation authority.
    for(const auto* field:{"plan_digest","idempotency_key"})
        if(value.find(field))return refused(id->text,"unexpected_mutation_field");
    const auto* revision=value.find("expected_revision");
    if(revision && command->text!="target.list" && command->text!="target.inspect" &&
        command->text!="topology.show" && command->text!="capability.explain" && command->text!="health.assess")return refused(id->text,"unexpected_revision");
    const auto error=validate_parameters(registry,*descriptor,*value.find("parameters"));
    if(error=="syntax_unavailable")return refused(id->text,"command_unavailable",3);
    if(!error.empty())return refused(id->text,error);
    return (streaming?events:handler)(id->text,command->text,*value.find("parameters"),revision?revision->text:"");
}
std::string response_frame(const Value& response) {
    std::string bytes=json::dump(response,response_limits(response));bytes+='\n';
    return bytes;
}
bool acquisition_watch_response(const Value& response) {
    const auto* id=response.find("operation_id"),*result=response.find("result");
    if(!string(id) || id->text.size()!=41 || id->text.compare(0,9,"image-op:")!=0 ||
       id->text.find_first_not_of("0123456789abcdef",9)!=std::string::npos || !kind(result,Value::Kind::object))return false;
    const auto* scope=result->find("scope"),*request=result->find("request_kind"),*events=result->find("events");
    return string(scope) && scope->text=="ordinary-local-raw-file-acquisition" && string(request) &&
        request->text=="operation-observation" && kind(events,Value::Kind::array);
}
bool report_watch_response(const Value& response) {
    const auto id=response.find("operation_id"),result=response.find("result");
    if(!string(id) || id->text.size()!=42 || id->text.compare(0,10,"report-op:")!=0 || id->text.find_first_not_of("0123456789abcdef",10)!=std::string::npos || !kind(result,Value::Kind::object))return false;
    const auto scope=result->find("scope"),request=result->find("request_kind"),events=result->find("events");
    return report_response(response) && string(scope) && string(request) && request->text=="operation-observation" && kind(events,Value::Kind::array);
}
bool report_response(const Value& response) {
    const auto result=response.find("result");if(!kind(result,Value::Kind::object))return false;
    const auto scope=result->find("scope");if(!string(scope) || (scope->text!="recorded-acquisition-case-support-export" && scope->text!="recorded-acquisition-verification-support-export"))return false;
    const auto phase=result->find("phase"),request=result->find("request_kind");
    return (string(phase) && phase->text=="prepare") || (string(request) && (request->text=="export-execution" || request->text=="operation-observation"));
}
bool verification_response(const Value& response) {
    const auto result=response.find("result");if(!kind(result,Value::Kind::object))return false;
    const auto scope=result->find("scope");if(!string(scope) || scope->text!="recorded-acquired-image-verification")return false;
    const auto phase=result->find("phase"),request=result->find("request_kind");
    return (string(phase) && phase->text=="prepare") || (string(request) && (request->text=="verification-execution" || request->text=="operation-observation"));
}
json::Limits response_limits(const Value& response) {
    json::Limits limits;limits.bytes=1048575; // LF is inside the one MiB wire bound.
    if(report_response(response) || verification_response(response))limits.values=131072;return limits;
}
int serve(FILE* input,bool ndjson,const Registry& registry,const Handler& handler,const ResponseSink& output,const Handler& events) {
    std::size_t total=0,count=0;int exit_code=0;std::string frame;
    auto emit=[&](Outcome out) {exit_code=(std::max)(exit_code,out.exit_code);return output(out.response);};
    for(;;) {
        const int byte=std::fgetc(input);
        if(byte==EOF && std::ferror(input)) {emit(refused("@unparsed","input_error",4));return 4;}
        if(byte!=EOF && ++total>4194304) {return emit(refused("@unparsed","session_limit"))?(std::max)(exit_code,2):4;}
        const bool delimiter=ndjson && byte=='\n';
        if(byte==EOF || delimiter) {
            if(byte==EOF && ndjson && frame.empty())return exit_code;
            if(++count>256)return emit(refused("@unparsed","request_limit"))?(std::max)(exit_code,2):4;
            // LF/CRLF count toward the frame bound. Strip CR only for LF-delimited records.
            if(delimiter && frame.size()+1>65536)return emit(refused("@unparsed","message_too_large"))?(std::max)(exit_code,2):4;
            if(delimiter && !frame.empty() && frame.back()=='\r')frame.pop_back();
            auto out=process_request(registry,frame,handler,ndjson?events:Handler{});
            bool stop=false;
            for(const auto& d:out.response.find("diagnostics")->items)stop=stop || resource_failure(d.find("code")->text);
            if(!emit(std::move(out)))return 4;
            if(stop || byte==EOF)return exit_code;
            frame.clear();
        } else {
            if(frame.size()==65536)return emit(refused("@unparsed","message_too_large"))?(std::max)(exit_code,2):4;
            frame+=static_cast<char>(byte);
        }
    }
}
std::string validate_response(const Value& value) {
    if(value.kind!=Value::Kind::object || !string(value.find("schema")) || value.find("schema")->text!="org.disked.response/1")return "incompatible_schema";
    if(!string(value.find("request_id")) || !string(value.find("status")))return "invalid_response";
    const auto status=value.find("status")->text;
    const std::set<std::string> statuses={"completed","accepted_running","refused","failed","unknown","recovery_required"};
    if(!statuses.count(status))return "unknown_status";
    const auto* operation=value.find("operation_id"),*result=value.find("result"),*diagnostics=value.find("diagnostics");
    if(!(kind(operation,Value::Kind::null) || string(operation)) ||
        (status=="accepted_running" && !string(operation)) ||
        !(kind(result,Value::Kind::null) || kind(result,Value::Kind::object)) ||
        !kind(diagnostics,Value::Kind::array) || !strings(value.find("evidence")))return "invalid_response";
    if(const auto* features=value.find("required_features")) {
        if(!strings(features))return "invalid_response";
        if(!features->items.empty())return "unsupported_feature";
    }
    for(const auto& d:diagnostics->items) {
        if(!string(d.find("code")) || !string(d.find("message_key")) || !string(d.find("severity")) ||
            !kind(d.find("parameters"),Value::Kind::object) || !strings(d.find("remediation")) ||
            !(kind(d.find("platform_code"),Value::Kind::null) || string(d.find("platform_code"),false)))return "invalid_response";
        const auto severity=d.find("severity")->text;
        if(severity!="info" && severity!="warning" && severity!="error")return "invalid_response";
    }
    return "";
}
int response_exit(const Value& value) {
    if(!validate_response(value).empty())return 2;
    const auto status=value.find("status")->text;
    if(status=="completed")return 0;
    if(status=="accepted_running")return 5;
    if(status=="unknown")return 6;
    if(status=="recovery_required")return 7;
    if(status=="failed")return 4;
    // Refusal subclasses are stable diagnostics, not message text.
    for(const auto& d:value.find("diagnostics")->items) {
        const auto code=d.find("code")->text;
        if(code=="command_unavailable" || code=="frontend_unavailable" || code=="interaction_unavailable" || code=="unsupported_feature" || code=="operation_unavailable" ||
           code=="export_provider_unavailable" || code=="export_provider_refused" || code=="export_definition_grant" || code=="export_preparation_or_definition_refused" ||
           code=="verification_provider_unavailable" || code=="verification_provider_refused" || code=="verification_definition_grant" || code=="verification_preparation_or_definition_refused" ||
           code=="request_resource_limit" || code=="request_thread_unavailable" ||
           code=="memory_budget_unavailable" || code=="memory_budget_busy" || code=="memory_budget_mismatch" || code=="memory_budget_incompatible")return 3;
    }
    return 2;
}
}
