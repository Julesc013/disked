#include "platform/windows/storage/fat_tree_worker.h"
#include "providers/image/fat_tree_file.h"
#include "providers/image/local_file.h"
#include "platform/windows/memory_budget.h"
#include <fcntl.h>
#include <io.h>
#include <iostream>
#include <memory>

namespace {
using V = disked::json::Value;
namespace f = disked::local_file;
namespace n = disked::nt_inventory;
const V &get(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("tree_probe_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = get(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("tree_probe_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!disked::json::decimal_u64(s))
        throw std::invalid_argument("tree_probe_integer");
    return std::stoull(s);
}
V metadata(const std::string &input) {
    const auto path = f::path_for(input);
    auto parents = f::pin_parents(path);
    const auto generations = f::parent_generations(parents);
    f::Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw f::Error("tree_probe_open", GetLastError());
    f::ordinary(file.value, false);
    f::bind_path(file.value, path);
    f::check_parents(path, parents, generations);
    return f::metadata(file.value).value;
}
void emit(V v) {
    std::cout << disked::json::dump(v, disked::fat_tree_json_limits()) << '\n' << std::flush;
}
disked::FatTreeInput input(const V &v) {
    disked::FatTreeInput r;
    r.path = text(v, "path");
    r.expected_source = v.find("expected_source") ? *v.find("expected_source") : metadata(r.path);
    r.capture_epoch = v.find("capture_epoch") ? integer(v, "capture_epoch") : 1;
    r.volume_offset = integer(v, "offset");
    r.volume_bytes = integer(v, "length");
    if (v.find("copy")) {
        const auto copy = integer(v, "copy");
        if (copy > 0xffffffffULL)
            throw std::invalid_argument("tree_probe_copy");
        r.fat_copy = static_cast<std::uint32_t>(copy);
    }
    auto value = disked::fat_tree_input_value(r);
    for (const auto key : {"page", "resources"})
        if (const auto *p = v.find(key))
            for (const auto &field : p->fields)
                value.fields.at(key).put(field.first, field.second);
    if (const auto *p = v.find("fixture"))
        value.put("fixture", *p);
    return disked::fat_tree_input_from(value);
}
void share_test(const std::string &input) {
    const auto path = f::path_for(input);
    f::Handle writer(CreateFileW(path.c_str(), GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                                 OPEN_EXISTING, 0, nullptr));
    const auto error = writer.value == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    emit(V::object()
             .put("kind", V::string("sharing"))
             .put("write_open", V::boolean_value(writer.value != INVALID_HANDLE_VALUE))
             .put("platform_code", V::string(std::to_string(error))));
}
void exercise(const V &request) {
    const auto r = input(request);
    const auto mode = request.find("mode") ? text(request, "mode") : "worker";
    if (mode == "metadata") {
        emit(V::object().put("kind", V::string("metadata")).put("source", r.expected_source));
        return;
    }
    if (mode == "replay") {
        disked::FatTreeReplay replay(r);
        const auto &frames = get(request, "frames");
        for (const auto &frame : frames.items) {
            auto page = replay.accept(frame);
            emit(V::object().put("kind", V::string("replayed")).put("page", std::move(page)));
        }
        return;
    }
    if (mode == "file") {
        disked::FatTreeFile file(r);
        disked::FatTreeReplay replay(r);
        std::uint64_t count = 0;
        while (!file.finished()) {
            const bool cancel =
                request.find("cancel_after") && count >= integer(request, "cancel_after");
            auto frame = file.next([cancel] { return cancel; });
            replay.accept(frame);
            emit(V::object().put("kind", V::string("page")).put("frame", std::move(frame)));
            if (count++ == 0 && request.find("sharing"))
                share_test(r.path);
        }
        emit(V::object()
                 .put("kind", V::string("finished"))
                 .put("pages", V::string(std::to_string(count))));
        return;
    }
    auto worker = n::FatTreeWorker::prepare(r);
    std::string startup_error;
    try {
        worker->launch();
        worker->wait_entered(1000);
        worker->release();
    } catch (const std::exception &e) {
        startup_error = e.what();
    }
    std::shared_ptr<const disked::FatTreePage> first;
    std::string original;
    const auto deadline = GetTickCount64() + 15000;
    std::uint64_t count = 0;
    bool cancel_sent = false;
    V last;
    if (startup_error.empty())
        for (;;) {
            if (auto page = worker->next_page()) {
                if (!first) {
                    first = page;
                    original = disked::json::dump(first->frame(), disked::fat_tree_json_limits());
                }
                emit(V::object()
                         .put("kind", V::string("page"))
                         .put("frame", page->frame())
                         .put("context", page->context()));
                ++count;
                if (count == 1 && request.find("sharing"))
                    share_test(r.path);
            }
            if (!cancel_sent && request.find("cancel_after") &&
                count >= integer(request, "cancel_after")) {
                worker->cancel();
                cancel_sent = true;
            }
            last = worker->observe(1);
            if (text(get(last, "worker"), "observation") == "exited" &&
                text(last, "status") != "accepted_running")
                break;
            if (GetTickCount64() >= deadline)
                break;
        }
    const auto retired = worker->retire(2000);
    const bool retained =
        !first || disked::json::dump(first->frame(), disked::fat_tree_json_limits()) == original;
    emit(V::object()
             .put("kind", V::string("finished"))
             .put("pages", V::string(std::to_string(count)))
             .put("retained_unchanged", V::boolean_value(retained))
             .put("startup_error", startup_error.empty() ? V{} : V::string(startup_error))
             .put("never_launched", V::boolean_value(worker->never_launched()))
             .put("last", std::move(last))
             .put("retirement", retired));
}
} // namespace
int wmain(int argc, wchar_t **argv) {
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_fat_tree_reader_worker") == 0)
        return n::fat_tree_worker_role(argc, argv);
    try {
        if (argc != 1)
            return 2;
        _setmode(_fileno(stdin), _O_BINARY);
        _setmode(_fileno(stdout), _O_BINARY);
        auto limits = disked::fat_tree_json_limits();
        limits.bytes = 16U * 1024U * 1024U;
        limits.values = 524288;
        std::string line;
        while (std::getline(std::cin, line))
            try {
                exercise(disked::json::parse(line, limits));
            } catch (const f::Error &e) {
                emit(V::object()
                         .put("kind", V::string("error"))
                         .put("code", V::string(e.what()))
                         .put("platform_code", V::string(std::to_string(e.platform_code))));
            } catch (const std::exception &e) {
                emit(V::object().put("kind", V::string("error")).put("code", V::string(e.what())));
            }
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
