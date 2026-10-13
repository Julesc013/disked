#include "fat_content_file.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
[[noreturn]] void fail() {
    throw std::invalid_argument("fat_file_content_input");
}
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        fail();
    return *p;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string || !json::decimal_u64(p.text))
        fail();
    return std::stoull(p.text);
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        fail();
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            fail();
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
} // namespace
void validate_fat_file_content_request(const FatFileContentRequest &r) {
    if (!r.reference_capture_epoch || r.node_id >= 128 || r.expected_file_bytes > 0xffffffffULL ||
        r.offset > r.expected_file_bytes || !r.count || r.count > r.limits.bytes ||
        !r.limits.bytes || r.limits.bytes > 196608 || !r.limits.read_requests ||
        r.limits.read_requests > 512 || !r.limits.read_chunk || r.limits.read_chunk > 4096 ||
        r.metadata_digest.size() != 71 || r.metadata_digest.substr(0, 7) != "sha256:" ||
        r.metadata_digest.find_first_not_of("0123456789abcdef", 7) != std::string::npos)
        fail();
}
V fat_file_content_request_value(const FatFileContentRequest &r) {
    validate_fat_file_content_request(r);
    return V::object()
        .put("reference_capture_epoch", number(r.reference_capture_epoch))
        .put("node_id", number(r.node_id))
        .put("expected_file_bytes", number(r.expected_file_bytes))
        .put("offset", number(r.offset))
        .put("count", number(r.count))
        .put("metadata_digest", V::string(r.metadata_digest))
        .put("limits", V::object()
                           .put("bytes", number(r.limits.bytes))
                           .put("read_requests", number(r.limits.read_requests))
                           .put("read_chunk", number(r.limits.read_chunk)));
}
FatFileContentRequest fat_file_content_request_from(const V &v) {
    exact(v, {"reference_capture_epoch", "node_id", "expected_file_bytes", "offset", "count",
              "metadata_digest", "limits"});
    FatFileContentRequest r;
    r.reference_capture_epoch = integer(v, "reference_capture_epoch");
    r.node_id = integer(v, "node_id");
    r.expected_file_bytes = integer(v, "expected_file_bytes");
    r.offset = integer(v, "offset");
    const auto count = integer(v, "count");
    const auto &l = field(v, "limits");
    exact(l, {"bytes", "read_requests", "read_chunk"});
    const auto bytes = integer(l, "bytes"), reads = integer(l, "read_requests"),
               chunk = integer(l, "read_chunk");
    if (count > 196608 || bytes > 196608 || reads > 512 || chunk > 4096)
        fail();
    r.count = static_cast<std::size_t>(count);
    r.limits = {static_cast<std::size_t>(bytes), static_cast<std::size_t>(reads),
                static_cast<std::size_t>(chunk)};
    const auto &digest = field(v, "metadata_digest");
    if (digest.kind != V::Kind::string)
        fail();
    r.metadata_digest = digest.text;
    validate_fat_file_content_request(r);
    return r;
}
std::string fat_content_metadata_digest(const V &observation) {
    const auto &schema = field(observation, "schema");
    if (schema.kind != V::Kind::string || schema.text != "org.disked.fat-volume-observation/1" ||
        !integer(observation, "capture_epoch"))
        fail();
    auto value = observation;
    value.put("capture_epoch", number(0));
    const auto bytes = json::dump(value, {1048576, 40, 262144, 32768});
    unsigned char hash[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), hash);
    static const char hex[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (auto b : hash) {
        out += hex[b >> 4];
        out += hex[b & 15];
    }
    return out;
}
} // namespace disked
