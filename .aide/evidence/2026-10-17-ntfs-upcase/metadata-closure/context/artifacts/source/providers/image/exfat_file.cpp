#include "exfat_file.h"
#include "providers/image/local_file.h"
#include "portable/hash/sha256.h"
#include <atomic>
#include <deque>
#include <limits>
#include <utility>

namespace disked {
namespace {
using V = json::Value;
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::runtime_error("exfat_file_extent");
    return std::stoull(text);
}
std::string digest(const std::string &text) {
    unsigned char bytes[32];
    sha256(reinterpret_cast<const unsigned char *>(text.data()), text.size(), bytes);
    const char alphabet[] = "0123456789abcdef";
    std::string result = "sha256:";
    for (auto byte : bytes) {
        result += alphabet[byte >> 4];
        result += alphabet[byte & 15];
    }
    return result;
}
json::Limits json_limits(std::size_t bytes = 4194304) {
    json::Limits limits;
    limits.bytes = bytes;
    limits.string_bytes = 2097152;
    limits.values = bytes > 4194304 ? 1048576 : 262144;
    limits.depth = 32;
    return limits;
}
std::string encode(const V &value, std::size_t bytes = 4194304) {
    return json::dump(value, json_limits(bytes));
}
ExfatFileRegion read(HANDLE file, std::uint64_t start, std::size_t count) {
    if (start > static_cast<std::uint64_t>(MAXLONGLONG) || !count || count > 49152)
        throw std::runtime_error("exfat_file_extent");
    ExfatFileRegion result;
    result.offset = start;
    result.requested = count;
    result.read_attempted = true;
    LARGE_INTEGER offset{};
    offset.QuadPart = static_cast<LONGLONG>(start);
    if (!SetFilePointerEx(file, offset, nullptr, FILE_BEGIN)) {
        result.error = GetLastError();
        return result;
    }
    result.bytes.resize(count);
    DWORD got = 0;
    if (!ReadFile(file, result.bytes.data(), static_cast<DWORD>(count), &got, nullptr))
        result.error = GetLastError();
    result.bytes.resize(result.error ? 0 : static_cast<std::size_t>(got));
    return result;
}
enum class FileEncoding { ExplicitV1, TypedV2, TreeV1 };
ExfatFileRead capture(const std::string &input, std::uint64_t offset, std::uint64_t bytes,
                      ExfatUpcaseFormat format, FileEncoding encoding,
                      const ExfatCaptureLimits &limits, const std::function<bool()> &stop,
                      const V *expected_source
#ifdef DISKED_EXFAT_FILE_TESTING
                      ,
                      const ExfatFileTestControl *control
#endif
                      ,
                      const ExfatTreeLimits *tree_input = nullptr) {
    const bool tree_mode = encoding == FileEncoding::TreeV1;
    const ExfatTreeLimits tree_limits = tree_input ? *tree_input : ExfatTreeLimits{};
    const V held_expected = expected_source ? *expected_source : V{};
    const auto stop_callback = stop;
#ifdef DISKED_EXFAT_FILE_TESTING
    const ExfatFileTestControl held_control = control ? *control : ExfatFileTestControl{};
    control = control ? &held_control : nullptr;
#endif
    if (tree_mode)
        validate_exfat_tree_limits(tree_limits);
    const auto maximum = static_cast<std::uint64_t>(MAXLONGLONG);
    if (offset > maximum || bytes > maximum - offset)
        throw std::invalid_argument("exfat_file_seek_range");
    ExfatCaptureRequest request;
    request.source_id = "exfat-pending";
    request.epoch = 1;
    request.source_bytes = maximum;
    request.volume_offset = offset;
    request.volume_bytes = bytes;
    request.upcase_format = format;
    request.limits = limits;
    validate_exfat_capture_request(request);
    const auto path = local_file::path_for(input);
    auto ancestors = local_file::pin_parents(path);
    const auto generations = local_file::parent_generations(ancestors);
    local_file::Handle file(CreateFileW(
        path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_RANDOM_ACCESS,
        nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw local_file::Error("exfat_file_open", GetLastError());
    std::size_t binding_checks = 0;
    auto check = [&] {
        ++binding_checks;
#ifdef DISKED_EXFAT_FILE_TESTING
        if (control && control->before_binding)
            control->before_binding(binding_checks);
#endif
        bool cancelled = false;
        try {
            cancelled = stop_callback && stop_callback();
        } catch (...) {
            throw local_file::Error("exfat_file_cancel_callback");
        }
        if (cancelled)
            throw local_file::Error("exfat_file_cancelled");
        local_file::check_parents(path, ancestors, generations);
        local_file::ordinary(file.value, false);
        local_file::bind_path(file.value, path);
    };
    check();
    const auto before = local_file::metadata(file.value);
    if (expected_source && encode(before.value) != encode(held_expected))
        throw local_file::Error("exfat_file_source_changed");
    static std::atomic<std::uint64_t> sequence{0};
    auto previous = sequence.load();
    for (;;) {
        if (previous == std::numeric_limits<std::uint64_t>::max())
            throw std::runtime_error("exfat_capture_epoch_exhausted");
        if (sequence.compare_exchange_weak(previous, previous + 1))
            break;
    }
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
        throw local_file::Error("exfat_capture_process", GetLastError());
    const auto process_created =
        (static_cast<std::uint64_t>(created.dwHighDateTime) << 32) | created.dwLowDateTime;
    request.source_id = digest(encode(before.value));
    request.epoch = previous + 1;
    request.source_bytes = before.size;
    validate_exfat_capture_request(request);
    std::deque<ExfatFileRegion> regions;
    RegionReader live_reader = [&](const de_byte_extent &extent) {
        const auto start = native(extent.start), end = native(extent.end);
        if (end < start || end - start > 49152 || end > before.size)
            throw std::runtime_error("exfat_file_extent");
        ExfatFileRegion region;
        region.offset = start;
        region.requested = static_cast<std::size_t>(end - start);
        try {
            check();
            region = read(file.value, start, region.requested);
#ifdef DISKED_EXFAT_FILE_TESTING
            if (control && control->after_read)
                control->after_read(regions.size() + 1, region);
#endif
        } catch (const local_file::Error &e) {
            region.error = e.platform_code;
            region.refusal = e.what();
        }
        regions.push_back(std::move(region));
        const auto &saved = regions.back();
        if (!saved.refusal.empty())
            throw local_file::Error(saved.refusal.c_str(), saved.error);
        if (saved.error)
            throw local_file::Error("exfat_file_read", saved.error);
        return de_view{saved.bytes.data(), saved.bytes.size()};
    };
    struct Applicability {
        bool allowed = false;
        std::string diagnostic;
        DWORD platform = 0;
    };
    std::vector<Applicability> applicability;
    std::size_t applicability_replay_index = 0;
    bool applicability_replay_ok = true;
    auto collect = [&](const RegionReader &reader, bool replaying) {
        if (!tree_mode)
            return observe_exfat_volume(request, reader);
        ExfatTreePort port;
        port.read = reader;
        port.applicable = [&](const ExfatCaptureRequest &binding) {
            if (binding.source_id != request.source_id || binding.epoch != request.epoch ||
                binding.source_bytes != request.source_bytes ||
                binding.volume_offset != request.volume_offset ||
                binding.volume_bytes != request.volume_bytes) {
                applicability_replay_ok = false;
                return false;
            }
            if (replaying) {
                if (applicability_replay_index == applicability.size()) {
                    applicability_replay_ok = false;
                    return false;
                }
                bool allowed = applicability[applicability_replay_index++].allowed;
#ifdef DISKED_EXFAT_FILE_TESTING
                if (control && control->before_applicability_replay)
                    control->before_applicability_replay(applicability_replay_index, allowed);
#endif
                if (allowed != applicability[applicability_replay_index - 1].allowed)
                    applicability_replay_ok = false;
                return allowed;
            }
            if (applicability.size() == tree_limits.read_requests + 2)
                throw local_file::Error("exfat_file_applicability_budget");
            Applicability decision;
            try {
                check();
                if (encode(local_file::metadata(file.value).value) != encode(before.value))
                    throw local_file::Error("exfat_file_source_changed");
                decision.allowed = true;
            } catch (const local_file::Error &e) {
                decision.diagnostic = e.what();
                decision.platform = e.platform_code;
            }
            applicability.push_back(std::move(decision));
            return applicability.back().allowed;
        };
        return observe_exfat_tree(request, port, tree_limits);
    };
    auto observation = collect(live_reader, false);
    V after;
    std::string binding_error;
    DWORD binding_platform_error = 0;
    bool binding_ok = false;
    try {
        check();
        after = local_file::metadata(file.value).value;
#ifdef DISKED_EXFAT_FILE_TESTING
        if (control && control->after_metadata)
            control->after_metadata(after);
#endif
        check();
        binding_ok = true;
    } catch (const local_file::Error &e) {
        binding_error = e.what();
        binding_platform_error = e.platform_code;
    }
    const bool metadata_equal =
        after.kind == V::Kind::object && encode(before.value) == encode(after);
    std::size_t replay_index = 0;
    std::deque<ExfatFileRegion> replay_regions;
    RegionReader replay_reader = [&](const de_byte_extent &extent) {
        if (replay_index == regions.size())
            throw std::runtime_error("exfat_replay_missing");
        auto region = regions[replay_index++];
#ifdef DISKED_EXFAT_FILE_TESTING
        if (control && control->before_replay)
            control->before_replay(replay_index, region);
#endif
        const auto start = native(extent.start), end = native(extent.end);
        if (start != region.offset || end < start || end - start != region.requested)
            throw std::runtime_error("exfat_replay_extent");
        if (!region.refusal.empty())
            throw local_file::Error(region.refusal.c_str(), region.error);
        if (region.error)
            throw local_file::Error("exfat_replay_read", region.error);
        // Retain immutable replay responses for the complete observation call.
        replay_regions.push_back(std::move(region));
        return de_view{replay_regions.back().bytes.data(), replay_regions.back().bytes.size()};
    };
    auto replay = collect(replay_reader, true);
    if (tree_mode) {
        for (const auto &decision : applicability) {
            if (!decision.allowed) {
                binding_ok = false;
                if (binding_error.empty()) {
                    binding_error = decision.diagnostic;
                    binding_platform_error = decision.platform;
                }
                break;
            }
        }
        try {
            check();
            if (encode(local_file::metadata(file.value).value) != encode(before.value))
                throw local_file::Error("exfat_file_source_changed");
        } catch (const local_file::Error &e) {
            binding_ok = false;
            binding_error = e.what();
            binding_platform_error = e.platform_code;
        }
    }
    const auto result_budget = tree_mode ? 8388608U : 4194304U;
    const bool replay_equal = replay_index == regions.size() && applicability_replay_ok &&
                              (!tree_mode || applicability_replay_index == applicability.size()) &&
                              encode(observation, result_budget) == encode(replay, result_budget);
    const bool stable = binding_ok && metadata_equal && replay_equal &&
                        (tree_mode ? (observation.find("reread_equal") &&
                                      observation.fields.at("reread_equal").boolean)
                                   : observation.fields.at("applicable").boolean);
    if (!binding_ok || !metadata_equal || !replay_equal) {
        observation.put(tree_mode ? "complete" : "applicable", V::boolean_value(false));
        const auto diagnostics = observation.fields.find("diagnostics");
        if (diagnostics != observation.fields.end())
            diagnostics->second.items.push_back(V::string("exfat_file_binding_disagreement"));
        else
            observation.put("binding_diagnostic", V::string("exfat_file_binding_disagreement"));
    }
    ExfatFileRead result;
    result.process_id = GetCurrentProcessId();
    result.process_created = process_created;
    result.result =
        V::object()
            .put("schema", V::string(tree_mode ? "org.disked.exfat-tree-file/1"
                                     : encoding == FileEncoding::ExplicitV1
                                         ? "org.disked.exfat-file-capture/1"
                                         : "org.disked.exfat-file-capture/2"))
            .put("observation", std::move(observation))
            .put("capture",
                 V::object()
                     .put("source_before", before.value)
                     .put("source_after", after)
                     .put("parent_generations", generations)
                     .put("metadata_equal", V::boolean_value(metadata_equal))
                     .put("source_identity_digest", V::string(request.source_id))
                     .put("observed_stable", V::boolean_value(stable))
                     .put("binding_checks_ok", V::boolean_value(binding_ok))
                     .put("binding_checks", exact(binding_checks))
                     .put("binding_error", V::string(binding_error))
                     .put("binding_platform_error", exact(binding_platform_error))
                     .put("replay_equal", V::boolean_value(replay_equal))
                     .put("process_id", exact(result.process_id))
                     .put("process_created", exact(process_created))
                     .put("sequence", exact(request.epoch))
                     .put("capture_domain",
                          V::string(digest(encode(
                              V::object()
                                  .put("provider", V::string(tree_mode ? "exfat-tree-file-prototype"
                                                                       : "exfat-file-prototype"))
                                  .put("process_id", exact(result.process_id))
                                  .put("process_created", exact(process_created))
                                  .put("sequence", exact(request.epoch))
                                  .put("source", before.value)))))
                     .put("source_consistency", V::string("live-uncoordinated"))
                     .put("atomic_snapshot", V::boolean_value(false)))
            .put("authorizes_effects", V::boolean_value(false))
            .put("product_dispatch_admitted", V::boolean_value(false));
    if (tree_mode) {
        auto decisions = V::array();
        for (const auto &decision : applicability)
            decisions.items.push_back(V::object()
                                          .put("allowed", V::boolean_value(decision.allowed))
                                          .put("diagnostic", V::string(decision.diagnostic))
                                          .put("platform_error", exact(decision.platform)));
        result.result.fields.at("capture")
            .put("applicability", std::move(decisions))
            .put("applicability_replay_count", exact(applicability_replay_index))
            .put("applicability_replay_ok",
                 V::boolean_value(applicability_replay_ok &&
                                  applicability_replay_index == applicability.size()))
            .put("current_source_authority", V::boolean_value(false));
        encode(result.result, result_budget);
    }
    for (auto &region : regions)
        result.regions.push_back(std::move(region));
    return result;
}
} // namespace
ExfatFileRead capture_exfat_tree_file_owned(const std::string &input, std::uint64_t offset,
                                            std::uint64_t bytes, ExfatUpcaseFormat format,
                                            const ExfatTreeLimits &tree_limits,
                                            const ExfatCaptureLimits &root_limits,
                                            const std::function<bool()> &stop,
                                            const V *expected_source) {
    return capture(input, offset, bytes, format, FileEncoding::TreeV1, root_limits, stop,
                   expected_source
#ifdef DISKED_EXFAT_FILE_TESTING
                   ,
                   nullptr
#endif
                   ,
                   &tree_limits);
}
ExfatFileRead capture_exfat_file_owned(const std::string &input, std::uint64_t offset,
                                       std::uint64_t bytes, bool compressed,
                                       const ExfatCaptureLimits &limits,
                                       const std::function<bool()> &stop,
                                       const V *expected_source) {
    return capture(input, offset, bytes,
                   compressed ? ExfatUpcaseFormat::Compressed : ExfatUpcaseFormat::Literal,
                   FileEncoding::ExplicitV1, limits, stop, expected_source
#ifdef DISKED_EXFAT_FILE_TESTING
                   ,
                   nullptr
#endif
    );
}
ExfatFileRead capture_exfat_file_owned(const std::string &input, std::uint64_t offset,
                                       std::uint64_t bytes, ExfatUpcaseFormat format,
                                       const ExfatCaptureLimits &limits,
                                       const std::function<bool()> &stop,
                                       const V *expected_source) {
    return capture(input, offset, bytes, format, FileEncoding::TypedV2, limits, stop,
                   expected_source
#ifdef DISKED_EXFAT_FILE_TESTING
                   ,
                   nullptr
#endif
    );
}
#ifdef DISKED_EXFAT_FILE_TESTING
ExfatFileRead capture_exfat_tree_file_testing(const std::string &input, std::uint64_t offset,
                                              std::uint64_t bytes, ExfatUpcaseFormat format,
                                              const ExfatTreeLimits &tree_limits,
                                              const ExfatCaptureLimits &root_limits,
                                              const std::function<bool()> &stop,
                                              const ExfatFileTestControl &control,
                                              const V *expected_source) {
    return capture(input, offset, bytes, format, FileEncoding::TreeV1, root_limits, stop,
                   expected_source, &control, &tree_limits);
}
ExfatFileRead capture_exfat_file_testing(const std::string &input, std::uint64_t offset,
                                         std::uint64_t bytes, bool compressed,
                                         const ExfatCaptureLimits &limits,
                                         const std::function<bool()> &stop,
                                         const ExfatFileTestControl &control,
                                         const V *expected_source) {
    return capture(input, offset, bytes,
                   compressed ? ExfatUpcaseFormat::Compressed : ExfatUpcaseFormat::Literal,
                   FileEncoding::ExplicitV1, limits, stop, expected_source, &control);
}
ExfatFileRead capture_exfat_file_testing(const std::string &input, std::uint64_t offset,
                                         std::uint64_t bytes, ExfatUpcaseFormat format,
                                         const ExfatCaptureLimits &limits,
                                         const std::function<bool()> &stop,
                                         const ExfatFileTestControl &control,
                                         const V *expected_source) {
    return capture(input, offset, bytes, format, FileEncoding::TypedV2, limits, stop,
                   expected_source, &control);
}
#endif
} // namespace disked
