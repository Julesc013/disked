#include "platform/windows/storage/exfat_worker.h"
#include "platform/windows/memory_budget.h"
#include "providers/image/local_file.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <iostream>

namespace {
using V = disked::json::Value;
namespace f = disked::local_file;
namespace n = disked::nt_inventory;
const V &get(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("exfat_probe_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = get(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("exfat_probe_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!disked::json::decimal_u64(s))
        throw std::invalid_argument("exfat_probe_integer");
    return std::stoull(s);
}
V metadata(const std::string &input) {
    const auto path = f::path_for(input);
    auto parents = f::pin_parents(path);
    const auto generation = f::parent_generations(parents);
    f::Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw f::Error("exfat_probe_open", GetLastError());
    f::ordinary(file.value, false);
    f::bind_path(file.value, path);
    f::check_parents(path, parents, generation);
    return f::metadata(file.value).value;
}
V exercise(const V &input) {
    disked::ExfatSnapshotInput request;
    request.capture_epoch = input.find("capture_epoch") ? integer(input, "capture_epoch") : 1;
    request.path = text(input, "path");
    request.expected_source =
        input.find("expected_source") ? get(input, "expected_source") : metadata(request.path);
    request.volume_offset = integer(input, "offset");
    request.volume_bytes = integer(input, "length");
    const auto &compressed = get(input, "compressed");
    if (compressed.kind != V::Kind::boolean)
        throw std::invalid_argument("exfat_probe_shape");
    request.compressed_upcase = compressed.boolean;
    auto value = disked::exfat_snapshot_input_value(request);
    if (const auto *limits = input.find("limits"))
        for (const auto &p : limits->fields)
            value.fields.at("limits").put(p.first, p.second);
    if (const auto *fixture = input.find("fixture"))
        value.put("fixture", *fixture);
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *fixture = input.find("fixture"))
            if (const auto *p = fixture->find(key))
                value.put(key, *p);
    auto header = V::object()
                      .put("capture_epoch", V::string(std::to_string(request.capture_epoch)))
                      .put("policy", V::object())
                      .put("provider_input", std::move(value));
    request = disked::exfat_snapshot_input_from(header);
    const auto mode = input.find("mode") ? text(input, "mode") : "worker";
    if (mode == "verify")
        return V::object().put("verified",
                               disked::verify_exfat_snapshot_frame(get(input, "replace"), request));
    if (mode == "frame") {
        auto captured = disked::read_exfat_snapshot_frame(request);
        return V::object()
            .put("frame", captured)
            .put("verified", disked::verify_exfat_snapshot_frame(captured, request));
    }
    auto worker = n::ExfatWorker::prepare(request);
    if (mode == "construction")
        return V::object().put("never_launched", V::boolean_value(worker->never_launched()));
    auto out = V::object();
    try {
        worker->launch();
    } catch (const std::exception &error) {
        out.put("startup_error", V::string(error.what()))
            .put("never_launched", V::boolean_value(worker->never_launched()))
            .put("before", worker->observe());
        if (!worker->never_launched())
            out.put("retirement", worker->retire());
        return out;
    }
    if (!worker->wait_entered(1000)) {
        const auto before = worker->observe();
        const auto retirement = worker->retire();
        return out.put("before", before)
            .put("has_snapshot", V::boolean_value(false))
            .put("retirement", retirement);
    }
    if (input.find("cancel"))
        worker->cancel();
    worker->release();
    if (mode == "pending") {
        auto before = worker->observe(50);
        const bool has_snapshot = bool(worker->snapshot());
        const auto retirement = worker->retire();
        return out.put("before", std::move(before))
            .put("has_snapshot", V::boolean_value(has_snapshot))
            .put("retirement", retirement);
    }
    if (mode == "retire-zero") {
        const auto before = worker->observe(50);
        const auto zero = worker->retire(0);
        return out.put("before", before)
            .put("zero_retirement", zero)
            .put("retirement", worker->retire());
    }
    auto samples = V::array();
    const auto deadline = GetTickCount64() + 5000;
    V last;
    do {
        last = worker->observe(10);
        samples.items.push_back(last);
        if (text(get(last, "worker"), "observation") == "exited" ||
            text(last, "status") == "completed")
            break;
    } while (GetTickCount64() < deadline);
    const auto snapshot = worker->snapshot(true);
    const auto retained =
        snapshot ? disked::json::dump(snapshot->result(), disked::exfat_snapshot_json_limits())
                 : std::string{};
    out.put("samples", std::move(samples))
        .put("before", last)
        .put("has_snapshot", V::boolean_value(bool(snapshot)));
    if (snapshot)
        out.put("snapshot", snapshot->result())
            .put("context", snapshot->context())
            .put("frame", snapshot->frame());
    out.put("retirement", worker->retire());
    out.put("retained_unchanged",
            V::boolean_value(snapshot &&
                             retained == disked::json::dump(snapshot->result(),
                                                            disked::exfat_snapshot_json_limits())));
    return out;
}
} // namespace
int wmain(int argc, wchar_t **argv) {
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_exfat_reader_worker") == 0)
        return n::exfat_worker_role(argc, argv);
    if (argc != 1 || _setmode(_fileno(stdin), _O_BINARY) < 0 ||
        _setmode(_fileno(stdout), _O_BINARY) < 0)
        return 2;
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        auto limits = disked::exfat_snapshot_json_limits();
        limits.bytes = 16777216;
        limits.string_bytes = 12582912;
        std::string line;
        while (std::getline(std::cin, line)) {
            V out;
            try {
                out = exercise(disked::json::parse(line, limits));
            } catch (const std::exception &error) {
                out = V::object().put("error", V::string(error.what()));
            }
            std::cout << disked::json::dump(out, limits) << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
