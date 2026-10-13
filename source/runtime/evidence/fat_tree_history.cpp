#include "fat_tree_history.h"
#include "portable/hash/sha256.h"
#include <deque>
#include <limits>
#include <set>

namespace disked {
namespace evidence {
namespace proposal {
namespace {
using V = json::Value;
[[noreturn]] void fail(const char *code) {
    throw FatTreeHistoryError(code);
}
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        fail("fat_tree_history_shape");
    return *p;
}
void keys(const V &v, std::initializer_list<const char *> names) {
    if (v.kind != V::Kind::object || v.fields.size() != names.size())
        fail("fat_tree_history_shape");
    for (const auto *name : names)
        field(v, name);
}
std::string text(const V &v, const char *name) {
    const auto &p = field(v, name);
    if (p.kind != V::Kind::string)
        fail("fat_tree_history_shape");
    return p.text;
}
std::uint64_t integer(const V &v) {
    if (v.kind != V::Kind::string || !json::decimal_u64(v.text))
        fail("fat_tree_history_integer");
    return std::stoull(v.text);
}
bool boolean(const V &v) {
    if (v.kind != V::Kind::boolean)
        fail("fat_tree_history_shape");
    return v.boolean;
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
json::Limits limits() {
    json::Limits l;
    l.bytes = 262144;
    l.depth = 32;
    l.values = 65536;
    l.string_bytes = 32768;
    return l;
}
std::string encode(const V &v) {
    return json::dump(v, limits());
}
std::string digest(const std::string &s) {
    unsigned char out[32];
    sha256(reinterpret_cast<const unsigned char *>(s.data()), s.size(), out);
    const char hex[] = "0123456789abcdef";
    std::string r = "sha256:";
    for (const auto b : out) {
        r += hex[b >> 4];
        r += hex[b & 15];
    }
    return r;
}
void hash_shape(const std::string &s) {
    if (s.size() != 71 || s.compare(0, 7, "sha256:") ||
        s.find_first_not_of("0123456789abcdef", 7) != s.npos)
        fail("fat_tree_history_digest");
}
void identity(const V &v) {
    keys(v, {"file_id", "volume_id"});
    const auto id = text(v, "file_id");
    if (id.size() != 32 || id.find_first_not_of("0123456789abcdef") != id.npos)
        fail("fat_tree_history_identity");
    integer(field(v, "volume_id"));
}
void equal(const V &a, const V &b, const char *code) {
    if (encode(a) != encode(b))
        fail(code);
}
void add(std::uint64_t &value, std::uint64_t n, std::uint64_t maximum) {
    if (value > maximum || n > maximum - value)
        fail("fat_tree_history_budget");
    value += n;
}
} // namespace
struct FatTreeHistory::Impl {
    struct Node {
        std::string parent, raw, record_digest, path, name, content_digest, identity;
        V mapping;
        std::uint64_t size = 0, offset = 0, content_offset = 0, content_sequence = 0;
        std::uint64_t pending_bytes = 0;
        std::string pending_digest;
        bool directory = false, metadata = false, created = false, applied = false;
        bool complete = false, content_complete = false, write_pending = false;
    };
    FatTreeHistoryBudget budget;
    std::string line, previous = "sha256:" + std::string(64, '0'), definition_digest, attempt;
    std::string tree_digest, tree_previous, pending_root;
    V definition, binding, outcome;
    std::map<std::string, Node> nodes;
    std::map<std::string, std::string> paths;
    std::set<std::string> observed_identities;
    std::deque<std::string> pending_metadata;
    std::uint64_t total = 0, admitted_bytes = 0, sequence = 0, pages = 0, entries = 0;
    std::uint64_t file_sizes = 0, checkpoints = 0, files = 0, directory_intents = 0;
    std::uint64_t metadata_bytes = 0, applied_fields = 0, unapplied_fields = 0;
    std::uint64_t declared_entries = 0, declared_bytes = 0, declared_pages = 0;
    std::uint64_t entry_limit = 0, content_limit = 0, metadata_limit = 0, page_limit = 0;
    bool done = false, failed = false, root = false, tree_complete = false, terminal = false;

