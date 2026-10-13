#include "platform/windows/storage/fat_tree_admission.h"
#ifdef DISKED_FAT_TREE_CONTROLLER_PROBE
#include "platform/windows/storage/fat_tree_controller.h"
#endif
#include "platform/windows/memory_budget.h"
#include "providers/image/local_file.h"
#include <iostream>

using V = disked::json::Value;
namespace n = disked::nt_inventory;
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::runtime_error("admission_probe_field");
    return *p;
}
static std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw std::runtime_error("admission_probe_field");
    return p->text;
}
static std::uint64_t number(const V &v, const char *key, std::uint64_t fallback = 0) {
    const auto s = text(v, key, std::to_string(fallback));
    if (!disked::json::decimal_u64(s))
        throw std::runtime_error("admission_probe_integer");
    return std::stoull(s);
}
static void emit(V v) {
    std::cout << disked::json::dump(v, disked::fat_tree_review_limits()) << '\n' << std::flush;
}
int wmain(int argc, wchar_t **argv) {
#ifdef DISKED_FAT_TREE_CONTROLLER_PROBE
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_fat_tree_controller") == 0)
        return n::fat_tree_controller_role(argc, argv);
#endif
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_fat_tree_extraction_worker") == 0)
        return n::fat_tree_extraction_worker_role(argc, argv);
    std::unique_ptr<n::FatTreeAdmission> owner;
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(raw, disked::fat_tree_review_limits());
        const auto fixture = input.find("fixture") ? *input.find("fixture") : V::object();
        disked::FatTreeReviewGrant grant{"", true, true, true, true, true};
        if (const auto *review = input.find("review")) {
            const auto checked = disked::validate_fat_tree_review(*review);
            grant.review_digest = text(input, "review_digest", checked.digest);
            const auto missing = text(input, "missing_grant");
            if (missing == "source")
                grant.source_read = false;
            if (missing == "destination")
                grant.destination_write = false;
            if (missing == "ledger")
                grant.ledger_write = false;
            if (missing == "operation")
                grant.operation_write = false;
            if (missing == "host")
                grant.host_effects = false;
#ifdef DISKED_FAT_TREE_CONTROLLER_PROBE
            const auto controller_mode = text(input, "controller_mode");
            if (!controller_mode.empty()) {
                auto controller = n::FatTreeController::prepare(checked, grant, fixture);
                controller->launch();
                if (controller_mode == "abandon") {
                    emit(V::object()
                             .put("kind", V::string("controller_abandoned"))
                             .put("observation", controller->observe()));
                    return 0;
                }
                if (controller_mode == "launch_reused") {
                    controller->launch();
                    throw std::runtime_error("controller_probe_expected_rejection");
                }
                controller->dispatch();
                if (controller_mode == "dispatch_reused") {
                    controller->dispatch();
                    throw std::runtime_error("controller_probe_expected_rejection");
                }
                const auto until = GetTickCount64() + number(input, "wait_ms", 10000);
                for (;;) {
                    auto observed = controller->observe();
                    const auto status = text(observed, "status");
                    const bool observe_exit = controller_mode == "observe_exit";
                    const bool exited =
                        text(field(observed, "controller"), "observation") == "exited";
                    if ((!observe_exit && status != "dispatch_pending") ||
                        (observe_exit && exited) || GetTickCount64() >= until) {
                        emit(V::object()
                                 .put("kind", V::string("controller_handoff"))
                                 .put("observation", observed));
                        return 0;
                    }
                    Sleep(10);
                }
            }
#endif
            owner = n::FatTreeAdmission::for_execution(checked, grant, fixture);
        } else {
            disked::FatTreeExtractionRequest request;
            request.tree.path = text(input, "source");
            request.tree.volume_offset = number(input, "offset");
            request.tree.volume_bytes = number(input, "length");
            request.tree.capture_epoch = 17;
            request.tree.fat_copy = static_cast<std::uint32_t>(number(input, "copy"));
            request.destination = text(input, "destination");
            request.ledger = text(input, "ledger");
            request.metadata.oem_code_page = 437;
            owner = n::FatTreeAdmission::prepare(request, text(input, "store"), fixture);
        }
        owner->launch();
        const auto start = GetTickCount64(), end = start + number(input, "wait_ms", 30000);
        bool announced = false, sent = false, cancelled = false;
        bool publication_announced = false;
        V last;
        for (;;) {
            last = owner->observe(0);
            if (!publication_announced &&
                field(field(last, "worker"), "outcome").kind != V::Kind::null &&
                text(field(field(last, "worker"), "worker"), "observation") == "running") {
                emit(V::object()
                         .put("kind", V::string("outcome_before_exit"))
                         .put("observation", last));
                publication_announced = true;
            }
            if (const auto prepared = owner->prepared_review())
                if (!announced) {
                    emit(V::object()
                             .put("kind", V::string("prepared"))
                             .put("review", prepared->definition)
                             .put("digest", V::string(prepared->digest))
                             .put("observation", last));
                    announced = true;
                    if (text(input, "mode") == "prepare") {
                        owner->cancel();
                        cancelled = true;
                    } else if (text(input, "mode") != "hold") {
                        if (const auto *review = input.find("review"))
                            owner->grant(disked::validate_fat_tree_review(*review), grant);
                        else {
                            grant.review_digest = prepared->digest;
                            owner->grant(*prepared, grant);
                        }
                        sent = true;
                    }
                }
            if (text(field(field(last, "worker"), "worker"), "observation") == "exited")
                break;
            if (field(last, "admission_failed").boolean)
                throw std::runtime_error(text(last, "diagnostic"));
            const auto destination =
                input.find("review")
                    ? text(field(field(*input.find("review"), "backend"), "paths"), "destination")
                    : text(input, "destination");
            const bool root_ready =
                text(input, "cancel_when_root") == "yes" &&
                GetFileAttributesW(disked::local_file::path_for(destination).c_str()) !=
                    INVALID_FILE_ATTRIBUTES;
            if (sent && !cancelled &&
                (root_ready || (number(input, "cancel_after_ms") &&
                                GetTickCount64() >= start + number(input, "cancel_after_ms")))) {
                owner->cancel();
                cancelled = true;
            }
            if (GetTickCount64() >= end) {
                emit(V::object()
                         .put("kind", V::string("before_retirement"))
                         .put("observation", last));
                break;
            }
            Sleep(10);
        }
        auto retired = owner->retire();
        emit(V::object()
                 .put("kind", V::string("finished"))
                 .put("observation", retired)
                 .put("retained",
                      V::string(std::to_string(n::FatTreeExtractionWorker::reap_retained()))));
        return 0;
    } catch (const std::exception &e) {
        auto out = V::object().put("kind", V::string("error")).put("code", V::string(e.what()));
        if (owner)
            try {
                out.put("retirement", owner->retire());
            } catch (...) {
            }
        emit(out);
        return 0;
    }
}
