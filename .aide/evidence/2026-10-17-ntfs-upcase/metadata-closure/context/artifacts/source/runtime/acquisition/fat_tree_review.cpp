#include "fat_tree_review.h"
#include "portable/hash/sha256.h"
#include <limits>
#include <set>

namespace disked {
namespace {
using V = json::Value;
[[noreturn]] void fail(const char *code) {
    throw FatTreeReviewError(code);
}
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        fail("fat_tree_review_shape");
    return *p;
}
void keys(const V &v, std::initializer_list<const char *> names) {
    if (v.kind != V::Kind::object || v.fields.size() != names.size())
        fail("fat_tree_review_shape");
    for (const auto *name : names)
        field(v, name);
}
std::string text(const V &v, const char *name) {
    const auto &p = field(v, name);
    if (p.kind != V::Kind::string)
        fail("fat_tree_review_shape");
    return p.text;
}
std::uint64_t number(const V &v) {
    if (v.kind != V::Kind::string || !json::decimal_u64(v.text))
        fail("fat_tree_review_integer");
    return std::stoull(v.text);
}
bool boolean(const V &v) {
    if (v.kind != V::Kind::boolean)
        fail("fat_tree_review_shape");
    return v.boolean;
}
std::string encode(const V &v) {
    return json::dump(v, fat_tree_review_limits());
}
std::string hash(const std::string &value) {
    unsigned char result[32];
    sha256(reinterpret_cast<const unsigned char *>(value.data()), value.size(), result);
    std::string out = "sha256:";
    const char hex[] = "0123456789abcdef";
    for (const auto b : result) {
        out += hex[b >> 4];
        out += hex[b & 15];
    }
    return out;
}
void digest(const std::string &value) {
    if (value.size() != 71 || value.compare(0, 7, "sha256:") ||
        value.find_first_not_of("0123456789abcdef", 7) != value.npos)
        fail("fat_tree_review_digest");
}
void equal(const V &a, const V &b, const char *code) {
    if (encode(a) != encode(b))
        fail(code);
}
void range(const V &v, std::uint64_t low, std::uint64_t high) {
    const auto n = number(v);
    if (n < low || n > high)
        fail("fat_tree_review_range");
}
void path(const std::string &s) {
    if (s.empty() || s.size() > 960 || s.find('\0') != s.npos || !json::valid_utf8(s))
        fail("fat_tree_review_path");
}
void empty_array(const V &v) {
    if (v.kind != V::Kind::array || !v.items.empty())
        fail("fat_tree_review_undeclared_resources");
}
void file_identity(const V &v, bool directory) {
    if (directory)
        keys(v, {"created", "file_id", "volume_id"});
    else
        keys(v, {"attributes", "bytes", "changed", "created", "file_id", "hardlinks", "volume_id",
                 "written"});
    const auto id = text(v, "file_id");
    if (id.size() != 32 || id.find_first_not_of("0123456789abcdef") != id.npos)
        fail("fat_tree_review_identity");
    for (const auto &p : v.fields)
        if (p.first != "file_id")
            number(p.second);
    if (!directory && number(field(v, "hardlinks")) != 1)
        fail("fat_tree_review_alias");
}
void parents(const V &v) {
    if (v.kind != V::Kind::array || v.items.empty() || v.items.size() > 240)
        fail("fat_tree_review_parents");
    for (const auto &p : v.items)
        file_identity(p, true);
}
void policy(const V &v) {
    keys(v, {"name_selection", "oem_code_page", "time_interpretation", "unrepresentable_name",
             "utc_offset_minutes"});
    const auto name = text(v, "name_selection"), fallback = text(v, "unrepresentable_name");
    if ((name != "long_or_short" && name != "short" && name != "identity") ||
        (fallback != "refuse" && fallback != "identity"))
        fail("fat_tree_review_policy");
    const auto cp = number(field(v, "oem_code_page"));
    if (cp != 437 && cp != 850)
        fail("fat_tree_review_policy");
    const auto time = text(v, "time_interpretation"), offset = text(v, "utc_offset_minutes");
    const auto magnitude = !offset.empty() && offset[0] == '-' ? offset.substr(1) : offset;
    if (!json::decimal_u64(magnitude) || std::stoull(magnitude) > 840 || offset == "-0" ||
        (time != "preserve_raw" && time != "fixed_offset") ||
        (time == "preserve_raw" && offset != "0"))
        fail("fat_tree_review_policy");
}
std::set<std::string> resource(const V &v, const char *access, const char *verification) {
    keys(v, {"identity", "epoch", "observed", "access", "footprint", "verification", "aliases",
             "failure_domain"});
    const auto d = hash(encode(field(v, "observed")));
    if (text(v, "epoch") != d || text(v, "identity") != "observed:" + d ||
        text(v, "access") != access || text(v, "verification") != verification ||
        text(v, "failure_domain").empty())
        fail("fat_tree_review_resource");
    const auto &aliases = field(v, "aliases");
    if (aliases.kind != V::Kind::array || aliases.items.empty() || aliases.items.size() > 2)
        fail("fat_tree_review_alias");
    std::set<std::string> result;
    result.insert("observed:" + d);
    const auto *f = field(v, "observed").find("file");
    if (f)
        result.insert("file:" + hash(encode(V::object()
                                                .put("volume_id", field(*f, "volume_id"))
                                                .put("file_id", field(*f, "file_id")))));
    std::set<std::string> supplied;
    for (const auto &a : aliases.items) {
        if (a.kind != V::Kind::string || !supplied.insert(a.text).second)
            fail("fat_tree_review_alias");
    }
    if (supplied != result)
        fail("fat_tree_review_alias");
    return result;
}
void byte_range(const V &v, std::uint64_t start, std::uint64_t end) {
    keys(v, {"kind", "start", "end"});
    if (text(v, "kind") != "byte-range" || number(field(v, "start")) != start ||
        number(field(v, "end")) != end)
        fail("fat_tree_review_footprint");
}
void backend(const V &v) {
    keys(v,
         {"schema", "selection", "prepared_input", "paths", "resources", "metadata_policy",
          "budgets", "effects", "scratch_resources", "recovery_resources", "source_consistency"});
    if (text(v, "schema") != "org.disked.fat-tree-effects-prototype/1" ||
        text(v, "effects") != "create-only-tree-and-independent-ordered-ledger" ||
        text(v, "source_consistency") != "held-identity-and-read-agreement-not-atomic")
        fail("fat_tree_review_effects");
    empty_array(field(v, "scratch_resources"));
    empty_array(field(v, "recovery_resources"));
    const auto &s = field(v, "selection"), &r = field(v, "resources"), &b = field(v, "budgets");
    keys(s, {"kind", "volume_offset", "volume_bytes", "fat_copy", "capture_epoch", "tree_digest",
             "pages", "entries", "content_bytes"});
    if (text(s, "kind") != "whole-live-tree")
        fail("fat_tree_review_selection");
    digest(text(s, "tree_digest"));
    range(field(s, "fat_copy"), 0, UINT32_MAX);
    range(field(s, "pages"), 1, 65536);
    range(field(s, "entries"), 0, 65536);
    range(field(s, "content_bytes"), 0, 1099511627776ULL);
    number(field(s, "capture_epoch"));
    const auto offset = number(field(s, "volume_offset")), size = number(field(s, "volume_bytes"));
    if (size < 512 || size > std::numeric_limits<std::uint64_t>::max() - offset)
        fail("fat_tree_review_range");
    keys(b, {"entries", "directories", "metadata_bytes", "pages", "content_bytes", "ledger_bytes",
             "record_bytes", "code_bytes", "native_path_units"});
    range(field(b, "entries"), 1, 65536);
    range(field(b, "directories"), 1, 4096);
    range(field(b, "metadata_bytes"), 16384, 67108864);
    range(field(b, "pages"), 1, 65536);
    range(field(b, "content_bytes"), 1, 1099511627776ULL);
    range(field(b, "ledger_bytes"), 1048576, 1073741824);
    if (number(field(b, "record_bytes")) != 262144 || number(field(b, "code_bytes")) != 8388608 ||
        number(field(b, "native_path_units")) != 240 ||
        number(field(s, "entries")) > number(field(b, "entries")) ||
        number(field(s, "pages")) > number(field(b, "pages")) ||
        number(field(s, "content_bytes")) > number(field(b, "content_bytes")))
        fail("fat_tree_review_budget");
    keys(r, {"source", "destination_tree", "metadata_ledger", "executable", "provider", "host"});
    const char *roles[] = {"source",     "destination_tree", "metadata_ledger",
                           "executable", "provider",         "host"};
    const char *access[] = {"read", "create-tree",    "create-append",
                            "read", "execute-linked", "declared-host-effects"};
    const char *checks[] = {"held-identity-and-region-agreement",
                            "file-id-and-content-readback",
                            "ordered-hash-chain",
                            "identity-and-code-sha256",
                            "same-linked-generation",
                            "selected-host-profile"};
    std::set<std::string> aliases;
    for (std::size_t i = 0; i < 6; ++i) {
        const auto ids = resource(field(r, roles[i]), access[i], checks[i]);
        for (const auto &id : ids)
            if (!aliases.insert(id).second)
                fail("fat_tree_review_alias");
    }
    keys(field(v, "paths"), {"source", "destination", "ledger"});
    std::set<std::string> paths;
    for (const auto *key : {"source", "destination", "ledger"}) {
        const auto p = text(field(v, "paths"), key);
        path(p);
        if (!paths.insert(p).second)
            fail("fat_tree_review_alias");
    }
    policy(field(v, "metadata_policy"));
    const auto &source = field(field(r, "source"), "observed");
    keys(source, {"file", "parents", "path"});
    file_identity(field(source, "file"), false);
    parents(field(source, "parents"));
    if (text(source, "path") != text(field(v, "paths"), "source") ||
        offset + size > number(field(field(source, "file"), "bytes")))
        fail("fat_tree_review_selection");
    byte_range(field(field(r, "source"), "footprint"), offset, offset + size);
    for (const auto *role : {"destination_tree", "metadata_ledger"}) {
        const auto &observed = field(field(r, role), "observed");
        keys(observed, {"location", "parents"});
        parents(field(observed, "parents"));
        const auto &location = field(observed, "location");
        keys(location, {"parent", "leaf", "absence_required"});
        equal(field(location, "parent"), field(observed, "parents").items.back(),
              "fat_tree_review_resource");
        const auto leaf = text(location, "leaf");
        const auto output = text(
            field(v, "paths"), std::string(role) == "destination_tree" ? "destination" : "ledger");
        if (!boolean(field(location, "absence_required")) || leaf.empty() ||
            leaf.find_first_of("\\/:") != leaf.npos ||
            output.substr(output.find_last_of("\\/") + 1) != leaf)
            fail("fat_tree_review_resource");
    }
    const auto &destination = field(field(r, "destination_tree"), "footprint");
    keys(destination, {"kind", "entries", "content_bytes"});
    if (text(destination, "kind") != "new-descendant-tree")
        fail("fat_tree_review_footprint");
    equal(field(destination, "entries"), field(s, "entries"), "fat_tree_review_footprint");
    equal(field(destination, "content_bytes"), field(s, "content_bytes"),
          "fat_tree_review_footprint");
    const auto &ledger = field(field(r, "metadata_ledger"), "footprint");
    keys(ledger, {"kind", "bytes"});
    if (text(ledger, "kind") != "bounded-new-file")
        fail("fat_tree_review_footprint");
    equal(field(ledger, "bytes"), field(b, "ledger_bytes"), "fat_tree_review_footprint");
    const auto &code = field(field(r, "executable"), "observed");
    keys(code, {"file", "parents", "path", "sha256"});
    file_identity(field(code, "file"), false);
    parents(field(code, "parents"));
    path(text(code, "path"));
    digest(text(code, "sha256"));
    range(field(field(code, "file"), "bytes"), 1, 8388608);
    byte_range(field(field(r, "executable"), "footprint"), 0,
               number(field(field(code, "file"), "bytes")));
    const auto &provider = field(field(r, "provider"), "observed");
    keys(provider, {"id", "code_sha256"});
    if (text(provider, "id") != "provider.image.fat-tree-extract.prototype/1" ||
        text(provider, "code_sha256") != text(code, "sha256"))
        fail("fat_tree_review_code");
    keys(field(field(r, "provider"), "footprint"), {"kind"});
    if (text(field(field(r, "provider"), "footprint"), "kind") != "declared-provider-effects")
        fail("fat_tree_review_footprint");
    const auto &host = field(field(r, "host"), "observed");
    keys(host, {"identity", "profile"});
    digest(text(host, "identity"));
    if (text(host, "profile") != "windows.nt10.x64.local-ntfs.prototype/1")
        fail("fat_tree_review_host");
    keys(field(field(r, "host"), "footprint"), {"kind"});
    if (text(field(field(r, "host"), "footprint"), "kind") !=
        "ordinary-local-process-and-file-effects")
        fail("fat_tree_review_footprint");
    const auto &input = field(v, "prepared_input");
    keys(input, {"schema", "path", "expected_source", "volume_offset", "volume_bytes", "fat_copy",
                 "capture_epoch", "page", "resources"});
    if (text(input, "schema") != "org.disked.fat-tree-input/1" ||
        text(input, "path") != text(source, "path"))
        fail("fat_tree_review_selection");
    equal(field(input, "expected_source"), field(source, "file"), "fat_tree_review_source");
    for (const auto *key : {"volume_offset", "volume_bytes", "fat_copy", "capture_epoch"})
        equal(field(input, key), field(s, key), "fat_tree_review_selection");
    const auto &page = field(input, "page"), &resources = field(input, "resources");
    keys(page, {"events", "records", "reads", "read_bytes", "output_bytes"});
    range(field(page, "records"), 1, 1024);
    range(field(page, "events"), 1, 512);
    range(field(page, "reads"), 1, 512);
    range(field(page, "read_bytes"), 4096, 65536);
    range(field(page, "output_bytes"), 32768, 65536);
    keys(resources, {"bitmap_bytes", "depth", "queued_directories"});
    range(field(resources, "bitmap_bytes"), 1, 67108864);
    range(field(resources, "depth"), 1, 1024);
    range(field(resources, "queued_directories"), 1, 65536);
}
void store(const V &v, const V &b) {
    const auto ids =
        resource(v, "create-operation-state", "identity-epoch-and-ordered-state-history");
    const auto &o = field(v, "observed");
    keys(o, {"file", "parents", "path"});
    file_identity(field(o, "file"), true);
    parents(field(o, "parents"));
    path(text(o, "path"));
    const auto &p = field(v, "footprint");
    keys(p, {"kind", "children", "record_bytes", "total_bytes", "records"});
    auto expected = V::array();
    for (const auto *name :
         {"recursive-request.json", "recursive-cancel", "recursive-state.ndjson"})
        expected.items.push_back(V::string(name));
    if (text(p, "kind") != "finite-control-files" || number(field(p, "record_bytes")) != 16384 ||
        number(field(p, "total_bytes")) != 1048576 || number(field(p, "records")) != 64)
        fail("fat_tree_review_store");
    equal(field(p, "children"), expected, "fat_tree_review_store");
    for (const auto &role : field(b, "resources").fields) {
        for (const auto &alias : field(role.second, "aliases").items)
            if (ids.count(alias.text))
                fail("fat_tree_review_alias");
    }
    for (const auto *key : {"source", "destination", "ledger"})
        if (text(o, "path") == text(field(b, "paths"), key))
            fail("fat_tree_review_alias");
}
} // namespace
json::Limits fat_tree_review_limits() {
    json::Limits l;
    l.bytes = 262144;
    l.depth = 32;
    l.values = 65536;
    l.string_bytes = 32768;
    return l;
}
FatTreeReview validate_fat_tree_review(const V &v) {
    encode(v);
    keys(v, {"schema", "backend", "operation_store"});
    if (text(v, "schema") != "org.disked.fat-tree-extraction-review-prototype/1")
        fail("fat_tree_review_version");
    backend(field(v, "backend"));
    store(field(v, "operation_store"), field(v, "backend"));
    return {v, hash("disked:fat-tree-extraction-review:1\n" + encode(v))};
}
FatTreeReview prepare_fat_tree_review(const V &process, const V &operation_store) {
    encode(process);
    keys(process, {"schema", "selection", "prepared_input", "paths", "resources", "metadata_policy",
                   "budgets", "effects", "scratch_resources", "recovery_resources",
                   "source_consistency", "owner_accepted"});
    if (text(process, "schema") != "org.disked.fat-tree-extraction-plan-prototype/1" ||
        boolean(field(process, "owner_accepted")))
        fail("fat_tree_review_process_definition");
    auto b = process;
    b.put("schema", V::string("org.disked.fat-tree-effects-prototype/1"));
    b.fields.erase("owner_accepted");
    auto &s = b.fields.at("selection");
    keys(s, {"kind", "volume_offset", "volume_bytes", "fat_copy", "capture_epoch",
             "preparation_binding", "preparation_context", "tree_digest", "pages", "entries",
             "content_bytes"});
    const auto &binding = field(s, "preparation_binding"),
               &context = field(s, "preparation_context");
    keys(binding, {"source_id", "capture_id", "source_bytes", "volume_offset", "volume_bytes",
                   "fat_copy", "capture_epoch"});
    digest(text(binding, "source_id"));
    digest(text(binding, "capture_id"));
    keys(context, {"process_id", "process_created", "capture_sequence"});
    range(field(context, "process_id"), 1, UINT32_MAX);
    range(field(context, "process_created"), 1, UINT64_MAX);
    range(field(context, "capture_sequence"), 1, UINT64_MAX);
    for (const auto *key : {"volume_offset", "volume_bytes", "fat_copy", "capture_epoch"})
        equal(field(binding, key), field(s, key), "fat_tree_review_process_binding");
    equal(
        field(binding, "source_bytes"),
        field(field(field(field(b, "resources"), "source"), "observed"), "file").fields.at("bytes"),
        "fat_tree_review_process_binding");
    s.fields.erase("preparation_binding");
    s.fields.erase("preparation_context");
    auto &input = b.fields.at("prepared_input");
    if (field(input, "fixture").kind != V::Kind::object || !field(input, "fixture").fields.empty())
        fail("fat_tree_review_fixture");
    input.fields.erase("fixture");
    return validate_fat_tree_review(
        V::object()
            .put("schema", V::string("org.disked.fat-tree-extraction-review-prototype/1"))
            .put("backend", std::move(b))
            .put("operation_store", operation_store));
}
void validate_fat_tree_review_grant(const FatTreeReview &review, const FatTreeReviewGrant &grant) {
    const auto checked = validate_fat_tree_review(review.definition);
    if (checked.digest != review.digest || grant.review_digest != checked.digest ||
        !grant.source_read || !grant.destination_write || !grant.ledger_write ||
        !grant.operation_write || !grant.host_effects)
        fail("fat_tree_review_grant");
}
bool same_fat_tree_review(const FatTreeReview &review, const V &process, const V &operation_store) {
    const auto checked = validate_fat_tree_review(review.definition);
    if (checked.digest != review.digest)
        fail("fat_tree_review_digest");
    const auto fresh = prepare_fat_tree_review(process, operation_store);
    return checked.digest == fresh.digest && encode(checked.definition) == encode(fresh.definition);
}
} // namespace disked
