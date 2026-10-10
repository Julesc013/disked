#include "cli.h"
#include "session.h"

namespace disked {
using json::Value;
CliText cli_text(const Outcome& outcome,const ParseResult& parsed,const InvocationHost& host,const Registry& registry,bool background,bool acquisition_watch) {
    if(background && parsed.kind!="help" && outcome.response.find("result")->kind!=Value::Kind::null)
    {
        json::Limits limits;if(report_response(outcome.response) || verification_response(outcome.response) || acquisition_watch)limits=response_limits(outcome.response);
        if(!host.output_usable)return {};
        return {true,false,presentation_json(outcome.response,limits)+"\n"};
    }
    if(outcome.exit_code) {
        if(!host.error_usable)return {};
        std::string text;for(const auto& d:outcome.response.find("diagnostics")->items)text+="disked: "+d.find("code")->text+"\n";
        return {true,true,std::move(text)};
    }
    if(!host.output_usable)return {};
    const auto& value=*outcome.response.find("result");std::string text;
    if(FrontendSession::handles(parsed.command_id) && parsed.kind!="help")text=presentation_json(value)+"\n";
    else if(parsed.command_id=="mode.explain" && parsed.kind!="help")text=json::dump(value)+"\n";
    else if(parsed.command_id=="build.inspect" && parsed.kind!="help") {
        for(const auto& pair:value.fields)text+=pair.first+"="+pair.second.text+"\n";
    } else {
        if(parsed.kind=="help")text+="DiskEd (ordinary-file image and fake native composition)\nUsage: disked <command-form> [operands] [options]\n";
        text+="id\tcontract_status\timplementation_status\tavailability\treason\tcommand\taliases\n";
        for(const auto& c:value.find("commands")->items) {
            for(const auto* key:{"id","contract_status","implementation_status","availability","reason"})text+=c.find(key)->text+"\t";
            bool first=true;
            for(const auto& word:c.find("words")->items) {text+=(first?"":" ")+word.text;first=false;}
            text+='\t';first=true;
            for(const auto& alias:c.find("aliases")->items) {text+=(first?"":", ")+alias.text;first=false;}
            text+='\n';
            if(parsed.kind=="help") {
                text+="  "+c.find("summary")->text+"\n";
                for(const auto& binding:c.find("argument_bindings")->items) {
                    const auto* option=binding.find("option");
                    text+="  "+(option?option->text+" ":"operand: ")+binding.find("parameter")->text+"\n";
                }
            }
        }
        if(parsed.kind=="help") {
            text+="Global options (may precede, separate or follow command words before --):\n";
            for(const auto& option:registry.syntax.find("global_options")->items) {
                for(const auto& spelling:option.find("spellings")->items)text+="  "+spelling.text;
                if(const auto* choices=option.find("choices"))for(const auto& choice:choices->items)text+=" "+choice.text;
                text+='\n';
            }
        }
    }
    return {true,false,std::move(text)};
}
}
