#pragma once
#include "acquisition_export.h"
namespace disked { namespace report_operation {
// Private bounded execution evidence. No public or production journal ABI.
constexpr std::size_t definition_limit=65536,record_limit=65536,history_limit=1048576,record_count_limit=16;
json::Limits definition_limits();
json::Limits row_limits();
std::string digest(const json::Value&);
void validate_definition(const json::Value&);
void validate_grant(const json::Value&,const json::Value& definition);
void validate_header(const json::Value&);
json::Value expected_binding(const json::Value& header);
void validate_state(const json::Value&,const json::Value& header,std::size_t sequence);
struct History {
    json::Value state;std::vector<json::Value> records;
    std::string previous=std::string(64,'0');std::size_t count=0;bool complete=true;
};
History read_history(const std::string&,const json::Value& header);
}}
