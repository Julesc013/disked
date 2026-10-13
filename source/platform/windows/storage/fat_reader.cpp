#include "fat_reader.h"
#include "fat_worker.h"
#include "providers/image/local_file.h"
#include <atomic>
#include <limits>
#include <cstring>

namespace disked {
namespace {
using V = json::Value;
namespace f = local_file;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("fat_reader_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("fat_reader_shape");
    return p.text;
}
bool exited(const V &value) {
    return text(field(value, "worker"), "observation") == "exited";
}
std::uint64_t epoch() {
    static std::atomic<std::uint64_t> sequence{0};
    auto before = sequence.load();
    for (;;) {
        if (before == std::numeric_limits<std::uint64_t>::max())
            throw std::runtime_error("fat_reader_epoch_exhausted");
        if (sequence.compare_exchange_weak(before, before + 1))
            return before + 1;
    }
}
struct Source {
    std::wstring path;
    std::vector<f::Handle> parents;
    V generations;
    f::Handle file;
    explicit Source(const std::string &input)
        : path(f::path_for(input)), parents(f::pin_parents(path)),
          generations(f::parent_generations(parents)),
          file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr)) {
        if (file.value == INVALID_HANDLE_VALUE)
            throw f::Error("fat_source_open", GetLastError());
        f::ordinary(file.value, false);
        f::bind_path(file.value, path);
        f::check_parents(path, parents, generations);
    }
};
FatInspectionRead failure(FatInspectionRead::Status status, const std::string &diagnostic,
                          const V &worker = V{}, std::uint32_t platform = 0) {
    FatInspectionRead out;
    out.status = status;
    out.diagnostic = diagnostic;
    out.worker = worker;
    out.platform_code = platform;
    return out;
}
// Keep ownership and the executing callback/slot until actual exit. Each wait is
// bounded; an outer frontend timeout neither acknowledges nor restarts this reader.
V finish_exit(nt_inventory::FatWorker &worker) {
    auto value = worker.observe();
    if (exited(value))
        return value;
    const auto grace = GetTickCount64() + 1000;
    do {
        value = worker.observe(20);
    } while (!exited(value) && GetTickCount64() < grace);
    if (exited(value))
        return value;
    try {
        worker.cancel();
        value = worker.retire();
    } catch (const std::exception &) {
    }
    while (!exited(value)) {
        try {
            value = worker.observe(100);
        } catch (const std::exception &) {
            Sleep(100);
        }
    }
    return value;
}
} // namespace
FatInspectionRead inspect_fat_image(const FatInspectionRequest &request) {
    std::unique_ptr<nt_inventory::FatWorker> worker;
    try {
#ifdef DISKED_FAT_COMMAND_TESTING
        if (GetEnvironmentVariableW(L"DISKED_FAT_COMMAND_TEST_OPEN_GUARD", nullptr, 0))
            throw f::Error("fat_source_open_forbidden");
#endif
        Source source(request.path);
        FatSnapshotInput input;
        input.path = request.path;
        input.expected_source = f::metadata(source.file.value).value;
        input.capture_epoch = epoch();
        input.volume_offset = request.volume_offset;
        input.volume_bytes = request.volume_bytes;
        input.fat_copy = request.fat_copy;
        input.name_code_page = request.name_code_page;
        input.allocation_scan = request.allocation_scan;
        input.allocation_window = request.allocation_window;
        input.auxiliary_checks = request.auxiliary_checks;
        input.queries = request.queries;
#ifdef DISKED_FAT_COMMAND_TESTING
        if (GetEnvironmentVariableW(L"DISKED_FAT_COMMAND_TEST_VERIFY_CHANGED", nullptr, 0))
            input.fixture.put("capture_fault", V::string("verify_changed"));
        if (GetEnvironmentVariableW(L"DISKED_FAT_COMMAND_TEST_VERIFY_ERROR", nullptr, 0))
            input.fixture.put("capture_fault", V::string("verify_error"));
        if (GetEnvironmentVariableW(L"DISKED_FAT_COMMAND_TEST_HANG", nullptr, 0))
            input.fixture.put("worker_fault", V::string("hang"));
        if (GetEnvironmentVariableW(L"DISKED_FAT_COMMAND_TEST_INVALID_REPLY", nullptr, 0))
            input.fixture.put("worker_fault", V::string("result_changed"));
#endif
        worker = nt_inventory::FatWorker::prepare(input);
        worker->launch();
        if (!worker->wait_entered(1000))
            return failure(FatInspectionRead::Status::Unresolved, "fat_reader_startup_unresolved",
                           finish_exit(*worker));
        worker->release();
        const auto deadline = GetTickCount64() + 3000;
        V observed;
        for (;;) {
            observed = worker->observe(100);
            if (text(observed, "status") == "completed" || exited(observed) ||
                GetTickCount64() >= deadline)
                break;
        }
        if (text(observed, "status") != "completed") {
            const auto result = finish_exit(*worker);
            return failure(FatInspectionRead::Status::Unresolved,
                           exited(observed) ? "fat_reader_validation_unresolved"
                                            : "fat_reader_wait_expired",
                           result);
        }
        const auto publication = field(observed, "result");
        if (text(publication, "status") == "unavailable") {
            const auto &diagnostic = field(publication, "diagnostic");
            const auto result = finish_exit(*worker);
            return failure(
                FatInspectionRead::Status::Refused, text(diagnostic, "code"), result,
                static_cast<std::uint32_t>(std::stoull(text(diagnostic, "platform_code"))));
        }
        const auto snapshot = worker->snapshot(request.retain_capture);
        if (!snapshot)
            return failure(FatInspectionRead::Status::Unresolved, "fat_reader_snapshot_unresolved",
                           finish_exit(*worker));
        const auto retired = finish_exit(*worker);
        FatInspectionRead out;
        out.status = FatInspectionRead::Status::Captured;
        out.file = snapshot->result();
        out.context = snapshot->context();
        out.worker = retired;
        if (request.retain_capture) out.frame = snapshot->frame();
        return out;
    } catch (const f::Error &error) {
        if (worker && !worker->never_launched())
            return failure(FatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker), error.platform_code);
        return failure(FatInspectionRead::Status::Refused, error.what(), V{}, error.platform_code);
    } catch (const std::invalid_argument &error) {
        if (worker && !worker->never_launched())
            return failure(FatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker));
        return failure(FatInspectionRead::Status::Refused, error.what());
    } catch (const std::exception &error) {
        if (worker && !worker->never_launched())
            return failure(FatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker));
        return failure(FatInspectionRead::Status::Refused, error.what());
    }
}
std::string new_fat_capture_domain() {
    struct Library {
        HMODULE value = LoadLibraryExW(L"advapi32.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
        ~Library() {if (value) FreeLibrary(value);}
    } library;
    if (!library.value) throw FatRetentionError("capture_retention_identity");
    const auto address = GetProcAddress(library.value, "SystemFunction036");
    using Random = BOOLEAN (WINAPI *)(void *, ULONG);
    Random random = nullptr;
    static_assert(sizeof(random) == sizeof(address), "native function pointer size");
    std::memcpy(&random, &address, sizeof(random));
    unsigned char bytes[16];
    if (!random || !random(bytes, sizeof(bytes))) throw FatRetentionError("capture_retention_identity");
    const char digits[] = "0123456789abcdef";
    std::string out;out.reserve(32);
    for (auto byte : bytes) {out += digits[byte >> 4];out += digits[byte & 15];}
    return out;
}
} // namespace disked
