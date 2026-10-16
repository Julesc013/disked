#pragma once
#include "pipeline.h"
namespace disked { namespace acquisition_operation {
constexpr std::size_t record_limit=16384,history_limit=1048576,record_count_limit=64;
json::Limits row_limits();
std::string hash(const std::string&);
json::Value expected_binding(const json::Value& header);
void validate_state(const json::Value&,const json::Value& header,std::size_t sequence);
// A consumer must supply the exact independently obtained definition. A record
// alone cannot establish its total/resource contract or execution authority.
void validate_record(const json::Value&,const json::Value& definition);
struct History {
    json::Value state;
    std::vector<json::Value> records;
    std::string previous=std::string(64,'0');
    std::size_t count=0;
    bool complete=true;
};
History read_history(const std::string& bytes,const json::Value& header);
}}
