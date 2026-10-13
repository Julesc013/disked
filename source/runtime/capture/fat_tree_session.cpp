#include "fat_tree_session.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <chrono>
#include <limits>
#include <set>
#include <thread>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw FatTreeSessionError("tree_session_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw FatTreeSessionError("tree_session_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string || !json::decimal_u64(p.text))
        throw FatTreeSessionError("invalid_parameter");
    return std::stoull(p.text);
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
json::Limits limits() {
    json::Limits l;
    l.bytes = FatTreeSessions::record_bytes;
    l.depth = 40;
    l.values = 262144;
    l.string_bytes = 65536;
    return l;
}
std::string hex(const char *bytes, std::size_t count) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(count * 2);
    for (std::size_t i = 0; i < count; ++i) {
        const auto c = static_cast<unsigned char>(bytes[i]);
        out += digits[c >> 4];
        out += digits[c & 15];
    }
    return out;
}
std::string hash(const std::string &bytes) {
    unsigned char digest[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), digest);
    return "sha256:" + hex(reinterpret_cast<const char *>(digest), sizeof(digest));
}
bool equal(const V &a, const V &b) {
    return json::dump(a, limits()) == json::dump(b, limits());
}
bool exited(const V &w) {
    const auto *worker = w.find("worker");
    const auto *state = worker ? worker->find("observation") : nullptr;
    return state && state->kind == V::Kind::string && state->text == "exited";
}
V result(const std::string &phase, const std::string &id = "") {
    auto out = V::object()
                   .put("schema", V::string("org.disked.fat-tree-session/1"))
                   .put("scope", V::string("ordinary-local-file-fat-tree"))
                   .put("phase", V::string(phase))
                   .put("process_lifetime_only", V::boolean_value(true))
                   .put("atomic_snapshot", V::string("not_established"))
                   .put("current_source_authority", V::boolean_value(false))
                   .put("authorizes_effects", V::boolean_value(false));
    if (!id.empty())
        out.put("session_id", V::string(id));
    return out;
}
FatTreeOpenRequest decode(const V &p) {
    const std::set<std::string> allowed = {"phase",
                                           "path",
                                           "volume_offset",
                                           "volume_bytes",
                                           "fat_copy",
                                           "page_records",
                                           "page_events",
                                           "page_reads",
                                           "page_read_bytes",
                                           "page_output_bytes",
                                           "bitmap_bytes",
                                           "queued_directories",
                                           "depth"};
    for (const auto &pair : p.fields)
        if (!allowed.count(pair.first))
            throw FatTreeSessionError("invalid_parameter");
    FatTreeOpenRequest r;
    r.path = text(p, "path");
    if (r.path.empty() || r.path.size() > 32768 || !json::valid_utf8(r.path) ||
        r.path.find('\0') != r.path.npos)
        throw FatTreeSessionError("invalid_parameter");
    r.volume_offset = integer(p, "volume_offset");
    r.volume_bytes = integer(p, "volume_bytes");
    if (r.volume_bytes < 512 || r.volume_offset > UINT64_MAX - r.volume_bytes)
        throw FatTreeSessionError("invalid_parameter");
    const auto bounded = [&](const char *key, std::uint64_t fallback, std::uint64_t minimum,
                             std::uint64_t maximum) {
        const auto n = p.find(key) ? integer(p, key) : fallback;
        if (n < minimum || n > maximum)
            throw FatTreeSessionError("invalid_parameter");
        return n;
    };
    r.fat_copy = static_cast<std::uint32_t>(bounded("fat_copy", 0, 0, UINT32_MAX));
    r.page.records = static_cast<std::size_t>(bounded("page_records", r.page.records, 1, 1024));
    r.page.events = static_cast<std::size_t>(bounded("page_events", r.page.events, 1, 512));
    r.page.reads = static_cast<std::size_t>(bounded("page_reads", r.page.reads, 1, 512));
    r.page.read_bytes =
        static_cast<std::size_t>(bounded("page_read_bytes", r.page.read_bytes, 4096, 65536));
    r.page.output_bytes =
        static_cast<std::size_t>(bounded("page_output_bytes", r.page.output_bytes, 32768, 65536));
    r.resources.bitmap_bytes =
        static_cast<std::size_t>(bounded("bitmap_bytes", r.resources.bitmap_bytes, 1, 67108864));
    r.resources.queued_directories = static_cast<std::size_t>(
        bounded("queued_directories", r.resources.queued_directories, 1, 65536));
    r.resources.depth = static_cast<std::size_t>(bounded("depth", r.resources.depth, 1, 1024));
    return r;
}
} // namespace
struct FatTreeSessions::Entry {
    std::mutex mutex;
    std::unique_ptr<FatTreeCursor> cursor;
    V source, binding, worker, page, context;
    std::shared_ptr<const std::string> bytes;
    std::string digest, page_digest, failed;
    std::uint64_t sequence = 0;
    bool cancelled = false, closing = false, streaming = false;
};
bool valid_fat_tree_session_id(const std::string &id) {
    if (id.size() < 43 || id.size() > 62 || id.compare(0, 9, "fat-tree:") || id[41] != ':' ||
        id.substr(9, 32).find_first_not_of("0123456789abcdef") != std::string::npos)
        return false;
    const auto n = id.substr(42);
    return json::decimal_u64(n) && n != "0";
}
FatTreeSessions::FatTreeSessions(std::function<std::string()> domain, FatTreeCursorFactory factory)
    : domain_source_(std::move(domain)), factory_(std::move(factory)) {
    if (!domain_source_ || !factory_)
        throw std::invalid_argument("tree_session_ports");
}
FatTreeSessions::~FatTreeSessions() = default;
Outcome FatTreeSessions::dispatch(const std::string &request, const V &p) {
    return dispatch_impl(request, p, false);
}
Outcome FatTreeSessions::dispatch_impl(const std::string &request, const V &p, bool stream_owner) {
    std::shared_ptr<Entry> entry;
    std::string id, phase;
    try {
        if (p.kind != V::Kind::object)
            throw FatTreeSessionError("invalid_parameter");
        phase = p.find("phase") ? text(p, "phase") : "list";
        if (phase == "scan")
            return refused(request, "tree_stream_requires_ndjson", 3);
        if (phase == "list") {
            if (p.fields.size() > (p.find("phase") ? 1U : 0U))
                throw FatTreeSessionError("invalid_parameter");
            auto rows = V::array();
            std::lock_guard<std::mutex> lock(mutex_);
            for (const auto &pair : entries_) {
                std::unique_lock<std::mutex> owner(pair.second->mutex, std::try_to_lock);
                rows.items.push_back(
                    V::object()
                        .put("session_id", V::string(pair.first))
                        .put("state", V::string(!owner                 ? "busy"
                                                : !pair.second->cursor ? "opening"
                                                : pair.second->closing ? "closing"
                                                                       : "owned")));
            }
            return completed(
                request,
                result(phase).put("sessions", std::move(rows)).put("capacity", number(slots)));
        }
        if (phase == "open") {
            FatTreeOpenRequest input;
            try {
                input = decode(p);
            } catch (const FatTreeSessionError &) {
                throw FatTreeSessionError("invalid_parameter");
            }
            entry = std::make_shared<Entry>();
            std::unique_lock<std::mutex> owner(entry->mutex);
            {
                std::lock_guard<std::mutex> lock(mutex_);
                if (entries_.size() == slots)
                    throw FatTreeSessionError("tree_session_capacity");
                if (sequence_ == UINT64_MAX)
                    throw FatTreeSessionError("tree_session_sequence_exhausted");
                if (domain_.empty()) {
                    const auto domain = domain_source_();
                    if (domain.size() != 32 ||
                        domain.find_first_not_of("0123456789abcdef") != domain.npos)
                        throw FatTreeSessionError("tree_session_identity");
                    domain_ = domain;
                }
                input.epoch = ++sequence_;
                id = "fat-tree:" + domain_ + ":" + std::to_string(input.epoch);
                entries_.emplace(id, entry);
            }
            try {
                entry->cursor = factory_(input);
                if (!entry->cursor)
                    throw FatTreeSessionError("tree_session_provider");
                entry->source = entry->cursor->source();
                entry->worker = entry->cursor->observe();
            } catch (...) {
                // Concrete cursor destruction retains its handles through exit.
                entry->cursor.reset();
                std::lock_guard<std::mutex> lock(mutex_);
                entries_.erase(id);
                throw;
            }
            return completed(request, result(phase, id)
                                          .put("source", entry->source)
                                          .put("worker", entry->worker)
                                          .put("state", V::string("owned")));
        }
        const std::set<std::string> phases = {"next", "read", "status", "cancel", "close"};
        if (!phases.count(phase))
            throw FatTreeSessionError("invalid_parameter");
        const std::set<std::string> allowed =
            phase == "read" ? std::set<std::string>{"phase", "session_id", "page_sequence",
                                                    "byte_offset", "byte_count"}
                            : std::set<std::string>{"phase", "session_id"};
        for (const auto &pair : p.fields)
            if (!allowed.count(pair.first))
                throw FatTreeSessionError("invalid_parameter");
        id = text(p, "session_id");
        if (!valid_fat_tree_session_id(id))
            throw FatTreeSessionError("invalid_parameter");
        if (phase == "read") {
            if (!integer(p, "page_sequence") || !integer(p, "byte_count") ||
                integer(p, "byte_count") > chunk_bytes)
                throw FatTreeSessionError("invalid_parameter");
            (void)integer(p, "byte_offset");
        }
        {
            std::lock_guard<std::mutex> lock(mutex_);
            const auto at = entries_.find(id);
            if (at == entries_.end())
                throw FatTreeSessionError("tree_session_unknown");
            entry = at->second;
        }
        std::unique_lock<std::mutex> owner(entry->mutex, std::try_to_lock);
        if (!owner || !entry->cursor)
            throw FatTreeSessionError("tree_session_busy");
        if (entry->streaming && !stream_owner &&
            (phase == "next" || phase == "read" || phase == "close"))
            throw FatTreeSessionError("tree_session_busy");
        auto out = result(phase, id);
        if (phase == "read") {
            if (!entry->bytes)
                throw FatTreeSessionError("tree_session_no_page");
            if (integer(p, "page_sequence") != entry->sequence)
                throw FatTreeSessionError("tree_session_stale_page");
            const auto offset = integer(p, "byte_offset"), count = integer(p, "byte_count");
            if (offset > entry->bytes->size())
                throw FatTreeSessionError("tree_session_range");
            const auto n = static_cast<std::size_t>(
                (std::min)(count, static_cast<std::uint64_t>(entry->bytes->size()) - offset));
            const auto part = entry->bytes->substr(static_cast<std::size_t>(offset), n);
            out.put("page_sequence", number(entry->sequence))
                .put("record_sha256", V::string(entry->digest))
                .put("total_bytes", number(entry->bytes->size()))
                .put("byte_offset", number(offset))
                .put("returned_bytes", number(n))
                .put("encoding", V::string("hex-json-utf8"))
                .put("chunk_sha256", V::string(hash(part)))
                .put("data", V::string(hex(part.data(), part.size())))
                .put("next_offset", offset + n == entry->bytes->size() ? V{} : number(offset + n));
            return completed(request, std::move(out));
        }
        if (phase == "cancel" || phase == "close") {
            if (phase == "cancel")
                entry->cancelled = true;
            entry->closing = phase == "close" || entry->closing;
            entry->worker = entry->cursor->stop(phase == "close");
            if (const auto *requested = entry->worker.find("cancellation_requested"))
                if (requested->kind == V::Kind::boolean)
                    entry->cancelled = entry->cancelled || requested->boolean;
        } else if (phase == "next" && entry->failed.empty() && !entry->closing) {
            const auto read = entry->cursor->poll();
            entry->worker = read.worker;
            if (read.packet) {
                const auto &page = field(read.packet->frame, "page");
                const auto sequence = integer(page, "sequence");
                if (entry->sequence == UINT64_MAX || sequence != entry->sequence + 1 ||
                    !equal(field(page, "previous_page_digest"),
                           entry->page_digest.empty() ? V{} : V::string(entry->page_digest)))
                    throw FatTreeSessionError("tree_session_page_sequence");
                auto unhashed = page;
                const auto page_digest = text(page, "page_digest");
                unhashed.fields.erase("page_digest");
                if (fat_traversal_page_digest(unhashed) != page_digest)
                    throw FatTreeSessionError("tree_session_page_digest");
                if (entry->sequence && !equal(field(page, "binding"), entry->binding))
                    throw FatTreeSessionError("tree_session_page_binding");
                if (!equal(field(read.packet->frame, "source_before"), entry->source))
                    throw FatTreeSessionError("tree_session_page_source");
                auto record = V::object()
                                  .put("schema", V::string("org.disked.fat-tree-page-record/1"))
                                  .put("frame", read.packet->frame)
                                  .put("context", read.packet->context);
                auto bytes = std::make_shared<const std::string>(json::dump(record, limits()));
                const auto digest = hash(*bytes);
                entry->binding = field(page, "binding");
                entry->page = page;
                entry->context = read.packet->context;
                entry->bytes = std::move(bytes);
                entry->digest = digest;
                entry->sequence = sequence;
                entry->page_digest = page_digest;
                out.put("page", entry->page).put("context", entry->context);
            }
        } else
            entry->worker = entry->cursor->observe();
        if (phase == "next" && text(entry->worker, "status") == "unknown" && entry->failed.empty())
            entry->failed = "tree_session_worker_unresolved";
        out.put("worker", entry->worker)
            .put("cancellation_requested", V::boolean_value(entry->cancelled))
            .put("state", V::string(entry->closing           ? "closing"
                                    : !entry->failed.empty() ? "unknown"
                                    : out.find("page")       ? "page"
                                                             : "pending"));
        if (entry->bytes)
            out.put("record", V::object()
                                  .put("page_sequence", number(entry->sequence))
                                  .put("bytes", number(entry->bytes->size()))
                                  .put("sha256", V::string(entry->digest)));
        if (phase == "close" && exited(entry->worker)) {
            out.put("state", V::string("closed"));
            std::lock_guard<std::mutex> lock(mutex_);
            entries_.erase(id);
        }
        if (phase == "next" && !entry->failed.empty()) {
            auto unresolved = completed(request, std::move(out));
            unresolved.exit_code = 6;
            unresolved.response.put("status", V::string("unknown"));
            unresolved.response.fields["diagnostics"].items.push_back(diagnostic(entry->failed));
            return unresolved;
        }
        return completed(request, std::move(out));
    } catch (const std::exception &error) {
        const auto *typed = dynamic_cast<const FatTreeSessionError *>(&error);
        const std::string code = typed ? error.what() : "tree_session_internal";
        const bool failed_page =
            phase == "next" && entry && code != "invalid_parameter" && code != "tree_session_busy";
        if (failed_page) {
            std::lock_guard<std::mutex> lock(entry->mutex);
            entry->failed = code;
            try {
                entry->worker = entry->cursor->stop(false);
            } catch (...) {
            }
            auto out = completed(
                request,
                result(phase, id).put("state", V::string("unknown")).put("worker", entry->worker));
            out.exit_code = 6;
            out.response.put("status", V::string("unknown"));
            out.response.fields["diagnostics"].items.push_back(diagnostic(code));
            return out;
        }
        auto out = refused(request, code, code == "invalid_parameter" ? 2 : typed ? 3 : 4);
        if (typed && typed->platform_code)
            out.response.fields["diagnostics"].items[0].put("platform_code",
                                                            number(typed->platform_code));
        return out;
    }
}
Outcome FatTreeSessions::stream(const std::string &request, const V &p,
                                const ResponseSink &output) {
    using Clock = std::chrono::steady_clock;
    std::string id;
    std::shared_ptr<Entry> retained;
    const auto call = [&](const char *phase) {
        return dispatch_impl(
            request, V::object().put("phase", V::string(phase)).put("session_id", V::string(id)),
            true);
    };
    const auto close = [&]() {
        auto closed = call("close");
        const auto deadline = Clock::now() + std::chrono::milliseconds(2000);
        while (!closed.exit_code && text(field(closed.response, "result"), "state") != "closed" &&
               Clock::now() < deadline) {
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
            closed = call("close");
        }
        return closed;
    };
    std::uint64_t emitted = 0;
    const auto emit = [&](Outcome event, const char *kind) {
        auto &body = event.response.fields.at("result");
        body.put("phase", V::string("scan"))
            .put("request_kind", V::string("tree-stream-event"))
            .put("event_kind", V::string(kind))
            .put("stream_sequence", number(++emitted))
            .put("final", V::boolean_value(false));
        return output(event.response);
    };
    struct Lease {
        std::shared_ptr<Entry> &entry;
        ~Lease() {
            if (entry) {
                std::lock_guard<std::mutex> lock(entry->mutex);
                entry->streaming = false;
            }
        }
    } lease{retained};
    try {
        if (!output || p.kind != V::Kind::object || text(p, "phase") != "scan")
            return refused(request, "invalid_parameter", 2);
        const auto pages = p.find("max_pages") ? integer(p, "max_pages") : 4096;
        const auto idle = p.find("idle_ms") ? integer(p, "idle_ms") : 30000;
        if (!pages || pages > 65536 || !idle || idle > 30000)
            return refused(request, "invalid_parameter", 2);
        auto input = p;
        input.put("phase", V::string("open"));
        input.fields.erase("max_pages");
        input.fields.erase("idle_ms");
        auto opened = dispatch_impl(request, input, true);
        if (opened.exit_code)
            return opened;
        id = text(field(opened.response, "result"), "session_id");
        {
            std::lock_guard<std::mutex> lock(mutex_);
            retained = entries_.at(id);
        }
        {
            std::lock_guard<std::mutex> lock(retained->mutex);
            retained->streaming = true;
        }
        if (!emit(std::move(opened), "opened")) {
            close();
            return refused(request, "output_error", 4);
        }
        auto deadline = Clock::now() + std::chrono::milliseconds(idle);
        std::uint64_t received = 0;
        V last_page;
        std::string problem, coverage;
        for (;;) {
            auto next = call("next");
            const bool uncertain_page =
                next.exit_code == 6 && field(next.response, "result").find("page");
            if (next.exit_code && !uncertain_page) {
                problem = "tree_stream_page_unresolved";
                break;
            }
            const auto &body = field(next.response, "result");
            if (const auto *page = body.find("page")) {
                last_page = *page;
                ++received;
                const auto receipt = field(body, "record");
                if (!emit(std::move(next), "page")) {
                    close();
                    return refused(request, "output_error", 4);
                }
                std::uint64_t offset = 0;
                for (;;) {
                    auto params = V::object()
                                      .put("phase", V::string("read"))
                                      .put("session_id", V::string(id))
                                      .put("page_sequence", field(receipt, "page_sequence"))
                                      .put("byte_offset", number(offset))
                                      .put("byte_count", number(chunk_bytes));
                    auto bytes = dispatch_impl(request, params, true);
                    if (bytes.exit_code) {
                        problem = "tree_stream_record_unresolved";
                        break;
                    }
                    const auto following = field(field(bytes.response, "result"), "next_offset");
                    if (!emit(std::move(bytes), "record-chunk")) {
                        close();
                        return refused(request, "output_error", 4);
                    }
                    if (following.kind == V::Kind::null)
                        break;
                    offset = std::stoull(following.text);
                }
                if (!problem.empty())
                    break;
                if (uncertain_page) {
                    problem = "tree_stream_page_unresolved";
                    break;
                }
                deadline = Clock::now() + std::chrono::milliseconds(idle);
                if (text(last_page, "status") != "running")
                    coverage = text(last_page, "status");
                if (received == pages && coverage.empty()) {
                    problem = "tree_stream_page_limit";
                    break;
                }
            } else {
                const auto &worker = field(body, "worker");
                if (text(worker, "status") == "unknown") {
                    problem = "tree_stream_worker_unresolved";
                    break;
                }
                if (text(worker, "status") == "completed" && exited(worker)) {
                    const auto status = text(field(worker, "result"), "status");
                    if (status == "cancelled")
                        coverage = "cancelled";
                    else if (status != "completed" || coverage.empty())
                        problem = "tree_stream_final_unresolved";
                    break;
                }
                if (Clock::now() >= deadline) {
                    problem = "tree_stream_progress_expired";
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
        }
        const auto closed = close();
        if (closed.exit_code || text(field(closed.response, "result"), "state") != "closed")
            problem = "tree_stream_retirement_unresolved";
        auto final = result("scan", id)
                         .put("request_kind", V::string("tree-stream-outcome"))
                         .put("final", V::boolean_value(true))
                         .put("events_emitted", number(emitted))
                         .put("pages", number(received))
                         .put("coverage", coverage.empty() ? V{} : V::string(coverage))
                         .put("last_page", last_page)
                         .put("closure", field(closed.response, "result"));
        auto outcome = completed(request, std::move(final));
        if (!problem.empty()) {
            outcome.exit_code = 6;
            outcome.response.put("status", V::string("unknown"));
            outcome.response.fields["diagnostics"].items.push_back(diagnostic(problem));
        }
        return outcome;
    } catch (const std::exception &) {
        if (!id.empty())
            try {
                close();
            } catch (...) {
            }
        return refused(request, "tree_stream_internal", 4);
    }
}
} // namespace disked
