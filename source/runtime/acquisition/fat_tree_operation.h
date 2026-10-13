#pragma once
#include "fat_tree_review.h"

namespace disked {
namespace fat_tree_operation {
struct Error : std::runtime_error {
    explicit Error(const char *code) : std::runtime_error(code) {
    }
};
struct History {
    json::Value header, last_worker, writer;
    std::vector<json::Value> records;
    std::string last_digest, tail_digest;
    std::size_t admitted_bytes = 0, tail_bytes = 0;
    bool complete = true, exited = false, outcome_published = false;
    bool has_dispatch_intent = false, uncertain = false;
    json::Value view() const;
};
// Pure supplied-data validation. No path/process access and no execution grant.
json::Value validate_header(const json::Value &);
void validate_record(const json::Value &header, const json::Value &record);
History read_history(const json::Value &header, const std::string &bytes);
json::Limits header_limits();
json::Limits record_limits();
} // namespace fat_tree_operation
} // namespace disked
