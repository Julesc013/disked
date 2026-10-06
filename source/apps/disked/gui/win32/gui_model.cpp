#include "gui_model.h"
#include <algorithm>
#include <limits>

namespace disked {
using json::Value;
GuiModel::GuiModel(FrontendSession& session,const Registry& registry,Value discovery,Handler dispatch):
    session_(session),registry_(registry),discovery_(std::move(discovery)),dispatch_(std::move(dispatch)),snapshot_(session.snapshot()) {
    const auto& nodes=snapshot_->value().find("nodes")->items;
    if(!nodes.empty())focus_=target_focus_=nodes.front().find("id")->text;
}
bool GuiModel::available(const std::string& id) const {
    if(id=="protocol.serve" || id=="shell.open" || id=="shell.close")return false;
    for(const auto& c:discovery_.find("commands")->items)
        if(c.find("id")->text==id)return c.find("availability")->text=="available";
    return false;
}
void GuiModel::navigate(bool commands) {
    commands_=commands;form_=reviewed_=false;outcome_=Outcome{};
    focus_=commands?registry_.commands.items.front().find("id")->text:target_focus_;
    notice_="Choose an item, then Inspect / Open";
}
void GuiModel::focus(const std::string& id) {
    const auto options=rows();
    for(const auto& row:options.items)if(row.find("id")->text==id) {
        focus_=id;if(!commands_)target_focus_=id;return;
    }
    // Missing focus is not rebound to a replacement row.
}
void GuiModel::result(Outcome outcome) {
    outcome_=std::move(outcome);
    notice_=outcome_.exit_code==5?"Operation accepted; inspect using its operation ID":
        outcome_.exit_code==6?"Operation outcome unknown; inspect retained evidence":
        outcome_.exit_code?"Request refused or failed; inspect diagnostics":"Request completed";
}
void GuiModel::open() {
    if(commands_) {stage(focus_,Value::object());return;}
    form_=reviewed_=false;
    auto selected=session_.act({ActionKind::Select,focus_,snapshot_->revision(),"gui:selection"});
    if(selected.exit_code)result(std::move(selected));
    else result(session_.act({ActionKind::Inspect,focus_,snapshot_->revision(),"gui:inspect"}));
}
void GuiModel::clear() {
    reviewed_=false;
    result(session_.act({ActionKind::ClearSelection,"",snapshot_->revision(),"gui:selection"}));
}
void GuiModel::refresh() {
    snapshot_=session_.snapshot();notice_="View refreshed; selected identity and staged revision are unchanged";
}
void GuiModel::stage(const std::string& command,const Value& supplied) {
    form_=reviewed_=false;command_=command;fields_=Value::array();parameters_=Value::object();outcome_=Outcome{};invalid_fields_.clear();
    if(!available(command)) {result(refused("gui","command_unavailable",3));return;}
    const auto* descriptor=registry_.command(command);
    const auto* schema=descriptor?registry_.parameter_schemas.find(descriptor->find("parameter_schema")->text):nullptr;
    if(!schema) {result(refused("gui","schema_unavailable",3));return;}
    for(const auto& pair:schema->find("properties")->fields) {
        if(fields_.items.size()==2 || pair.second.find("type")->text!="string") {result(refused("gui","form_unavailable",3));return;}
        std::string value;
        if(pair.first=="target_id") {const auto selected=session_.selection();const auto* id=selected.find("target_id");if(id->kind==Value::Kind::string)value=id->text;}
        if(pair.first=="operation")value="target.inspect";
        if(const auto* input=supplied.find(pair.first)) {
            if(input->kind!=Value::Kind::string) {result(refused("gui","invalid_parameter"));return;}
            value=input->text;
        }
        if(value.size()>4096 || !json::valid_utf8(value)) {result(refused("gui","form_limit"));return;}
        fields_.items.push_back(Value::string(pair.first));parameters_.put(pair.first,Value::string(value));
    }
    revision_=snapshot_->revision();form_=true;notice_="Edit parameters, then review. No request has run.";
}
void GuiModel::edit(const std::string& field,const std::string& value) {
    if(!form_ || !parameters_.find(field))return;
    reviewed_=false;outcome_=Outcome{};
    // Retain bounded rejected editor text so Review does not replace it with an
    // older valid identity. A separate error bit prevents admission, including
    // when the private API supplies malformed or over-buffer input.
    if(value.size()>4096 || !json::valid_utf8(value) ||
       std::any_of(value.begin(),value.end(),[](unsigned char c){return c<32 || c==127;})) {
        invalid_fields_.insert(field);
        parameters_.put(field,Value::string(value.size()<=16388 && json::valid_utf8(value)?value:"[rejected invalid or oversized editor input]"));
        notice_="Invalid or oversized field; correct it before review";
    } else {invalid_fields_.erase(field);parameters_.put(field,Value::string(value));notice_="Edited; review is required";}
}
void GuiModel::review() {
    if(!form_)return;
    reviewed_=false;outcome_=Outcome{};
    for(const auto& pair:parameters_.fields)if(pair.second.text.size()>4096) {notice_="form_limit; correct the field";return;}
    if(!invalid_fields_.empty()) {notice_="invalid_parameter; correct the field";return;}
    const auto error=validate_parameters(registry_,*registry_.command(command_),parameters_);
    if(!error.empty()) {notice_=error+"; correct the fields";return;}
    reviewed_=true;notice_="Review the exact escaped request; Submit is a separate action";
}
void GuiModel::submit() {
    if(!form_ || !reviewed_)return;
    reviewed_=false; // Consume before dispatch, including refusals and exceptions.
    if(requests_==(std::numeric_limits<std::uint64_t>::max)()) {result(refused("gui","request_limit"));return;}
    result(dispatch_("gui:"+std::to_string(++requests_),command_,parameters_,FrontendSession::handles(command_)?revision_:""));
}
void GuiModel::back() {form_=reviewed_=false;outcome_=Outcome{};notice_="Ready";}
Value GuiModel::rows() const {
    auto result=Value::array();
    if(commands_)for(const auto& c:registry_.commands.items) {
        const auto id=c.find("id")->text;
        result.items.push_back(Value::object().put("id",Value::string(id))
            .put("state",Value::string(id=="protocol.serve"?"transport-only":available(id)?"available":"unavailable")));
    } else for(const auto& n:snapshot_->value().find("nodes")->items)
        result.items.push_back(Value::object().put("id",*n.find("id")).put("state",*n.find("properties")->find("state")));
    return result;
}
Value GuiModel::details() const {
    if(outcome_.response.kind!=Value::Kind::null)return outcome_.response;
    if(form_)return Value::object().put("command",Value::string(command_)).put("parameters",parameters_)
        .put("expected_revision",Value::string(revision_)).put("reviewed",Value::boolean_value(reviewed_));
    return Value::object().put("current",snapshot_->value()).put("proposed",Value{})
        .put("proposed_reason",Value::string("Planning is not implemented; no storage changes are proposed"));
}
Value GuiModel::state() const {
    return Value::object().put("commands",Value::boolean_value(commands_)).put("form",Value::boolean_value(form_))
        .put("reviewed",Value::boolean_value(reviewed_)).put("focus",Value::string(focus_)).put("notice",Value::string(notice_))
        .put("selection",session_.selection()).put("view_revision",Value::string(snapshot_->revision()))
        .put("command",Value::string(command_)).put("fields",fields_).put("parameters",parameters_)
        .put("requests",Value::string(std::to_string(requests_))).put("last_outcome",outcome_.response);
}
}
