#include "fat_retention.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <limits>
#include <set>

namespace disked {
namespace {
using V = json::Value;
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const unsigned char *bytes, std::size_t count) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(count * 2);
    for (std::size_t n = 0; n < count; ++n) {
        out += digits[bytes[n] >> 4];
        out += digits[bytes[n] & 15];
    }
    return out;
}
std::string hash(const char *bytes, std::size_t count) {
    unsigned char out[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes), count, out);
    return "sha256:" + hex(out, 32);
}
std::string text(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p || p->kind != V::Kind::string)
        throw FatRetentionError("invalid_parameter");
    return p->text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw FatRetentionError("invalid_parameter");
    return std::stoull(s);
}
V result(const char *schema, const char *phase) {
    return V::object()
        .put("schema", V::string(schema))
        .put("scope", V::string("retained-fat-capture"))
        .put("phase", V::string(phase))
        .put("lifetime", V::string("current-process"))
        .put("authorizes_effects", V::boolean_value(false))
        .put("current_source_qualified", V::boolean_value(false));
}
} // namespace
FatCaptureStore::FatCaptureStore(std::function<std::string()> source)
    : domain_source_(std::move(source)) {
}
std::string FatCaptureStore::reserve(const std::string &request) {
    if (request.empty() || request.size() > 4096 || !json::valid_utf8(request) ||
        request.find('\0') != request.npos)
        throw FatRetentionError("invalid_parameter");
    std::lock_guard<std::mutex> lock(mutex_);
    if (entries_.size() == slots || sequence_ == std::numeric_limits<std::uint64_t>::max())
        throw FatRetentionError("capture_retention_resource");
    if (domain_.empty()) {
        if (!domain_source_)
            throw FatRetentionError("capture_retention_identity");
        auto domain = domain_source_();
        if (domain.size() != 32 || domain.find_first_not_of("0123456789abcdef") != domain.npos)
            throw FatRetentionError("capture_retention_identity");
        domain_ = std::move(domain);
    }
    const auto id = "fat-capture:" + domain_ + ":" + std::to_string(++sequence_);
    Entry entry;
    entry.request_id = request;
    entries_.emplace(id, std::move(entry));
    return id;
}
V FatCaptureStore::commit(const std::string &id, const V &record) {
    json::Limits limits;
    limits.bytes = record_bytes;
    limits.string_bytes = 8 * 1024 * 1024;
    limits.values = 524288;
    limits.depth = 40;
    std::string encoded;
    try {
        encoded = json::dump(record, limits);
    } catch (const json::Error &) {
        throw FatRetentionError("capture_retention_resource");
    }
    const auto digest = hash(encoded.data(), encoded.size());
    auto bytes = std::make_shared<const std::string>(std::move(encoded));
    std::lock_guard<std::mutex> lock(mutex_);
    const auto at = entries_.find(id);
    if (at == entries_.end() || at->second.bytes)
        throw FatRetentionError("capture_retention_unknown");
    auto receipt = V::object()
                       .put("capture_id", V::string(id))
                       .put("bytes", number(bytes->size()))
                       .put("sha256", V::string(digest))
                       .put("lifetime", V::string("current-process"));
    at->second.sha256 = digest;
    at->second.bytes = std::move(bytes);
    return receipt;
}
void FatCaptureStore::abandon(const std::string &id) noexcept {
    try {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto at = entries_.find(id);
        if (at != entries_.end() && !at->second.bytes)
            entries_.erase(at);
    } catch (...) {
    }
}
V FatCaptureStore::list() const {
    auto rows = V::array();
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto &pair : entries_) {
        const auto &entry = pair.second;
        rows.items.push_back(V::object()
                                 .put("capture_id", V::string(pair.first))
                                 .put("request_id", V::string(entry.request_id))
                                 .put("state", V::string(entry.bytes ? "retained" : "reserved"))
                                 .put("bytes", entry.bytes ? number(entry.bytes->size()) : V{})
                                 .put("sha256", entry.bytes ? V::string(entry.sha256) : V{}));
    }
    return result("org.disked.retained-fat-captures/1", "list")
        .put("captures", std::move(rows))
        .put("capacity", number(slots))
        .put("record_byte_limit", number(record_bytes));
}
V FatCaptureStore::read(const std::string &id, std::uint64_t offset, std::uint64_t count) const {
    if (!valid_fat_capture_id(id) || !count || count > chunk_bytes)
        throw FatRetentionError("invalid_parameter");
    std::shared_ptr<const std::string> bytes;
    std::string digest;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto at = entries_.find(id);
        if (at == entries_.end())
            throw FatRetentionError("capture_retention_unknown");
        if (!at->second.bytes)
            throw FatRetentionError("capture_retention_busy");
        bytes = at->second.bytes;
        digest = at->second.sha256;
    }
    if (offset > bytes->size())
        throw FatRetentionError("capture_retention_range");
    const auto size = static_cast<std::size_t>(
        (std::min)(count, static_cast<std::uint64_t>(bytes->size()) - offset));
    const auto first = bytes->data() + static_cast<std::size_t>(offset);
    return result("org.disked.retained-fat-capture-chunk/1", "read")
        .put("capture_id", V::string(id))
        .put("total_bytes", number(bytes->size()))
        .put("byte_offset", number(offset))
        .put("returned_bytes", number(size))
        .put("next_offset", offset + size == bytes->size() ? V{} : number(offset + size))
        .put("record_sha256", V::string(digest))
        .put("encoding", V::string("hex-json-utf8"))
        .put("chunk_sha256", V::string(hash(first, size)))
        .put("data", V::string(hex(reinterpret_cast<const unsigned char *>(first), size)));
}
V FatCaptureStore::release(const std::string &id) {
    if (!valid_fat_capture_id(id))
        throw FatRetentionError("invalid_parameter");
    std::lock_guard<std::mutex> lock(mutex_);
    const auto at = entries_.find(id);
    if (at == entries_.end())
        throw FatRetentionError("capture_retention_unknown");
    if (!at->second.bytes)
        throw FatRetentionError("capture_retention_busy");
    entries_.erase(at);
    return result("org.disked.retained-fat-capture-release/1", "release")
        .put("capture_id", V::string(id))
        .put("released", V::boolean_value(true));
}
Outcome dispatch_fat_capture(const std::string &request, const std::string &command,
                             const V &parameters, FatCaptureStore &store) {
    try {
        if (parameters.kind != V::Kind::object)
            return refused(request, "invalid_parameter", 2);
        const auto *phase = parameters.find("phase");
        const bool release = command == "image.capture.release";
        if (!release && command != "image.capture.inspect")
            return refused(request, "command_unavailable", 3);
        const auto selected = release ? "release" : phase ? text(parameters, "phase") : "list";
        if (!release && selected != "list" && selected != "read")
            return refused(request, "invalid_parameter", 2);
        const std::set<std::string> allowed =
            release ? std::set<std::string>{"capture_id"}
            : selected == "list"
                ? std::set<std::string>{"phase"}
                : std::set<std::string>{"phase", "capture_id", "byte_offset", "byte_count"};
        for (const auto &field : parameters.fields)
            if (!allowed.count(field.first))
                return refused(request, "invalid_parameter", 2);
        if (selected == "list")
            return completed(request, store.list());
        const auto id = text(parameters, "capture_id");
        if (!valid_fat_capture_id(id))
            return refused(request, "invalid_parameter", 2);
        if (release)
            return completed(request, store.release(id));
        return completed(request, store.read(id, integer(parameters, "byte_offset"),
                                             integer(parameters, "byte_count")));
    } catch (const FatRetentionError &e) {
        return refused(request, e.what(), std::string(e.what()) == "invalid_parameter" ? 2 : 3);
    } catch (const std::exception &) {
        return refused(request, "internal_error", 4);
    }
}
} // namespace disked
