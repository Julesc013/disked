#include "fat_tree_commands.h"
#include "fat_metadata.h"

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw FatTreeReviewError("fat_tree_command_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw FatTreeReviewError("fat_tree_command_shape");
    return p.text;
}
std::string optional(const V &v, const char *key, const std::string &fallback) {
    return v.find(key) ? text(v, key) : fallback;
}
bool operation(const V &v) {
    return v.kind == V::Kind::string && v.text.size() == 40 && !v.text.compare(0, 8, "tree-op:") &&
           v.text.find_first_not_of("0123456789abcdef", 8) == v.text.npos;
}
V policy(const V &v) {
    FatMetadataPolicy p;
    p.oem_code_page = static_cast<std::uint32_t>(std::stoul(text(v, "oem_code_page")));
    p.name_selection = optional(v, "name_selection", "long_or_short");
    p.unrepresentable_name = optional(v, "unrepresentable_name", "refuse");
    p.time_interpretation = optional(v, "time_interpretation", "preserve_raw");
    const auto offset = optional(v, "utc_offset_minutes", "0");
    std::size_t used = 0;
    try {
        p.utc_offset_minutes = std::stoi(offset, &used);
    } catch (const std::exception &) {
        throw FatTreeReviewError("fat_tree_command_policy");
    }
    if (used != offset.size() || std::to_string(p.utc_offset_minutes) != offset ||
        (p.time_interpretation == "fixed_offset" && !v.find("utc_offset_minutes")))
        throw FatTreeReviewError("fat_tree_command_policy");
    return fat_metadata_policy_value(p);
}
V scoped(V value, const char *kind) {
    return value.put("scope", V::string("ordinary-local-fat-tree-extraction"))
        .put("request_kind", V::string(kind));
}
} // namespace
Outcome fat_tree_command_unresolved(const std::string &request, const V &p) {
    auto value = V::object().put("request_state", V::string("unresolved"));
    if (const auto *d = p.find("definition")) {
        if (const auto *store = d->find("operation_store"))
            if (const auto *observed = store->find("observed"))
                if (const auto *path = observed->find("path"))
                    value.put("state_directory", *path);
    }
    if (const auto *digest = p.find("definition_digest"))
        value.put("definition_digest", *digest);
    auto out = completed(request, scoped(value, "recursive-execution"));
    out.exit_code = 6;
    out.response.put("status", V::string("unknown"));
    out.response.fields["diagnostics"].items.push_back(diagnostic("fat_tree_execution_unresolved"));
    return out;
}
Outcome dispatch_fat_tree_extraction(const Registry &registry, const std::string &request,
                                     const V &p, const FatTreeCommandActions &actions) {
    bool invoked = false;
    V reply;
    try {
        const auto *descriptor = registry.command("filesystem.tree.extract");
        if (!descriptor)
            return refused(request, "command_unavailable", 3);
        const auto error = validate_parameters(registry, *descriptor, p);
        if (!error.empty())
            return refused(request, error);
        if (text(p, "phase") == "prepare") {
            const auto requested_policy = policy(p);
            if (!actions.prepare)
                return refused(request, "fat_tree_provider_unavailable", 3);
            const auto prepared = actions.prepare(p);
            if (prepared.kind != V::Kind::object || prepared.fields.size() != 3)
                throw FatTreeReviewError("fat_tree_preparation_shape");
            const auto review = validate_fat_tree_review(field(prepared, "definition"));
            const auto &backend = field(review.definition, "backend");
            if (json::dump(field(backend, "metadata_policy")) != json::dump(requested_policy))
                throw FatTreeReviewError("fat_tree_preparation_binding");
            for (const auto *name : {"volume_offset", "volume_bytes", "fat_copy", "capture_epoch"})
                if (text(field(backend, "selection"), name) != text(p, name))
                    throw FatTreeReviewError("fat_tree_preparation_binding");
            if (text(prepared, "definition_digest") != review.digest)
                throw FatTreeReviewError("fat_tree_preparation_digest");
            auto definition_descriptor =
                V::object()
                    .put("syntax_status", V::string("defined"))
                    .put("parameter_schema",
                         V::string("urn:disked:schema:fat-tree-review-prototype:1"));
            if (!validate_parameters(registry, definition_descriptor, review.definition).empty())
                throw FatTreeReviewError("fat_tree_preparation_shape");
            auto small = fat_tree_review_limits();
            small.bytes = 32768;
            json::dump(review.definition, small);
            const auto &facts = field(field(prepared, "preparation"), "worker");
            if (text(field(facts, "worker"), "observation") != "exited" ||
                field(facts, "dependencies_retained").kind != V::Kind::boolean ||
                field(facts, "dependencies_retained").boolean)
                throw FatTreeReviewError("fat_tree_preparation_exit_unresolved");
            auto value = prepared;
            value.put("phase", V::string("prepare"))
                .put("execution_admitted", V::boolean_value(false));
            return completed(request, scoped(value, "recursive-preparation"));
        }
        const auto review = validate_fat_tree_review(field(p, "definition"));
        FatTreeReviewGrant grant{text(p, "definition_digest"),
                                 field(p, "allow_source_read").boolean,
                                 field(p, "allow_destination_write").boolean,
                                 field(p, "allow_ledger_write").boolean,
                                 field(p, "allow_operation_write").boolean,
                                 field(p, "allow_host_effects").boolean};
        validate_fat_tree_review_grant(review, grant);
        if (!actions.execute)
            return refused(request, "fat_tree_provider_unavailable", 3);
        invoked = true;
        reply = actions.execute(review, grant);
        const auto status = text(reply, "status");
        const auto &id = field(reply, "operation_id");
        if (id.kind != V::Kind::null && !operation(id))
            throw FatTreeReviewError("fat_tree_execution_identity");
        auto out = completed(request, scoped(reply, "recursive-execution"));
        out.response.put("operation_id", id);
        if (status == "accepted_running") {
            if (!operation(id))
                throw FatTreeReviewError("fat_tree_execution_identity");
            const auto &receipt = field(reply, "reply");
            if (text(receipt, "phase") != "admitted" ||
                text(receipt, "review_digest") != review.digest ||
                json::dump(field(receipt, "operation_id")) != json::dump(id))
                throw FatTreeReviewError("fat_tree_execution_binding");
            out.response.put("status", V::string("accepted_running"));
            out.exit_code = 5;
        } else if (status == "completed") {
            const auto &receipt = field(reply, "reply");
            if (!operation(id) || text(receipt, "phase") != "finished" ||
                text(receipt, "review_digest") != review.digest ||
                json::dump(field(receipt, "operation_id")) != json::dump(id))
                throw FatTreeReviewError("fat_tree_execution_binding");
            const auto &worker = field(field(field(reply, "reply"), "admission"), "worker");
            if (text(field(worker, "worker"), "observation") != "exited" ||
                field(worker, "dependencies_retained").kind != V::Kind::boolean ||
                field(worker, "dependencies_retained").boolean)
                throw FatTreeReviewError("fat_tree_execution_exit_unresolved");
            const auto *outcome = worker.find("outcome");
            if (!outcome || outcome->kind != V::Kind::object ||
                text(*outcome, "status") != "complete") {
                out.response.put("status", V::string("failed"));
                out.exit_code = 4;
                out.response.fields["diagnostics"].items.push_back(
                    diagnostic("fat_tree_extraction_incomplete"));
            }
        } else if (status == "refused") {
            out.response.put("status", V::string("refused"));
            out.exit_code = 3;
        } else {
            out.response.put("status", V::string("unknown"));
            out.exit_code = 6;
            out.response.fields["diagnostics"].items.push_back(
                diagnostic("fat_tree_execution_unresolved"));
        }
        if (const auto *d = reply.find("diagnostic"))
            if (d->kind == V::Kind::string)
                out.response.fields["diagnostics"].items.push_back(diagnostic(d->text));
        return out;
    } catch (const std::exception &e) {
        if (invoked) {
            auto out = fat_tree_command_unresolved(request, p);
            if (const auto *id = reply.find("operation_id"))
                if (operation(*id))
                    out.response.put("operation_id", *id);
            return out;
        }
        return refused(request, e.what(), 3);
    }
}
} // namespace disked
