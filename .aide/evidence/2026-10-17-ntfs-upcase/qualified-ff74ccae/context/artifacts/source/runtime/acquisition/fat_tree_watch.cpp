#include "fat_tree_watch.h"
#include "portable/hash/sha256.h"

namespace disked {
namespace fat_tree_operation {
namespace {
using V = json::Value;
[[noreturn]] void fail(const char *code) {
    throw Error(code);
}
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        fail("fat_tree_watch_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        fail("fat_tree_watch_shape");
    return p.text;
}
std::string optional(const V &v, const char *key, const std::string &fallback = {}) {
    return v.find(key) ? text(v, key) : fallback;
}
std::size_t number(const std::string &s) {
    if (!json::decimal_u64(s))
        fail("fat_tree_watch_integer");
    const auto n = std::stoull(s);
    if (n > 2000)
        fail("fat_tree_watch_budget");
    return static_cast<std::size_t>(n);
}
void identity(const std::string &s, const std::string &prefix, std::size_t length) {
    if (s.size() != prefix.size() + length || s.compare(0, prefix.size(), prefix) ||
        s.find_first_not_of("0123456789abcdef", prefix.size()) != s.npos)
        fail("fat_tree_watch_identity");
}
std::string hash(const std::string &bytes) {
    unsigned char out[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), out);
    const char chars[] = "0123456789abcdef";
    std::string result = "sha256:";
    for (auto b : out) {
        result += chars[b >> 4];
        result += chars[b & 15];
    }
    return result;
}
std::string record_digest(const V &v) {
    return hash(json::dump(v, record_limits()) + "\n");
}
bool snapshot(const V &v) {
    const auto *p = v.find("snapshot");
    return p && p->boolean;
}
} // namespace
void validate_watch_options(const V &v) {
    if (v.kind != V::Kind::object)
        fail("fat_tree_watch_shape");
    for (const auto &item : v.fields)
        if (item.first != "after_sequence" && item.first != "after_digest" &&
            item.first != "worker_epoch" && item.first != "follow_ms" && item.first != "snapshot")
            fail("fat_tree_watch_shape");
    const auto after = number(optional(v, "after_sequence", "0"));
    if (after > 64)
        fail("fat_tree_watch_cursor_ahead");
    if (number(optional(v, "follow_ms", "0")) > 2000)
        fail("fat_tree_watch_budget");
    const auto worker = optional(v, "worker_epoch"), digest = optional(v, "after_digest");
    if (!worker.empty())
        identity(worker, "worker:", 32);
    if (!digest.empty())
        identity(digest, "", 64);
    if (const auto *p = v.find("snapshot"))
        if (p->kind != V::Kind::boolean)
            fail("fat_tree_watch_shape");
    if (after && (worker.empty() || digest.empty()))
        fail("fat_tree_watch_cursor_incomplete");
    if ((!after && !digest.empty()) || (after && snapshot(v)))
        fail("fat_tree_watch_cursor_conflict");
}
Watch::Watch(const std::string &operation, const std::string &request, const std::string &observer,
             const V &options)
    : operation_(operation), request_(request), observer_(observer),
      digest_("sha256:" + std::string(64, '0')) {
    validate_watch_options(options);
    identity(operation, "tree-op:", 32);
    identity(observer, "watch:", 32);
    if (request.empty() || request.size() > 128 || request.find('\0') != request.npos)
        fail("fat_tree_watch_request");
    sequence_ = number(optional(options, "after_sequence", "0"));
    worker_ = optional(options, "worker_epoch");
    if (sequence_)
        digest_ = "sha256:" + text(options, "after_digest");
    snapshot_ = snapshot(options);
}
bool Watch::project(const History &h, const EventSink &sink) {
    if (closed_)
        return false;
    if (!sink)
        fail("fat_tree_watch_sink");
    if (!h.complete || h.uncertain)
        fail("fat_tree_watch_history_unresolved");
    if (h.records.size() > 64)
        fail("fat_tree_watch_event_budget");
    std::string retained;
    for (const auto &record : h.records) {
        const auto raw = json::dump(record, record_limits()) + "\n";
        if (raw.size() > 1048576 - retained.size())
            fail("fat_tree_watch_event_budget");
        retained += raw;
    }
    const auto checked = read_history(h.header, retained);
    if (checked.uncertain)
        fail("fat_tree_watch_history_unresolved");
    const auto &header = checked.header;
    if (text(header, "operation_id") != operation_)
        fail("fat_tree_watch_operation");
    const auto hd = hash(json::dump(header, header_limits()));
    const auto worker = text(field(header, "process_owner"), "worker_epoch");
    if (!worker_.empty() && worker_ != worker)
        fail("fat_tree_watch_epoch");
    if (!header_digest_.empty() && hd != header_digest_)
        fail("fat_tree_watch_header_changed");
    if (sequence_ > h.records.size())
        fail("fat_tree_watch_cursor_ahead");
    if (sequence_ && record_digest(h.records[sequence_ - 1]) != digest_)
        fail("fat_tree_watch_cursor_conflict");
    if (h.records.empty())
        fail("fat_tree_watch_no_records");
    // Allocate binding state before delivering anything to the caller's sink.
    worker_ = worker;
    header_digest_ = hd;
    review_digest_ = text(header, "review_digest");
    initialized_ = true;
    const auto begin = snapshot_ ? h.records.size() - 1 : sequence_;
    for (auto i = begin; i < h.records.size(); ++i) {
        const auto &record = h.records[i];
        auto rd = record_digest(record);
        const auto event =
            V::object()
                .put("schema", V::string("org.disked.event/1"))
                .put("operation_id", V::string(operation_))
                .put("sequence", V::string(std::to_string(i + 1)))
                .put("type", V::string(snapshot_ ? "fat.tree.operation.snapshot"
                                                 : "fat.tree.operation.record"))
                .put(
                    "payload",
                    V::object()
                        .put("schema", V::string("org.disked.fat-tree-operation-event-prototype/1"))
                        .put("request_id", V::string(request_))
                        .put("observer_epoch", V::string(observer_))
                        .put("worker_epoch", V::string(worker_))
                        .put("review_digest", V::string(review_digest_))
                        .put("header_digest", V::string(header_digest_))
                        .put("sequence_domain", V::string("fat-tree-control-record-index-plus-one"))
                        .put("record_digest", V::string(rd))
                        .put("record", record));
        const auto bytes = json::dump(event, header_limits()).size();
        if (bytes > 16384 || events_ == 64 || bytes > 1048576 - event_bytes_)
            fail("fat_tree_watch_event_budget");
        // A rejected/throwing sink admits no new cursor. The native wrapper
        // seals this observer; it never retries effects or restarts a worker.
        bool accepted = false;
        try {
            accepted = sink(event);
        } catch (...) {
            closed_ = true;
            throw;
        }
        if (!accepted) {
            closed_ = true;
            return false;
        }
        digest_.swap(rd);
        sequence_ = i + 1;
        ++events_;
        event_bytes_ += bytes;
        snapshot_ = false;
    }
    initialized_ = true;
    return true;
}
V Watch::cursor() const {
    return V::object()
        .put("operation_id", V::string(operation_))
        .put("observer_epoch", V::string(observer_))
        .put("worker_epoch", worker_.empty() ? V{} : V::string(worker_))
        .put("header_digest", header_digest_.empty() ? V{} : V::string(header_digest_))
        .put("review_digest", review_digest_.empty() ? V{} : V::string(review_digest_))
        .put("sequence", V::string(std::to_string(sequence_)))
        .put("last_digest", V::string(digest_))
        .put("events", V::string(std::to_string(events_)))
        .put("event_bytes", V::string(std::to_string(event_bytes_)))
        .put("initialized", V::boolean_value(initialized_))
        .put("closed", V::boolean_value(closed_));
}
Reader::Reader(const V &header, bool snapshot_allowed)
    : header_(validate_header(header)), header_digest_(hash(json::dump(header_, header_limits()))),
      digest_("sha256:" + std::string(64, '0')), snapshot_allowed_(snapshot_allowed) {
}
bool Reader::accept(const V &event) {
    json::dump(event, record_limits());
    const auto required = [](const V &v) {
        if (const auto *r = v.find("required_features"))
            if (r->kind != V::Kind::array || !r->items.empty())
                fail("fat_tree_reader_feature");
    };
    required(event);
    const auto &p = field(event, "payload");
    required(p);
    if (text(event, "schema") != "org.disked.event/1" ||
        text(p, "schema") != "org.disked.fat-tree-operation-event-prototype/1")
        fail("fat_tree_reader_schema");
    const auto type = text(event, "type");
    const bool snapshot = type == "fat.tree.operation.snapshot";
    if (!snapshot && type != "fat.tree.operation.record")
        fail("fat_tree_reader_type");
    if (text(event, "operation_id") != text(header_, "operation_id") ||
        text(p, "header_digest") != header_digest_ ||
        text(p, "review_digest") != text(header_, "review_digest") ||
        text(p, "worker_epoch") != text(field(header_, "process_owner"), "worker_epoch") ||
        text(p, "sequence_domain") != "fat-tree-control-record-index-plus-one")
        fail("fat_tree_reader_binding");
    const auto observer = text(p, "observer_epoch"), request = text(p, "request_id");
    identity(observer, "watch:", 32);
    if (request.empty() || request.size() > 128 || request.find('\0') != request.npos)
        fail("fat_tree_reader_binding");
    if (!observer_.empty() && (observer != observer_ || request != request_))
        fail("fat_tree_reader_observer");
    const auto next = number(text(event, "sequence"));
    const auto &record = field(p, "record");
    if (!next || next > 64 || text(record, "sequence") != std::to_string(next - 1) ||
        text(record, "operation_id") != text(header_, "operation_id") ||
        text(record, "review_digest") != text(header_, "review_digest"))
        fail("fat_tree_reader_sequence");
    const auto rd = record_digest(record);
    if (text(p, "record_digest") != rd)
        fail("fat_tree_reader_digest");
    validate_record(header_, record);
    if (next == sequence_) {
        if (rd != digest_)
            fail("fat_tree_reader_duplicate");
        return false;
    }
    if (snapshot) {
        if (!snapshot_allowed_ || sequence_)
            fail("fat_tree_reader_snapshot");
    } else if (snapshot_mode_ && !records_.empty()) {
        const auto &old = field(field(records_.back(), "payload"), "worker");
        const auto &current = field(field(record, "payload"), "worker");
        if (text(field(records_.back(), "payload"), "phase") == "exited" ||
            (text(field(old, "worker"), "observation") == "exited" &&
             text(field(current, "worker"), "observation") != "exited") ||
            (field(old, "grant_sent").boolean && !field(current, "grant_sent").boolean) ||
            std::stoull(text(current, "progress_pulse")) < std::stoull(text(old, "progress_pulse")))
            fail("fat_tree_reader_progress");
        if (field(old, "outcome").kind != V::Kind::null &&
            json::dump(field(old, "outcome"), header_limits()) !=
                json::dump(field(current, "outcome"), header_limits()))
            fail("fat_tree_reader_progress");
    }
    if (!snapshot && (next != sequence_ + 1 || text(record, "previous") != digest_))
        fail("fat_tree_reader_gap");
    auto candidate = records_;
    if (snapshot || snapshot_mode_) {
        // A snapshot cannot independently prove omitted transition history.
        // Check the actual row without rewriting mutation-critical fields.
        validate_record(header_, record);
        candidate.clear();
        candidate.push_back(record);
    } else {
        candidate.push_back(record);
        std::string bytes;
        for (const auto &r : candidate)
            bytes += json::dump(r, record_limits()) + "\n";
        read_history(header_, bytes);
    }
    auto new_observer = observer, new_request = request, new_digest = rd;
    observer_.swap(new_observer);
    request_.swap(new_request);
    digest_.swap(new_digest);
    records_ = std::move(candidate);
    sequence_ = next;
    snapshot_allowed_ = false;
    snapshot_mode_ = snapshot_mode_ || snapshot;
    return true;
}
V Reader::cursor() const {
    return V::object()
        .put("sequence", V::string(std::to_string(sequence_)))
        .put("last_digest", V::string(digest_))
        .put("header_digest", V::string(header_digest_))
        .put("omitted_prefix_verified", V::boolean_value(!snapshot_mode_))
        .put("authenticity", V::string("not_established"));
}
} // namespace fat_tree_operation
} // namespace disked
