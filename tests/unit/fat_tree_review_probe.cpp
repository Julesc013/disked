#include "runtime/acquisition/fat_tree_review.h"
#include <iostream>
using V = disked::json::Value;
static const V &get(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        throw std::runtime_error("review_probe_field");
    return *p;
}
int main() {
    try {
        const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(raw, disked::fat_tree_review_limits());
        const auto *supplied = input.find("review");
        const auto review = supplied
                                ? disked::validate_fat_tree_review(*supplied)
                                : disked::prepare_fat_tree_review(get(input, "process_definition"),
                                                                  get(input, "operation_store"));
        auto out = V::object()
                       .put("definition", review.definition)
                       .put("digest", V::string(review.digest))
                       .put("authorizes_effects", V::boolean_value(false));
        if (const auto *g = input.find("grant")) {
            disked::FatTreeReviewGrant grant;
            grant.review_digest = get(*g, "review_digest").text;
            grant.source_read = get(*g, "source_read").boolean;
            grant.destination_write = get(*g, "destination_write").boolean;
            grant.ledger_write = get(*g, "ledger_write").boolean;
            grant.operation_write = get(*g, "operation_write").boolean;
            grant.host_effects = get(*g, "host_effects").boolean;
            disked::validate_fat_tree_review_grant(review, grant);
            out.put("grant_shape_valid", V::boolean_value(true));
        }
        if (const auto *fresh = input.find("fresh_process_definition"))
            out.put("matches", V::boolean_value(disked::same_fat_tree_review(
                                   review, *fresh, get(input, "fresh_operation_store"))));
        std::cout << disked::json::dump(out, disked::fat_tree_review_limits()) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cout << disked::json::dump(V::object().put("error", V::string(e.what()))) << '\n';
        return 20;
    }
}
