#include "fat_tree_file.h"
#include "local_file.h"
#include "fat_native_metadata.h"
#include "portable/fat/fat.h"
#include <algorithm>
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
V capture_context() {
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
    return V::object()
        .put("process_id", number(GetCurrentProcessId()))
        .put("process_created", number((static_cast<std::uint64_t>(created.dwHighDateTime) << 32) |
                                       created.dwLowDateTime))
        .put("capture_sequence", number(previous + 1));
}
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
    std::unique_ptr<FatContentStream> content;
    V last_page, content_record;
    std::vector<unsigned char> borrowed;
    std::function<bool()> stop;
    bool read_consistent = true;
    std::uint64_t calls = 0, total_reads = 0;
    int observed_bits = 0;
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
        context = capture_context();
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
        if (content && !content->finished())
            throw std::invalid_argument("fat_tree_content_busy");
        if (traversal->finished())
            throw std::invalid_argument("fat_tree_finished");
        regions = V::array();
        checks = V::array();
        stop = cancel;
        struct ResetStop {
            std::function<bool()> &value;
            ~ResetStop() {
                value = {};
            }
        } reset{stop};
        ++calls;
        auto page = traversal->next(binding, input.page);
        for (const auto &value : page.fields.at("events").items) {
            const auto *type = value.find("type");
            if (type && type->text == "volume")
                observed_bits = std::stoi(value.fields.at("bits").text);
        }
        last_page = page;
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
    void begin_reinspection() {
        if (!traversal->finished() || (content && !content->finished()))
            throw std::invalid_argument("fat_tree_reinspection_busy");
        stop = {};
        if (!applicable())
            throw std::invalid_argument("fat_tree_reinspection_source_changed");
        auto next_context = capture_context();
        auto next_binding = fat_tree_binding(input, next_context);
        FatTraversalPort port;
        port.read = [this](const de_byte_extent &e) { return region(e); };
        port.applicable = [this](const FatTraversalBinding &) { return applicable(); };
        std::unique_ptr<FatTraversal> next(new FatTraversal(next_binding, port, input.resources));
        traversal = std::move(next);
        context = std::move(next_context);
        binding = std::move(next_binding);
        content.reset();
        content_record = V{};
        last_page = V{};
        observed_bits = 0;
        regions = V::array();
        checks = V::array();
    }
    void start_content(const std::string &key) {
        if (key.empty() || key.size() > 26)
            throw std::invalid_argument("fat_tree_content_key");
        if (content && !content->finished())
            throw std::invalid_argument("fat_tree_content_busy");
        const auto *applies = last_page.find("applicable"), *events = last_page.find("events");
        if (!applies || applies->kind != V::Kind::boolean || !applies->boolean || !events ||
            events->kind != V::Kind::array)
            throw std::invalid_argument("fat_tree_content_view_unavailable");
        const V *record = nullptr;
        for (const auto &value : events->items) {
            const auto *kind = value.find("type"), *id = value.find("key"),
                       *type = value.find("kind");
            if (kind && kind->text == "record" && id && id->text == key && type &&
                type->kind == V::Kind::string && type->text == std::to_string(DE_FAT_DIRENT_FILE)) {
                if (record)
                    throw std::invalid_argument("fat_tree_content_key");
                record = &value;
            }
        }
        if (!record)
            throw std::invalid_argument("fat_tree_content_not_observed");
        const auto *raw = record->find("raw"), *offset = record->find("source_offset");
        if (!raw || raw->kind != V::Kind::string || raw->text.size() != 64 ||
            raw->text.find_first_not_of("0123456789abcdef") != raw->text.npos || !offset ||
            offset->kind != V::Kind::string || !json::decimal_u64(offset->text))
            throw std::invalid_argument("fat_tree_content_record");
        stop = {};
        if (!applicable())
            throw std::invalid_argument("fat_tree_content_source_changed");
        FatContentStreamSelection selected;
        selected.binding = binding;
        selected.record_source_offset = std::stoull(offset->text);
        auto digit = [](char c) {
            return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
        };
        for (std::size_t i = 0; i < selected.record.size(); ++i)
            selected.record[i] = static_cast<unsigned char>(digit(raw->text[i * 2]) * 16 +
                                                            digit(raw->text[i * 2 + 1]));
        FatTraversalPort port;
        port.read = [this](const de_byte_extent &e) { return region(e); };
        port.applicable = [this](const FatTraversalBinding &) { return applicable(); };
        content.reset(new FatContentStream(selected, port, input.resources.bitmap_bytes));
        content_record = *record;
    }
    V next_content(const FatContentStreamBudget &budget, const std::function<bool()> &cancel) {
        if (!content || content->finished())
            throw std::invalid_argument("fat_tree_content_finished");
        if (budget.bytes > 65536 || budget.reads > 256 || budget.read_bytes > 196608 ||
            budget.cells > 256 || budget.output_bytes > 1048576)
            throw std::invalid_argument("fat_tree_content_budget");
        regions = V::array();
        checks = V::array();
        stop = cancel;
        struct ResetStop {
            std::function<bool()> &value;
            ~ResetStop() {
                value = {};
            }
        } reset{stop};
        FatContentStreamSelection selected;
        selected.binding = binding;
        selected.record_source_offset = std::stoull(content_record.fields.at("source_offset").text);
        const auto &raw = content_record.fields.at("raw").text;
        for (std::size_t i = 0; i < selected.record.size(); ++i) {
            const auto digit = [](char c) {
                return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
            };
            selected.record[i] =
                static_cast<unsigned char>(digit(raw[i * 2]) * 16 + digit(raw[i * 2 + 1]));
        }
        auto page = content->next(selected, budget);
        stop = {};
        auto frame = V::object()
                         .put("schema", V::string("org.disked.fat-tree-content-frame/1"))
                         .put("context", context)
                         .put("source_before", source_before)
                         .put("source_after", last_metadata)
                         .put("record", content_record)
                         .put("page", std::move(page))
                         .put("regions", regions)
                         .put("checks", checks)
                         .put("directory_membership", V::string("held-source-traversal"));
        json::dump(frame, fat_tree_content_json_limits());
        return frame;
    }
    void check_metadata_applicable() {
        if (applicable())
            return;
        if (!checks.items.empty() && checks.items.back().fields.at("cancelled").boolean)
            throw std::invalid_argument("fat_tree_metadata_cancelled");
        throw std::invalid_argument("fat_tree_metadata_source_changed");
    }
    V metadata_candidates(const std::string &key, const FatMetadataPolicy &policy,
                          const std::function<bool()> &cancel) {
        fat_metadata_policy_value(policy); // Refuse invalid policy before read callbacks.
        if (key.empty() || key.size() > 26 || !observed_bits)
            throw std::invalid_argument("fat_tree_metadata_key");
        if (content && !content->finished())
            throw std::invalid_argument("fat_tree_content_busy");
        const auto *applies = last_page.find("applicable"), *events = last_page.find("events");
        if (!applies || applies->kind != V::Kind::boolean || !applies->boolean || !events ||
            events->kind != V::Kind::array)
            throw std::invalid_argument("fat_tree_metadata_view_unavailable");
        const V *record = nullptr;
        for (const auto &value : events->items) {
            const auto *type = value.find("type"), *id = value.find("key"),
                       *kind = value.find("kind");
            if (type && type->text == "record" && id && id->text == key && kind &&
                (kind->text == "3" || kind->text == "4")) {
                if (record)
                    throw std::invalid_argument("fat_tree_metadata_key");
                record = &value;
            }
        }
        if (!record)
            throw std::invalid_argument("fat_tree_metadata_not_observed");
        regions = V::array();
        checks = V::array();
        stop = cancel;
        struct ResetStop {
            std::function<bool()> &value;
            ~ResetStop() {
                value = {};
            }
        } reset{stop};
        auto reobserve = [this](const std::string &raw, const std::string &offset) {
            if (raw.size() != 64 || raw.find_first_not_of("0123456789abcdef") != raw.npos ||
                !json::decimal_u64(offset))
                throw std::invalid_argument("fat_tree_metadata_record");
            const auto at = std::stoull(offset);
            if (at < binding.volume_offset || at - binding.volume_offset > binding.volume_bytes ||
                32 > binding.volume_bytes - (at - binding.volume_offset))
                throw std::invalid_argument("fat_tree_metadata_record");
            check_metadata_applicable();
            de_u64 begin{}, size{};
            if (de_u64_parse(offset.data(), offset.size(), &begin) || de_u64_parse("32", 2, &size))
                throw std::invalid_argument("fat_tree_metadata_record");
            de_block_space space{};
            const auto extent_text = std::to_string(binding.source_bytes);
            de_u64 extent{};
            if (de_u64_parse(extent_text.data(), extent_text.size(), &extent) ||
                de_space_init(binding.source_id.data(), binding.source_id.size(), &extent, 1,
                              &space))
                throw std::invalid_argument("fat_tree_metadata_record");
            de_block_extent blocks{};
            de_byte_extent bytes{};
            if (de_extent_make(&space, &begin, &size, &blocks) ||
                de_extent_to_bytes(&blocks, &bytes))
                throw std::invalid_argument("fat_tree_metadata_record");
            const auto view = region(bytes);
            std::vector<unsigned char> observed;
            if (view.size)
                observed.assign(view.data, view.data + view.size);
            check_metadata_applicable();
            if (hex(observed) != raw)
                throw std::invalid_argument("fat_tree_metadata_record_changed");
            return observed;
        };
        FatMetadataInput selected;
        selected.bits = observed_bits;
        selected.source_offset = std::stoull(record->fields.at("source_offset").text);
        const auto raw =
            reobserve(record->fields.at("raw").text, record->fields.at("source_offset").text);
        std::copy(raw.begin(), raw.end(), selected.record.begin());
        if (const auto *long_name = record->find("long_name")) {
            const auto &stored = long_name->fields.at("raw_slots").text;
            const auto &offsets = long_name->fields.at("source_offsets").items;
            if (offsets.size() > 20 || stored.size() != offsets.size() * 64)
                throw std::invalid_argument("fat_tree_metadata_slots");
            for (std::size_t i = 0; i < offsets.size(); ++i) {
                auto slot = reobserve(stored.substr(i * 64, 64), offsets[i].text);
                selected.long_slots.insert(selected.long_slots.end(), slot.begin(), slot.end());
            }
        }
        auto mapping = fat_native_metadata_candidates(selected, policy);
        check_metadata_applicable();
        auto frame = V::object()
                         .put("schema", V::string("org.disked.fat-tree-metadata-frame/1"))
                         .put("context", context)
                         .put("binding", fat_tree_binding_value(binding))
                         .put("source_before", source_before)
                         .put("source_after", last_metadata)
                         .put("record", *record)
                         .put("mapping", std::move(mapping))
                         .put("regions", regions)
                         .put("checks", checks)
                         .put("directory_membership", V::string("held-source-traversal"))
                         .put("authorizes_effects", V::boolean_value(false));
        json::dump(frame, fat_tree_content_json_limits());
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
void FatTreeFile::start_content(const std::string &key) {
    impl_->start_content(key);
}
V FatTreeFile::next_content(const FatContentStreamBudget &b, const std::function<bool()> &stop) {
    return impl_->next_content(b, stop);
}
bool FatTreeFile::content_finished() const {
    return !impl_->content || impl_->content->finished();
}
V FatTreeFile::metadata_candidates(const std::string &key, const FatMetadataPolicy &policy,
                                   const std::function<bool()> &stop) {
    return impl_->metadata_candidates(key, policy, stop);
}
void FatTreeFile::begin_reinspection() {
    impl_->begin_reinspection();
}
json::Limits fat_tree_content_json_limits() {
    auto limits = fat_tree_json_limits();
    limits.values = 131072;
    limits.string_bytes = 393216;
    return limits;
}
} // namespace disked
