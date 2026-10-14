#include "providers/image/exfat_file.h"
#include "providers/image/local_file.h"
#include <iostream>
#include <stdexcept>

using V = disked::json::Value;
static void require(bool v) {
    if (!v)
        throw std::runtime_error("exfat_file_probe_input");
}
static const V &field(const V &v, const char *key) {
    const auto *result = v.find(key);
    require(result != nullptr);
    return *result;
}
static std::uint64_t integer(const V &v) {
    require(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static std::string hex(const std::vector<unsigned char> &bytes) {
    const char digits[] = "0123456789abcdef";
    std::string result;
    for (auto byte : bytes) {
        result += digits[byte >> 4];
        result += digits[byte & 15];
    }
    return result;
}
static V observe(const V &input) {
    const auto &path = field(input, "path");
    require(path.kind == V::Kind::string);
    const auto offset = integer(field(input, "offset")), bytes = integer(field(input, "length"));
    const auto *format = input.find("upcase_format");
    const auto *compressed = input.find("compressed");
    require(format ? !compressed && format->kind == V::Kind::string
                   : compressed && compressed->kind == V::Kind::boolean);
    disked::ExfatCaptureLimits limits;
    if (const auto *values = input.find("limits")) {
        require(values->kind == V::Kind::object);
#define LOAD_LIMIT(name)                                                                           \
    if (const auto *v = values->find(#name))                                                       \
    limits.name = static_cast<std::size_t>(integer(*v))
        LOAD_LIMIT(read_requests);
        LOAD_LIMIT(read_bytes);
        LOAD_LIMIT(clusters);
        LOAD_LIMIT(records);
        LOAD_LIMIT(retained_bytes);
        LOAD_LIMIT(output_bytes);
#undef LOAD_LIMIT
    }
    auto out = V::object(), held_access = V::array();
    const auto *supplied = input.find("mode");
    const auto mode = supplied ? supplied->text : "";
    const auto *call_value = input.find("call");
    const auto call = call_value ? integer(*call_value) : 1;
    std::size_t stop_calls = 0;
    std::size_t read_calls = 0;
    std::function<bool()> stop;
#ifdef DISKED_EXFAT_FILE_TESTING
    out.put("fault_controls_available", V::boolean_value(true));
    if (mode == "cancel")
        stop = [&] { return ++stop_calls >= call; };
    if (mode == "cancel_throw")
        stop = [&] {
            if (++stop_calls >= call)
                throw std::runtime_error("test_cancel_callback");
            return false;
        };
    disked::ExfatFileTestControl control;
    control.after_read = [&](std::size_t ordinal, disked::ExfatFileRegion &region) {
        ++read_calls;
        if (ordinal != call)
            return;
        if (mode == "short" && !region.bytes.empty())
            region.bytes.pop_back();
        else if (mode == "error") {
            region.error = ERROR_READ_FAULT;
            region.bytes.clear();
        } else if (mode == "changed" && !region.bytes.empty())
            region.bytes[0] ^= 1;
        else if (mode == "throw")
            throw disked::local_file::Error("test_after_read_failure", ERROR_INVALID_DATA);
        else if (mode == "held_access") {
            const auto native = disked::local_file::path_for(path.text);
            for (auto access : {static_cast<DWORD>(GENERIC_WRITE), static_cast<DWORD>(DELETE)}) {
                HANDLE handle = CreateFileW(
                    native.c_str(), access, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                    nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
                const bool opened = handle != INVALID_HANDLE_VALUE;
                const auto error = opened ? 0 : GetLastError();
                if (opened)
                    CloseHandle(handle);
                held_access.items.push_back(V::object()
                                                .put("access", exact(access))
                                                .put("opened", V::boolean_value(opened))
                                                .put("error", exact(error)));
            }
            const auto destination = native + L".rename-probe";
            const bool renamed = MoveFileW(native.c_str(), destination.c_str()) != 0;
            const auto rename_error = renamed ? 0 : GetLastError();
            held_access.items.push_back(V::object()
                                            .put("rename_succeeded", V::boolean_value(renamed))
                                            .put("error", exact(rename_error)));
        }
    };
    control.after_metadata = [&](V &value) {
        if (mode == "metadata")
            value.put("written", V::string("test-changed-observation"));
    };
    control.before_replay = [&](std::size_t ordinal, disked::ExfatFileRegion &region) {
        if (ordinal == call && mode == "replay_bytes" && !region.bytes.empty())
            region.bytes[0] ^= 1;
        if (ordinal == call && mode == "replay_offset")
            ++region.offset;
    };
    control.before_binding = [&](std::size_t ordinal) {
        if (ordinal == call && mode == "binding")
            throw disked::local_file::Error("test_binding_failure", ERROR_INVALID_HANDLE);
    };
#else
    out.put("fault_controls_available", V::boolean_value(false));
    (void)mode;
    (void)call;
#endif
    try {
        // Fixture input has exactly one selector. Unknown enum reaches the native
        // API validation so tests can observe refusal before any content reads.
        disked::ExfatUpcaseFormat typed = disked::ExfatUpcaseFormat::Automatic;
        if (format) {
            try {
                typed = disked::exfat_upcase_format_from(format->text);
            } catch (const std::invalid_argument &) {
                typed = static_cast<disked::ExfatUpcaseFormat>(99);
            }
        }
#ifdef DISKED_EXFAT_FILE_TESTING
        auto owned =
            format
                ? disked::capture_exfat_file_testing(path.text, offset, bytes, typed, limits, stop,
                                                     control, input.find("expected_source"))
                : disked::capture_exfat_file_testing(path.text, offset, bytes, compressed->boolean,
                                                     limits, stop, control,
                                                     input.find("expected_source"));
#else
        auto owned =
            format ? disked::capture_exfat_file_owned(path.text, offset, bytes, typed, limits, stop,
                                                      input.find("expected_source"))
                   : disked::capture_exfat_file_owned(path.text, offset, bytes, compressed->boolean,
                                                      limits, stop, input.find("expected_source"));
#endif
        auto regions = V::array();
        for (const auto &region : owned.regions)
            regions.items.push_back(
                V::object()
                    .put("offset", exact(region.offset))
                    .put("requested", exact(region.requested))
                    .put("error", exact(region.error))
                    .put("read_attempted", V::boolean_value(region.read_attempted))
                    .put("refusal", V::string(region.refusal))
                    .put("bytes", V::string(hex(region.bytes))));
        require(owned.process_id == GetCurrentProcessId());
        FILETIME created{}, exited{}, kernel{}, user{};
        require(GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user) != 0);
        require(
            owned.process_created ==
            ((static_cast<std::uint64_t>(created.dwHighDateTime) << 32) | created.dwLowDateTime));
        out.put("result", std::move(owned.result)).put("regions", std::move(regions));
    } catch (const disked::local_file::Error &e) {
        out.put("refusal", V::string(e.what())).put("platform_error", exact(e.platform_code));
    } catch (const std::invalid_argument &e) {
        out.put("refusal", V::string(e.what())).put("platform_error", exact(0));
    }
    return out.put("stop_calls", exact(stop_calls))
        .put("read_calls", exact(read_calls))
        .put("held_access", std::move(held_access));
}
int main() {
    try {
        disked::json::Limits limits;
        limits.bytes = 33554432;
        limits.string_bytes = 16777216;
        limits.values = 1048576;
        limits.depth = 48;
        const std::string text((std::istreambuf_iterator<char>(std::cin)),
                               std::istreambuf_iterator<char>());
        const auto input = disked::json::parse(text, limits);
        require(input.kind == V::Kind::array && input.items.size() <= 16);
        auto output = V::array();
        for (const auto &row : input.items)
            output.items.push_back(observe(row));
        std::cout << disked::json::dump(output, limits);
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what();
        return 1;
    }
}
