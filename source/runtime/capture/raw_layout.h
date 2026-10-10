#pragma once
#include "json.h"
#include "checked.h"
#include <memory>
#include <vector>

namespace disked {
struct RawLayoutPolicy {unsigned partitions=64,ebr_nodes=128;};
struct RawLayoutError : std::runtime_error {
    explicit RawLayoutError(const char* code):std::runtime_error(code) {}
};
class RawPartitionLayout;
json::Limits raw_layout_limits();
// Supplied bytes remain immutable until return. No file/device access or borrows
// escape; metadata completeness does not assert source/acquisition consistency.
std::shared_ptr<const RawPartitionLayout> decode_raw_layout(
    const std::vector<unsigned char>&,const de_u64& blocks,de_u32 unit,
    RawLayoutPolicy policy={});
class RawPartitionLayout final {
    const json::Value value_;
    explicit RawPartitionLayout(json::Value v):value_(std::move(v)) {}
    friend std::shared_ptr<const RawPartitionLayout> decode_raw_layout(
        const std::vector<unsigned char>&,const de_u64&,de_u32,RawLayoutPolicy);
public:
    const json::Value& value() const {return value_;}
};
}
