#pragma once
#include "runtime/command/json.h"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace disked { namespace planner { namespace proposal {
using Bytes=std::vector<unsigned char>;
struct RepairError:std::runtime_error {explicit RepairError(const char* code):std::runtime_error(code) {}};
enum class GptCopy { unspecified, primary, backup };
// Supplied observations only; caller keeps inputs immutable during a call.
// Image identity/epoch are declarations, never an opened or authenticated target.
struct GptRepairCapture {
    std::string image_id;
    std::uint64_t epoch=0,blocks=0;
    std::uint32_t block_bytes=0;
    Bytes protective_mbr,primary_header,primary_array,backup_header,backup_array;
};
struct GptRepairSelection {GptCopy source=GptCopy::unspecified;std::string decision_digest;};
struct GptRepairPatch {
    std::string id;
    std::uint64_t offset=0;
    Bytes before,after;
    std::vector<std::string> depends_on;
};
// Bounded canonical captured-byte fingerprint, not source freshness or authority.
std::string gpt_repair_capture_digest(const GptRepairCapture&);
class GptRepairPlan final {
    json::Value definition_;
    std::string digest_,capture_digest_;
    std::vector<GptRepairPatch> patches_;
public:
    GptRepairPlan(const GptRepairCapture&,const std::string& expected_capture_digest,const GptRepairSelection&);
    const json::Value& definition() const {return definition_;}
    const std::string& digest() const {return digest_;}
    const std::vector<GptRepairPatch>& patches() const {return patches_;}
    bool matches_capture(const GptRepairCapture&) const;
};
}}}
