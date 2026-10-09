#pragma once
#include "image_collection.h"
namespace disked { namespace verification_operation {
constexpr std::size_t definition_limit=262144,header_limit=278528,record_limit=65536,history_limit=2097152,record_count_limit=32;
json::Limits definition_limits();
json::Limits row_limits();
std::string digest(const json::Value&);
evidence::proposal::VerificationDefinition verification(const json::Value& definition);
void validate_definition(const json::Value&);
void validate_grant(const json::Value&,const json::Value& definition);
void validate_header(const json::Value&);
json::Value expected_binding(const json::Value& header);
void validate_state(const json::Value&,const json::Value& header,std::size_t sequence);
void validate_progress(const json::Value& previous,const json::Value& next);
struct History {
    json::Value state;std::vector<json::Value> records;
    std::string previous=std::string(64,'0');std::size_t count=0;bool complete=true;
};
History read_history(const std::string&,const json::Value& header);
}}
