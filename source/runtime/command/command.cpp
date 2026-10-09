#include "command.h"
#include <algorithm>
#include <cstdint>
#include <limits>
#include <set>
#include <sstream>

namespace disked {
using json::Value;
namespace {
std::string text(const Value& object,const std::string& key) {
    const auto* p=object.find(key);return p && p->kind==Value::Kind::string ? p->text : "";
}
const std::vector<Value>& array(const Value& object,const std::string& key) {
    static const std::vector<Value> empty;
    const auto* p=object.find(key);return p && p->kind==Value::Kind::array ? p->items : empty;
}
bool boolean(const Value& object,const std::string& key) {const auto* p=object.find(key);return p && p->kind==Value::Kind::boolean && p->boolean;}
bool contains(const std::vector<Value>& values,const std::string& value) {
    return std::any_of(values.begin(),values.end(),[&](const Value& v){return v.text==value;});
}
std::vector<std::string> split(const std::string& words) {
    std::istringstream in(words);std::vector<std::string> result;std::string word;
    while(in>>word) result.push_back(word);return result;
}
bool prefix(const std::vector<std::string>& form,const std::vector<std::string>& words,std::size_t boundary) {
    return form.size()<=boundary && std::equal(form.begin(),form.end(),words.begin());
}
const Value* global_option(const Registry& registry,const std::string& word) {
    for(const auto& option:array(registry.syntax,"global_options")) if(contains(array(option,"spellings"),word))return &option;
    return nullptr;
}
const Value* named_binding(const Value& command,const std::string& word) {
    for(const auto& binding:array(command,"argument_bindings"))
        if(text(binding,"option")==word || contains(array(binding,"option_aliases"),word))return &binding;
    return nullptr;
}
const Value* any_binding(const Registry& registry,const std::string& word) {
    for(const auto& command:registry.commands.items) {const auto* b=named_binding(command,word);if(b)return b;}
    return nullptr;
}
void setting(ParseResult& result,const std::string& field,const std::string& value,std::size_t token) {
    const auto previous=result.controls.find(field);
    if(previous!=result.controls.end()) {
        result.error(previous->second==value?"duplicate_option":"argument_conflict",token);
        if(field=="format" && previous->second!=value)result.output_ambiguous=true;
    } else result.controls[field]=value;
}
std::string validate_scalar(const Value& shape,const Value& value) {
    const auto type=text(shape,"type");
    if(type=="string") {
        if(value.kind!=Value::Kind::string || !json::valid_utf8(value.text) || value.text.find('\0')!=std::string::npos)return "invalid_parameter";
        // The admitted scalar schemas contain positive lengths and string IDs/paths.
        if(shape.find("minLength") && value.text.empty())return "invalid_parameter";
        if(value.text.size()>32768)return "invalid_parameter";
        if(shape.find("enum") && !contains(array(shape,"enum"),value.text))return "invalid_parameter";
        if(text(shape,"x-disked-scalar")=="positive-byte-quantity" && !positive_byte_quantity(value.text))return "invalid_parameter";
        if(text(shape,"x-disked-scalar")=="operation-id") {
            const auto offset=value.text.compare(0,8,"fake-op:")==0?8:value.text.compare(0,9,"image-op:")==0?9:value.text.compare(0,10,"report-op:")==0?10:0;
            if(!offset || value.text.size()!=static_cast<std::size_t>(offset)+32 || value.text.find_first_not_of("0123456789abcdef",offset)!=std::string::npos)return "invalid_parameter";
        }
        if(text(shape,"x-disked-scalar")=="acquisition-operation-id" && (value.text.size()!=41 ||
            value.text.compare(0,9,"image-op:")!=0 || value.text.find_first_not_of("0123456789abcdef",9)!=std::string::npos))return "invalid_parameter";
        if(text(shape,"x-disked-scalar")=="fake-operation-id" && (value.text.size()!=40 ||
            value.text.compare(0,8,"fake-op:")!=0 || value.text.find_first_not_of("0123456789abcdef",8)!=std::string::npos))return "invalid_parameter";
        const auto scalar=text(shape,"x-disked-scalar");
        if((scalar=="decimal-u64" || scalar=="watch-follow-ms") && (!json::decimal_u64(value.text) ||
            (scalar=="watch-follow-ms" && std::stoull(value.text)>2000)))return "invalid_parameter";
        if(scalar=="worker-epoch" && (value.text.size()!=39 || value.text.compare(0,7,"worker:")!=0 ||
            value.text.find_first_not_of("0123456789abcdef",7)!=std::string::npos))return "invalid_parameter";
        if(scalar=="record-digest" && (value.text.size()!=64 || value.text.find_first_not_of("0123456789abcdef")!=std::string::npos))return "invalid_parameter";
        if(text(shape,"x-disked-scalar")=="local-state-directory" && (value.text.size()<3 || value.text.size()>960 ||
            !((value.text[0]>='A' && value.text[0]<='Z') || (value.text[0]>='a' && value.text[0]<='z')) || value.text[1]!=':' || value.text[2]!='\\'))return "invalid_parameter";
    } else if(type=="boolean") {if(value.kind!=Value::Kind::boolean)return "invalid_parameter";}
    else if(type=="array") {
        if(value.kind!=Value::Kind::array || !shape.find("items"))return "invalid_parameter";
        for(const auto& item:value.items)if(!validate_scalar(*shape.find("items"),item).empty())return "invalid_parameter";
    } else return "schema_unavailable";
    return "";
}
// Bounded compiled parameter-schema subset. Domain admission validates plan
// semantics again before invoking an effect port; this is not a general schema
// engine or a way to accept unknown mutation fields.
json::Limits parameter_limits(const Value& shape) {
    json::Limits limits;limits.bytes=16384;limits.depth=20;limits.values=2048;limits.string_bytes=1024;
    const auto bound=[&](const char* key,std::size_t fallback,std::size_t maximum) {
        const auto p=shape.find(key);if(!p)return fallback;
        if(p->kind!=Value::Kind::number || !json::decimal_u64(p->text))throw std::invalid_argument("schema_budget");
        const auto n=std::stoull(p->text);if(!n || n>maximum)throw std::invalid_argument("schema_budget");return static_cast<std::size_t>(n);
    };
    limits.bytes=bound("x-disked-byte-budget",limits.bytes,65536);
    limits.depth=bound("x-disked-depth-budget",limits.depth,32);
    limits.values=bound("x-disked-value-budget",limits.values,8192);
    limits.string_bytes=bound("x-disked-string-budget",limits.string_bytes,32768);return limits;
}
std::string validate_shape(const Registry& registry,const Value& shape,const Value& value,std::size_t depth=0,bool help=false) {
    if(depth>32)return "schema_unavailable";
    if(shape.kind==Value::Kind::boolean)return shape.boolean?"":"invalid_parameter";
    if(shape.kind!=Value::Kind::object)return "schema_unavailable";
    bool referenced=false;
    if(const auto ref=shape.find("$ref")) {
        if(ref->kind!=Value::Kind::string)return "schema_unavailable";
        const auto target=registry.parameter_schemas.find(ref->text);if(!target)return "schema_unavailable";
        const auto error=validate_shape(registry,*target,value,depth+1,help);if(!error.empty())return error;referenced=true;
    }
    if(const auto c=shape.find("const"))if(json::dump(*c)!=json::dump(value))return "invalid_parameter";
    if(const auto e=shape.find("enum")) {
        bool match=false;for(const auto& c:e->items)if(json::dump(c)==json::dump(value))match=true;
        if(!match)return "invalid_parameter";
    }
    const auto type=text(shape,"type");
    const auto bound=[&](const char* key,std::size_t count,bool minimum) {
        const auto v=shape.find(key);return !v || (minimum?count>=std::stoull(v->text):count<=std::stoull(v->text));
    };
    if(type=="object" || shape.find("properties") || shape.find("required")) {
        if(value.kind!=Value::Kind::object)return "invalid_parameter";
        if(!bound("minProperties",value.fields.size(),true) || !bound("maxProperties",value.fields.size(),false))return "invalid_parameter";
        const auto properties=shape.find("properties");
        for(const auto& pair:value.fields) {
            const auto child=properties?properties->find(pair.first):nullptr;
            if(child) {const auto error=validate_shape(registry,*child,pair.second,depth+1);if(!error.empty())return error;}
            else if(shape.find("additionalProperties") && !boolean(shape,"additionalProperties"))return "invalid_parameter";
        }
        if(!help)for(const auto& k:array(shape,"required"))if(!value.find(k.text))return "missing_parameter";
    } else if(type=="array") {
        if(value.kind!=Value::Kind::array)return "invalid_parameter";
        if(!shape.find("items") && !shape.find("const") && !shape.find("enum"))return "schema_unavailable";
        if(!bound("minItems",value.items.size(),true) || !bound("maxItems",value.items.size(),false))return "invalid_parameter";
        std::set<std::string> unique;
        const auto tuple=shape.find("prefixItems");if(tuple && tuple->kind!=Value::Kind::array)return "schema_unavailable";
        for(std::size_t i=0;i<value.items.size();++i) {
            const auto& child=value.items[i];
            if(boolean(shape,"uniqueItems") && !unique.insert(json::dump(child)).second)return "invalid_parameter";
            const auto item=tuple && i<tuple->items.size()?&tuple->items[i]:shape.find("items");
            if(item) {const auto error=validate_shape(registry,*item,child,depth+1);if(!error.empty())return error;}
        }
    } else if(!type.empty()) {
        const auto error=validate_scalar(shape,value);if(!error.empty())return error;
        if(type=="string") {
            std::size_t characters=0;for(const unsigned char c:value.text)if((c&0xc0)!=0x80)++characters;
            if(!bound("minLength",characters,true) || !bound("maxLength",characters,false))return "invalid_parameter";
            const auto scalar=text(shape,"x-disked-scalar");
            const std::size_t hex=scalar=="file-generation-id"?32:scalar=="source-revision"?40:0;
            if(hex && (value.text.size()!=hex || value.text.find_first_not_of("0123456789abcdef")!=std::string::npos))return "invalid_parameter";
            if(scalar=="sha256-digest" && (value.text.size()!=71 || value.text.compare(0,7,"sha256:") || value.text.find_first_not_of("0123456789abcdef",7)!=std::string::npos))return "invalid_parameter";
        }
    } else if(!referenced && !shape.find("const") && !shape.find("enum") && !shape.find("allOf") && !shape.find("if") && !shape.find("required"))return "schema_unavailable";
    if(shape.find("x-disked-byte-budget")) {
        try {json::dump(value,parameter_limits(shape));}catch(const json::Error&) {return "invalid_parameter";}
        catch(const std::exception&) {return "schema_unavailable";}
    }
    for(const auto& child:array(shape,"allOf")) {const auto error=validate_shape(registry,child,value,depth+1,help);if(!error.empty())return error;}
    if(const auto condition=shape.find("if")) {
        const auto error=validate_shape(registry,*condition,value,depth+1);
        if(error=="schema_unavailable")return error;
        if(const auto branch=shape.find(error.empty()?"then":"else"))return validate_shape(registry,*branch,value,depth+1,help);
    }
    return "";
}
std::string decode_parameter(const Value& shape,const std::string& text_value,Value& value) {
    if(text(shape,"type")=="object") {
        try {value=json::parse(text_value,parameter_limits(shape));}catch(const json::Error&) {return "invalid_parameter";}
        catch(const std::exception&) {return "schema_unavailable";}
        if(value.kind!=Value::Kind::object)return "invalid_parameter";
    } else value=Value::string(text_value);
    return "";
}
}
const Value* Registry::command(const std::string& id) const {
    for(const auto& c:commands.items)if(text(c,"id")==id)return &c;return nullptr;
}
void ParseResult::error(const std::string& code,std::size_t token) {
    diagnostics.items.push_back(Value::object().put("code",Value::string(code)).put("token",Value::number(std::to_string(token))));
}
Value ParseResult::normalized() const {
    Value out=Value::object();out.put("kind",Value::string(valid()?kind:"error"));
    Value settings=Value::object();for(const auto& pair:controls)settings.put(pair.first,Value::string(pair.second));
    out.put("controls",settings).put("help_requested",Value::boolean_value(help_requested));
    if(!valid()) {out.put("code",*diagnostics.items.front().find("code")).put("diagnostics",diagnostics);return out;}
    if(!command_id.empty())out.put("command_id",Value::string(command_id));
    if(!domain.empty())out.put("domain",Value::string(domain));
    if(kind=="command") {
        Value args=Value::array();for(const auto& s:operands)args.items.push_back(Value::string(s));
        Value named=Value::object();for(const auto& pair:named_options)named.put(pair.first,Value::string(pair.second));
        out.put("operands",args).put("named_options",named).put("parameters",parameters);
    }
    return out;
}
bool positive_byte_quantity(const std::string& value,std::string* bytes) {
    if(value.empty() || value[0]<'1' || value[0]>'9')return false;
    std::size_t count=0;std::uint64_t integer=0;
    const auto maximum=(std::numeric_limits<std::uint64_t>::max)();
    while(count<value.size() && value[count]>='0' && value[count]<='9') {
        const auto digit=static_cast<unsigned>(value[count++]-'0');
        if(integer>(maximum-digit)/10)return false;integer=integer*10+digit;
    }
    const auto unit=value.substr(count);unsigned shift=0;
    if(unit=="B")shift=0;else if(unit=="KiB")shift=10;else if(unit=="MiB")shift=20;
    else if(unit=="GiB")shift=30;else if(unit=="TiB")shift=40;else return false;
    if(integer>(maximum>>shift))return false;
    if(bytes)*bytes=std::to_string(integer<<shift);return true;
}
std::string validate_parameters(const Registry& registry,const Value& command,const Value& parameters,bool help) {
    if(parameters.kind!=Value::Kind::object)return "invalid_parameters";
    if(text(command,"syntax_status")!="defined")return "syntax_unavailable";
    const auto* schema=registry.parameter_schemas.find(text(command,"parameter_schema"));
    if(!schema || !schema->find("properties"))return "schema_unavailable";
    for(const auto& pair:parameters.fields) {
        const auto* shape=schema->find("properties")->find(pair.first);
        if(!shape)return "unexpected_parameter";
        const auto error=validate_shape(registry,*shape,pair.second);if(!error.empty())return error;
    }
    if(!help)for(const auto& key:array(*schema,"required"))if(!parameters.find(key.text))return "missing_parameter";
    return validate_shape(registry,*schema,parameters,0,help);
}
std::string form_discriminator(const Registry& registry,const Value& command) {
    const auto* schema=registry.parameter_schemas.find(text(command,"parameter_schema"));
    return schema && schema->find("x-disked-form-discriminator")?text(*schema,"x-disked-form-discriminator"):"";
}
std::string form_default(const Registry& registry,const Value& command) {
    const auto* schema=registry.parameter_schemas.find(text(command,"parameter_schema"));
    return schema && schema->find("x-disked-form-default")?text(*schema,"x-disked-form-default"):"";
}
Value form_shapes(const Registry& registry,const Value& command,const Value& editor) {
    const auto* schema=registry.parameter_schemas.find(text(command,"parameter_schema"));
    if(!schema || !schema->find("properties"))throw std::invalid_argument("schema_unavailable");
    auto properties=*schema->find("properties");const auto discriminator=form_discriminator(registry,command);
    if(discriminator.empty())return properties;
    if(!properties.find(discriminator))throw std::invalid_argument("form_unavailable");
    const auto* selected=editor.find(discriminator);bool matched=false;
    if(const auto* conditions=schema->find("allOf"))for(const auto& branch:conditions->items) {
        const auto* condition=branch.find("if");const auto* constraints=condition?condition->find("properties"):nullptr;
        const auto* identity=constraints?constraints->find(discriminator):nullptr;const auto* expected=identity?identity->find("const"):nullptr;
        // Policy conditions involving additional fields do not select a form.
        if(!constraints || constraints->fields.size()!=1 || !expected || !selected || json::dump(*expected)!=json::dump(*selected))continue;
        const auto* then=branch.find("then");const auto* changes=then?then->find("properties"):nullptr;
        if(changes)for(const auto& pair:changes->fields)if(pair.second.kind==Value::Kind::boolean && !pair.second.boolean)properties.fields.erase(pair.first);
        matched=true;
    }
    if(!matched) {auto only=Value::object();only.put(discriminator,*properties.find(discriminator));return only;}
    return properties;
}
std::size_t form_field_limit(const Value& shape) {
    const auto type=text(shape,"type");
    if(type=="string" || type=="boolean")return 4096;
    const auto* budget=shape.find("x-disked-byte-budget");
    if(type!="object" || !budget || budget->kind!=Value::Kind::number || (budget->text!="16384" && budget->text!="65536"))throw std::invalid_argument("form_unavailable");
    return parameter_limits(shape).bytes;
}
std::string form_field_text(const Value& shape,const Value& supplied) {
    const auto type=text(shape,"type");
    if(type=="boolean" && supplied.kind==Value::Kind::boolean)return supplied.boolean?"true":"false";
    if(type=="string" && supplied.kind==Value::Kind::string)return supplied.text;
    if(type=="object" && supplied.kind==Value::Kind::object) {
        form_field_limit(shape);return json::dump(supplied,parameter_limits(shape));
    }
    throw std::invalid_argument("invalid_parameter");
}
std::string form_parameters(const Registry& registry,const Value& command,const Value& editor,Value& typed) {
    const auto* schema=registry.parameter_schemas.find(text(command,"parameter_schema"));
    if(!schema || !schema->find("properties"))return "schema_unavailable";
    auto next=Value::object();
    for(const auto& pair:editor.fields) {
        const auto* shape=schema->find("properties")->find(pair.first);
        if(!shape || pair.second.kind!=Value::Kind::string)return "invalid_parameter";
        if(pair.second.text.empty() && !contains(array(*schema,"required"),pair.first))continue;
        if(text(*shape,"type")=="boolean") {
            if(pair.second.text!="true" && pair.second.text!="false")return "invalid_parameter";
            next.put(pair.first,Value::boolean_value(pair.second.text=="true"));
        } else if(text(*shape,"type")=="string" || text(*shape,"type")=="object") {
            Value value;const auto error=decode_parameter(*shape,pair.second.text,value);if(!error.empty())return error;next.put(pair.first,value);
        }
        else return "form_unavailable";
    }
    const auto error=validate_parameters(registry,command,next);if(error.empty())typed=std::move(next);return error;
}
ParseResult parse_invocation(const Registry& registry,const std::vector<std::string>& argv) {
    ParseResult result;std::vector<std::string> words;std::vector<std::size_t> positions;
    struct Named {std::string spelling,value;std::size_t token;};std::vector<Named> named;
    bool literal=false;std::size_t boundary=0, total=0;
    if(argv.size()>1024) {result.error("argument_limit_exceeded",0);return result;}
    for(std::size_t i=0;i<argv.size();++i) {
        const auto& word=argv[i];
        if(total>65536 || word.size()>65536-total) {result.error("argument_limit_exceeded",i);return result;}
        total+=word.size();
        if(!json::valid_utf8(word) || word.find('\0')!=std::string::npos) {result.error("invalid_argument_encoding",i);continue;}
        if(!literal && word=="--") {literal=true;boundary=words.size();continue;}
        if(!literal && !word.empty() && word[0]=='-') {
            const auto equal=word.find('=');const auto spelling=word.substr(0,equal);
            const Value* option=global_option(registry,spelling);
            const Value* binding=option?nullptr:any_binding(registry,spelling);
            if(!option && !binding) {result.error("unknown_option",i);continue;}
            const auto* arity=(option?option:binding)->find("value_arity");
            const bool consumes=arity && arity->text=="1";std::string value;const auto token=i;
            if(consumes) {
                if(equal!=std::string::npos)value=word.substr(equal+1);
                else if(i+1<argv.size() && argv[i+1]!="--") {
                    value=argv[++i];
                    if(value.size()>65536-total) {result.error("argument_limit_exceeded",token);return result;}
                    total+=value.size();
                }
                else {result.error("missing_option_value",token);continue;}
                if(!json::valid_utf8(value) || value.find('\0')!=std::string::npos) {result.error("invalid_argument_encoding",token);continue;}
            } else if(equal!=std::string::npos) {result.error("invalid_option_value",token);continue;}
            if(option) {
                if(consumes) {
                    if(!contains(array(*option,"choices"),value)) {result.error("invalid_option_value",token);continue;}
                    setting(result,text(*option,"field"),value,token);
                } else {
                    const auto* sets=option->find("sets");
                    for(const auto& pair:sets->fields) {
                        if(pair.first=="help") {if(result.help_requested)result.error("duplicate_option",token);result.help_requested=true;}
                        else setting(result,pair.first,pair.second.text,token);
                    }
                }
            } else named.push_back(Named{spelling,value,token});
        } else {words.push_back(word);positions.push_back(i);}
    }
    if(!literal)boundary=words.size();
    if(boundary && words[0]=="help") {
        if(result.help_requested)result.error("duplicate_option",positions[0]);result.help_requested=true;
        words.erase(words.begin());positions.erase(positions.begin());--boundary;
    }
    if(boundary==1 && words.size()==1 && (words[0]=="tui" || words[0]=="gui")) {
        setting(result,"frontend",words[0],positions[0]);words.clear();positions.clear();boundary=0;
    }
    const auto format=result.controls.find("format"), frontend=result.controls.find("frontend"), interactive=result.controls.find("interactive");
    const bool machine=format!=result.controls.end() && format->second!="human";
    const bool graphical=frontend!=result.controls.end() && (frontend->second=="gui" || frontend->second=="tui");
    const auto terminal_conflict=[&](const std::string& command) {
        if(result.controls.count("terminal_presentation") && command!="shell.open" && (frontend==result.controls.end() || frontend->second!="tui"))result.error("argument_conflict",0);
    };
    if((machine && graphical) || (machine && interactive!=result.controls.end() && interactive->second=="yes") || (graphical && interactive!=result.controls.end() && interactive->second=="no"))result.error("argument_conflict",0);
    if(words.empty()) {
        terminal_conflict("");
        if(!named.empty())result.error("command_not_found",named.front().token);
        result.kind="help";result.domain="@root";return result;
    }
    for(const auto& retired:array(registry.syntax,"retired_command_spellings"))
        if(prefix(split(text(retired,"spelling")),words,boundary)) {result.error("retired_command",positions[0]);return result;}
    const Value* selected=nullptr;std::size_t consumed=0;
    for(const auto& command:registry.commands.items) {
        std::vector<std::vector<std::string>> forms;
        std::vector<std::string> canonical;for(const auto& w:array(command,"words"))canonical.push_back(w.text);forms.push_back(canonical);
        for(const auto& alias:array(command,"aliases"))forms.push_back(split(alias.text));
        for(const auto& form:forms)if(form.size()>consumed && prefix(form,words,boundary)) {selected=&command;consumed=form.size();}
    }
    if(!selected) {
        terminal_conflict("");
        if(result.help_requested && words.size()==1 && boundary==1) {
            for(const auto& domain:array(registry.syntax,"domains"))if(text(domain,"word")==words[0] || contains(array(domain,"aliases"),words[0])) {
                result.kind="help";result.domain=text(domain,"word");
                if(!named.empty())result.error("option_not_applicable",named.front().token);return result;
            }
        }
        result.error("command_not_found",positions.empty()?0:positions[0]);return result;
    }
    result.command_id=text(*selected,"id");result.kind=result.help_requested?"help":"command";
    terminal_conflict(result.command_id);
    if(result.command_id=="shell.open" && !result.help_requested &&
       (machine || graphical || (frontend!=result.controls.end() && frontend->second!="auto" && frontend->second!="cli") ||
        (interactive!=result.controls.end() && interactive->second=="no")))result.error("argument_conflict",0);
    result.operands.assign(words.begin()+static_cast<std::ptrdiff_t>(consumed),words.end());
    std::map<std::string,std::size_t> parameter_tokens;
    for(const auto& input:named) {
        const auto* binding=named_binding(*selected,input.spelling);
        if(!binding) {result.error("option_not_applicable",input.token);continue;}
        const auto name=text(*binding,"parameter"), spelling=text(*binding,"option");
        Value value=binding->find("value_arity")->text=="0" ? Value::boolean_value(true) : Value::string(input.value);
        const auto schema=registry.parameter_schemas.find(text(*selected,"parameter_schema"));
        const auto properties=schema?schema->find("properties"):nullptr;
        const auto shape=properties?properties->find(name):nullptr;
        if(shape && text(*shape,"type")=="object" && !decode_parameter(*shape,input.value,value).empty()) {result.error("invalid_option_value",input.token);continue;}
        if(result.parameters.find(name) && !boolean(*binding,"repeatable")) {result.error("duplicate_option",input.token);continue;}
        if(boolean(*binding,"repeatable")) {
            if(!result.parameters.find(name))result.parameters.put(name,Value::array());
            result.parameters.fields[name].items.push_back(value);
        } else result.parameters.put(name,value);
        parameter_tokens[name]=input.token;
        result.named_options[spelling]=input.value;
    }
    if(text(*selected,"syntax_status")=="defined") {
        std::size_t positional_count=0;
        for(const auto& binding:array(*selected,"argument_bindings"))if(const auto* position=binding.find("position")) {
            const auto index=static_cast<std::size_t>(std::stoul(position->text));++positional_count;
            if(index<result.operands.size()) {
                const auto name=text(binding,"parameter");
                result.parameters.put(name,Value::string(result.operands[index]));
                parameter_tokens[name]=positions[consumed+index];
            }
        }
        if(result.operands.size()>positional_count)result.error("unexpected_operand",positions[consumed+positional_count]);
        const auto validation=validate_parameters(registry,*selected,result.parameters,result.help_requested);
        if(!validation.empty()) {
            std::size_t token=positions.empty()?0:positions[0];
            const auto* schema=registry.parameter_schemas.find(text(*selected,"parameter_schema"));
            if(schema && schema->find("properties"))for(const auto& pair:result.parameters.fields) {
                const auto* shape=schema->find("properties")->find(pair.first);
                if(shape && !validate_shape(registry,*shape,pair.second).empty()) {token=parameter_tokens[pair.first];break;}
            }
            result.error(validation=="invalid_parameter"?"invalid_option_value":validation,token);
        }
    }
    return result;
}
Value complete_static(const Registry& registry,const std::vector<std::string>& words,const std::string& fragment) {
    Value result=Value::array();
    if(words.size()>16 || fragment.size()>256 || !json::valid_utf8(fragment))return result;
    for(const auto& word:words)if(word.size()>256 || word=="--" || !json::valid_utf8(word))return result;
    std::set<std::string> candidates;
    for(const auto& command:registry.commands.items) {
        std::vector<std::vector<std::string>> forms;
        std::vector<std::string> canonical;
        for(const auto& w:array(command,"words"))canonical.push_back(w.text);
        forms.push_back(canonical);
        for(const auto& alias:array(command,"aliases"))forms.push_back(split(alias.text));
        for(const auto& form:forms) {
            if(words.size()<form.size() && std::equal(words.begin(),words.end(),form.begin()))candidates.insert(form[words.size()]);
            if(words==form)for(const auto& binding:array(command,"argument_bindings")) {
                if(binding.find("option"))candidates.insert(text(binding,"option"));
                for(const auto& alias:array(binding,"option_aliases"))candidates.insert(alias.text);
            }
        }
    }
    if(!fragment.empty() && fragment[0]=='-')for(const auto& option:array(registry.syntax,"global_options"))
        for(const auto& spelling:array(option,"spellings"))candidates.insert(spelling.text);
    for(const auto& candidate:candidates)if(candidate.compare(0,fragment.size(),fragment)==0)result.items.push_back(Value::string(candidate));
    return result;
}
}
