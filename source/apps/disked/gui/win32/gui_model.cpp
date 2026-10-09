#include "gui_model.h"
#include <algorithm>
#include <limits>

namespace disked {
using json::Value;
GuiModel::GuiModel(FrontendSession& session,const Registry& registry,Value discovery,FrontendHandler dispatch,CompletionPoll poll):
    session_(session),registry_(registry),discovery_(std::move(discovery)),dispatch_(std::move(dispatch)),poll_(std::move(poll)),snapshot_(session.snapshot()) {
    const auto& nodes=snapshot_->value().find("nodes")->items;
    if(!nodes.empty())focus_=target_focus_=nodes.front().find("id")->text;
}
void GuiModel::view_changed() {
    if(view_epoch_==(std::numeric_limits<std::uint64_t>::max)())throw std::runtime_error("frontend_epoch_limit");++view_epoch_;
}
bool GuiModel::tick() {
    Outcome value;if(!poll_ || !poll_(value))return false;
    const auto* id=value.response.find("request_id");
    if(pending_.empty() || !id || id->text!=pending_)throw std::runtime_error("frontend_completion_identity");
    pending_.clear();
    if(pending_view_==view_epoch_)result(std::move(value));
    else {earlier_=std::move(value.response);notice_="Earlier request finished; retained separately from the current view";}
    return true;
}
bool GuiModel::available(const std::string& id) const {
    if(id=="protocol.serve" || id=="shell.open" || id=="shell.close")return false;
    for(const auto& c:discovery_.find("commands")->items)
        if(c.find("id")->text==id)return c.find("availability")->text=="available";
    return false;
}
void GuiModel::navigate(bool commands) {
    view_changed();
    commands_=commands;form_=reviewed_=false;outcome_=Outcome{};
    focus_=commands?registry_.commands.items.front().find("id")->text:target_focus_;
    notice_="Choose an item, then Inspect / Open";
}
void GuiModel::focus(const std::string& id) {
    view_changed();
    const auto options=rows();
    for(const auto& row:options.items)if(row.find("id")->text==id) {
        focus_=id;if(!commands_)target_focus_=id;return;
    }
    // Missing focus is not rebound to a replacement row.
}
void GuiModel::result(Outcome outcome) {
    outcome_=std::move(outcome);
    notice_=outcome_.exit_code==5?"Operation still running; inspect using its operation ID":
        outcome_.exit_code==6?"Operation outcome unknown; inspect retained evidence":
        outcome_.exit_code?"Request refused or failed; inspect diagnostics":"Request completed";
}
void GuiModel::open() {
    view_changed();
    if(commands_) {stage(focus_,Value::object());return;}
    form_=reviewed_=false;
    auto selected=session_.act({ActionKind::Select,focus_,snapshot_->revision(),"gui:selection"});
    if(selected.exit_code)result(std::move(selected));
    else result(session_.act({ActionKind::Inspect,focus_,snapshot_->revision(),"gui:inspect"}));
}
void GuiModel::clear() {
    view_changed();
    reviewed_=false;
    result(session_.act({ActionKind::ClearSelection,"",snapshot_->revision(),"gui:selection"}));
}
void GuiModel::refresh() {
    view_changed();
    snapshot_=session_.snapshot();notice_="View refreshed; selected identity and staged revision are unchanged";
}
void GuiModel::stage(const std::string& command,const Value& supplied) {
    view_changed();
    form_=reviewed_=false;command_=command;fields_=Value::array();parameters_=Value::object();typed_=Value::object();outcome_=Outcome{};invalid_fields_.clear();
    if(!available(command)) {result(refused("gui","command_unavailable",3));return;}
    const auto* descriptor=registry_.command(command);
    const auto* schema=descriptor?registry_.parameter_schemas.find(descriptor->find("parameter_schema")->text):nullptr;
    if(!schema) {result(refused("gui","schema_unavailable",3));return;}
    discriminator_=form_discriminator(registry_,*descriptor);auto seed=supplied;
    if(!discriminator_.empty() && !seed.find(discriminator_))seed.put(discriminator_,Value::string(form_default(registry_,*descriptor)));
    try {shapes_=form_shapes(registry_,*descriptor,seed);}catch(const std::exception& e) {result(refused("gui",e.what(),3));return;}
    std::vector<std::string> names;if(!discriminator_.empty())names.push_back(discriminator_);
    for(const auto& pair:shapes_.fields)if(pair.first!=discriminator_)names.push_back(pair.first);
    for(const auto& name:names) {
        const auto& shape=*shapes_.find(name);std::size_t limit=0;
        try {limit=form_field_limit(shape);}catch(const std::exception& e) {result(refused("gui",e.what(),3));return;}
        if(fields_.items.size()==16) {result(refused("gui","form_unavailable",3));return;}
        std::string value;
        if(name=="target_id") {const auto selected=session_.selection();const auto* id=selected.find("target_id");if(id->kind==Value::Kind::string)value=id->text;}
        if(name=="operation")value="target.inspect";
        if(const auto* input=seed.find(name)) {
            try {value=form_field_text(shape,*input);}catch(...) {result(refused("gui","invalid_parameter"));return;}
        }
        if(value.size()>limit || !json::valid_utf8(value)) {result(refused("gui","form_limit"));return;}
        fields_.items.push_back(Value::string(name));parameters_.put(name,Value::string(value));
    }
    revision_=snapshot_->revision();form_=true;notice_="Edit, then review. Empty optional fields are omitted; booleans use true/false.";
}
void GuiModel::edit(const std::string& field,const std::string& value) {
    if(!form_ || !parameters_.find(field))return;
    view_changed();
    reviewed_=false;outcome_=Outcome{};
    // Retain bounded rejected editor text so Review does not replace it with an
    // older valid identity. A separate error bit prevents admission, including
    // when the private API supplies malformed or over-buffer input.
    if(value.size()>field_limit(field) || !json::valid_utf8(value) ||
       std::any_of(value.begin(),value.end(),[](unsigned char c){return c<32 || c==127;})) {
        invalid_fields_.insert(field);
        parameters_.put(field,Value::string(value.size()<=16388 && json::valid_utf8(value)?value:"[rejected invalid or oversized editor input]"));
        notice_="Invalid or oversized field; correct it before review";
    } else {
        if(field==discriminator_ && value!=parameters_.find(field)->text) {stage(command_,Value::object().put(field,Value::string(value)));return;}
        invalid_fields_.erase(field);parameters_.put(field,Value::string(value));notice_="Edited; review is required";
    }
}
std::size_t GuiModel::field_limit(const std::string& field) const {const auto* shape=shapes_.find(field);return shape?form_field_limit(*shape):4096;}
void GuiModel::review() {
    if(!form_)return;
    view_changed();
    reviewed_=false;outcome_=Outcome{};
    for(const auto& pair:parameters_.fields)if(pair.second.text.size()>field_limit(pair.first)) {notice_="form_limit; correct the field";return;}
    if(!invalid_fields_.empty()) {notice_="invalid_parameter; correct the field";return;}
    const auto error=form_parameters(registry_,*registry_.command(command_),parameters_,typed_);
    if(!error.empty()) {notice_=error+"; correct the fields";return;}
    reviewed_=true;notice_="Review the exact escaped request; Submit is a separate action";
}
void GuiModel::submit() {
    if(!form_ || !reviewed_)return;
    reviewed_=false; // Consume before dispatch, including refusals and exceptions.
    if(requests_==(std::numeric_limits<std::uint64_t>::max)()) {result(refused("gui","request_limit"));return;}
    view_changed();const auto id="gui:"+std::to_string(++requests_);
    auto reply=dispatch_(id,command_,typed_,FrontendSession::handles(command_)?revision_:"");
    if(reply.pending) {
        if(!pending_.empty())throw std::runtime_error("frontend_pending_limit");
        pending_=id;pending_view_=view_epoch_;outcome_=Outcome{};
        notice_="Waiting for request; outcome is not yet observed. Cached views remain usable.";
    } else result(std::move(reply.outcome));
}
void GuiModel::back() {view_changed();form_=reviewed_=false;outcome_=Outcome{};notice_="Ready";}
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
    Value current;
    if(outcome_.response.kind!=Value::Kind::null)current=outcome_.response;
    else if(form_)current=Value::object().put("command",Value::string(command_)).put("parameters",reviewed_?typed_:parameters_)
        .put("expected_revision",FrontendSession::handles(command_)?Value::string(revision_):Value{}).put("reviewed",Value::boolean_value(reviewed_));
    else current=Value::object().put("current",snapshot_->value()).put("proposed",Value{})
        .put("proposed_reason",Value::string("Planning is not implemented; no storage changes are proposed"));
    if(!pending_.empty())current.put("pending_request",Value::string(pending_));
    if(earlier_.kind!=Value::Kind::null)current.put("earlier_request",earlier_);
    return current;
}
Value GuiModel::state() const {
    return Value::object().put("commands",Value::boolean_value(commands_)).put("form",Value::boolean_value(form_))
        .put("reviewed",Value::boolean_value(reviewed_)).put("focus",Value::string(focus_)).put("notice",Value::string(notice_))
        .put("selection",session_.selection()).put("view_revision",Value::string(snapshot_->revision()))
        .put("command",Value::string(command_)).put("fields",fields_).put("parameters",parameters_)
        .put("requests",Value::string(std::to_string(requests_))).put("last_outcome",outcome_.response)
        .put("pending_request",Value::string(pending_)).put("earlier_request",earlier_);
}
std::string GuiModel::detail_text() const {
    // Two independently bounded replies plus private correlation fields. These
    // presentation limits do not enlarge the public protocol frame contract.
    json::Limits limits;limits.bytes=2*65536+1024;limits.values=2*8192+16;limits.depth=33;
    const bool expanded=acquisition_watch_response(outcome_.response) || acquisition_watch_response(earlier_) || report_watch_response(outcome_.response) || report_watch_response(earlier_);
    if(expanded)limits.bytes=2*1048575+1024;
    if(report_watch_response(outcome_.response) || report_watch_response(earlier_))limits.values=2*131072+16;
    std::string text;
    for(const auto& line:presentation_lines(details(),limits,expanded?8388608:1048576)) {text+=line;text+="\r\n";}
    return text;
}
}
