#include "platform/windows/storage/fat_tree_extraction_worker.h"
#include "platform/windows/memory_budget.h"
#include "platform/windows/worker_files.h"
#include "providers/image/local_file.h"
#include <iostream>

using V = disked::json::Value;
namespace n = disked::nt_inventory;
namespace f = disked::local_file;
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::runtime_error("writer_probe_field");
    return *p;
}
static std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw std::runtime_error("writer_probe_field");
    return p->text;
}
static std::uint64_t integer(const V &v, const char *key, std::uint64_t fallback = 0) {
    const auto s = text(v, key, std::to_string(fallback));
    if (!disked::json::decimal_u64(s))
        throw std::runtime_error("writer_probe_integer");
    return std::stoull(s);
}
static void emit(V value) {
    auto l = disked::fat_tree_content_json_limits();
    std::cout << disked::json::dump(value, l) << '\n' << std::flush;
}
static bool exited(const V &v) {
    return text(field(v, "worker"), "observation") == "exited";
}
static V process_identity() {
    auto value = V::object();
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token))
        throw std::runtime_error("probe_token_open");
    for (const auto kind : {TokenUser, TokenIntegrityLevel, TokenRestrictedSids}) {
        DWORD size = 0;
        GetTokenInformation(token, kind, nullptr, 0, &size);
        if (!size || size > 65536) {
            CloseHandle(token);
            throw std::runtime_error("probe_token_size");
        }
        std::vector<unsigned char> buffer(size);
        if (!GetTokenInformation(token, kind, buffer.data(), size, &size)) {
            CloseHandle(token);
            throw std::runtime_error("probe_token_query");
        }
        auto sids = V::array();
        auto add = [&](PSID sid) {
            LPWSTR result = nullptr;
            if (!ConvertSidToStringSidW(sid, &result))
                throw std::runtime_error("probe_token_sid");
            sids.items.push_back(V::string(f::utf8(result)));
            LocalFree(result);
        };
        if (kind == TokenRestrictedSids) {
            const auto *groups = reinterpret_cast<const TOKEN_GROUPS *>(buffer.data());
            for (DWORD i = 0; i < groups->GroupCount; ++i)
                add(groups->Groups[i].Sid);
            value.put("restricting_sids", std::move(sids));
        } else {
            add(reinterpret_cast<const SID_AND_ATTRIBUTES *>(buffer.data())->Sid);
            value.put(kind == TokenUser ? "user_sid" : "integrity_sid", std::move(sids.items[0]));
        }
    }
    DWORD size = 0, container = ~0u, elevated = ~0u;
    if (GetTokenInformation(token, TokenIsAppContainer, &container, sizeof(container), &size))
        value.put("appcontainer", V::string(std::to_string(container)));
    if (GetTokenInformation(token, TokenElevation, &elevated, sizeof(elevated), &size))
        value.put("elevated", V::string(std::to_string(elevated)));
    value.put("restricted", V::boolean_value(IsTokenRestricted(token) != FALSE));
    CloseHandle(token);
    return value;
}
int wmain(int argc, wchar_t **argv) {
    std::wstring observed_source;
    if (argc == 2 && std::wcscmp(argv[1], L"--token-identity") == 0) {
        emit(process_identity());
        return 0;
    }
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_fat_tree_extraction_worker") == 0)
        return n::fat_tree_extraction_worker_role(argc, argv);
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        const std::string data((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(data, disked::fat_tree_content_json_limits());
        disked::FatTreeExtractionRequest request;
        request.tree.path = text(input, "source");
        request.tree.volume_offset = integer(input, "offset");
        request.tree.volume_bytes = integer(input, "length");
        request.tree.capture_epoch = 17;
        request.destination = text(input, "destination");
        request.ledger = text(input, "ledger");
        request.metadata.oem_code_page = 437;
        const auto path = f::path_for(request.tree.path);
        observed_source = path;
        auto parents = f::pin_parents(path);
        f::Handle source(
            CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (source.value == INVALID_HANDLE_VALUE)
            throw std::runtime_error("writer_probe_source");
        f::bind_path(source.value, path);
        request.tree.expected_source = f::metadata(source.value).value;
        if (text(input, "mode") == "quota") {
            std::vector<std::unique_ptr<n::FatTreeExtractionWorker>> owned;
            for (unsigned i = 0; i < 4; ++i) {
                auto child = n::FatTreeExtractionWorker::prepare(request);
                child->launch();
                child->release();
                owned.push_back(std::move(child));
            }
            bool refused = false;
            std::string error_code;
            DWORD platform_code = ERROR_SUCCESS;
            auto before = V::array();
            for (auto &child : owned)
                before.items.push_back(child->observe());
            std::unique_ptr<n::FatTreeExtractionWorker> extra;
            try {
                extra = n::FatTreeExtractionWorker::prepare(request);
                extra->launch();
                extra->release();
            } catch (const disked::worker_files::Failure &error) {
                refused = true;
                error_code = error.what();
                platform_code = error.platform;
            }
            const auto extra_retirement = extra ? extra->retire() : V{};
            auto retirement = V::array();
            for (auto &child : owned) {
                child->cancel();
                retirement.items.push_back(child->retire());
            }
            emit(V::object()
                     .put("kind", V::string("quota"))
                     .put("owned", V::string("4"))
                     .put("fifth_refused", V::boolean_value(refused))
                     .put("fifth_error", V::string(error_code))
                     .put("fifth_platform_code", V::string(std::to_string(platform_code)))
                     .put("fifth_constructed", V::boolean_value(extra != nullptr))
                     .put("before", before)
                     .put("fifth_retirement", extra_retirement)
                     .put("retirement", retirement));
            return 0;
        }
        auto worker = n::FatTreeExtractionWorker::prepare(
            request, input.find("fixture") ? field(input, "fixture") : V::object());
        try {
            worker->launch();
            worker->release();
        } catch (const std::exception &error) {
            const auto retired = worker->retire();
            emit(V::object()
                     .put("kind", V::string("startup_error"))
                     .put("code", V::string(error.what()))
                     .put("retirement", retired));
            return 0;
        }
        const auto started = GetTickCount64(), duration = integer(input, "wait_ms", 30000);
        bool granted = false, cancelled = false, announced = false, observed_outcome = false;
        V last = worker->observe();
        while (GetTickCount64() - started < duration) {
            last = worker->observe(10);
            if (const auto prepared = worker->prepared()) {
                if (!granted && !cancelled && !announced) {
                    announced = true;
                    emit(V::object()
                             .put("kind", V::string("prepared"))
                             .put("definition", prepared->definition())
                             .put("digest", V::string(prepared->digest()))
                             .put("owner", prepared->owner()));
                    if (text(input, "mode") == "cancel_prepared" ||
                        text(input, "mode") == "prepare_only") {
                        worker->cancel();
                        cancelled = true;
                    } else if (text(input, "mode") != "hold_prepared") {
                        disked::FatTreeExtractionGrant grant{prepared->digest(), true, true, true,
                                                             true};
                        if (text(input, "mode") == "bad_grant")
                            grant.definition_digest = "sha256:" + std::string(64, '0');
                        const auto missing = text(input, "missing_grant");
                        if (missing == "source")
                            grant.source_read = false;
                        if (missing == "destination")
                            grant.destination_write = false;
                        if (missing == "ledger")
                            grant.ledger_write = false;
                        if (missing == "host")
                            grant.host_effects = false;
                        try {
                            worker->grant(grant);
                            granted = true;
                        } catch (const std::exception &error) {
                            emit(V::object()
                                     .put("kind", V::string("grant_refused"))
                                     .put("code", V::string(error.what())));
                            worker->cancel();
                            cancelled = true;
                        }
                    }
                }
            }
            if (!observed_outcome && field(last, "outcome").kind == V::Kind::object &&
                !exited(last)) {
                observed_outcome = true;
                emit(V::object().put("kind", V::string("outcome_before_exit")).put("value", last));
            }
            if (!cancelled && input.find("cancel_after_ms") &&
                GetTickCount64() - started >= integer(input, "cancel_after_ms")) {
                worker->cancel();
                cancelled = true;
            }
            if (!cancelled && granted && input.find("cancel_after_pulse") &&
                integer(last, "progress_pulse") >= integer(input, "cancel_after_pulse")) {
                worker->cancel();
                cancelled = true;
            }
            if (exited(last) || text(last, "status") == "unknown")
                break;
        }
        if (!exited(last))
            emit(V::object().put("kind", V::string("before_retirement")).put("value", last));
        const auto retirement = worker->retire();
        emit(V::object()
                 .put("kind", V::string("finished"))
                 .put("value", retirement)
                 .put("retained",
                      V::string(std::to_string(n::FatTreeExtractionWorker::reap_retained()))));
        return 0;
    } catch (const f::Error &error) {
        auto parents = V::array();
        auto token_info = process_identity();
        if (!observed_source.empty()) {
            std::size_t end = 2;
            for (;;) {
                const auto path = end == 2 ? observed_source.substr(0,3) : observed_source.substr(0,end);
                SetLastError(0);
                f::Handle handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
                    FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
                const auto status = handle.value == INVALID_HANDLE_VALUE ? GetLastError() : ERROR_SUCCESS;
                parents.items.push_back(V::object().put("path",V::string(f::utf8(path)))
                    .put("opened",V::boolean_value(handle.value != INVALID_HANDLE_VALUE))
                    .put("platform_code",V::string(std::to_string(status))));
                end = observed_source.find(L'\\',end+1);if(end == observed_source.npos)break;
            }
        }
        emit(V::object().put("kind",V::string("error")).put("code",V::string(error.what()))
            .put("platform_code",V::string(std::to_string(error.platform_code)))
            .put("process_token",std::move(token_info))
            .put("parents_after_failure",std::move(parents)));
        return 0;
    } catch (const std::exception &error) {
        emit(V::object().put("kind", V::string("error")).put("code", V::string(error.what())));
        return 0;
    }
}
