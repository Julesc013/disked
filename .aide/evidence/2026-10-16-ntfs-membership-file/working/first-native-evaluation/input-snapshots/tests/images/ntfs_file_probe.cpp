#include "providers/image/ntfs_file.h"
#include "providers/image/local_file.h"
#include <cstdio>
#include <iostream>
#include <stdexcept>

using V = disked::json::Value;
static void need(bool value) {
    if (!value)
        throw std::runtime_error("ntfs_file_probe_input");
}
static const V &field(const V &v, const char *key) {
    const auto p = v.find(key);
    need(p != nullptr);
    return *p;
}
static std::uint64_t integer(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static std::string hex(const std::vector<unsigned char> &v) {
    const char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(v.size() * 2);
    for (auto byte : v) {
        result += digits[byte >> 4];
        result += digits[byte & 15];
    }
    return result;
}
static V access(const std::string &input, bool rename) {
    const auto path = disked::local_file::path_for(input);
    auto out = V::array();
    for (const auto rights : {static_cast<DWORD>(GENERIC_WRITE), static_cast<DWORD>(DELETE)}) {
        const auto handle = CreateFileW(
            path.c_str(), rights, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
            OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        const auto error = handle == INVALID_HANDLE_VALUE ? GetLastError() : 0;
        if (handle != INVALID_HANDLE_VALUE)
            CloseHandle(handle);
        out.items.push_back(V::object()
                                .put("opened", V::boolean_value(handle != INVALID_HANDLE_VALUE))
                                .put("error", exact(error)));
    }
    if (rename) {
        const auto target = path + L".rename-probe";
        const bool moved = MoveFileExW(path.c_str(), target.c_str(), 0) != FALSE;
        const auto error = moved ? 0 : GetLastError();
        if (moved)
            need(MoveFileExW(target.c_str(), path.c_str(), 0) != FALSE);
        out.items.push_back(
            V::object().put("moved", V::boolean_value(moved)).put("error", exact(error)));
    }
    return out;
}
static V observe(const V &input) {
    disked::NtfsFileRequest request;
    request.path = field(input, "path").text;
    request.volume_offset = integer(field(input, "offset"));
    request.volume_bytes = integer(field(input, "length"));
    const auto original_path = request.path;
    const auto *selected = input.find("profile");
    const auto profile = selected ? selected->text : "auto";
    request.profile = profile == "auto"  ? disked::NtfsFileProfile::Automatic
                      : profile == "3.0" ? disked::NtfsFileProfile::Version30
                      : profile == "3.1" ? disked::NtfsFileProfile::Version31
                                         : static_cast<disked::NtfsFileProfile>(99);
    if (const auto *expected = input.find("expected_source"))
        request.expected_source = *expected;
    if (const auto *limits = input.find("limits")) {
#define LOAD(name)                                                                                 \
    if (const auto *value = limits->find(#name))                                                   \
    request.limits.name = static_cast<std::size_t>(integer(*value))
        LOAD(read_requests);
        LOAD(read_bytes);
        LOAD(retained_bytes);
        LOAD(attributes);
        LOAD(runs);
        LOAD(output_bytes);
#undef LOAD
    }
    const auto directory_input = input.find("directory");
    disked::NtfsDirectoryFileRequest directory;
    directory.file = request;
    if (directory_input) {
        need(directory_input->kind == V::Kind::object);
        if (const auto value = directory_input->find("reference"))
            directory.reference = integer(*value);
        if (const auto limits = directory_input->find("limits")) {
#define LOAD(name)                                                                                 \
    if (const auto *value = limits->find(#name))                                                   \
    directory.limits.name = static_cast<std::size_t>(integer(*value))
            LOAD(entries);
            LOAD(blocks);
            LOAD(bitmap_bytes);
#undef LOAD
        }
    }
    const auto membership_input = input.find("membership");
    disked::NtfsMembershipFileRequest membership;
    membership.directory = directory;
    if (membership_input) {
        need(membership_input->kind == V::Kind::object);
        if (const auto value = membership_input->find("targets")) {
            const auto targets = integer(*value);
            // Preserve rejection across pointer widths; never truncate a large wire value.
            membership.targets = targets > 256 ? 257 : static_cast<std::size_t>(targets);
        }
    }
    std::function<bool()> stop;
    V held_access = V::array();
    std::size_t stop_calls = 0, read_calls = 0;
#ifdef DISKED_NTFS_FILE_TESTING
    const auto *mode_value = input.find("mode");
    const auto mode = mode_value ? mode_value->text : std::string();
    const auto *at = input.find("call");
    const auto call = at ? integer(*at) : 1;
    disked::NtfsFileTestControl control;
    if (mode == "cancel" || mode == "cancel_once" || mode == "cancel_throw")
        stop = [&] {
            ++stop_calls;
            if (mode == "cancel_throw" && stop_calls >= call)
                throw std::runtime_error("test_cancel_callback");
            return mode == "cancel_once" ? stop_calls == call : stop_calls >= call;
        };
    control.before_binding = [&](std::size_t n) {
        if (n != call)
            return;
        if (mode == "binding")
            throw disked::local_file::Error("test_binding_refusal", ERROR_INVALID_DATA);
        if (mode == "binding_throw")
            throw std::runtime_error("test_binding_callback");
        if (mode == "mutate_request") {
            request.path = "invalid-changed-path";
            request.volume_bytes = 512;
            request.profile = static_cast<disked::NtfsFileProfile>(99);
            request.expected_source = V{};
            request.limits.read_requests = 1;
            directory.file = request;
            directory.reference = 1;
            directory.limits.entries = 0;
            membership.directory = directory;
            membership.targets = 0;
            stop = {};
            control = {};
        }
    };
    control.after_read = [&](std::size_t n, disked::NtfsFileRegion &region) {
        ++read_calls;
        if (n != call)
            return;
        if (mode == "short" && !region.bytes.empty())
            region.bytes.pop_back();
        if (mode == "error") {
            region.error = ERROR_READ_FAULT;
            region.bytes.clear();
        }
        if (mode == "partial_error") {
            region.error = ERROR_READ_FAULT;
            region.bytes.resize(region.bytes.size() / 2);
        }
        if (mode == "changed" && !region.bytes.empty())
            region.bytes[0] ^= 1;
        if (mode == "throw")
            throw disked::local_file::Error("test_read_refusal", ERROR_INVALID_DATA);
        if (mode == "read_throw")
            throw std::runtime_error("test_read_callback");
        if (mode == "held_access") {
            held_access.items.push_back(access(original_path, true));
            if (const auto *parents = input.find("access_parents"))
                for (const auto &parent : parents->items)
                    held_access.items.push_back(access(parent.text, true));
        }
    };
    control.after_metadata = [&](V &metadata) {
        if (mode == "metadata")
            metadata.put("bytes", V::string("1"));
        if (mode == "metadata_throw")
            throw std::runtime_error("test_metadata_callback");
    };
    control.before_replay = [&](std::size_t n, disked::NtfsFileRegion &region) {
        if (n != call)
            return;
        if (mode == "replay_bytes" && !region.bytes.empty())
            region.bytes[0] ^= 1;
        if (mode == "replay_offset")
            ++region.offset;
        if (mode == "replay_provenance")
            region.read_attempted = !region.read_attempted;
        if (mode == "replay_throw")
            throw std::runtime_error("test_replay_callback");
    };
#endif
    auto out = V::object();
#ifdef DISKED_NTFS_FILE_TESTING
    out.put("fault_controls_available", V::boolean_value(true));
#else
    out.put("fault_controls_available", V::boolean_value(false));
#endif
    try {
#ifdef DISKED_NTFS_FILE_TESTING
        auto read = membership_input
                        ? disked::capture_ntfs_membership_file_testing(membership, stop, control)
                    : directory_input
                        ? disked::capture_ntfs_directory_file_testing(directory, stop, control)
                        : disked::capture_ntfs_file_testing(request, stop, control);
#else
        auto read = membership_input  ? disked::capture_ntfs_membership_file_owned(membership, stop)
                    : directory_input ? disked::capture_ntfs_directory_file_owned(directory, stop)
                                      : disked::capture_ntfs_file_owned(request, stop);
#endif
        auto regions = V::array();
        for (const auto &region : read.regions)
            regions.items.push_back(
                V::object()
                    .put("offset", exact(region.offset))
                    .put("requested", exact(region.requested))
                    .put("seek_attempted", V::boolean_value(region.seek_attempted))
                    .put("read_attempted", V::boolean_value(region.read_attempted))
                    .put("error", exact(region.error))
                    .put("refusal", V::string(region.refusal))
                    .put("bytes", V::string(hex(region.bytes))));
        out.put("result", std::move(read.result)).put("regions", std::move(regions));
    } catch (const disked::local_file::Error &e) {
        out.put("refusal", V::string(e.what())).put("platform_error", exact(e.platform_code));
    } catch (const std::exception &e) {
        out.put("refusal", V::string(e.what()));
    }
    out.put("held_access", std::move(held_access))
        .put("stop_calls", exact(stop_calls))
        .put("read_calls", exact(read_calls));
    if (const auto *release = input.find("release_check"))
        if (release->boolean) {
            out.put("released_access", access(original_path, false));
            if (const auto *parents = input.find("access_parents")) {
                auto released = V::array();
                for (const auto &parent : parents->items)
                    released.items.push_back(access(parent.text, false));
                out.put("released_parent_access", std::move(released));
            }
        }
    return out;
}
int main() {
    try {
        std::string input;
        char block[4096];
        for (;;) {
            const auto n = std::fread(block, 1, sizeof(block), stdin);
            input.append(block, n);
            need(input.size() <= 8388608);
            if (n < sizeof(block))
                break;
        }
        disked::json::Limits limits;
        limits.bytes = 33554432;
        limits.string_bytes = 16777216;
        limits.values = 1048576;
        const auto rows = disked::json::parse(input, limits);
        need(rows.kind == V::Kind::array);
        auto out = V::array();
        for (const auto &row : rows.items)
            out.items.push_back(observe(row));
        std::cout << disked::json::dump(out, limits) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
