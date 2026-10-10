#pragma once
#include "session.h"
#include <functional>
#include <set>

namespace disked {
enum class TuiKey {Text,Up,Down,PageUp,PageDown,Enter,Tab,BackTab,Backspace,Escape,F2,F3,F4,F5,F6,F9,F10,Left,Right,Home,End,Delete};
struct TuiInput {TuiKey key;std::string text;bool repeat=false;};
class TuiModel final {
public:
    TuiModel(FrontendSession& session,const Registry& registry,json::Value discovery,FrontendHandler dispatch,CompletionPoll poll={});
    bool tick();
    void input(const TuiInput& event);
    void stage(const std::string& command,const json::Value& parameters);
    std::vector<std::string> render(unsigned columns,unsigned rows,bool linear);
    bool done() const {return done_;}
    bool take_toggle();
    json::Value state() const;
private:
    enum class View {Inventory,Commands,Form,Review,Result};
    FrontendSession& session_;
    const Registry& registry_;
    json::Value discovery_;
    FrontendHandler dispatch_;
    CompletionPoll poll_;
    std::shared_ptr<const GraphSnapshot> snapshot_;
    View view_=View::Inventory;
    std::string focus_,inventory_focus_,command_,review_revision_,notice_="Ready";
    std::vector<std::string> fields_;
    json::Value parameters_=json::Value::object(),typed_=json::Value::object();
    json::Value shapes_=json::Value::object();
    std::string discriminator_;
    std::set<std::string> invalid_object_fields_;
    Outcome outcome_;
    json::Value earlier_=json::Value{};
    std::string pending_;
    std::uint64_t view_epoch_=0,pending_view_=0;
    std::size_t field_=0,scroll_=0,page_size_=1;
    std::uint64_t requests_=0;
    bool done_=false,toggle_=false,follow_focus_=true;
    std::vector<std::string> choices() const;
    bool available(const std::string& id) const;
    void move(int direction);
    void result(Outcome outcome);
    std::vector<std::string> body() const;
};
std::vector<std::string> tui_json_lines(const json::Value& value);
}
