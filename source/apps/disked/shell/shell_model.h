#pragma once
#include "model.h"
#include "shell_lexer.h"
#include <deque>

namespace disked {
struct ShellPrompt {std::string text;unsigned cursor=0;};
class ShellModel final {
public:
    ShellModel(FrontendSession& session,const Registry& registry,json::Value discovery,FrontendHandler dispatch,bool history,CompletionPoll poll={});
    bool tick();
    void input(const TuiInput& event);
    std::vector<std::string> render(unsigned columns,unsigned rows,bool linear);
    std::vector<std::string> linear_records(std::uint64_t& after) const;
    ShellPrompt prompt(unsigned columns) const;
    bool done() const {return done_;}
    bool take_toggle() {const auto value=toggle_;toggle_=false;return value;}
    json::Value state() const;
private:
    enum class View {Editor,Review,Complete,Commands,Targets};
    struct Record {std::uint64_t sequence;std::vector<std::string> lines;std::size_t bytes;};
    FrontendSession& session_;
    const Registry& registry_;
    json::Value discovery_;
    FrontendHandler dispatch_;
    CompletionPoll poll_;
    std::shared_ptr<const GraphSnapshot> snapshot_;
    std::string editor_,draft_,notice_="Ready; input is inert",review_revision_;
    std::size_t cursor_=0,history_at_=0,history_bytes_=0,choice_=0,replace_begin_=0,replace_end_=0,scroll_=0,page_size_=1;
    std::deque<std::string> history_;
    std::deque<Record> transcript_;
    std::vector<std::string> candidates_;
    std::size_t transcript_bytes_=0;
    std::uint64_t sequence_=0,dropped_=0,requests_=0;
    bool history_enabled_=false,done_=false,toggle_=false,follow_=true;
    View view_=View::Editor;
    ParseResult reviewed_;
    Outcome last_;
    std::string pending_;
    bool pending_secret_=false;
    std::uint64_t pending_request_=0;
    void received(Outcome outcome,bool secret,bool latest);
    void record(const std::string& kind,const json::Value& value);
    void diagnostic(const std::string& code,std::size_t byte,std::size_t token=0);
    void invalidate();
    void review();
    void submit();
    void complete();
    void recall(int direction);
    bool available(const std::string& id) const;
    bool sensitive(const ParseResult& parsed) const;
    json::Value review_value() const;
    std::vector<std::string> content() const;
};
}
