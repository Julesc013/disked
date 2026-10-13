#include "fat_tree_file.h"
#include "local_file.h"
#include <atomic>
#include <limits>

namespace disked {
namespace {
using V = json::Value;
namespace f = local_file;
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::uint64_t native(const de_u64 &n) {
    char s[21];
    if (de_u64_format(&n, s, sizeof(s)))
        throw std::runtime_error("fat_tree_extent");
    return std::stoull(s);
}
std::string hex(const std::vector<unsigned char> &v) {
    const char digits[] = "0123456789abcdef";
    std::string s;
    s.reserve(v.size() * 2);
    for (auto b : v) {
        s += digits[b >> 4];
        s += digits[b & 15];
    }
    return s;
}
bool equal(const V &a, const V &b) {
    return json::dump(a, fat_tree_json_limits()) == json::dump(b, fat_tree_json_limits());
}
struct Read {
    std::vector<unsigned char> bytes;
    DWORD error = 0;
};
Read read(HANDLE file, std::uint64_t offset, std::size_t bytes) {
    Read out;
    if (offset > static_cast<std::uint64_t>(MAXLONGLONG) || bytes > 4096)
        throw std::runtime_error("fat_tree_extent");
    LARGE_INTEGER at{};
    at.QuadPart = static_cast<LONGLONG>(offset);
    if (!SetFilePointerEx(file, at, nullptr, FILE_BEGIN)) {
        out.error = GetLastError();
        return out;
    }
    out.bytes.resize(bytes);
    DWORD got = 0;
    if (!ReadFile(file, out.bytes.data(), static_cast<DWORD>(bytes), &got, nullptr))
        out.error = GetLastError();
    out.bytes.resize(out.error ? 0 : got);
    return out;
}
} // namespace
struct FatTreeFile::Impl {
    FatTreeInput input;
    std::wstring path;
    std::vector<f::Handle> ancestors;
    V generations, source_before, context, last_metadata, regions = V::array(), checks = V::array();
    f::Handle file;
    FatTraversalBinding binding;
    std::unique_ptr<FatTraversal> traversal;
    std::vector<unsigned char> borrowed;
    std::function<bool()> stop;
    bool read_consistent = true;
    std::uint64_t calls = 0, total_reads = 0;
    std::string fault;
    explicit Impl(const FatTreeInput &v) : input(v) {
        validate_fat_tree_input(input);
#ifdef DISKED_FAT_TREE_FILE_TESTING
        if (const auto *p = input.fixture.find("file_fault"))
            fault = p->text;
#endif
        path = f::path_for(input.path);
        ancestors = f::pin_parents(path);
        generations = f::parent_generations(ancestors);
        file = f::Handle(CreateFileW(
            path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_RANDOM_ACCESS,
            nullptr));
        if (file.value == INVALID_HANDLE_VALUE)
            throw f::Error("fat_tree_file_open", GetLastError());
        guard();
        source_before = f::metadata(file.value).value;
        if (!equal(source_before, input.expected_source))
            throw f::Error("fat_tree_source_changed");
        static std::atomic<std::uint64_t> sequence{0};
        auto previous = sequence.load();
        for (;;) {
            if (previous == std::numeric_limits<std::uint64_t>::max())
                throw std::runtime_error("fat_tree_sequence_exhausted");
            if (sequence.compare_exchange_weak(previous, previous + 1))
                break;
        }
        FILETIME created{}, exited{}, kernel{}, user{};
        if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
            throw f::Error("fat_tree_process", GetLastError());
        context = V::object()
                      .put("process_id", number(GetCurrentProcessId()))
                      .put("process_created",
                           number((static_cast<std::uint64_t>(created.dwHighDateTime) << 32) |
                                  created.dwLowDateTime))
                      .put("capture_sequence", number(previous + 1));
        binding = fat_tree_binding(input, context);
        FatTraversalPort port;
        port.read = [this](const de_byte_extent &e) { return region(e); };
        port.applicable = [this](const FatTraversalBinding &) { return applicable(); };
        traversal.reset(new FatTraversal(binding, port, input.resources));
    }
    void guard() {
        f::check_parents(path, ancestors, generations);
        f::ordinary(file.value, false);
        f::bind_path(file.value, path);
    }
    bool applicable() {
        V observed, code;
        DWORD platform = 0;
        bool cancelled = false;
        try {
            cancelled = stop && stop();
            if (cancelled)
                code = V::string("fat_tree_cancelled");
            else {
                guard();
                observed = f::metadata(file.value).value;
#ifdef DISKED_FAT_TREE_FILE_TESTING
                if (fault == "metadata_changed" && total_reads)
                    observed.put("written", V::string("1"));
#endif
                if (!equal(observed, input.expected_source))
                    code = V::string("fat_tree_source_changed");
                else if (!read_consistent)
                    code = V::string("fat_tree_read_disagreement");
            }
        } catch (const f::Error &e) {
            code = V::string(e.what());
            platform = e.platform_code;
        } catch (const std::exception &) {
            code = V::string("fat_tree_check_failed");
        }
        const bool applies = !cancelled && read_consistent && code.kind == V::Kind::null &&
                             equal(observed, input.expected_source);
        last_metadata = observed;
        checks.items.push_back(V::object()
                                   .put("applicable", V::boolean_value(applies))
                                   .put("cancelled", V::boolean_value(cancelled))
                                   .put("read_consistent", V::boolean_value(read_consistent))
                                   .put("metadata", std::move(observed))
                                   .put("code", std::move(code))
                                   .put("platform_code", number(platform)));
        return applies;
    }
    de_view region(const de_byte_extent &e) {
        const auto begin = native(e.start), end = native(e.end);
        if (!e.space || std::string(e.space->name, e.space->name_length) != binding.source_id ||
            end < begin || end - begin > 4096 || end > binding.source_bytes)
            throw std::runtime_error("fat_tree_extent");
        const auto count = static_cast<std::size_t>(end - begin);
        ++total_reads;
        auto first = read(file.value, begin, count), second = read(file.value, begin, count);
#ifdef DISKED_FAT_TREE_FILE_TESTING
        if (total_reads == 1) {
            if (fault == "read_error") {
                first.error = ERROR_READ_FAULT;
                first.bytes.clear();
            }
            if (fault == "short_read" && !first.bytes.empty())
                first.bytes.pop_back();
            if (fault == "verify_changed" && !second.bytes.empty())
                second.bytes[0] ^= 1;
            if (fault == "hold")
                Sleep(200);
        }
#endif
        const bool matches = !first.error && !second.error && first.bytes.size() == count &&
                             second.bytes.size() == count && first.bytes == second.bytes;
        read_consistent = read_consistent && matches;
        regions.items.push_back(V::object()
                                    .put("offset", number(begin))
                                    .put("requested", number(count))
                                    .put("bytes", V::string(hex(first.bytes)))
                                    .put("read_error", number(first.error))
                                    .put("reread_bytes", V::string(hex(second.bytes)))
                                    .put("reread_error", number(second.error))
                                    .put("matches", V::boolean_value(matches)));
        borrowed = std::move(first.bytes);
        return de_view{borrowed.data(), borrowed.size()};
    }
    V next(const std::function<bool()> &cancel) {
        if (traversal->finished())
            throw std::invalid_argument("fat_tree_finished");
        regions = V::array();
        checks = V::array();
        stop = cancel;
        ++calls;
        auto page = traversal->next(binding, input.page);
        stop = {};
        auto frame = V::object()
                         .put("schema", V::string("org.disked.fat-tree-frame/1"))
                         .put("input", fat_tree_input_value(input))
                         .put("context", context)
                         .put("source_before", source_before)
                         .put("source_after", last_metadata)
                         .put("page", std::move(page))
                         .put("regions", regions)
                         .put("checks", checks);
        json::dump(frame, fat_tree_json_limits());
        return frame;
    }
};
FatTreeFile::FatTreeFile(const FatTreeInput &input) : impl_(new Impl(input)) {
}
FatTreeFile::~FatTreeFile() = default;
V FatTreeFile::next(const std::function<bool()> &stop) {
    return impl_->next(stop);
}
bool FatTreeFile::finished() const {
    return impl_->traversal->finished();
}
} // namespace disked
