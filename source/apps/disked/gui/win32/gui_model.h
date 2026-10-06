#pragma once
#include "session.h"
#include <set>

namespace disked {
class GuiModel final {
public:
    GuiModel(FrontendSession& session,const Registry& registry,json::Value discovery,FrontendHandler dispatch,CompletionPoll poll={});
    bool tick();
    void navigate(bool commands);
    void focus(const std::string& id);
    void open();
    void clear();
    void refresh();
    void stage(const std::string& command,const json::Value& supplied);
    void edit(const std::string& field,const std::string& value);
    void review();
    void submit();
    void back();
    json::Value state() const;
    json::Value rows() const;
    json::Value details() const;
    std::string detail_text() const;
private:
    FrontendSession& session_;
    const Registry& registry_;
    json::Value discovery_;
    FrontendHandler dispatch_;
    CompletionPoll poll_;
    std::shared_ptr<const GraphSnapshot> snapshot_;
    bool commands_=false,form_=false,reviewed_=false;
    std::string focus_,target_focus_,command_,revision_,notice_="Ready";
    json::Value fields_=json::Value::array(),parameters_=json::Value::object();
    Outcome outcome_;
    json::Value earlier_=json::Value{};
    std::string pending_;
    std::uint64_t view_epoch_=0,pending_view_=0;
    std::set<std::string> invalid_fields_;
    std::uint64_t requests_=0;
    bool available(const std::string& id) const;
    void result(Outcome outcome);
    void view_changed();
};
}
