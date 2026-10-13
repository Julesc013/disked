#include "fat_tree_operation.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace fat_tree_operation {
namespace {
using V = json::Value;
[[noreturn]] void fail(const char *code) {
    throw Error(code);
}
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        fail("fat_tree_operation_shape");
    return *p;
}
std::string text(const V &v, const char *name) {
    const auto &p = field(v, name);
    if (p.kind != V::Kind::string)
        fail("fat_tree_operation_shape");
    return p.text;
}
void keys(const V &v, std::initializer_list<const char *> names) {
    if (v.kind != V::Kind::object || v.fields.size() != names.size())
        fail("fat_tree_operation_shape");
    for (const auto *name : names)
        field(v, name);
}
std::uint64_t number(const V &v) {
    if (v.kind != V::Kind::string || !json::decimal_u64(v.text))
        fail("fat_tree_operation_integer");
    return std::stoull(v.text);
}
bool boolean(const V &v) {
    if (v.kind != V::Kind::boolean)
        fail("fat_tree_operation_shape");
    return v.boolean;
}
void identity(const std::string &s, const std::string &prefix, std::size_t n) {
    if (s.size() != prefix.size() + n || s.compare(0, prefix.size(), prefix) ||
        s.find_first_not_of("0123456789abcdef", prefix.size()) != s.npos)
        fail("fat_tree_operation_identity");
}
std::string hash(const std::string &s) {
    unsigned char bytes[32];
    sha256(reinterpret_cast<const unsigned char *>(s.data()), s.size(), bytes);
    std::string out = "sha256:";
    const char digits[] = "0123456789abcdef";
    for (const auto b : bytes) {
        out += digits[b >> 4];
        out += digits[b & 15];
    }
    return out;
}
void equal(const V &a, const V &b) {
    if (json::dump(a, header_limits()) != json::dump(b, header_limits()))
        fail("fat_tree_operation_binding");
}
void process(const V &v) {
    keys(v, {"pid", "created"});
    const auto pid = number(field(v, "pid"));
    if (!pid || pid > UINT32_MAX || !number(field(v, "created")))
        fail("fat_tree_operation_process");
}
bool modern(const V &v) {
    return text(v, "schema") == "org.disked.fat-tree-operation-request-prototype/2";
}
void outcome(const V &o, const V &header) {
    auto value = o;
    if (const auto *p = value.find("notification_diagnostic")) {
        if (p->kind != V::Kind::null && p->kind != V::Kind::string)
            fail("fat_tree_operation_outcome");
        value.fields.erase("notification_diagnostic");
    }
    keys(value, {"schema",
                 "status",
                 "definition_digest",
                 "attempt_id",
                 "effects_possible",
                 "cancellation_observed",
                 "files_complete",
                 "directories_created",
                 "verified_bytes",
                 "checkpointed_bytes",
                 "ledger_records",
                 "ledger_bytes",
                 "last_record_digest",
                 "diagnostic",
                 "platform_code",
                 "platform_domain",
                 "source_writes",
                 "atomic_snapshot",
                 "contained_worker_qualified",
                 "owner_accepted"});
    if (text(value, "schema") != "org.disked.fat-tree-extraction-outcome-prototype/1" ||
        text(value, "definition_digest") != text(header, "process_definition_digest") ||
        text(value, "attempt_id") != text(field(header, "process_owner"), "attempt_id") ||
        !boolean(field(value, "effects_possible")))
        fail("fat_tree_operation_outcome");
    for (const auto *k :
         {"source_writes", "atomic_snapshot", "contained_worker_qualified", "owner_accepted"})
        if (boolean(field(value, k)))
            fail("fat_tree_operation_claim");
    boolean(field(value, "cancellation_observed"));
    const auto &backend = field(field(header, "review"), "backend"),
               &selection = field(backend, "selection");
    const auto files = number(field(value, "files_complete")),
               dirs = number(field(value, "directories_created"));
    const auto verified = number(field(value, "verified_bytes")),
               checkpoint = number(field(value, "checkpointed_bytes"));
    if (verified < checkpoint || verified > number(field(selection, "content_bytes")) ||
        files > number(field(selection, "entries")) ||
        dirs > number(field(field(backend, "budgets"), "directories")) ||
        number(field(value, "ledger_records")) > 2000000 ||
        number(field(value, "ledger_bytes")) >
            number(field(field(backend, "budgets"), "ledger_bytes")) ||
        number(field(value, "platform_code")) > UINT32_MAX)
        fail("fat_tree_operation_outcome");
    identity(text(value, "last_record_digest"), "sha256:", 64);
    const auto status = text(value, "status");
    if (status != "complete" && status != "partial" && status != "partial_evidence_uncertain")
        fail("fat_tree_operation_outcome");
    if (status == "complete" &&
        (files + dirs != number(field(selection, "entries")) + 1 || !dirs ||
         verified != number(field(selection, "content_bytes")) || checkpoint != verified ||
         field(value, "diagnostic").kind != V::Kind::null ||
         boolean(field(value, "cancellation_observed"))))
        fail("fat_tree_operation_outcome");
}
V worker(const V &v, const V &header) {
    keys(v, {"schema",         "admitted",
             "attempt_id",     "cancellation_requested",
             "capture_epoch",  "claims",
             "code_sha256",    "dependencies_retained",
             "diagnostic",     "effects_possible",
             "grant_sent",     "observer_epoch",
             "outcome",        "phase",
             "preparation",    "progress_pulse",
             "request_digest", "result",
             "retired",        "status",
             "worker",         "worker_epoch"});
    if (text(v, "schema") != "org.disked.fat-tree-extraction-worker-observation/1")
        fail("fat_tree_operation_version");
    const auto &owner = field(header, "process_owner");
    for (const auto *key :
         {"attempt_id", "capture_epoch", "code_sha256", "observer_epoch", "worker_epoch"})
        equal(field(v, key), field(owner, key));
    if ("sha256:" + text(v, "request_digest") != text(owner, "request_digest"))
        fail("fat_tree_operation_binding");
    const auto &p = field(v, "preparation");
    keys(p, {"definition_digest"});
    equal(field(p, "definition_digest"), field(header, "process_definition_digest"));
    number(field(v, "progress_pulse"));
    boolean(field(v, "admitted"));
    boolean(field(v, "retired"));
    boolean(field(v, "cancellation_requested"));
    if (boolean(field(v, "effects_possible")) != boolean(field(v, "grant_sent")))
        fail("fat_tree_operation_grant");
    const auto &facts = field(v, "worker");
    keys(facts, {"pid", "created", "exit_code", "observation"});
    const auto pvalue =
        V::object().put("pid", field(facts, "pid")).put("created", field(facts, "created"));
    process(pvalue);
    if (modern(header))
        equal(pvalue, field(header, "writer"));
    if (number(field(facts, "exit_code")) > UINT32_MAX)
        fail("fat_tree_operation_process");
    const auto observation = text(facts, "observation");
    if (observation != "running" && observation != "exited")
        fail("fat_tree_operation_process");
    if (boolean(field(v, "dependencies_retained")) != (observation == "running"))
        fail("fat_tree_operation_dependencies");
    const auto &claims = field(v, "claims");
    keys(claims, {"compiled_effects_capable", "durable_reconnect", "live_namespace",
                  "mutation_authority", "physical_admission"});
    if (!boolean(field(claims, "compiled_effects_capable")))
        fail("fat_tree_operation_claim");
    for (const auto *k :
         {"durable_reconnect", "live_namespace", "mutation_authority", "physical_admission"})
        if (boolean(field(claims, k)))
            fail("fat_tree_operation_claim");
    if (field(v, "outcome").kind != V::Kind::null) {
        if (!boolean(field(v, "grant_sent")))
            fail("fat_tree_operation_grant");
        outcome(field(v, "outcome"), header);
    }
    const auto status = text(v, "status");
    if (status != "accepted_running" && status != "awaiting_grant" && status != "completed" &&
        status != "unknown")
        fail("fat_tree_operation_status");
    if (status == "awaiting_grant" && (observation != "running" || boolean(field(v, "grant_sent"))))
        fail("fat_tree_operation_status");
    return pvalue;
}
} // namespace
json::Limits header_limits() {
    auto l = fat_tree_review_limits();
    l.bytes = 524288;
    return l;
}
json::Limits record_limits() {
    auto l = header_limits();
    l.bytes = 16384;
    return l;
}
json::Value validate_header(const V &h) {
    json::dump(h, header_limits());
    const auto schema = text(h, "schema");
    if (modern(h))
        keys(h, {"schema", "operation_id", "review", "review_digest", "process_owner",
                 "process_definition_digest", "files", "controller_host", "controller", "writer"});
    else {
        if (schema != "org.disked.fat-tree-operation-request-prototype/1")
            fail("fat_tree_operation_version");
        keys(h, {"schema", "operation_id", "review", "review_digest", "process_owner",
                 "process_definition_digest", "files", "controller_host"});
    }
    identity(text(h, "operation_id"), "tree-op:", 32);
    const auto r = validate_fat_tree_review(field(h, "review"));
    if (text(h, "review_digest") != r.digest)
        fail("fat_tree_operation_review");
    identity(text(h, "process_definition_digest"), "sha256:", 64);
    identity(text(h, "controller_host"), "", 64);
    const auto &owner = field(h, "process_owner");
    keys(owner, {"attempt_id", "capture_epoch", "code_sha256", "host_id", "observer_epoch",
                 "request_digest", "worker_epoch"});
    identity(text(owner, "attempt_id"), "fat-tree-write-attempt:", 32);
    identity(text(owner, "code_sha256"), "", 64);
    identity(text(owner, "host_id"), "", 64);
    identity(text(owner, "observer_epoch"), "observer:", 32);
    identity(text(owner, "worker_epoch"), "worker:", 32);
    identity(text(owner, "request_digest"), "sha256:", 64);
    const auto &backend = field(r.definition, "backend");
    equal(field(owner, "capture_epoch"), field(field(backend, "selection"), "capture_epoch"));
    if ("sha256:" + text(owner, "code_sha256") !=
            text(field(field(field(backend, "resources"), "executable"), "observed"), "sha256") ||
        text(owner, "host_id") != text(h, "controller_host"))
        fail("fat_tree_operation_binding");
    const auto &files = field(h, "files");
    if (files.kind != V::Kind::array || files.items.size() != 3)
        fail("fat_tree_operation_files");
    std::set<std::string> ids;
    for (const auto &f : files.items) {
        keys(f, {"created", "file_id", "volume_id"});
        number(field(f, "created"));
        number(field(f, "volume_id"));
        identity(text(f, "file_id"), "", 32);
        const auto id = json::dump(V::object()
                                       .put("file_id", field(f, "file_id"))
                                       .put("volume_id", field(f, "volume_id")));
        if (!ids.insert(id).second)
            fail("fat_tree_operation_files");
    }
    if (modern(h)) {
        process(field(h, "controller"));
        process(field(h, "writer"));
    }
    return h;
}
History read_history(const V &supplied, const std::string &bytes) {
    History h;
    h.header = validate_header(supplied);
    if (bytes.size() > 1048576)
        fail("fat_tree_operation_budget");
    h.last_digest = "sha256:" + std::string(64, '0');
    std::size_t at = 0;
    bool intent = false;
    while (at < bytes.size()) {
        const auto end = bytes.find('\n', at);
        if (end == bytes.npos) {
            h.complete = false;
            h.tail_bytes = bytes.size() - at;
            if (h.tail_bytes > 16384)
                fail("fat_tree_operation_budget");
            break;
        }
        if (end - at + 1 > 16384 || h.records.size() == 64)
            fail("fat_tree_operation_budget");
        if (h.exited)
            fail("fat_tree_operation_terminal");
        const auto raw = bytes.substr(at, end - at + 1);
        const auto row = json::parse(raw.substr(0, raw.size() - 1), record_limits());
        keys(row, {"schema", "operation_id", "review_digest", "sequence", "previous", "payload"});
        if (json::dump(row, record_limits()) + "\n" != raw)
            fail("fat_tree_operation_canonical");
        if (text(row, "schema") != "org.disked.fat-tree-state-record-prototype/1" ||
            number(field(row, "sequence")) != h.records.size() ||
            text(row, "previous") != h.last_digest)
            fail("fat_tree_operation_chain");
        equal(field(row, "operation_id"), field(h.header, "operation_id"));
        equal(field(row, "review_digest"), field(h.header, "review_digest"));
        const auto &p = field(row, "payload");
        keys(p, {"observed_at", "phase", "worker"});
        if (!number(field(p, "observed_at")))
            fail("fat_tree_operation_clock");
        const auto &state = field(p, "worker"), pid = worker(state, h.header);
        if (!h.records.empty())
            equal(pid, h.writer);
        else
            h.writer = pid;
        const auto phase = text(p, "phase");
        if (h.outcome_published) {
            const auto &current = field(state, "outcome");
            if (current.kind == V::Kind::null) {
                if (text(state, "status") != "unknown")
                    fail("fat_tree_operation_outcome_withdrawal");
                h.uncertain = true;
            } else
                equal(current, field(h.last_worker, "outcome"));
        }
        if (h.uncertain && phase != "exited" && phase != "outcome_published")
            fail("fat_tree_operation_terminal");
        const bool sent = boolean(field(state, "grant_sent"));
        if (h.records.empty()) {
            if (phase != "admitted" || sent || field(state, "outcome").kind != V::Kind::null)
                fail("fat_tree_operation_phase");
        } else if (phase == "dispatch_possible") {
            if (h.records.size() != 1 || sent)
                fail("fat_tree_operation_phase");
            intent = true;
        } else if (phase == "admission_uncertain") {
            h.uncertain = true;
        } else if (phase == "observing") {
            if (!intent || !sent || h.outcome_published)
                fail("fat_tree_operation_phase");
        } else if (phase == "outcome_published") {
            if (!intent || !sent || h.outcome_published ||
                field(state, "outcome").kind == V::Kind::null)
                fail("fat_tree_operation_phase");
            h.outcome_published = true;
        } else if (phase == "exited") {
            if (text(field(state, "worker"), "observation") != "exited")
                fail("fat_tree_operation_phase");
            h.exited = true;
        } else
            fail("fat_tree_operation_phase");
        if (sent && !intent)
            fail("fat_tree_operation_grant");
        if (!h.records.empty() && boolean(field(h.last_worker, "grant_sent")) && !sent)
            fail("fat_tree_operation_grant");
        if (!h.records.empty() &&
            number(field(state, "progress_pulse")) < number(field(h.last_worker, "progress_pulse")))
            fail("fat_tree_operation_progress");
        h.last_worker = state;
        h.records.push_back(row);
        h.last_digest = hash(raw);
        at = end + 1;
        h.admitted_bytes = at;
    }
    h.has_dispatch_intent = intent;
    h.tail_digest = hash(bytes.substr(at));
    return h;
}
void validate_record(const V &header, const V &row) {
    validate_header(header);
    json::dump(row, record_limits());
    keys(row, {"schema", "operation_id", "review_digest", "sequence", "previous", "payload"});
    if (text(row, "schema") != "org.disked.fat-tree-state-record-prototype/1" ||
        number(field(row, "sequence")) >= 64)
        fail("fat_tree_operation_chain");
    identity(text(row, "previous"), "sha256:", 64);
    equal(field(row, "operation_id"), field(header, "operation_id"));
    equal(field(row, "review_digest"), field(header, "review_digest"));
    const auto &p = field(row, "payload");
    keys(p, {"observed_at", "phase", "worker"});
    if (!number(field(p, "observed_at")))
        fail("fat_tree_operation_clock");
    worker(field(p, "worker"), header);
    const auto phase = text(p, "phase");
    if (phase != "admitted" && phase != "dispatch_possible" && phase != "observing" &&
        phase != "outcome_published" && phase != "exited" && phase != "admission_uncertain")
        fail("fat_tree_operation_phase");
    const auto &w = field(p, "worker");
    const bool sent = boolean(field(w, "grant_sent"));
    if (((phase == "admitted" || phase == "dispatch_possible") &&
         (sent || field(w, "outcome").kind != V::Kind::null)) ||
        (phase == "observing" && !sent))
        fail("fat_tree_operation_phase");
    if ((phase == "outcome_published" && field(w, "outcome").kind == V::Kind::null) ||
        (phase == "exited" && text(field(w, "worker"), "observation") != "exited"))
        fail("fat_tree_operation_phase");
}
json::Value History::view() const {
    const auto *out = last_worker.find("outcome");
    const bool has_outcome = out && out->kind != V::Kind::null;
    const auto state = !complete           ? "truncated"
                       : uncertain         ? "recorded_uncertain"
                       : exited            ? has_outcome ? text(*out, "status") == "complete"
                                                               ? "recorded_complete"
                                                               : "recorded_partial"
                                                         : "recorded_exit_unresolved"
                       : outcome_published ? "recorded_outcome_pending_exit"
                       : records.empty()   ? "unresolved"
                                           : "recorded_active";
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-operation-history-prototype/1"))
        .put("state", V::string(state))
        .put("operation_id", field(header, "operation_id"))
        .put("review_digest", field(header, "review_digest"))
        .put("records", V::string(std::to_string(records.size())))
        .put("admitted_bytes", V::string(std::to_string(admitted_bytes)))
        .put("last_digest", V::string(last_digest))
        .put("last_worker", last_worker)
        .put("tail", V::object()
                         .put("bytes", V::string(std::to_string(tail_bytes)))
                         .put("sha256", V::string(tail_digest))
                         .put("admitted", V::boolean_value(false)))
        .put("claims", V::object()
                           .put("authenticity", V::string("not_established"))
                           .put("current_source_verification", V::string("not_performed"))
                           .put("current_destination_verification", V::string("not_performed"))
                           .put("worker_exit", V::string("recorded-declaration-only"))
                           .put("mutation_authority", V::boolean_value(false))
                           .put("replay_authority", V::boolean_value(false)));
}
} // namespace fat_tree_operation
} // namespace disked
