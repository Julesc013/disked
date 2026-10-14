#include "exfat_reader.h"
#include "exfat_worker.h"
#include "platform/windows/worker_files.h"
#include "providers/image/local_file.h"
#include <atomic>
#include <limits>

namespace disked {
namespace {
using V = json::Value;
namespace f = local_file;
const V &field(const V &value, const char *key) {
    const auto *found = value.find(key);
    if (!found)
        throw std::runtime_error("exfat_reader_shape");
    return *found;
}
std::string text(const V &value, const char *key) {
    const auto &found = field(value, key);
    if (found.kind != V::Kind::string)
        throw std::runtime_error("exfat_reader_shape");
    return found.text;
}
bool exited(const V &value) {
    return text(field(value, "worker"), "observation") == "exited";
}
std::uint64_t epoch() {
    static std::atomic<std::uint64_t> sequence{0};
    auto before = sequence.load();
    for (;;) {
        if (before == std::numeric_limits<std::uint64_t>::max())
            throw std::runtime_error("exfat_reader_epoch_exhausted");
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
            throw f::Error("exfat_source_open", GetLastError());
        f::ordinary(file.value, false);
        f::bind_path(file.value, path);
        f::check_parents(path, parents, generations);
    }
};
#ifdef DISKED_EXFAT_COMMAND_TESTING
void source_gate() {
    wchar_t name[161];
    const auto count = GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_GATE", name, 161);
    if (!count)
        return;
    if (count >= 161)
        throw std::runtime_error("exfat_test_gate_name");
    struct Event {
        HANDLE value;
        explicit Event(const std::wstring &label)
            : value(OpenEventW(SYNCHRONIZE | EVENT_MODIFY_STATE, FALSE, label.c_str())) {
            if (!value)
                throw std::runtime_error("exfat_test_gate_open");
        }
        ~Event() {
            CloseHandle(value);
        }
    };
    Event entered(std::wstring(name) + L".entered"), release(std::wstring(name) + L".release");
    if (!SetEvent(entered.value))
        throw std::runtime_error("exfat_test_gate_signal");
    if (WaitForSingleObject(release.value, 15000) != WAIT_OBJECT_0)
        throw std::runtime_error("exfat_test_gate_wait");
}
#endif
ExfatInspectionRead failure(ExfatInspectionRead::Status status, const std::string &code,
                            const V &worker = V{}, std::uint32_t platform = 0) {
    ExfatInspectionRead result;
    result.status = status;
    result.diagnostic = code;
    result.worker = worker;
    result.platform_code = platform;
    return result;
}
// Preserve the session/source and callback slot until actual exit. A frontend
// deadline returns unknown to its caller; it does not release this ownership.
V finish_exit(nt_inventory::ExfatWorker &worker) {
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
ExfatInspectionRead inspect_exfat_image(const ExfatInspectionRequest &request) {
    std::unique_ptr<Source> source;
    std::unique_ptr<nt_inventory::ExfatWorker> worker;
    try {
#ifdef DISKED_EXFAT_COMMAND_TESTING
        if (GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_OPEN_GUARD", nullptr, 0))
            throw f::Error("exfat_source_open_forbidden");
#endif
        source.reset(new Source(request.path));
#ifdef DISKED_EXFAT_COMMAND_TESTING
        source_gate();
#endif
        ExfatSnapshotInput input;
        input.path = request.path;
        input.expected_source = f::metadata(source->file.value).value;
        input.capture_epoch = epoch();
        input.volume_offset = request.volume_offset;
        input.volume_bytes = request.volume_bytes;
        input.upcase_format = request.upcase_format;
#ifdef DISKED_EXFAT_COMMAND_TESTING
        if (GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_VERIFY_CHANGED", nullptr, 0))
            input.fixture.put("capture_fault", V::string("metadata"));
        if (GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_VERIFY_ERROR", nullptr, 0))
            input.fixture.put("capture_fault", V::string("error"));
        if (GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_HANG", nullptr, 0))
            input.fixture.put("worker_fault", V::string("hang"));
        if (GetEnvironmentVariableW(L"DISKED_EXFAT_COMMAND_TEST_INVALID_REPLY", nullptr, 0))
            input.fixture.put("worker_fault", V::string("result_changed"));
#endif
        worker = nt_inventory::ExfatWorker::prepare(input);
        worker->launch();
        if (!worker->wait_entered(1000))
            return failure(ExfatInspectionRead::Status::Unresolved,
                           "exfat_reader_startup_unresolved", finish_exit(*worker));
        worker->release();
        const auto deadline = GetTickCount64() + 3000;
        V observed;
        for (;;) {
            observed = worker->observe(100);
            if (text(observed, "status") == "completed" || exited(observed) ||
                GetTickCount64() >= deadline)
                break;
        }
        if (text(observed, "status") != "completed")
            return failure(ExfatInspectionRead::Status::Unresolved,
                           exited(observed) ? "exfat_reader_validation_unresolved"
                                            : "exfat_reader_wait_expired",
                           finish_exit(*worker));
        const auto &publication = field(observed, "result");
        if (text(publication, "status") == "unavailable") {
            const auto &diagnostic = field(publication, "diagnostic");
            return failure(
                ExfatInspectionRead::Status::Refused, text(diagnostic, "code"),
                finish_exit(*worker),
                static_cast<std::uint32_t>(std::stoull(text(diagnostic, "platform_code"))));
        }
        const auto snapshot = worker->snapshot();
        if (!snapshot)
            return failure(ExfatInspectionRead::Status::Unresolved,
                           "exfat_reader_snapshot_unresolved", finish_exit(*worker));
        const auto retired = finish_exit(*worker);
        ExfatInspectionRead result;
        result.status = ExfatInspectionRead::Status::Captured;
        result.file = snapshot->result();
        result.context = snapshot->context();
        result.worker = retired;
        return result;
    } catch (const f::Error &error) {
        if (worker && !worker->never_launched())
            return failure(ExfatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker), error.platform_code);
        return failure(ExfatInspectionRead::Status::Refused, error.what(), V{},
                       error.platform_code);
    } catch (const worker_files::Failure &error) {
        if (worker && !worker->never_launched())
            return failure(ExfatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker), error.platform);
        return failure(ExfatInspectionRead::Status::Refused, error.what(), V{}, error.platform);
    } catch (const std::exception &error) {
        if (worker && !worker->never_launched())
            return failure(ExfatInspectionRead::Status::Unresolved, error.what(),
                           finish_exit(*worker));
        return failure(ExfatInspectionRead::Status::Refused, error.what());
    }
}
} // namespace disked
