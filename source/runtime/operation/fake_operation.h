#pragma once
#include "json.h"
#include <cstddef>
#include <string>

namespace disked { namespace fake_operation {
// Private DE-W016 simulation evidence, not a production storage journal.
constexpr std::size_t record_limit = 16384;
constexpr std::size_t history_limit = 1048576;
constexpr std::size_t record_count_limit = 64;
std::string hash(const std::string& bytes);
bool fixture(const std::string& id);
void validate_binding(const json::Value& binding);
json::Value origin(const json::Value& binding);

class Operation {
    json::Value state_;
public:
    explicit Operation(const json::Value& binding);
    const json::Value& state() const { return state_; }
    bool terminal() const;
    // Returns false for an idempotent cancellation/checkpoint that changes nothing.
    // Invalid identities, transitions or counts throw without changing state.
    bool advance(const std::string& action, const json::Value& observation_origin,
        const std::string& observed_count = "");
};

struct History {
    json::Value state;
    std::string digest = std::string(64, '0');
    std::size_t count = 0;
};
std::string record(const json::Value& state, const std::string& previous);
// A complete, bounded, replay-validated history is required. No tail repair.
History read_history(const std::string& bytes);
}}
