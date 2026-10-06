#pragma once
#include "json.h"
#include <map>
#include <string>
#include <vector>

namespace disked {
struct Registry {
    json::Value commands, syntax, parameter_schemas;
    const json::Value* command(const std::string& id) const;
};
struct ParseResult {
    std::string kind="command", command_id, domain;
    std::vector<std::string> operands;
    std::map<std::string,std::string> controls, named_options;
    json::Value parameters=json::Value::object();
    json::Value diagnostics=json::Value::array();
    bool help_requested=false;
    bool output_ambiguous=false;
    void error(const std::string& code,std::size_t token);
    bool valid() const {return diagnostics.items.empty();}
    json::Value normalized() const;
};
ParseResult parse_invocation(const Registry& registry,const std::vector<std::string>& argv);
// Static suggestions only. Tokens are never dispatched or expanded implicitly.
json::Value complete_static(const Registry& registry,const std::vector<std::string>& command_words,const std::string& prefix);
bool positive_byte_quantity(const std::string& value,std::string* bytes=nullptr);
std::string validate_parameters(const Registry& registry,const json::Value& command,const json::Value& parameters,bool help=false);
}
