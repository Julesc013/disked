#include "shell_model.h"
#include <algorithm>
#include <limits>
#include <set>

namespace disked {
using json::Value;
namespace {
constexpr std::size_t max_line=shell_line_bytes,max_history=65536,max_transcript=262144,max_acquisition_transcript=8388608;
std::string text(const Value& value,const std::string& key) {const auto* p=value.find(key);return p?p->text:"";}
std::string display(const std::string& value) {
    json::Limits limits;limits.bytes=2*shell_line_bytes+2;limits.string_bytes=shell_line_bytes;
    return presentation_json(Value::string(value),limits);
}
std::size_t previous(const std::string& text,std::size_t cursor) {
    if(cursor) {--cursor;while(cursor && (static_cast<unsigned char>(text[cursor])&0xc0)==0x80)--cursor;}return cursor;
}
std::size_t next(const std::string& text,std::size_t cursor) {
    if(cursor<text.size()) {++cursor;while(cursor<text.size() && (static_cast<unsigned char>(text[cursor])&0xc0)==0x80)++cursor;}return cursor;
}
std::vector<std::string> wrap(const std::vector<std::string>& lines,unsigned columns) {
    std::vector<std::string> out;
    for(const auto& line:lines) {if(line.empty())out.push_back("");for(std::size_t at=0;at<line.size();at+=columns)out.push_back(line.substr(at,columns));}return out;
}
bool truth(const Value* value) {return value && value->kind==Value::Kind::boolean && value->boolean;}
std::string words(const Value& descriptor) {
    std::string out;for(const auto& w:descriptor.find("words")->items) {if(!out.empty())out+=' ';out+=w.text;}return out;
}
}
ShellModel::ShellModel(FrontendSession& session,const Registry& registry,Value discovery,FrontendHandler dispatch,bool history,CompletionPoll poll):
    session_(session),registry_(registry),discovery_(std::move(discovery)),dispatch_(std::move(dispatch)),poll_(std::move(poll)),snapshot_(session.snapshot()),history_enabled_(history) {
    record("session",Value::object().put("host",Value::string(session_.cached_observations()?"local cached observations":"local fake composition"))
        .put("history",Value::string(history?"session-only; 32 entries/64 KiB":"off"))
        .put("controls",Value::string("F9 review, fresh F9 submit; Enter displays inert input; F10/Ctrl+C closes")));
}
bool ShellModel::tick() {
    Outcome value;if(!poll_ || !poll_(value))return false;
    const auto* id=value.response.find("request_id");
    if(pending_.empty() || !id || id->text!=pending_)throw std::runtime_error("frontend_completion_identity");
    pending_.clear();received(std::move(value),pending_secret_,pending_request_==requests_ && view_==View::Editor && editor_.empty());return true;
}
bool ShellModel::available(const std::string& id) const {
    if(id=="protocol.serve" || id=="shell.open")return false;
    for(const auto& c:discovery_.find("commands")->items)if(text(c,"id")==id)return text(c,"availability")=="available";return false;
}
void ShellModel::record(const std::string& kind,const Value& value) {
    if(sequence_==(std::numeric_limits<std::uint64_t>::max)())throw std::runtime_error("shell_sequence_exhausted");
    std::vector<std::string> lines;
    bool acquisition=cached_observation_response(value) || acquisition_watch_response(value) || report_response(value) || verification_response(value);
    try {lines=observation_lines(value);}
    catch(const json::Error& error) {
        ++dropped_;lines={"presentation_unavailable: "+error.code+"; complete result was not displayed; no retry performed"};
    }
    catch(const std::length_error&) {
        ++dropped_;lines={"presentation_unavailable: presentation_limit; complete result was not displayed; no retry performed"};
    }
    lines.insert(lines.begin(),"["+std::to_string(++sequence_)+"] "+kind);
    std::size_t bytes=0;for(const auto& line:lines)bytes+=line.size()+1;
    if(bytes>(acquisition?max_acquisition_transcript:max_transcript)) {
        ++dropped_;acquisition=false;lines={"["+std::to_string(sequence_)+"] transcript_record_unavailable: complete record exceeds its declared budget"};bytes=lines.front().size()+1;
    }
    auto quota=[&]() {return acquisition || std::any_of(transcript_.begin(),transcript_.end(),[](const Record& r){return r.acquisition;})?max_acquisition_transcript:max_transcript;};
    while(!transcript_.empty() && (transcript_.size()==64 || bytes>quota() || transcript_bytes_>quota()-bytes)) {
        transcript_bytes_-=transcript_.front().bytes;transcript_.pop_front();++dropped_;
    }
    transcript_.push_back({sequence_,std::move(lines),bytes,acquisition});transcript_bytes_+=bytes;follow_=true;
}
void ShellModel::diagnostic(const std::string& code,std::size_t byte,std::size_t token) {
    notice_=code+" at byte "+std::to_string(byte)+" (token "+std::to_string(token)+")";
    record("diagnostic",Value::object().put("code",Value::string(code)).put("byte",Value::string(std::to_string(byte)))
        .put("token",Value::string(std::to_string(token))));view_=View::Editor;
}
void ShellModel::invalidate() {view_=View::Editor;reviewed_=ParseResult{};review_revision_.clear();candidates_.clear();choice_=0;notice_="Editing; input is inert";}
bool ShellModel::sensitive(const ParseResult& parsed) const {
    const auto* command=registry_.command(parsed.command_id);if(!command)return false;
    const auto* schema=registry_.parameter_schemas.find(text(*command,"parameter_schema"));if(!schema)return false;
    for(const auto& parameter:parsed.parameters.fields) {
        const auto* shape=schema->find("properties")->find(parameter.first);if(shape && truth(shape->find("writeOnly")))return true;
    }
    return false;
}
Value ShellModel::review_value() const {
    auto parameters=reviewed_.parameters;
    if(const auto* command=registry_.command(reviewed_.command_id)) {
        const auto* schema=registry_.parameter_schemas.find(text(*command,"parameter_schema"));
        if(schema)for(auto& parameter:parameters.fields) {
            const auto* shape=schema->find("properties")->find(parameter.first);
            if(shape && truth(shape->find("writeOnly")))parameter.second=Value::string("[redacted]");
        }
    }
    return Value::object().put("command",Value::string(reviewed_.kind=="help"?"help":reviewed_.command_id))
        .put("help_scope",Value::string(reviewed_.domain)).put("parameters",parameters)
        .put("expected_revision",FrontendSession::handles(reviewed_.command_id)?Value::string(review_revision_):Value{}).put("selection",session_.selection());
}
void ShellModel::review() {
    const auto line=tokenize_shell(editor_);
    if(!line.error.empty()) {diagnostic(line.error,line.error_byte);return;}
    auto parsed=parse_invocation(registry_,line.arguments());
    if(!parsed.valid()) {
        const auto& error=parsed.diagnostics.items.front();const auto token=static_cast<std::size_t>(std::stoull(text(error,"token")));
        diagnostic(text(error,"code"),token<line.tokens.size()?line.tokens[token].begin:editor_.size(),token);return;
    }
    for(const auto& control:parsed.controls) {
        if((control.first=="format" && control.second!="human") ||
           (control.first=="frontend" && control.second!="auto" && control.second!="cli") ||
           (control.first=="interactive" && control.second=="no") || control.first=="terminal_presentation") {
            diagnostic("shell_control_conflict",0);return;
        }
    }
    if(parsed.kind!="help" && !parsed.help_requested && !available(parsed.command_id)) {
        diagnostic(parsed.command_id=="shell.open" || parsed.command_id=="protocol.serve"?"shell_nested_session":"command_unavailable",0);return;
    }
    if(parsed.help_requested)parsed.kind="help";
    if(rejected_input_ && (parsed.command_id=="image.acquire" || parsed.command_id=="evidence.export") && parsed.parameters.find("phase") && parsed.parameters.find("phase")->text=="execute") {
        diagnostic("shell_rejected_definition_input",0);return;
    }
    reviewed_=std::move(parsed);review_revision_=snapshot_->revision();view_=View::Review;
    notice_="REQUEST REVIEW: fresh F9 submits; editing cancels review";record("review (inert)",review_value());
}
void ShellModel::submit() {
    if(requests_==(std::numeric_limits<std::uint64_t>::max)())throw std::runtime_error("shell_request_limit");
    const auto parsed=reviewed_;const auto revision=review_revision_;const bool secret=sensitive(parsed);
    // Consume review before any callback, including a throwing callback.
    view_=View::Editor;reviewed_=ParseResult{};review_revision_.clear();++requests_;
    const auto id="shell:"+std::to_string(requests_);
    Submission reply(Outcome{});
    if(parsed.kind=="help") {
        auto commands=Value::array();
        for(const auto& command:discovery_.find("commands")->items) {
            if(!parsed.command_id.empty() && text(command,"id")!=parsed.command_id)continue;
            if(!parsed.domain.empty() && parsed.domain!="@root" && command.find("words")->items.front().text!=parsed.domain)continue;
            commands.items.push_back(command);
        }
        reply=completed(id,Value::object().put("commands",commands).put("global_options",*registry_.syntax.find("global_options")));
    } else if(parsed.command_id=="shell.close") {reply=completed(id,Value::object().put("session",Value::string("closed")));done_=true;}
    else reply=dispatch_(id,parsed.command_id,parsed.parameters,FrontendSession::handles(parsed.command_id)?revision:"");
    if(history_enabled_ && !secret && (history_.empty() || history_.back()!=editor_)) {
        while(!history_.empty() && (history_.size()==32 || history_bytes_>max_history-editor_.size())) {history_bytes_-=history_.front().size();history_.pop_front();}
        history_.push_back(editor_);history_bytes_+=editor_.size();
    }
    editor_.clear();cursor_=0;history_at_=history_.size();draft_.clear();
    if(reply.pending) {
        if(!pending_.empty())throw std::runtime_error("frontend_pending_limit");
        pending_=id;pending_secret_=secret;pending_request_=requests_;
        notice_="Waiting for request; outcome is not yet observed";
        record("pending request",Value::object().put("request_id",Value::string(id)).put("outcome",Value::string("unresolved; no permission to retry")));
    } else received(std::move(reply.outcome),secret,true);
}
void ShellModel::received(Outcome outcome,bool secret,bool latest) {
    notice_=!latest?"Earlier request finished; current input remains inert":
        outcome.exit_code==5?"Operation still running; retain its operation ID":outcome.exit_code==6?"Operation outcome unknown; inspect retained evidence":
        outcome.exit_code?"Request refused or failed; see diagnostics":"Request completed";
    // Current profile has no secret outputs. Do not echo a secret-bearing input
    // through a future handler's diagnostic or result into session history.
    if(secret) {
        auto safe=Value::object().put("status",*outcome.response.find("status")).put("request_id",*outcome.response.find("request_id"))
            .put("detail",Value::string("suppressed for secret-bearing request"));
        if(const auto* operation=outcome.response.find("operation_id"))safe.put("operation_id",*operation);
        outcome.response=std::move(safe);
    }
    record(latest?"outcome":"earlier request outcome",outcome.response);
    if(latest)last_=std::move(outcome);
}
void ShellModel::recall(int direction) {
    if(!history_enabled_ || history_.empty()) {notice_="History is off or empty";return;}
    invalidate();
    if(direction<0) {if(history_at_==history_.size())draft_=editor_;if(history_at_)--history_at_;}
    else if(history_at_<history_.size())++history_at_;
    editor_=history_at_==history_.size()?draft_:history_[history_at_];cursor_=editor_.size();notice_="Recalled input is inert";
}
void ShellModel::complete() {
    const auto prefix=tokenize_shell(editor_.substr(0,cursor_),true);
    if(!prefix.error.empty()) {diagnostic(prefix.error,prefix.error_byte);return;}
    auto tokens=prefix.arguments();std::string fragment;replace_begin_=cursor_;replace_end_=cursor_;
    if(!prefix.tokens.empty() && ((cursor_ && editor_[cursor_-1]!=' ') || prefix.open_quote)) {
        fragment=tokens.back();tokens.pop_back();replace_begin_=prefix.tokens.back().begin;
        const auto whole=tokenize_shell(editor_,true);
        for(const auto& token:whole.tokens)if(token.begin==replace_begin_)replace_end_=token.end;
    }
    std::set<std::string> choices;
    for(const auto& candidate:complete_static(registry_,tokens,fragment).items)choices.insert(candidate.text);
    auto before=tokens;std::string option;
    if(!before.empty() && before.back().compare(0,2,"--")==0) {option=before.back();before.pop_back();}
    before.push_back("--help");const auto parsed=parse_invocation(registry_,before);
    if(const auto* command=registry_.command(parsed.command_id)) {
        std::string parameter;
        for(const auto& binding:command->find("argument_bindings")->items) {
            if(!option.empty() && text(binding,"option")==option)parameter=text(binding,"parameter");
            const auto* position=binding.find("position");
            if(option.empty() && position && std::stoull(position->text)==parsed.operands.size())parameter=text(binding,"parameter");
        }
        const auto* schema=registry_.parameter_schemas.find(text(*command,"parameter_schema"));
        const auto* shape=schema?schema->find("properties")->find(parameter):nullptr;
        if(shape && shape->find("enum"))for(const auto& candidate:shape->find("enum")->items)choices.insert(candidate.text);
        if(parameter=="target_id")for(const auto& node:snapshot_->value().find("nodes")->items) {
            const auto& id=text(*command,"id");
            if(text(*node.find("properties"),"scope")!="observation-only" || id=="target.inspect" || id=="capability.explain")choices.insert(text(node,"id"));
        }
        if(parameter=="operation" && text(*command,"id")=="capability.explain")for(const auto& c:registry_.commands.items)choices.insert(text(c,"id"));
        else if(parameter=="operation_id" && last_.response.find("operation_id") && last_.response.find("operation_id")->kind==Value::Kind::string)
            choices.insert(text(last_.response,"operation_id"));
    }
    const std::size_t candidate_limit=session_.cached_observations()?320:64;
    candidates_.clear();for(const auto& candidate:choices)if(candidate.compare(0,fragment.size(),fragment)==0 && candidates_.size()<candidate_limit)candidates_.push_back(candidate);
    view_=View::Complete;choice_=0;review_revision_.clear();reviewed_=ParseResult{};notice_="Completion is inert; fresh Tab inserts";
    auto list=Value::array();for(const auto& c:candidates_)list.items.push_back(Value::string(c));record("completion (inert)",list);
}
void ShellModel::input(const TextInput& event) {
    if(done_)return;
    if(event.key==TextKey::F10) {done_=true;return;}
    if(event.repeat && event.key!=TextKey::Text && event.key!=TextKey::Backspace && event.key!=TextKey::Delete && event.key!=TextKey::Left && event.key!=TextKey::Right)return;
    if(event.key==TextKey::F6) {toggle_=true;return;}
    if(event.key==TextKey::PageUp) {follow_=false;scroll_=scroll_>page_size_?scroll_-page_size_:0;return;}
    if(event.key==TextKey::PageDown) {follow_=false;scroll_+=page_size_;return;}
    if(event.key==TextKey::F9) {if(view_==View::Review)submit();else {invalidate();review();}return;}
    if(event.key==TextKey::Escape) {invalidate();return;}
    if(event.key==TextKey::F2 || event.key==TextKey::F3) {
        invalidate();view_=event.key==TextKey::F2?View::Commands:View::Targets;
        auto choices=Value::array();
        if(view_==View::Commands)for(const auto& command:registry_.commands.items)
            choices.items.push_back(Value::object().put("command",Value::string(words(command))).put("id",*command.find("id"))
                .put("availability",Value::string(available(text(command,"id"))?"available":"unavailable in shell")));
        else for(const auto& node:snapshot_->value().find("nodes")->items)
            choices.items.push_back(Value::object().put("id",*node.find("id")).put("state",*node.find("properties")->find("state")));
        record(view_==View::Commands?"commands (inert)":"targets (cached)",choices);return;
    }
    if(event.key==TextKey::F4) {
        invalidate();const auto result=session_.act({ActionKind::ClearSelection,"",snapshot_->revision(),"shell:clear"});
        record("selection",result.response);return;
    }
    if(event.key==TextKey::F5) {invalidate();snapshot_=session_.snapshot();record("view refreshed",Value::object().put("revision",Value::string(snapshot_->revision())));return;}
    if(view_==View::Complete && event.key==TextKey::Tab) {
        if(candidates_.empty()) {invalidate();return;}
        const auto insertion=quote_shell(candidates_[choice_]);const auto proposed=editor_.substr(0,replace_begin_)+insertion+editor_.substr(replace_end_);
        if(proposed.size()>max_line) {diagnostic("shell_line_limit",cursor_);return;}
        editor_=proposed;cursor_=replace_begin_+insertion.size();rejected_input_=false;invalidate();return;
    }
    if((view_==View::Complete || view_==View::Commands || view_==View::Targets) && (event.key==TextKey::Up || event.key==TextKey::Down)) {
        follow_=true;
        const auto count=view_==View::Complete?candidates_.size():view_==View::Commands?registry_.commands.items.size():snapshot_->value().find("nodes")->items.size();
        if(event.key==TextKey::Up) {if(choice_)--choice_;}else if(choice_+1<count)++choice_;return;
    }
    if(event.key==TextKey::Enter) {
        if(view_==View::Targets && choice_<snapshot_->value().find("nodes")->items.size()) {
            const auto id=text(snapshot_->value().find("nodes")->items[choice_],"id");
            const auto selected=session_.act({ActionKind::Select,id,snapshot_->revision(),"shell:select"});
            invalidate();record("selection",selected.response);return;
        }
        if(view_==View::Commands && choice_<registry_.commands.items.size()) {
            editor_=words(registry_.commands.items[choice_]);cursor_=editor_.size();rejected_input_=false;invalidate();return;
        }
        // Do not retain raw editable data in a transcript before schema validation.
        notice_="Input remains inert; use F9 to review";return;
    }
    if(event.key==TextKey::Tab) {complete();return;}
    if(event.key==TextKey::Up || event.key==TextKey::Down) {recall(event.key==TextKey::Up?-1:1);return;}
    if(event.key==TextKey::Text) {
        if(event.text.empty())return;
        if(!json::valid_utf8(event.text) || event.text.size()>max_line-editor_.size()) {rejected_input_=true;diagnostic("shell_line_limit",cursor_);return;}
        for(const auto c:event.text)if(static_cast<unsigned char>(c)<32 || c==127) {rejected_input_=true;diagnostic("shell_control_input",cursor_);return;}
        invalidate();editor_.insert(cursor_,event.text);cursor_+=event.text.size();history_at_=history_.size();rejected_input_=false;return;
    }
    if(event.key==TextKey::Left) {invalidate();cursor_=previous(editor_,cursor_);}
    else if(event.key==TextKey::Right) {invalidate();cursor_=next(editor_,cursor_);}
    else if(event.key==TextKey::Home) {invalidate();cursor_=0;}
    else if(event.key==TextKey::End) {invalidate();cursor_=editor_.size();}
    else if(event.key==TextKey::Backspace) {invalidate();const auto before=previous(editor_,cursor_);if(before!=cursor_)rejected_input_=false;editor_.erase(before,cursor_-before);cursor_=before;}
    else if(event.key==TextKey::Delete) {invalidate();const auto count=next(editor_,cursor_)-cursor_;if(count)rejected_input_=false;editor_.erase(cursor_,count);}
}
std::vector<std::string> ShellModel::linear_records(std::uint64_t& after) const {
    std::vector<std::string> lines;
    if(!transcript_.empty() && after<transcript_.front().sequence-1)lines.push_back("Transcript gap; oldest retained record "+std::to_string(transcript_.front().sequence));
    for(const auto& record:transcript_)if(record.sequence>after)lines.insert(lines.end(),record.lines.begin(),record.lines.end());after=sequence_;return lines;
}
ShellPrompt ShellModel::prompt(unsigned columns) const {
    columns=(std::max)(1u,(std::min)(columns,240u));
    if(view_!=View::Editor) {
        std::string label;
        if(view_==View::Review)label="F9 submits: "+reviewed_.command_id;
        else if(view_==View::Complete)label="Tab inserts: "+(candidates_.empty()?std::string("no candidates"):display(candidates_[choice_]));
        else if(view_==View::Targets)label="Enter selects: "+(snapshot_->value().find("nodes")->items.empty()?std::string("none"):display(text(snapshot_->value().find("nodes")->items[choice_],"id")));
        else label="Enter inserts: "+words(registry_.commands.items[choice_]);
        if(label.size()>=columns)label=label.substr(0,columns-1)+">";
        return {label,static_cast<unsigned>(label.empty()?0:label.size()-1)};
    }
    const auto encoded=display(editor_);const auto prefix=display(editor_.substr(0,cursor_));
    const auto selection=session_.selection();const auto* target=selection.find("target_id"),*observation=selection.find("observation_id");
    const auto focus=target && target->kind==Value::Kind::string?display(target->text):
        observation && observation->kind==Value::Kind::string?"evidence:"+display(observation->text):std::string("none");
    const auto context="disked> [local|"+focus+"] ";
    const auto complete=context+encoded;const std::size_t caret=context.size()+prefix.size()-1;
    const auto start=caret>=columns?caret-columns+1:0;
    auto visible=complete.substr(start,columns);if(start && !visible.empty())visible[0]='<';
    return {visible,static_cast<unsigned>(caret-start)};
}
std::vector<std::string> ShellModel::content() const {
    std::vector<std::string> lines;
    if(view_==View::Review) {lines.push_back("REQUEST REVIEW (inert)");const auto review=presentation_lines(review_value());lines.insert(lines.end(),review.begin(),review.end());}
    else if(view_==View::Complete)for(std::size_t i=0;i<candidates_.size();++i)lines.push_back((i==choice_?"> ":"  ")+display(candidates_[i]));
    else if(view_==View::Commands)for(std::size_t i=0;i<registry_.commands.items.size();++i) {
        const auto& c=registry_.commands.items[i];lines.push_back((i==choice_?"> ":"  ")+words(c)+" ["+(available(text(c,"id"))?"available":"unavailable in shell")+"]");
    } else if(view_==View::Targets)for(std::size_t i=0;i<snapshot_->value().find("nodes")->items.size();++i) {
        const auto& node=snapshot_->value().find("nodes")->items[i];lines.push_back((i==choice_?"> ":"  ")+display(text(node,"id"))+" ["+text(*node.find("properties"),"state")+"]");
    } else for(const auto& record:transcript_)lines.insert(lines.end(),record.lines.begin(),record.lines.end());
    return lines;
}
std::vector<std::string> ShellModel::render(unsigned columns,unsigned rows,bool linear) {
    columns=(std::max)(1u,(std::min)(columns,240u));rows=(std::max)(1u,(std::min)(rows,80u));
    auto header=wrap({"DiskEd shell | "+std::string(session_.cached_observations()?"CACHED OBSERVATIONS":"IMAGE / FAKE PROTOTYPE")+" | "+std::string(linear?"linear":"screen"),"Host: local | Selection: "+presentation_json(session_.selection()),
        "History: "+std::string(history_enabled_?"session":"off")+" | Evicted transcript records: "+std::to_string(dropped_),"Notice: "+notice_},columns);
    auto footer=wrap({prompt(columns).text,"F9 review/submit | Tab completion | Arrows edit/history | Enter inert", "F2 commands F3 targets F4 clear F5 refresh F6 layout | F10/Ctrl+C quit"},columns);
    auto body=wrap(content(),columns);page_size_=rows>header.size()+footer.size()+1?rows-header.size()-footer.size()-1:1;
    if(follow_) {
        if(view_==View::Editor)scroll_=body.size()>page_size_?body.size()-page_size_:0;
        else if(view_==View::Review)scroll_=0;
        else {
            // Locate the highlighted row after wrapping, so long labels and
            // navigation never leave the selected candidate off screen.
            std::size_t selected=0;for(std::size_t i=0;i<body.size();++i)if(body[i].compare(0,2,"> ")==0) {selected=i;break;}
            scroll_=selected>=page_size_?selected-page_size_+1:0;
        }
    }
    if(scroll_>=body.size())scroll_=body.empty()?0:body.size()-1;
    auto lines=header;const auto end=(std::min)(body.size(),scroll_+page_size_);
    lines.insert(lines.end(),body.begin()+scroll_,body.begin()+end);lines.push_back("Transcript/view lines "+std::to_string(scroll_)+"-"+std::to_string(end));
    lines.insert(lines.end(),footer.begin(),footer.end());return lines;
}
Value ShellModel::state() const {
    const char* views[]={"editor","review","completion","commands","targets"};
    auto history=Value::array(),candidates=Value::array(),records=Value::array();
    for(const auto& value:history_)history.items.push_back(Value::string(value));for(const auto& value:candidates_)candidates.items.push_back(Value::string(value));
    for(const auto& r:transcript_) {auto lines=Value::array();for(const auto& line:r.lines)lines.items.push_back(Value::string(line));records.items.push_back(lines);}
    return Value::object().put("view",Value::string(views[static_cast<unsigned>(view_)])).put("editor",Value::string(editor_))
        .put("cursor",Value::string(std::to_string(cursor_))).put("notice",Value::string(notice_)).put("history",history).put("candidates",candidates)
        .put("transcript",records).put("transcript_bytes",Value::string(std::to_string(transcript_bytes_))).put("dropped",Value::string(std::to_string(dropped_)))
        .put("requests",Value::string(std::to_string(requests_))).put("last_outcome",last_.response).put("selection",session_.selection()).put("done",Value::boolean_value(done_))
        .put("pending_request",Value::string(pending_));
}
}
