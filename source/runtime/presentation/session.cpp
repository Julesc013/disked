#include "session.h"
#include <limits>

namespace disked {
using json::Value;
FrontendSession::FrontendSession(const Registry& registry,const GraphInput& initial,ObservationPoll observations,HealthObservation health):
    registry_(registry),observations_(std::move(observations)),health_(std::move(health)) {publish(initial);}
bool FrontendSession::refresh_observations() {
    if(!observations_)return false;auto next=observations_();if(!next || next==observed_)return false;
    publish(*next);observed_=std::move(next);return true;
}
void FrontendSession::publish(const GraphInput& input) {
    if(epoch_==(std::numeric_limits<std::uint64_t>::max)())throw std::invalid_argument("epoch_limit");
    auto next=GraphSnapshot::create(input,epoch_+1);
    auto identities=identities_;
    for(const auto& node:next->value().find("nodes")->items) {
        const auto& id=node.find("id")->text;const auto& p=*node.find("properties");
        const auto identity=json::dump(Value::object().put("identity",*p.find("identity")).put("generation",*p.find("media_generation")));
        auto prior=identities.find(id);
        if(prior!=identities.end() && prior->second!=identity)throw std::invalid_argument("identity_reuse");
        identities[id]=identity;
    }
    if(identities.size()>1024)throw std::invalid_argument("identity_limit");
    // All potentially throwing work precedes these no-throw publications.
    identities_.swap(identities);snapshot_.swap(next);++epoch_;
}
Value FrontendSession::selection() const {
    return Value::object().put("target_id",selected_.empty()?Value{}:Value::string(selected_))
        .put("state",Value::string(selected_.empty()?"none":snapshot_->node(selected_)?"present":"missing"));
}
Outcome FrontendSession::act(const FrontendAction& action) {
    refresh_observations();return act_cached(action);
}
Outcome FrontendSession::act_cached(const FrontendAction& action) {
    if(action.expected_revision!=snapshot_->revision())return refused(action.request_id,"revision_conflict");
    if(action.kind==ActionKind::ClearSelection) {
        if(!action.target_id.empty())return refused(action.request_id,"invalid_action");
        selected_.clear();return completed(action.request_id,selection());
    }
    if(action.kind!=ActionKind::Select && action.kind!=ActionKind::Inspect)return refused(action.request_id,"invalid_action");
    const auto* node=snapshot_->node(action.target_id);
    if(!node)return refused(action.request_id,"target_not_found");
    if(action.kind==ActionKind::Select) {selected_=action.target_id;return completed(action.request_id,selection());}
    return completed(action.request_id,Value::object().put("scope",Value::string("fake-only"))
        .put("capture_id",*snapshot_->value().find("capture_id")).put("basis_revision",Value::string(snapshot_->revision())).put("target",*node));
}
bool FrontendSession::handles(const std::string& command) {
    return command=="target.list" || command=="target.inspect" || command=="topology.show" || command=="capability.explain" || command=="health.assess";
}
Value FrontendSession::assessment(const std::string& target,const std::string& operation) const {
    const auto& state=snapshot_->node(target)->find("properties")->find("state")->text;
    Value checks=Value::object(),blockers=Value::array();
    const bool cached_read=handles(operation) && operation!="health.assess";
    const bool health_read=operation=="health.assess" && static_cast<bool>(health_);
    for(const auto* check:{"implementation","provider","qualification","host_media","permission","policy","freshness","target_state","resources","recovery"}) {
        const std::string name=check;std::string status="satisfied";
        if(name=="qualification")status="unknown";
        if((name=="implementation" || name=="provider") && !cached_read && !health_read)status="unavailable";
        // Selecting a port does not prove an observer for this exact node.
        if(name=="provider" && health_read)status="unknown";
        if(name=="permission" && state=="denied")status="denied";
        if((name=="freshness" && state=="stale") || (name=="target_state" && state=="unknown"))status="unknown";
        if((name=="policy" || name=="recovery") && !cached_read && !health_read)status="unavailable";
        checks.put(name,Value::string(status));
        if(status!="satisfied")blockers.items.push_back(Value::string(name+":"+status));
    }
    Value alternatives=Value::array();alternatives.items.push_back(Value::string("inspect_cached_observations"));
    return Value::object().put("schema",Value::string("org.disked.capability-assessment/1"))
        .put("operation",Value::string(operation)).put("target_id",Value::string(target))
        .put("basis_revision",Value::string(snapshot_->revision())).put("provider_reference",Value::string("provider.fake.bootstrap/1"))
        .put("checks",std::move(checks)).put("execution_eligible",Value::boolean_value(false)).put("blockers",std::move(blockers))
        .put("alternatives",std::move(alternatives)).put("authorizes_execution",Value::boolean_value(false));
}
Outcome FrontendSession::dispatch(const std::string& request,const std::string& command,const Value& parameters,const std::string& revision) {
    const auto* descriptor=registry_.command(command);
    if(!handles(command) || !descriptor)return refused(request,"command_unavailable",3);
    const auto error=validate_parameters(registry_,*descriptor,parameters);
    if(!error.empty())return refused(request,error);
    refresh_observations();
    if(!revision.empty() && revision!=snapshot_->revision())return refused(request,"revision_conflict");
    if(command=="topology.show")return completed(request,snapshot_->value());
    if(command=="target.list") {
        Value ids=Value::array();for(const auto& node:snapshot_->value().find("nodes")->items)ids.items.push_back(*node.find("id"));
        return completed(request,Value::object().put("scope",Value::string("fake-only")).put("graph",snapshot_->value()).put("target_ids",std::move(ids)));
    }
    const auto& target=parameters.find("target_id")->text;
    if(command=="target.inspect")return act_cached({ActionKind::Inspect,target,revision.empty()?snapshot_->revision():revision,request});
    if(!snapshot_->node(target))return refused(request,"target_not_found");
    if(command=="health.assess") {
        const auto& node=*snapshot_->node(target);const auto& state=node.find("properties")->find("state")->text;
        if(state=="stale")return refused(request,"health_observation_stale");
        if(state=="denied")return refused(request,"health_observation_denied",3);
        if(!health_)return refused(request,"health_observer_unavailable",3);
        Value policy=Value::object();
        for(const auto& item:std::vector<std::pair<const char*,const char*>>{{"identifiers","include_identifiers"},{"raw_values","include_raw"},{"interpretations","include_interpretations"},{"customer_data","include_customer_data"}}) {
            const auto* flag=parameters.find(item.second);policy.put(item.first,Value::boolean_value(flag && flag->boolean));
        }
        return health_(request,node,snapshot_->revision(),policy);
    }
    const auto& operation=parameters.find("operation")->text;
    if(!registry_.command(operation))return refused(request,"operation_unavailable",3);
    return completed(request,Value::object().put("scope",Value::string("fake-only")).put("assessment",assessment(target,operation)));
}
std::string presentation_json(const Value& value,json::Limits limits) {
    const auto utf8=json::dump(value,limits);std::string ascii;ascii.reserve(utf8.size());
    const char* hex="0123456789abcdef";
    auto escape=[&](unsigned cp) {ascii+="\\u";for(int shift=12;shift>=0;shift-=4)ascii+=hex[(cp>>shift)&15];};
    for(std::size_t i=0;i<utf8.size();) {
        unsigned cp=static_cast<unsigned char>(utf8[i++]);
        if(cp<0x7f) {ascii+=static_cast<char>(cp);continue;}
        if(cp==0x7f) {escape(cp);continue;}
        unsigned count=cp<0xe0?1:cp<0xf0?2:3;cp&=count==1?0x1f:count==2?0x0f:0x07;
        while(count--)cp=(cp<<6)|(static_cast<unsigned char>(utf8[i++])&0x3f);
        if(cp<=0xffff)escape(cp);else {cp-=0x10000;escape(0xd800+(cp>>10));escape(0xdc00+(cp&0x3ff));}
    }
    return ascii;
}
std::vector<std::string> presentation_lines(const Value& value,json::Limits limits,std::size_t display_bytes) {
    if(!display_bytes || display_bytes>8388608)throw std::length_error("presentation_limit");
    const auto text=presentation_json(value,limits);std::vector<std::string> lines;std::string line;
    if(text.size()+2>display_bytes)throw std::length_error("presentation_limit");
    bool quoted=false,escape=false;unsigned depth=0;
    auto emit=[&]() {if(!line.empty())lines.push_back(line);line.assign(depth*2,' ');};
    for(char c:text) {
        if(quoted) {line+=c;if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quoted=false;continue;}
        if(c=='"') {quoted=true;line+=c;}
        else if(c=='{' || c=='[') {line+=c;++depth;emit();}
        else if(c=='}' || c==']') {if(line.find_first_not_of(' ')!=std::string::npos)emit();--depth;line.assign(depth*2,' ');line+=c;}
        else if(c==',') {line+=c;emit();}
        else if(c==':')line+=": ";else line+=c;
    }
    if(!line.empty())lines.push_back(line);
    std::size_t bytes=0;for(const auto& row:lines)bytes+=row.size()+2;
    // Whitespace is dispensable; valid bounded content is not. Compact escaped
    // JSON retains every value when indentation would exceed the display budget.
    if(bytes>display_bytes)return {text};return lines;
}
std::vector<std::string> observation_lines(const Value& value) {
    json::Limits limits;const bool expanded=acquisition_watch_response(value) || report_watch_response(value) || verification_response(value);
    if(expanded)limits=response_limits(value);
    return presentation_lines(value,limits,expanded?4194304:1048576);
}

}
