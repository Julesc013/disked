#include "platform/windows/storage/fat_worker.h"
#include "platform/windows/memory_budget.h"
#include "platform/windows/worker_files.h"
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
        throw std::invalid_argument("fat_probe_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = get(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("fat_probe_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!disked::json::decimal_u64(s))
        throw std::invalid_argument("fat_probe_integer");
    return std::stoull(s);
}
V metadata(const std::string &input) {
    const auto path = f::path_for(input);
    auto parents = f::pin_parents(path);
    const auto generation = f::parent_generations(parents);
    f::Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw f::Error("fat_probe_open", GetLastError());
    f::ordinary(file.value, false);
    f::bind_path(file.value, path);
    f::check_parents(path, parents, generation);
    return f::metadata(file.value).value;
}
V exercise(const V &input) {
    disked::FatSnapshotInput r;
    r.capture_epoch = 1;
    r.path = text(input, "path");
    r.expected_source =
        input.find("expected_source") ? *input.find("expected_source") : metadata(r.path);
    r.volume_offset = integer(input, "offset");
    r.volume_bytes = integer(input, "length");
    if (const auto *value = input.find("capture_epoch"))
        r.capture_epoch = std::stoull(value->text);
    if (const auto *value = input.find("expected_source"))
        r.expected_source = *value;
    if (const auto *value = input.find("name_code_page")) {
        const auto page = std::stoull(value->text);
        if (page > 0xffffffffULL)
            throw std::invalid_argument("fat_probe_page");
        r.name_code_page = static_cast<std::uint32_t>(page);
    }
    if (const auto *value = input.find("copy")) {
        const auto copy = std::stoull(value->text);
        if (copy > 0xffffffffULL)
            throw std::invalid_argument("fat_probe_copy");
        r.fat_copy = static_cast<std::uint32_t>(copy);
    }
    r.allocation_scan = input.find("allocation_scan") && input.find("allocation_scan")->boolean;
    if (const auto *window = input.find("allocation_window")) {
        const auto first = integer(*window, "first_cluster"), count = integer(*window, "clusters");
        if (window->kind != V::Kind::object || window->fields.size() != 2 || first < 2 ||
            first > 268435446 || !count || count > 8192)
            throw std::invalid_argument("fat_allocation_window_input");
        r.allocation_window = {static_cast<std::uint32_t>(first),
                               static_cast<std::uint32_t>(count)};
    }
    r.auxiliary_checks = input.find("auxiliary_checks") && input.find("auxiliary_checks")->boolean;
    if (const auto *queries = input.find("queries"))
        for (const auto &q : queries->items) {
            disked::FatNameQuery query;
            const auto directory = integer(q, "directory");
            if (directory >= 128)
                throw std::invalid_argument("fat_probe_query");
            query.directory = static_cast<std::size_t>(directory);
            for (const auto &u : get(q, "units").items) {
                const auto unit = std::stoull(u.text);
                if (unit > 65535)
                    throw std::invalid_argument("fat_probe_query");
                query.component.push_back(static_cast<std::uint16_t>(unit));
            }
            r.queries.push_back(std::move(query));
        }
    auto value = disked::fat_snapshot_input_value(r);
    if (const auto *l = input.find("limits"))
        for (const auto &p : l->fields)
            value.fields.at("limits").put(p.first, p.second);
    if (const auto *l = input.find("namespace_limits"))
        for (const auto &p : l->fields)
            value.fields.at("namespace_limits").put(p.first, p.second);
    if (const auto *content = input.find("content")) {
        auto selected = *content;
        if (text(selected, "metadata_digest") == "auto") {
            const auto primed = disked::read_fat_snapshot_frame(r);
            const auto &observation = get(get(primed, "result"), "observation");
            selected.put("metadata_digest",
                         V::string(disked::fat_content_metadata_digest(observation)));
            if (text(selected, "expected_file_bytes") == "auto") {
                const auto node = static_cast<std::size_t>(integer(selected, "node_id"));
                selected.put("expected_file_bytes",
                             get(get(observation, "nodes").items.at(node), "file_bytes"));
            }
        }
        value.put("content", std::move(selected));
    }
    if (const auto *fixture = input.find("fixture"))
        value.put("fixture", *fixture);
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *fixture = input.find("fixture"))
            if (const auto *p = fixture->find(key))
                value.put(key, *p);
    auto header = V::object()
                      .put("capture_epoch", V::string(std::to_string(r.capture_epoch)))
                      .put("policy", V::object())
                      .put("provider_input", std::move(value));
    r = disked::fat_snapshot_input_from(header);
    const auto mode = input.find("mode") ? input.find("mode")->text : "worker";
    if (mode == "verify")
        return V::object().put("verified",
                               disked::verify_fat_snapshot_frame(get(input, "replace"), r));
    if (mode == "frame") {
        auto captured = disked::read_fat_snapshot_frame(r);
        const auto *replacement = input.find("replace");
        if (replacement)
            captured = *replacement;
        auto out = V::object()
                       .put("frame", captured)
                       .put("verified", disked::verify_fat_snapshot_frame(captured, r));
        return out;
    }
    if (mode == "quota") {
        // Owned hung readers retain four actual leases. No source read is started.
        auto held = r;
        held.fixture = V::object().put("worker_fault", V::string("hang"));
        std::vector<std::unique_ptr<n::FatWorker>> peers;
        auto out = V::object();
        for (unsigned i = 0; i < 4; ++i) {
            auto peer = n::FatWorker::prepare(held);
            peer->launch();
            if (!peer->wait_entered(1000))
                throw std::runtime_error("fat_probe_quota_not_entered");
            peer->release();
            peers.push_back(std::move(peer));
        }
        std::unique_ptr<n::FatWorker> fifth;
        try {
            fifth = n::FatWorker::prepare(r);
            fifth->launch();
            out.put("fifth_error", V{});
        } catch (const disked::worker_files::Failure &error) {
            out.put("fifth_error", V::string(error.what()));
            out.put("fifth_platform_code", V::string(std::to_string(error.platform)));
        }
        out.put("fifth_constructed", V::boolean_value(fifth != nullptr));
        out.put("fifth_never_launched", V::boolean_value(!fifth || fifth->never_launched()));
        if (fifth && !fifth->never_launched())
            out.put("fifth_retirement", fifth->retire());
        auto before = V::array();
        for (auto &peer : peers)
            before.items.push_back(peer->observe());
        out.put("peers_before_retirement", std::move(before));
        auto retirements = V::array();
        for (auto &peer : peers)
            retirements.items.push_back(peer->retire());
        out.put("peer_retirements", std::move(retirements));
        return out;
    }
    f::Handle writer;
    if (input.find("hold_writer")) {
        const auto path = f::path_for(r.path);
        writer = f::Handle(CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                                       OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (writer.value == INVALID_HANDLE_VALUE)
            throw f::Error("fat_probe_writer", GetLastError());
        f::ordinary(writer.value, false);
        f::bind_path(writer.value, path);
    }
    auto worker = n::FatWorker::prepare(r);
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
        out.put("before", worker->observe())
            .put("retirement", worker->retire())
            .put("has_snapshot", V::boolean_value(false));
        return out;
    }
    if (input.find("cancel"))
        worker->cancel();
    worker->release();
    if (mode == "held-content") {
        // Fault provider holds its ordinary source during the first payload read.
        // We require actual sharing violations; elapsed time alone is not proof.
        Sleep(1000);
        const auto path = f::path_for(r.path);
        auto access = [&](DWORD rights) {
            f::Handle attempted(CreateFileW(
                path.c_str(), rights, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            return attempted.value == INVALID_HANDLE_VALUE ? GetLastError() : 0;
        };
        out.put("write_error", V::string(std::to_string(access(GENERIC_WRITE))))
            .put("delete_error", V::string(std::to_string(access(DELETE))));
        out.put("before_cancel", worker->observe());
        worker->cancel();
        out.put("retirement", worker->retire(2000));
        out.put("has_snapshot", V::boolean_value(bool(worker->snapshot())));
        return out;
    }
    auto samples = V::array();
    if (mode == "publication") {
        const auto deadline = GetTickCount64() + 2000;
        V before;
        do {
            before = worker->observe(10);
            if (text(before, "status") == "completed" ||
                text(get(before, "worker"), "observation") == "exited")
                break;
        } while (GetTickCount64() < deadline);
        const auto snapshot = worker->snapshot();
        out.put("before", before).put("has_snapshot", V::boolean_value(bool(snapshot)));
        const auto bytes =
            snapshot ? disked::json::dump(snapshot->result(),
                                          disked::fat_snapshot_json_limits(r.content_enabled))
                     : std::string{};
        out.put("retirement", worker->retire());
        out.put("retained_unchanged",
                V::boolean_value(
                    snapshot && bytes == disked::json::dump(
                                             snapshot->result(),
                                             disked::fat_snapshot_json_limits(r.content_enabled))));
        return out;
    }
    if (mode == "pending") {
        const auto before = worker->observe(50);
        out.put("before", before)
            .put("has_snapshot", V::boolean_value(bool(worker->snapshot())))
            .put("retirement", worker->retire());
        return out;
    }
    const auto end = GetTickCount64() + 3000;
    V last;
    do {
        last = worker->observe(10);
        if (text(get(last, "worker"), "observation") == "exited")
            break;
    } while (GetTickCount64() < end);
    samples.items.push_back(last);
    if (text(get(last, "worker"), "observation") != "exited")
        samples.items.push_back(worker->retire());
    const auto snapshot = worker->snapshot();
    out.put("samples", samples).put("has_snapshot", V::boolean_value(bool(snapshot)));
    if (snapshot) {
        const auto before = disked::json::dump(snapshot->result(),
                                               disked::fat_snapshot_json_limits(r.content_enabled));
        out.put("result", snapshot->result()).put("context", snapshot->context());
        out.put("retirement", worker->retire());
        if (before != disked::json::dump(snapshot->result(),
                                         disked::fat_snapshot_json_limits(r.content_enabled)))
            throw std::runtime_error("fat_probe_retained_changed");
        out.put("retained_unchanged", V::boolean_value(true));
    }
    return out;
}
} // namespace
int wmain(int argc, wchar_t **argv) {
    if (argc > 1 && std::wstring(argv[1]) == L"__disked_fat_reader_worker")
        return n::fat_worker_role(argc, argv);
    if (argc != 1 || _setmode(_fileno(stdin), _O_BINARY) < 0 ||
        _setmode(_fileno(stdout), _O_BINARY) < 0)
        return 2;
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        auto limits = disked::fat_snapshot_json_limits(true);
        limits.bytes = 8 * 1024 * 1024;
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
