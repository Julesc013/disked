#include "platform/windows/storage/fat_tree_actions.h"
#include "platform/windows/storage/fat_tree_controller.h"
#include "platform/windows/storage/fat_tree_extraction_worker.h"
#include "platform/windows/memory_budget.h"
#include "apps/disked/command_registry.h"
#include <iostream>

using V = disked::json::Value;
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::runtime_error("command_probe_field");
    return *p;
}
int wmain(int argc, wchar_t **argv) {
    namespace n = disked::nt_inventory;
    if (argc > 1 && !std::wcscmp(argv[1], L"__disked_fat_tree_controller"))
        return n::fat_tree_controller_role(argc, argv);
    if (argc > 1 && !std::wcscmp(argv[1], L"__disked_fat_tree_extraction_worker"))
        return n::fat_tree_extraction_worker_role(argc, argv);
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(raw);
        const auto &registry = disked::command_registry();
        if (const auto *review = input.find("validate_review")) {
            const auto descriptor =
                V::object()
                    .put("syntax_status", V::string("defined"))
                    .put("parameter_schema",
                         V::string("urn:disked:schema:fat-tree-review-prototype:1"));
            auto output = V::object().put(
                "error", V::string(disked::validate_parameters(registry, descriptor, *review)));
            std::cout << disked::json::dump(output) << '\n';
            return 0;
        }
        auto actions = n::fat_tree_command_actions();
        unsigned prepare_calls = 0, execute_calls = 0;
        if (input.find("spy")) {
            actions.prepare = [&](const V &) {
                ++prepare_calls;
                return field(input, "prepared");
            };
            actions.execute = [&](const disked::FatTreeReview &,
                                  const disked::FatTreeReviewGrant &) {
                ++execute_calls;
                return field(input, "reply");
            };
        }
        disked::Outcome out;
        V parameters, normalized;
        if (const auto *words = input.find("argv")) {
            std::vector<std::string> args;
            for (const auto &v : words->items)
                args.push_back(v.text);
            const auto parsed = disked::parse_invocation(registry, args);
            normalized = parsed.normalized();
            if (!parsed.valid())
                out = disked::refused("probe", parsed.diagnostics.items.front().find("code")->text);
            else if (parsed.command_id != "filesystem.tree.extract")
                out = disked::refused("probe", "command_unavailable", 3);
            else
                out = disked::dispatch_fat_tree_extraction(registry, "probe", parsed.parameters,
                                                           actions);
        } else if (const auto *editor = input.find("editor")) {
            const auto error = disked::form_parameters(
                registry, *registry.command("filesystem.tree.extract"), *editor, parameters);
            out = error.empty()
                      ? disked::dispatch_fat_tree_extraction(registry, "probe", parameters, actions)
                      : disked::refused("probe", error);
        } else {
            out = disked::process_request(
                registry, disked::json::dump(field(input, "request")),
                [&](const std::string &request, const std::string &command, const V &p,
                    const std::string &) {
                    return command == "filesystem.tree.extract"
                               ? disked::dispatch_fat_tree_extraction(registry, request, p, actions)
                               : disked::refused(request, "command_unavailable", 3);
                });
        }
        auto response = V::object()
                            .put("response", out.response)
                            .put("normalized", normalized)
                            .put("prepare_calls", V::string(std::to_string(prepare_calls)))
                            .put("execute_calls", V::string(std::to_string(execute_calls)));
        auto limits = disked::fat_tree_review_limits();
        limits.bytes = 1048575;
        std::cout << disked::json::dump(response, limits) << '\n';
        return out.exit_code;
    } catch (const std::exception &e) {
        std::cout << disked::json::dump(V::object().put("error", V::string(e.what()))) << '\n';
        return 20;
    }
}
