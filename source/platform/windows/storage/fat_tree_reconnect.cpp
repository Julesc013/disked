#include "fat_tree_reconnect.h"
#include "runtime/acquisition/fat_tree_operation.h"
#include "platform/windows/worker_files.h"
#include <cstring>

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
    wchar_t path[32768];
    DWORD size = 32768;
    if (!QueryFullProcessImageNameW(process.value, 0, path, &size))
        return result;
    const auto expected = f::path_for(text(code, "path"));
    if (CompareStringOrdinal(expected.c_str(), -1, path, static_cast<int>(size), TRUE) !=
        CSTR_EQUAL)
        return result.put("observation", V::string("code_mismatch"));
    f::Handle image(CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
                                nullptr));
    if (image.value == INVALID_HANDLE_VALUE)
        return result;
    f::ordinary(image.value, false);
    const auto metadata = f::metadata(image.value);
    if (json::dump(metadata.value) != json::dump(field(code, "file")) || metadata.size > 8388608)
        return result.put("observation", V::string("code_mismatch"));
    const auto raw = w::read_file(image.value, 8388608);
    if ("sha256:" + w::hash(raw) != text(code, "sha256"))
        return result.put("observation", V::string("code_mismatch"));
    const auto wait = WaitForSingleObject(process.value, 0);
    DWORD exit = 0;
    if (!GetExitCodeProcess(process.value, &exit))
        return result;
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
V observe_fat_tree_operation(const std::string &id, const std::string &path, bool cancel) {
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
} // namespace nt_inventory
} // namespace disked
