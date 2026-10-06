#include "model.h"
#include <algorithm>
#include <limits>

namespace disked {
using json::Value;
namespace {
std::string quote(const std::string& value) {return presentation_json(Value::string(value));}
std::vector<std::string> wrapped(const std::vector<std::string>& lines,unsigned columns) {
    std::vector<std::string> result;columns=(std::max)(columns,1u);
    for(const auto& line:lines) {
        if(line.empty())result.push_back("");
        for(std::size_t i=0;i<line.size();i+=columns)result.push_back(line.substr(i,columns));
    }
    return result;
}
}
std::vector<std::string> tui_json_lines(const Value& value) {return presentation_lines(value);}
TuiModel::TuiModel(FrontendSession& session,const Registry& registry,Value discovery,Handler dispatch):
    session_(session),registry_(registry),discovery_(std::move(discovery)),dispatch_(std::move(dispatch)),snapshot_(session.snapshot()) {
    const auto options=choices();if(!options.empty())focus_=inventory_focus_=options.front();
}
bool TuiModel::available(const std::string& id) const {
    if(id=="protocol.serve")return false;
    for(const auto& c:discovery_.find("commands")->items)
        if(c.find("id")->text==id)return c.find("availability")->text=="available";
    return false;
}
std::vector<std::string> TuiModel::choices() const {
    std::vector<std::string> ids;
    if(view_==View::Commands)for(const auto& c:registry_.commands.items)ids.push_back(c.find("id")->text);
    else for(const auto& n:snapshot_->value().find("nodes")->items)ids.push_back(n.find("id")->text);
    return ids;
}
void TuiModel::move(int direction) {
    auto ids=choices();if(ids.empty())return;
    auto at=std::find(ids.begin(),ids.end(),focus_);
    if(at==ids.end())focus_=direction<0?ids.back():ids.front();
    else if(direction<0 && at!=ids.begin())focus_=*--at;
    else if(direction>0 && at+1!=ids.end())focus_=*++at;
    if(view_==View::Inventory)inventory_focus_=focus_;follow_focus_=true;
}
void TuiModel::result(Outcome outcome) {
    outcome_=std::move(outcome);view_=View::Result;scroll_=0;
    notice_=outcome_.exit_code==5?"Operation accepted; inspect using its operation ID":
        outcome_.exit_code==6?"Operation outcome unknown; inspect retained evidence":
        outcome_.exit_code?"Request refused or failed; see diagnostic":"Request completed";
}
void TuiModel::stage(const std::string& command,const Value& supplied) {
    command_=command;fields_.clear();parameters_=Value::object();field_=0;scroll_=0;
    if(!available(command)) {result(refused("tui","command_unavailable",3));return;}
    const auto* descriptor=registry_.command(command);
    const auto* schema=descriptor?registry_.parameter_schemas.find(descriptor->find("parameter_schema")->text):nullptr;
    if(!schema) {result(refused("tui","schema_unavailable",3));return;}
    for(const auto& pair:schema->find("properties")->fields) {
        if(fields_.size()==16 || pair.second.find("type")->text!="string") {result(refused("tui","form_unavailable",3));return;}
        fields_.push_back(pair.first);std::string value;
        if(pair.first=="target_id") {const auto selected=session_.selection();const auto* id=selected.find("target_id");if(id->kind==Value::Kind::string)value=id->text;}
        if(pair.first=="operation")value="target.inspect";
        if(const auto* input=supplied.find(pair.first))value=input->text;
        if(value.size()>4096 || !json::valid_utf8(value)) {result(refused("tui","form_limit"));return;}
        parameters_.put(pair.first,Value::string(value));
    }
    review_revision_=snapshot_->revision();view_=View::Form;notice_="Edit fields, then F9 to review. No command has run.";
}
bool TuiModel::take_toggle() {const bool value=toggle_;toggle_=false;return value;}
void TuiModel::input(const TuiInput& e) {
    if(done_)return;
    const bool activation=e.key==TuiKey::Enter || e.key==TuiKey::F2 || e.key==TuiKey::F3 || e.key==TuiKey::F4 ||
        e.key==TuiKey::F5 || e.key==TuiKey::F6 || e.key==TuiKey::F9 || e.key==TuiKey::F10 || e.key==TuiKey::Escape;
    if(e.repeat && activation)return;
    if(e.key==TuiKey::F10) {done_=true;return;}
    if(e.key==TuiKey::F6) {toggle_=true;return;}
    if(e.key==TuiKey::PageUp) {scroll_=scroll_>page_size_?scroll_-page_size_:0;follow_focus_=false;return;}
    if(e.key==TuiKey::PageDown) {scroll_=(std::min)(std::size_t(1048576),scroll_+page_size_);follow_focus_=false;return;}
    if(e.key==TuiKey::Escape) {
        if(view_==View::Inventory)done_=true;
        else {view_=view_==View::Review?View::Form:View::Inventory;if(view_==View::Inventory)focus_=inventory_focus_;scroll_=0;follow_focus_=true;}return;
    }
    if(view_==View::Form) {
        if(e.key==TuiKey::Tab || e.key==TuiKey::BackTab) {if(!fields_.empty())field_=(field_+(e.key==TuiKey::Tab?1:fields_.size()-1))%fields_.size();follow_focus_=true;return;}
        if(e.key==TuiKey::Backspace && !fields_.empty()) {
            auto& value=parameters_.fields[fields_[field_]].text;
            if(!value.empty()) {std::size_t end=value.size()-1;while(end && (static_cast<unsigned char>(value[end])&0xc0)==0x80)--end;value.resize(end);}return;
        }
        if(e.key==TuiKey::Text && !fields_.empty()) {
            auto& value=parameters_.fields[fields_[field_]].text;
            const bool controls=std::any_of(e.text.begin(),e.text.end(),[](unsigned char c){return c<32 || c==127;});
            if(controls || !json::valid_utf8(e.text))notice_="Control input ignored; nothing submitted";
            else if(e.text.size()>4096-value.size())notice_="Field limit reached; nothing submitted";
            else value+=e.text;return;
        }
        if(e.key==TuiKey::F9) {
            const auto error=validate_parameters(registry_,*registry_.command(command_),parameters_);
            if(!error.empty())notice_=error+"; correct the fields";
            else {view_=View::Review;scroll_=0;notice_="Review the exact request. Release F9, then press F9 to submit.";}return;
        }
        return; // Newlines, shortcuts and unrelated keys never submit a form.
    }
    if(view_==View::Review) {
        if(e.key==TuiKey::F9) {
            if(requests_==(std::numeric_limits<std::uint64_t>::max)()) {result(refused("tui","request_limit"));return;}
            result(dispatch_("tui:"+std::to_string(++requests_),command_,parameters_,FrontendSession::handles(command_)?review_revision_:""));
        }return;
    }
    if(e.key==TuiKey::F2) {view_=View::Commands;focus_=registry_.commands.items.front().find("id")->text;scroll_=0;follow_focus_=true;return;}
    if(e.key==TuiKey::F3) {view_=View::Inventory;focus_=inventory_focus_;scroll_=0;follow_focus_=true;return;}
    if(e.key==TuiKey::F4) {result(session_.act({ActionKind::ClearSelection,"",snapshot_->revision(),"tui:selection"}));return;}
    if(e.key==TuiKey::F5) {snapshot_=session_.snapshot();notice_="View refreshed; selected identity is unchanged";scroll_=0;return;}
    if(view_==View::Result)return;
    if(e.key==TuiKey::Up || e.key==TuiKey::Down) {move(e.key==TuiKey::Up?-1:1);return;}
    if(e.key==TuiKey::Enter) {
        if(view_==View::Commands)stage(focus_,Value::object());
        else {
            const auto selected=session_.act({ActionKind::Select,focus_,snapshot_->revision(),"tui:selection"});
            if(selected.exit_code)result(selected);
            else result(session_.act({ActionKind::Inspect,focus_,snapshot_->revision(),"tui:inspect"}));
        }
    }
}
std::vector<std::string> TuiModel::body() const {
    std::vector<std::string> lines;
    if(view_==View::Inventory) {
        lines.push_back("TARGET INVENTORY (cached fake observations)");
        for(const auto& n:snapshot_->value().find("nodes")->items) {
            const auto& p=*n.find("properties");const auto* cap=p.find("capacity_bytes");
            lines.push_back((n.find("id")->text==focus_?"> ":"  ")+quote(n.find("id")->text)+" ["+p.find("state")->text+"]");
            lines.push_back("    "+quote(p.find("label")->text)+"; bytes="+(cap->kind==Value::Kind::null?"unknown":cap->text));
        }
        for(const auto& o:snapshot_->value().find("omissions")->items)lines.push_back("Omission: "+quote(o.text));
    } else if(view_==View::Commands) {
        lines.push_back("COMMAND EXPLORER");
        for(const auto& c:registry_.commands.items) {
            const auto id=c.find("id")->text;
            lines.push_back((id==focus_?"> ":"  ")+id+" ["+(id=="protocol.serve"?"transport-only":available(id)?"available":"unavailable")+"]");
        }
    } else if(view_==View::Form || view_==View::Review) {
        lines.push_back(view_==View::Form?"TYPED FORM (inert)":"REQUEST REVIEW (inert)");lines.push_back("Command: "+command_);
        for(std::size_t i=0;i<fields_.size();++i)lines.push_back((view_==View::Form && field_==i?"> ":"  ")+fields_[i]+" = "+quote(parameters_.find(fields_[i])->text));
        lines.push_back("Expected graph revision: "+review_revision_);
        lines.push_back("No storage permission is granted by review.");
    } else lines=tui_json_lines(outcome_.response);
    return lines;
}
std::vector<std::string> TuiModel::render(unsigned columns,unsigned rows,bool linear) {
    columns=(std::max)(1u,(std::min)(240u,columns));rows=(std::max)(1u,(std::min)(80u,rows));
    auto header=std::vector<std::string>{"DiskEd | FAKE ONLY | "+std::string(linear?"linear":"screen"),"Selection: "+presentation_json(session_.selection()),"Notice: "+notice_};
    auto footer=std::vector<std::string>{"Arrows focus | Enter inspect/open | F2 commands | F3 inventory", "F4 clear | F5 refresh view | F6 layout | F9 review/submit", "Tab field | PgUp/PgDn page | Esc back | F10/Ctrl+C quit"};
    auto content=body();std::vector<std::string> lines;
    if(linear) {
        lines=header;lines.insert(lines.end(),content.begin(),content.end());lines.insert(lines.end(),footer.begin(),footer.end());return lines;
    }
    header=wrapped(header,columns);footer=wrapped(footer,columns);content=wrapped(content,columns);
    if(header.size()+footer.size()+2>=rows)return render(columns,rows,true);
    page_size_=rows-header.size()-footer.size()-1;
    if(follow_focus_) {
        for(std::size_t i=0;i<content.size();++i)if(content[i].compare(0,2,"> ")==0) {scroll_=(i/page_size_)*page_size_;break;}
        follow_focus_=false;
    }
    if(scroll_>=content.size())scroll_=content.empty()?0:((content.size()-1)/page_size_)*page_size_;
    lines=header;const auto end=(std::min)(content.size(),scroll_+page_size_);
    lines.insert(lines.end(),content.begin()+scroll_,content.begin()+end);
    while(lines.size()<rows-footer.size()-1)lines.push_back("");
    lines.push_back("Lines "+std::to_string(scroll_+1)+"-"+std::to_string(end)+" of "+std::to_string(content.size()));
    lines.insert(lines.end(),footer.begin(),footer.end());return lines;
}
Value TuiModel::state() const {
    const char* views[]={"inventory","commands","form","review","result"};
    return Value::object().put("view",Value::string(views[static_cast<unsigned>(view_)]))
        .put("notice",Value::string(notice_)).put("selection",session_.selection()).put("view_revision",Value::string(snapshot_->revision()))
        .put("focus",Value::string(focus_)).put("requests",Value::string(std::to_string(requests_)))
        .put("parameters",parameters_).put("last_outcome",outcome_.response).put("done",Value::boolean_value(done_));
}
}