    explicit Impl(const FatTreeHistoryBudget &b) : budget(b) {
        if (!b.bytes || b.bytes > 1073741824 || !b.records || b.records > 2000000 || !b.entries ||
            b.entries > 65536)
            fail("fat_tree_history_budget");
    }
    Node &node(const V &v) {
        const auto key = text(v, "key");
        const auto at = nodes.find(key);
        if (at == nodes.end())
            fail("fat_tree_history_entry");
        return at->second;
    }
    void prepare(const V &v) {
        keys(v, {"schema", "selection", "prepared_input", "paths", "resources", "metadata_policy",
                 "budgets", "effects", "scratch_resources", "recovery_resources",
                 "source_consistency", "owner_accepted"});
        if (text(v, "schema") != "org.disked.fat-tree-extraction-plan-prototype/1" ||
            text(v, "effects") != "create-only-tree-and-independent-ordered-ledger" ||
            boolean(field(v, "owner_accepted")))
            fail("fat_tree_history_definition");
        if (digest("disked:fat-tree-extraction-plan:1\n" + encode(v)) != definition_digest)
            fail("fat_tree_history_definition_digest");
        keys(field(v, "resources"),
             {"source", "destination_tree", "metadata_ledger", "executable", "provider", "host"});
        keys(field(v, "paths"), {"source", "destination", "ledger"});
        for (const auto *name : {"source", "destination", "ledger"}) {
            const auto path = text(field(v, "paths"), name);
            if (path.empty() || path.size() > 960 || path.find('\0') != path.npos)
                fail("fat_tree_history_definition");
        }
        for (const auto *name : {"scratch_resources", "recovery_resources"}) {
            const auto &a = field(v, name);
            if (a.kind != V::Kind::array || !a.items.empty())
                fail("fat_tree_history_definition");
        }
        const auto &s = field(v, "selection"), &b = field(v, "budgets");
        keys(s, {"kind", "volume_offset", "volume_bytes", "fat_copy", "capture_epoch",
                 "preparation_binding", "preparation_context", "tree_digest", "pages", "entries",
                 "content_bytes"});
        keys(b, {"entries", "directories", "metadata_bytes", "pages", "content_bytes",
                 "ledger_bytes", "record_bytes", "code_bytes", "native_path_units"});
        if (text(s, "kind") != "whole-live-tree")
            fail("fat_tree_history_definition");
        declared_entries = integer(field(s, "entries"));
        declared_bytes = integer(field(s, "content_bytes"));
        declared_pages = integer(field(s, "pages"));
        entry_limit = integer(field(b, "entries"));
        content_limit = integer(field(b, "content_bytes"));
        metadata_limit = integer(field(b, "metadata_bytes"));
        page_limit = integer(field(b, "pages"));
        if (!entry_limit || entry_limit > budget.entries || content_limit > 1099511627776ULL ||
            metadata_limit > 67108864 || !page_limit || page_limit > 65536 ||
            integer(field(b, "record_bytes")) != 262144 ||
            integer(field(b, "ledger_bytes")) > 1073741824 || declared_entries > entry_limit ||
            declared_bytes > content_limit || !declared_pages || declared_pages > page_limit)
            fail("fat_tree_history_budget");
        hash_shape(text(s, "tree_digest"));
        definition = v;
    }
    void check_binding(const V &b) {
        if (binding.kind == V::Kind::null) {
            const auto &prepared = field(field(definition, "selection"), "preparation_binding");
            for (const auto *key : {"source_id", "source_bytes", "volume_offset", "volume_bytes",
                                    "fat_copy", "capture_epoch"})
                equal(field(b, key), field(prepared, key), "fat_tree_history_source_binding");
            hash_shape(text(b, "capture_id"));
            binding = b;
        } else
            equal(b, binding, "fat_tree_history_source_binding");
    }
    void tree(const V &v) {
        if (!root || tree_complete || !pending_metadata.empty() ||
            text(v, "schema") != "org.disked.fat-traversal-page/1" ||
            !boolean(field(v, "applicable")) || integer(field(v, "sequence")) != pages + 1)
            fail("fat_tree_history_tree");
        check_binding(field(v, "binding"));
        const auto &prev = field(v, "previous_page_digest");
        if (tree_previous.empty() ? prev.kind != V::Kind::null
                                  : prev.kind != V::Kind::string || prev.text != tree_previous)
            fail("fat_tree_history_tree_chain");
        auto body = v;
        body.fields.erase("page_digest");
        tree_previous = digest("disked:fat-traversal-page:1\n" + encode(body));
        if (text(v, "page_digest") != tree_previous)
            fail("fat_tree_history_tree_digest");
        const auto status = text(v, "status");
        if (status != "running" && status != "complete")
            fail("fat_tree_history_tree");
        tree_complete = status == "complete";
        add(pages, 1, page_limit);
        const auto &events = field(v, "events");
        if (events.kind != V::Kind::array)
            fail("fat_tree_history_shape");
        tree_digest = digest(tree_digest + ":" + digest(encode(events)));
        for (const auto &e : events.items) {
            if (text(e, "type") != "record")
                continue;
            const auto kind = integer(field(e, "kind"));
            if ((kind != 3 && kind != 4) || integer(field(e, "dot")))
                continue;
            const auto key = text(e, "key");
            if (key != "entry:" + text(e, "source_offset") || nodes.count(key))
                fail("fat_tree_history_entry");
            const auto parent = text(e, "directory");
            if (parent != "root") {
                const auto at = nodes.find(parent);
                if (at == nodes.end() || !at->second.directory)
                    fail("fat_tree_history_parent");
            }
            Node n;
            n.parent = parent;
            n.raw = text(e, "raw");
            n.record_digest = digest(encode(e));
            n.directory = kind == 4;
            n.size = integer(field(e, "file_bytes"));
            if (n.raw.size() != 64 || n.raw.find_first_not_of("0123456789abcdef") != n.raw.npos)
                fail("fat_tree_history_entry");
            add(entries, 1, entry_limit);
            if (!n.directory)
                add(file_sizes, n.size, content_limit);
            nodes.emplace(key, std::move(n));
            pending_metadata.push_back(key);
        }
    }
    void metadata(const V &v) {
        if (pending_metadata.empty() ||
            text(field(v, "record"), "key") != pending_metadata.front() ||
            text(v, "schema") != "org.disked.fat-tree-metadata-frame/1" ||
            boolean(field(v, "authorizes_effects")))
            fail("fat_tree_history_metadata");
        auto &n = node(field(v, "record"));
        if (digest(encode(field(v, "record"))) != n.record_digest)
            fail("fat_tree_history_metadata");
        check_binding(field(v, "binding"));
        const auto &m = field(v, "mapping");
        if (text(m, "schema") != "org.disked.fat-metadata-candidates/1" ||
            text(m, "status") != "candidate" || boolean(field(m, "authorizes_effects")) ||
            boolean(field(m, "native_metadata_applied")))
            fail("fat_tree_history_metadata");
        equal(field(m, "policy"), field(definition, "metadata_policy"), "fat_tree_history_policy");
        const auto &original = field(m, "original");
        keys(original,
             {"attributes", "case_flags", "entry_issues", "long_name_issues", "long_units",
              "raw_long_slots", "raw_oem_name", "raw_record", "source_offset"});
        if (text(original, "raw_record") != n.raw ||
            text(original, "raw_oem_name") != n.raw.substr(0, 22) ||
            text(original, "source_offset") != text(field(v, "record"), "source_offset"))
            fail("fat_tree_history_metadata");
        equal(field(original, "attributes"), field(field(v, "record"), "attributes"),
              "fat_tree_history_metadata");
        equal(field(original, "case_flags"), field(field(v, "record"), "case_flags"),
              "fat_tree_history_metadata");
        const auto slots = text(original, "raw_long_slots");
        if (slots.size() > 1280 || slots.size() % 64 ||
            slots.find_first_not_of("0123456789abcdef") != slots.npos ||
            field(original, "long_units").kind != V::Kind::array ||
            field(original, "long_units").items.size() > 255)
            fail("fat_tree_history_metadata");
        n.name = text(field(m, "name"), "utf8");
        if (n.name.empty() || n.name.find_first_of("\\/:\0", 0, 4) != n.name.npos ||
            n.name == "." || n.name == "..")
            fail("fat_tree_history_name");
        n.path = (n.parent == "root" ? text(field(definition, "paths"), "destination")
                                     : nodes.at(n.parent).path) +
                 "\\" + n.name;
        if (!paths.emplace(n.path, text(field(v, "record"), "key")).second)
            fail("fat_tree_history_name_collision");
        add(metadata_bytes, encode(m).size(), metadata_limit);
        // Only the policy/candidate fields needed for result consistency survive.
        n.mapping = V::object();
        for (const auto *key : {"creation", "access", "write", "native_attributes_candidate"})
            n.mapping.put(key, field(m, key));
        n.metadata = true;
        pending_metadata.pop_front();
    }
    void intent(const V &v) {
        const auto effect = text(v, "effect");
        if (effect == "create-root") {
            keys(v, {"effect", "path"});
            if (root || !pending_root.empty() ||
                text(v, "path") != text(field(definition, "paths"), "destination"))
                fail("fat_tree_history_root");
            pending_root = text(v, "path");
            return;
        }
        auto &n = node(v);
        if (!root || !n.metadata || text(v, "path") != n.path || text(v, "parent") != n.parent ||
            n.complete)
            fail("fat_tree_history_intent");
        if (n.parent != "root" && !nodes.at(n.parent).created)
            fail("fat_tree_history_parent");
        if (effect == "create-file" || effect == "create-directory") {
            keys(v, {"effect", "key", "parent", "path"});
            if (n.created || n.directory != (effect == "create-directory"))
                fail("fat_tree_history_intent");
            n.created = true;
            if (n.directory)
                add(directory_intents, 1, 4095);
        } else if (effect == "write-content") {
            keys(v, {"effect", "key", "parent", "path", "offset", "bytes", "sha256"});
            if (n.directory || !n.created || n.applied || n.write_pending ||
                integer(field(v, "offset")) != n.offset ||
                integer(field(v, "bytes")) != n.pending_bytes || !n.pending_bytes ||
                text(v, "sha256") != n.pending_digest)
                fail("fat_tree_history_write");
            n.write_pending = true;
        } else if (effect == "apply-native-metadata" ||
                   effect == "apply-native-directory-metadata") {
            keys(v, {"effect", "key", "parent", "path"});
            if (!n.created || n.applied ||
                n.directory != (effect == "apply-native-directory-metadata") || n.write_pending ||
                (!n.directory && (!n.content_complete || n.offset != n.size)))
                fail("fat_tree_history_metadata_order");
            n.applied = true;
        } else
            fail("fat_tree_history_intent");
    }
    void content(const V &v) {
        keys(v, {"key", "page"});
        auto &n = node(v);
        const auto &p = field(v, "page");
        if (n.directory || !n.created || n.applied || n.content_complete || n.write_pending ||
            n.pending_bytes || text(p, "schema") != "org.disked.fat-content-stream-page/1" ||
            !boolean(field(p, "applicable")) || boolean(field(p, "authorizes_effects")) ||
            integer(field(p, "sequence")) != n.content_sequence + 1 ||
            integer(field(p, "file_bytes")) != n.size ||
            integer(field(p, "file_offset")) != n.content_offset)
            fail("fat_tree_history_content");
        const auto &selected = field(p, "selection");
        for (const auto *key : {"source_id", "source_bytes", "volume_offset", "volume_bytes",
                                "fat_copy", "capture_epoch", "capture_id"})
            equal(field(selected, key), field(binding, key), "fat_tree_history_content_binding");
        if (text(selected, "raw_record") != n.raw ||
            "entry:" + text(selected, "record_source_offset") != text(v, "key"))
            fail("fat_tree_history_content_binding");
        const auto &prev = field(p, "previous_page_digest");
        if (n.content_digest.empty()
                ? prev.kind != V::Kind::null
                : prev.kind != V::Kind::string || prev.text != n.content_digest)
            fail("fat_tree_history_content_chain");
        n.content_digest = text(p, "page_digest");
        hash_shape(n.content_digest);
        // The writer removes data from this page. Its original page digest is
        // retained, not recomputable here; current byte verification is separate.
        n.pending_bytes = integer(field(p, "returned_bytes"));
        if (n.content_offset > n.size || n.pending_bytes > n.size - n.content_offset)
            fail("fat_tree_history_content");
        n.content_offset += n.pending_bytes;
        if (integer(field(p, "next_file_offset")) != n.content_offset)
            fail("fat_tree_history_content");
        n.pending_digest = text(p, "data_sha256");
        hash_shape(n.pending_digest);
        if (!n.pending_bytes && n.pending_digest != digest(""))
            fail("fat_tree_history_content");
        const auto status = text(p, "status");
        if (status != "running" && status != "complete")
            fail("fat_tree_history_content");
        n.content_complete = status == "complete";
        ++n.content_sequence;
        if (n.content_complete && n.content_offset != n.size)
            fail("fat_tree_history_content");
    }
    void checkpoint(const V &v) {
        keys(v, {"key", "offset", "bytes", "sha256"});
        auto &n = node(v);
        if (!n.write_pending || integer(field(v, "offset")) != n.offset ||
            integer(field(v, "bytes")) != n.pending_bytes || text(v, "sha256") != n.pending_digest)
            fail("fat_tree_history_checkpoint");
        add(checkpoints, n.pending_bytes, content_limit);
        n.offset += n.pending_bytes;
        n.pending_bytes = 0;
        n.write_pending = false;
    }
    void result(const V &v) {
        keys(v, {"key", "identity", "fields"});
        auto &n = node(v);
        if (!n.applied || !n.identity.empty())
            fail("fat_tree_history_metadata_order");
        identity(field(v, "identity"));
        n.identity = encode(field(v, "identity"));
        if (!observed_identities.insert(n.identity).second)
            fail("fat_tree_history_identity_alias");
        const auto &f = field(v, "fields");
        keys(f, {"creation", "access", "write", "attributes"});
        for (const auto *key : {"creation", "access", "write"}) {
            const auto &r = field(f, key), &candidate = field(n.mapping, key);
            keys(r, {"candidate", "observed_filetime", "status"});
            equal(field(r, "candidate"), candidate, "fat_tree_history_metadata_result");
            const auto state = text(r, "status");
            const bool wanted = text(candidate, "status") == "candidate";
            if (state != "mismatch" && state != (wanted ? "applied_verified" : "unapplied"))
                fail("fat_tree_history_metadata_result");
            const auto observed = integer(field(r, "observed_filetime"));
            if (wanted && (state == "applied_verified") !=
                              (observed == integer(field(candidate, "filetime_candidate"))))
                fail("fat_tree_history_metadata_result");
            if (state == "applied_verified")
                ++applied_fields;
            else
                ++unapplied_fields;
        }
        const auto &a = field(f, "attributes");
        keys(a, {"candidate", "observed", "status"});
        equal(field(a, "candidate"), field(n.mapping, "native_attributes_candidate"),
              "fat_tree_history_metadata_result");
        const auto state = text(a, "status");
        if ((state != "applied_verified" && state != "mismatch") ||
            (state == "applied_verified") !=
                ((integer(field(a, "observed")) & 0x27) == integer(field(a, "candidate"))))
            fail("fat_tree_history_metadata_result");
        if (state == "applied_verified")
            ++applied_fields;
        else
            ++unapplied_fields;
        n.mapping = V::object().put(
            "verified", V::boolean_value(text(field(f, "creation"), "status") != "mismatch" &&
                                         text(field(f, "access"), "status") != "mismatch" &&
                                         text(field(f, "write"), "status") != "mismatch" &&
                                         state != "mismatch"));
    }
    void end(const V &v) {
        keys(v, {"schema",
                 "status",
                 "definition_digest",
                 "attempt_id",
                 "effects_possible",
                 "cancellation_observed",
                 "files_complete",
                 "directories_created",
                 "verified_bytes",
                 "checkpointed_bytes",
                 "ledger_records_before_outcome",
                 "ledger_bytes_before_outcome",
                 "last_digest_before_outcome",
                 "diagnostic",
                 "platform_code",
                 "platform_domain",
                 "source_writes",
                 "atomic_snapshot",
                 "contained_worker_qualified",
                 "owner_accepted"});
        const auto status = text(v, "status");
        if (text(v, "schema") != "org.disked.fat-tree-extraction-outcome-prototype/1" ||
            (status != "complete" && status != "partial") ||
            text(v, "definition_digest") != definition_digest || text(v, "attempt_id") != attempt ||
            !boolean(field(v, "effects_possible")) ||
            integer(field(v, "files_complete")) != files ||
            integer(field(v, "checkpointed_bytes")) != checkpoints ||
            integer(field(v, "ledger_records_before_outcome")) != sequence ||
            integer(field(v, "ledger_bytes_before_outcome")) != admitted_bytes ||
            text(v, "last_digest_before_outcome") != previous)
            fail("fat_tree_history_outcome");
        for (const auto *key :
             {"source_writes", "atomic_snapshot", "contained_worker_qualified", "owner_accepted"})
            if (boolean(field(v, key)))
                fail("fat_tree_history_claim");
        const auto verified = integer(field(v, "verified_bytes")),
                   dirs = integer(field(v, "directories_created"));
        if (verified < checkpoints || verified > declared_bytes || dirs < (root ? 1u : 0u) ||
            dirs > directory_intents + (pending_root.empty() ? 0u : 1u))
            fail("fat_tree_history_outcome");
        boolean(field(v, "cancellation_observed"));
        integer(field(v, "platform_code"));
        if (status == "complete") {
            if (!root || !tree_complete || pages != declared_pages || entries != declared_entries ||
                file_sizes != declared_bytes || checkpoints != declared_bytes ||
                verified != checkpoints ||
                tree_digest != text(field(definition, "selection"), "tree_digest") ||
                files + dirs != entries + 1 || dirs != directory_intents + 1 ||
                !pending_metadata.empty() || field(v, "diagnostic").kind != V::Kind::null)
                fail("fat_tree_history_incomplete");
            if (boolean(field(v, "cancellation_observed")))
                fail("fat_tree_history_incomplete");
            for (const auto &p : nodes) {
                const auto &n = p.second;
                if (!n.created || !n.applied || n.identity.empty() ||
                    !boolean(field(n.mapping, "verified")) || (!n.directory && !n.complete))
                    fail("fat_tree_history_incomplete");
            }
        }
        outcome = v;
        terminal = true;
    }
    void record(const std::string &raw) {
        if (terminal || sequence >= budget.records)
            fail("fat_tree_history_after_outcome");
        const auto v = json::parse(raw.substr(0, raw.size() - 1), limits());
        keys(v, {"schema", "sequence", "previous", "definition_digest", "attempt_id", "kind",
                 "payload"});
        if (encode(v) + "\n" != raw)
            fail("fat_tree_history_canonical");
        const auto d = text(v, "definition_digest"), a = text(v, "attempt_id");
        hash_shape(d);
        if (a.empty() || a.size() > 128 || a.find('\0') != a.npos ||
            text(v, "schema") != "org.disked.fat-tree-extraction-record-prototype/1" ||
            integer(field(v, "sequence")) != sequence || text(v, "previous") != previous)
            fail("fat_tree_history_chain");
        const auto kind = text(v, "kind");
        const auto &p = field(v, "payload");
        if (!sequence) {
            if (kind != "definition")
                fail("fat_tree_history_missing_definition");
            definition_digest = d;
            attempt = a;
            prepare(p);
        } else {
            if (d != definition_digest || a != attempt)
                fail("fat_tree_history_binding");
            if (kind == "intent")
                intent(p);
            else if (kind == "root-created") {
                keys(p, {"identity", "source_metadata"});
                if (root || pending_root.empty() || text(p, "source_metadata") != "no-root-dirent")
                    fail("fat_tree_history_root");
                identity(field(p, "identity"));
                observed_identities.insert(encode(field(p, "identity")));
                root = true;
            } else if (kind == "tree-observation")
                tree(p);
            else if (kind == "original-metadata")
                metadata(p);
            else if (kind == "content-observation")
                content(p);
            else if (kind == "checkpoint")
                checkpoint(p);
            else if (kind == "metadata-result")
                result(p);
            else if (kind == "file-complete") {
                keys(p, {"key", "bytes", "identity"});
                auto &n = node(p);
                if (n.directory || n.complete || n.identity.empty() || !n.content_complete ||
                    !boolean(field(n.mapping, "verified")) || n.offset != n.size ||
                    integer(field(p, "bytes")) != n.size ||
                    encode(field(p, "identity")) != n.identity)
                    fail("fat_tree_history_file_complete");
                n.complete = true;
                ++files;
            } else if (kind == "outcome")
                end(p);
            else
                fail("fat_tree_history_kind");
        }
        previous = digest(raw);
        ++sequence;
        admitted_bytes += raw.size();
    }
    V finish() {
        if (done || failed)
            fail("fat_tree_history_closed");
        done = true;
        const auto status = !line.empty() ? "truncated"
                            : terminal    ? "recorded_" + text(outcome, "status")
                            : sequence    ? "unresolved"
                                          : "empty";
        return V::object()
            .put("schema", V::string("org.disked.fat-tree-history-inspection-prototype/1"))
            .put("state", V::string(status))
            .put("records", exact(sequence))
            .put("admitted_bytes", exact(admitted_bytes))
            .put("input_bytes", exact(total))
            .put("last_record_digest", sequence ? V::string(previous) : V{})
            .put("definition_digest", sequence ? V::string(definition_digest) : V{})
            .put("attempt_id", sequence ? V::string(attempt) : V{})
            .put("tree_entries_observed", exact(entries))
            .put("files_complete_recorded", exact(files))
            .put("directory_create_intents", exact(directory_intents))
            .put("checkpointed_bytes_recorded", exact(checkpoints))
            .put("metadata_fields_applied_recorded", exact(applied_fields))
            .put("metadata_fields_unapplied_recorded", exact(unapplied_fields))
            .put("outcome", outcome)
            .put("tail", V::object()
                             .put("bytes", exact(line.size()))
                             .put("sha256", V::string(digest(line)))
                             .put("admitted", V::boolean_value(false)))
            .put("claims",
                 V::object()
                     .put("origin", V::string("validated-supplied-record-declarations"))
                     .put("authenticity", V::string("not_established"))
                     .put("current_source_verification", V::string("not_performed"))
                     .put("current_destination_verification", V::string("not_performed"))
                     .put("content_page_digest", V::string("retained-not-recomputed-data-omitted"))
                     .put("worker_exit", V::string("not_observed"))
                     .put("power_loss_persistence", V::string("not_established"))
                     .put("mutation_authority", V::boolean_value(false))
                     .put("replay_authority", V::boolean_value(false))
                     .put("physical_admission", V::boolean_value(false))
                     .put("owner_accepted", V::boolean_value(false)));
    }
};
FatTreeHistory::FatTreeHistory(const FatTreeHistoryBudget &budget) : impl_(new Impl(budget)) {
}
FatTreeHistory::~FatTreeHistory() = default;
void FatTreeHistory::consume(const std::string &bytes) {
    auto &p = *impl_;
    if (p.done || p.failed)
        fail("fat_tree_history_closed");
    try {
        if (bytes.size() > 262144)
            fail("fat_tree_history_chunk_budget");
        add(p.total, bytes.size(), p.budget.bytes);
        for (const auto c : bytes) {
            if (p.line.size() == 262144)
                fail("fat_tree_history_record_budget");
            p.line += c;
            if (c == '\n') {
                p.record(p.line);
                p.line.clear();
            }
        }
    } catch (...) {
        p.failed = true;
        throw;
    }
}
json::Value FatTreeHistory::finish() {
    return impl_->finish();
}
} // namespace proposal
} // namespace evidence
} // namespace disked
