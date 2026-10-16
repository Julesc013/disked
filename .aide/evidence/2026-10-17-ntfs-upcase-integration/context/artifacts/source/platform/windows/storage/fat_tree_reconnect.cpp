#include "fat_tree_reconnect.h"
#include "runtime/acquisition/fat_tree_operation.h"
#include "platform/windows/worker_files.h"
#include <cstring>
#include <memory>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace w = worker_files;
namespace f = local_file;
const wchar_t *const names[] = {L"recursive-request.json", L"recursive-cancel",
                                L"recursive-state.ndjson"};
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        throw std::runtime_error("fat_tree_reconnect_shape");
    return *p;
}
std::string text(const V &v, const char *name) {
    const auto &p = field(v, name);
    if (p.kind != V::Kind::string)
        throw std::runtime_error("fat_tree_reconnect_shape");
    return p.text;
}
void same(const V &a, const V &b, const char *code) {
    if (json::dump(a, fat_tree_operation::header_limits()) !=
        json::dump(b, fat_tree_operation::header_limits()))
        throw std::runtime_error(code);
}
V pid_facts(const V &identity, const V &code) {
    const auto pid = static_cast<DWORD>(std::stoull(text(identity, "pid")));
    w::Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, pid));
    auto result = V::object()
                      .put("pid", field(identity, "pid"))
                      .put("created", field(identity, "created"))
                      .put("observation", V::string("unavailable"))
                      .put("exit_code", V{});
    if (!process.valid()) {
        if (GetLastError() == ERROR_INVALID_PARAMETER)
            result.put("observation", V::string("not_present"));
        return result;
    }
    if (w::process_created(process.value) != text(identity, "created"))
        return result.put("observation", V::string("reused_identity"));
    const auto finish = [&](V value) {
        DWORD exit = 0;
        if (WaitForSingleObject(process.value, 25) == WAIT_OBJECT_0 &&
            GetExitCodeProcess(process.value, &exit))
            return value.put("exit_code", V::string(std::to_string(exit)))
                .put("observation", V::string("exited"));
        return value;
    };
    // An exited process can retain a queryable birth/exit handle after Windows
    // stops exposing its image path. This establishes exit, not current code
    // applicability; only the running branch can authorize cancellation.
    if (WaitForSingleObject(process.value, 0) == WAIT_OBJECT_0) {
        DWORD exit = 0;
        if (!GetExitCodeProcess(process.value, &exit))
            return result;
        return result.put("exit_code", V::string(std::to_string(exit)))
            .put("observation", V::string("exited"));
    }
    wchar_t path[32768];
    DWORD size = 32768;
    if (!QueryFullProcessImageNameW(process.value, 0, path, &size)) {
        DWORD exit = 0;
        if (WaitForSingleObject(process.value, 0) == WAIT_OBJECT_0 &&
            GetExitCodeProcess(process.value, &exit))
            return result.put("exit_code", V::string(std::to_string(exit)))
                .put("observation", V::string("exited"));
        return finish(result);
    }
    const auto expected = f::path_for(text(code, "path"));
    if (CompareStringOrdinal(expected.c_str(), -1, path, static_cast<int>(size), TRUE) !=
        CSTR_EQUAL)
        return finish(result.put("observation", V::string("code_mismatch")));
    f::Handle image(CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
                                nullptr));
    if (image.value == INVALID_HANDLE_VALUE)
        return finish(result);
    f::ordinary(image.value, false);
    const auto metadata = f::metadata(image.value);
    if (json::dump(metadata.value) != json::dump(field(code, "file")) || metadata.size > 8388608)
        return finish(result.put("observation", V::string("code_mismatch")));
    const auto raw = w::read_file(image.value, 8388608);
    if ("sha256:" + w::hash(raw) != text(code, "sha256"))
        return finish(result.put("observation", V::string("code_mismatch")));
    const auto wait = WaitForSingleObject(process.value, 0);
    DWORD exit = 0;
    if (!GetExitCodeProcess(process.value, &exit))
        return finish(result);
    result.put("exit_code", V::string(std::to_string(exit)));
    result.put("observation", V::string(wait == WAIT_OBJECT_0  ? "exited"
                                        : wait == WAIT_TIMEOUT ? "running"
                                                               : "unavailable"));
    return result;
}
bool live(const V &v) {
    return text(v, "observation") == "running";
}
} // namespace
V observe_fat_tree_operation(const std::string &id, const std::string &path, bool cancel,
                             fat_tree_operation::History *retained) {
    auto out =
        V::object()
            .put("schema", V::string("org.disked.fat-tree-reconnect-observation-prototype/1"))
            .put("operation_id", V::string(id))
            .put("status", V::string("unknown"))
            .put("cancellation_request", V::string(cancel ? "not_admitted" : "not_requested"))
            .put("history", V{})
            .put("controller", V{})
            .put("writer", V{})
            .put("diagnostic", V{})
            .put("claims", V::object()
                               .put("authenticity", V::string("not_established"))
                               .put("source_access", V::boolean_value(false))
                               .put("destination_access", V::boolean_value(false))
                               .put("mutation_authority", V::boolean_value(false))
                               .put("replay_authority", V::boolean_value(false)));
    try {
        if (id.size() != 40 || id.compare(0, 8, "tree-op:") ||
            id.find_first_not_of("0123456789abcdef", 8) != id.npos)
            throw std::runtime_error("fat_tree_reconnect_identity");
        w::Directory directory(path);
        wchar_t fs[32]{};
        if (!GetVolumeInformationByHandleW(directory.pinned.back().value, nullptr, 0, nullptr,
                                           nullptr, nullptr, fs, 32) ||
            std::wcscmp(fs, L"NTFS"))
            throw std::runtime_error("fat_tree_reconnect_store_profile");
        w::Handle files[3];
        for (std::size_t i = 0; i < 3; ++i) {
            files[i] =
                directory.open(names[i], GENERIC_READ | (cancel && i == 1 ? GENERIC_WRITE : 0),
                               FILE_SHARE_READ | FILE_SHARE_WRITE, OPEN_EXISTING);
            if (!files[i].valid())
                throw std::runtime_error("fat_tree_reconnect_files_missing");
        }
        const auto raw = w::read_file(files[0].value, 524288);
        const auto header = json::parse(raw, fat_tree_operation::header_limits());
        if (json::dump(header, fat_tree_operation::header_limits()) != raw)
            throw std::runtime_error("fat_tree_reconnect_header_canonical");
        fat_tree_operation::validate_header(header);
        if (text(header, "operation_id") != id)
            throw std::runtime_error("fat_tree_reconnect_operation");
        w::Security security;
        if (text(header, "controller_host") != security.host_id)
            throw std::runtime_error("fat_tree_reconnect_host");
        const auto &store = field(field(field(header, "review"), "operation_store"), "observed");
        same(field(store, "file"), f::generation(directory.pinned.back().value, true),
             "fat_tree_reconnect_store_changed");
        same(field(store, "parents"), directory.generations, "fat_tree_reconnect_store_changed");
        if (text(store, "path") != w::narrow(directory.path))
            throw std::runtime_error("fat_tree_reconnect_store_changed");
        auto check = [&] {
            directory.check();
            for (std::size_t i = 0; i < 3; ++i)
                same(f::generation(files[i].value, false), field(header, "files").items[i],
                     "fat_tree_reconnect_child_changed");
            if (w::read_file(files[0].value, 524288) != raw)
                throw std::runtime_error("fat_tree_reconnect_header_changed");
        };
        check();
        const auto history_raw = w::read_file(files[2].value, 1048576);
        if (raw.size() + 1 + history_raw.size() > 1048576)
            throw std::runtime_error("fat_tree_reconnect_budget");
        const auto history = fat_tree_operation::read_history(header, history_raw);
        out.put("history", history.view());
        const auto flag = w::read_file(files[1].value, 1);
        if (flag != "0" && flag != "1")
            throw std::runtime_error("fat_tree_reconnect_cancel_changed");
        const auto &code =
            field(field(field(field(header, "review"), "backend"), "resources"), "executable");
        const auto &observed_code = field(code, "observed");
        const auto *controller = header.find("controller");
        const auto writer = header.find("writer") ? *header.find("writer") : history.writer;
        V controller_facts, writer_facts;
        if (controller)
            controller_facts = pid_facts(*controller, observed_code);
        if (writer.kind != V::Kind::null)
            writer_facts = pid_facts(writer, observed_code);
        out.put("controller", controller_facts).put("writer", writer_facts);
        check();
        if (retained)
            *retained = history;
        for (const auto *facts : {&controller_facts, &writer_facts})
            if (facts->kind != V::Kind::null) {
                const auto status = text(*facts, "observation");
                if (status == "reused_identity" || status == "code_mismatch" ||
                    status == "unavailable")
                    throw std::runtime_error("fat_tree_reconnect_process_unverified");
            }
        out.put("status", V::string(history.complete ? "observed" : "unknown"));
        if (cancel) {
            if (!history.complete)
                throw std::runtime_error("fat_tree_reconnect_torn_history");
            if (history.exited)
                out.put("cancellation_request", V::string("too_late_recorded"));
            else if (!controller || !live(controller_facts) || writer_facts.kind == V::Kind::null ||
                     !live(writer_facts) || history.uncertain)
                throw std::runtime_error("fat_tree_reconnect_cancel_identity_unverified");
            else {
                check();
                LARGE_INTEGER zero{};
                if (!SetFilePointerEx(files[1].value, zero, nullptr, FILE_BEGIN))
                    w::fail("fat_tree_reconnect_seek");
                w::write_file(files[1].value, "1", "fat_tree_reconnect_cancel");
                check();
                out.put("cancellation_request", V::string("requested"));
            }
        }
        return out;
    } catch (const std::exception &e) {
        out.put("status", V::string("unknown")).put("diagnostic", V::string(e.what()));
        return out;
    }
}
V watch_fat_tree_operation(const std::string &id, const std::string &store, const V &options,
                           const fat_tree_operation::EventSink &sink, const std::string &request) {
    auto result = V::object()
                      .put("schema", V::string("org.disked.fat-tree-operation-watch-prototype/1"))
                      .put("operation_id", V::string(id))
                      .put("status", V::string("unknown"))
                      .put("cursor", V{})
                      .put("events", V::array())
                      .put("observation", V{})
                      .put("diagnostic", V{})
                      .put("polls", V::string("0"));
    std::unique_ptr<fat_tree_operation::Watch> cursor;
    try {
        fat_tree_operation::validate_watch_options(options);
        w::Security security;
        cursor.reset(
            new fat_tree_operation::Watch(id, request, security.identity("watch:"), options));
        const auto *follow = options.find("follow_ms");
        const auto budget = follow ? std::stoull(follow->text) : 0;
        const auto start = GetTickCount64();
        for (std::size_t poll = 0; poll < 81; ++poll) {
            fat_tree_operation::History history;
            const auto observation = observe_fat_tree_operation(id, store, false, &history);
            result.put("observation", observation)
                .put("polls", V::string(std::to_string(poll + 1)));
            if (history.header.kind == V::Kind::null || !history.complete) {
                const auto &diagnostic = field(observation, "diagnostic");
                result.put("diagnostic",
                           diagnostic.kind == V::Kind::null
                               ? V::string(history.header.kind != V::Kind::null && !history.complete
                                               ? "fat_tree_watch_torn_history"
                                               : "fat_tree_watch_observation_unresolved")
                               : diagnostic);
                break;
            }
            const bool admitted = cursor->project(history, [&](const V &event) {
                if (sink)
                    return sink(event);
                result.fields["events"].items.push_back(event);
                return true;
            });
            result.put("cursor", cursor->cursor());
            if (!admitted) {
                result.put("status", V::string("observer_closed"))
                    .put("diagnostic", V::string("fat_tree_watch_observer_closed"));
                break;
            }
            if (history.exited) {
                result.put("status", V::string("recorded_terminal"))
                    .put("diagnostic", field(observation, "diagnostic"));
                break;
            }
            const auto &controller = field(observation, "controller"),
                       &writer = field(observation, "writer");
            if (controller.kind != V::Kind::object || writer.kind != V::Kind::object)
                throw std::runtime_error("fat_tree_watch_owner_unresolved");
            const auto worker_fact = text(writer, "observation");
            const auto controller_fact = text(controller, "observation");
            if (worker_fact == "reused_identity" || worker_fact == "code_mismatch" ||
                controller_fact == "reused_identity" || controller_fact == "code_mismatch")
                throw std::runtime_error("fat_tree_watch_owner_unresolved");
            const bool active = live(controller) && live(writer);
            result.put("status", V::string(active ? "following_boundary" : "unknown"))
                .put("diagnostic",
                     active ? V{} : V::string("fat_tree_watch_retained_exit_pending"));
            const auto elapsed = GetTickCount64() - start;
            if (elapsed >= budget)
                break;
            const auto remaining = budget - elapsed;
            Sleep(static_cast<DWORD>(remaining < 25 ? remaining : 25));
        }
    } catch (const std::exception &e) {
        result.put("status", V::string("unknown")).put("diagnostic", V::string(e.what()));
    }
    if (cursor)
        result.put("cursor", cursor->cursor());
    return result;
}
V wait_fat_tree_operation(const std::string &id, const std::string &store, std::uint32_t follow_ms,
                          const fat_tree_operation::EventSink &sink) {
    return watch_fat_tree_operation(id, store,
                                    V::object()
                                        .put("follow_ms", V::string(std::to_string(follow_ms)))
                                        .put("snapshot", V::boolean_value(true)),
                                    sink);
}
} // namespace nt_inventory
} // namespace disked
