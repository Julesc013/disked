#include "ntfs_file.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <atomic>
#include <deque>
#include <limits>

namespace disked {
namespace {
using V = json::Value;
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V flag(bool n) {
    return V::boolean_value(n);
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::logic_error("ntfs_file_extent");
    return std::stoull(text);
}
json::Limits output_limits(std::size_t bytes = 4194304) {
    json::Limits limits;
    limits.bytes = bytes;
    limits.string_bytes = bytes;
    limits.values = 262144;
    return limits;
}
std::string encode(const V &v) {
    return json::dump(v, output_limits());
}
std::string digest(const V &v) {
    const auto text = encode(v);
    unsigned char bytes[32];
    sha256(reinterpret_cast<const unsigned char *>(text.data()), text.size(), bytes);
    const char alphabet[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (auto byte : bytes) {
        out += alphabet[byte >> 4];
        out += alphabet[byte & 15];
    }
    return out;
}
const char *profile_name(NtfsFileProfile profile) {
    switch (profile) {
    case NtfsFileProfile::Automatic:
        return "auto";
    case NtfsFileProfile::Version30:
        return "3.0";
    case NtfsFileProfile::Version31:
        return "3.1";
    }
    throw std::invalid_argument("ntfs_file_profile");
}
V limits_value(const NtfsCaptureLimits &l) {
    return V::object()
        .put("read_requests", exact(l.read_requests))
        .put("read_bytes", exact(l.read_bytes))
        .put("retained_bytes", exact(l.retained_bytes))
        .put("attributes", exact(l.attributes))
        .put("runs", exact(l.runs))
        .put("output_bytes", exact(l.output_bytes));
}
bool same_region(const NtfsFileRegion &a, const NtfsFileRegion &b) {
    return a.offset == b.offset && a.requested == b.requested && a.error == b.error &&
           a.seek_attempted == b.seek_attempted && a.read_attempted == b.read_attempted &&
           a.refusal == b.refusal && a.bytes == b.bytes;
}
bool version(const V &value, const char *minor) {
    const auto info = value.find("volume_information");
    const auto major_value = info ? info->find("major") : nullptr;
    const auto minor_value = info ? info->find("minor") : nullptr;
    return major_value && minor_value && major_value->kind == V::Kind::string &&
           minor_value->kind == V::Kind::string && major_value->text == "3" &&
           minor_value->text == minor;
}
#ifdef DISKED_NTFS_FILE_TESTING
template <class Callback> void test_callback(const Callback &callback) {
    try {
        callback();
    } catch (const local_file::Error &) {
        throw;
    } catch (...) {
        throw local_file::Error("ntfs_file_test_callback", ERROR_INVALID_DATA);
    }
}
#endif
NtfsFileRead capture(const NtfsFileRequest &input, const std::function<bool()> &stop
#ifdef DISKED_NTFS_FILE_TESTING
                     ,
                     const NtfsFileTestControl *control_input
#endif
) {
    const NtfsFileRequest held = input;
    const auto stop_callback = stop;
#ifdef DISKED_NTFS_FILE_TESTING
    const auto control = control_input ? *control_input : NtfsFileTestControl{};
#endif
    const auto selector = std::string(profile_name(held.profile));
    const auto maximum = static_cast<std::uint64_t>(MAXLONGLONG);
    if (held.volume_offset > maximum || held.volume_bytes > maximum - held.volume_offset)
        throw std::invalid_argument("ntfs_file_seek_range");
    NtfsCaptureRequest request;
    request.source_id = "ntfs-pending";
    request.epoch = 1;
    request.source_bytes = maximum;
    request.volume_offset = held.volume_offset;
    request.volume_bytes = held.volume_bytes;
    request.minor = held.profile == NtfsFileProfile::Version30 ? 0 : 1;
    request.limits = held.limits;
    validate_ntfs_capture_request(request);
    if (held.expected_source.kind != V::Kind::null && held.expected_source.kind != V::Kind::object)
        throw std::invalid_argument("ntfs_file_expected_source");
    try {
        json::dump(held.expected_source, output_limits(8192));
    } catch (const json::Error &) {
        throw std::invalid_argument("ntfs_file_expected_source");
    }
    const auto path = local_file::path_for(held.path);
    auto parents = local_file::pin_parents(path);
    const auto generations = local_file::parent_generations(parents);
    local_file::Handle file(CreateFileW(
        path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_RANDOM_ACCESS,
        nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw local_file::Error("ntfs_file_open", GetLastError());
    V before;
    bool bindings_ok = true, cancelled = false;
    std::string binding_error;
    DWORD binding_platform = 0;
    std::size_t checks = 0;
    auto note_binding_error = [&](const local_file::Error &error) {
        bindings_ok = false;
        if (binding_error.empty()) {
            binding_error = error.what();
            binding_platform = error.platform_code;
        }
    };
    auto check = [&] {
        ++checks;
        try {
#ifdef DISKED_NTFS_FILE_TESTING
            if (control.before_binding)
                test_callback([&] { control.before_binding(checks); });
#endif
            bool requested = false;
            try {
                requested = stop_callback && stop_callback();
            } catch (...) {
                throw local_file::Error("ntfs_file_cancel_callback");
            }
            if (requested) {
                cancelled = true;
                throw local_file::Error("ntfs_file_cancelled");
            }
            local_file::check_parents(path, parents, generations);
            local_file::ordinary(file.value, false);
            local_file::bind_path(file.value, path);
            if (before.kind == V::Kind::object &&
                encode(local_file::metadata(file.value).value) != encode(before))
                throw local_file::Error("ntfs_file_source_changed");
        } catch (const local_file::Error &e) {
            note_binding_error(e);
            throw;
        }
    };
    check();
    const auto metadata = local_file::metadata(file.value);
    before = metadata.value;
    if (held.expected_source.kind != V::Kind::null &&
        encode(before) != encode(held.expected_source))
        throw local_file::Error("ntfs_file_source_changed");
    request.source_bytes = metadata.size;
    validate_ntfs_capture_request(request);
    static std::atomic<std::uint64_t> sequence{0};
    auto previous = sequence.load();
    for (;;) {
        if (previous == std::numeric_limits<std::uint64_t>::max())
            throw std::runtime_error("ntfs_file_epoch_exhausted");
        if (sequence.compare_exchange_weak(previous, previous + 1))
            break;
    }
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
        throw local_file::Error("ntfs_file_process", GetLastError());
    const auto pid = static_cast<std::uint64_t>(GetCurrentProcessId());
    const auto process_created =
        (static_cast<std::uint64_t>(created.dwHighDateTime) << 32) | created.dwLowDateTime;
    request.source_id = digest(before);
    request.epoch = previous + 1;
    std::deque<NtfsFileRegion> regions;
    RegionReader reader = [&](const de_byte_extent &extent) {
        const auto start = native(extent.start), end = native(extent.end);
        if (!extent.space || extent.space->logical_block_bytes != 1 ||
            native(extent.space->blocks) != metadata.size ||
            std::string(extent.space->name, extent.space->name_length) != request.source_id ||
            start < request.volume_offset || end <= start || end - start > 49152 ||
            end > metadata.size || end - request.volume_offset > request.volume_bytes)
            throw std::logic_error("ntfs_file_extent");
        NtfsFileRegion region;
        region.offset = start;
        region.requested = static_cast<std::size_t>(end - start);
        try {
            check();
            region.seek_attempted = true;
            LARGE_INTEGER at{};
            at.QuadPart = static_cast<LONGLONG>(start);
            if (!SetFilePointerEx(file.value, at, nullptr, FILE_BEGIN))
                region.error = GetLastError();
            else {
                region.bytes.resize(region.requested);
                region.read_attempted = true;
                DWORD got = 0;
                if (!ReadFile(file.value, region.bytes.data(), static_cast<DWORD>(region.requested),
                              &got, nullptr))
                    region.error = GetLastError();
                if (got > region.requested) {
                    region.bytes.clear();
                    throw local_file::Error("ntfs_file_read_count", ERROR_INVALID_DATA);
                }
                region.bytes.resize(static_cast<std::size_t>(got));
            }
#ifdef DISKED_NTFS_FILE_TESTING
            if (control.after_read)
                test_callback([&] { control.after_read(regions.size() + 1, region); });
#endif
            check();
        } catch (const local_file::Error &e) {
            region.error = e.platform_code;
            region.refusal = e.what();
        }
        regions.push_back(std::move(region));
        const auto &saved = regions.back();
        if (!saved.refusal.empty())
            throw local_file::Error(saved.refusal.c_str(), saved.error);
        if (saved.error)
            throw local_file::Error("ntfs_file_read", saved.error);
        return de_view{saved.bytes.data(), saved.bytes.size()};
    };
    const auto probe = observe_ntfs_bootstrap(request, reader);
    V after, final;
    auto after_check = [&](V &value, bool hook) {
        try {
            check();
            value = local_file::metadata(file.value).value;
#ifdef DISKED_NTFS_FILE_TESTING
            if (hook && control.after_metadata)
                test_callback([&] { control.after_metadata(value); });
#else
            (void)hook;
#endif
            check();
        } catch (const local_file::Error &error) {
            note_binding_error(error);
        }
    };
    after_check(after, true);
    std::size_t replay_passes = 0, replay_calls = 0;
    struct Replay {
        V value;
        bool equal = false;
    };
    auto replay = [&](const NtfsCaptureRequest &selected) {
        ++replay_passes;
        std::deque<NtfsFileRegion> buffers;
        std::size_t used = 0;
        bool trace_equal = true;
        RegionReader retained = [&](const de_byte_extent &extent) {
            if (used == regions.size()) {
                trace_equal = false;
                throw std::runtime_error("ntfs_file_replay_missing");
            }
            const auto &original = regions[used++];
            auto region = original;
#ifdef DISKED_NTFS_FILE_TESTING
            ++replay_calls;
            if (control.before_replay) {
                try {
                    control.before_replay(replay_calls, region);
                } catch (...) {
                    trace_equal = false;
                    throw;
                }
            }
#else
            ++replay_calls;
#endif
            if (!same_region(original, region))
                trace_equal = false;
            const auto start = native(extent.start), end = native(extent.end);
            if (start != region.offset || end < start || end - start != region.requested) {
                trace_equal = false;
                throw std::runtime_error("ntfs_file_replay_extent");
            }
            if (!region.refusal.empty())
                throw local_file::Error(region.refusal.c_str(), region.error);
            if (region.error)
                throw local_file::Error("ntfs_file_read", region.error);
            buffers.push_back(std::move(region));
            return de_view{buffers.back().bytes.data(), buffers.back().bytes.size()};
        };
        auto value = observe_ntfs_bootstrap(selected, retained);
        return Replay{std::move(value), trace_equal && used == regions.size()};
    };
    auto observation = probe;
    bool profile_equal = true;
    bool selected = held.profile != NtfsFileProfile::Automatic || version(probe, "1");
    if (held.profile == NtfsFileProfile::Automatic && probe.fields.at("complete").boolean &&
        probe.fields.at("diagnostic").text == "ntfs_volume_version" && version(probe, "0")) {
        request.minor = 0;
        auto choice = replay(request);
        auto expected = probe;
        expected.put("requested_minor", exact(0))
            .put("applicable", flag(true))
            .put("diagnostic", V::string(""));
        expected.fields.at("volume_information").put("profile_matches", flag(true));
        profile_equal = choice.equal && encode(choice.value) == encode(expected);
        selected = profile_equal;
        observation = std::move(choice.value);
    }
    auto repeated = replay(request);
    const bool replay_equal = repeated.equal && encode(repeated.value) == encode(observation);
    after_check(final, false);
    const bool metadata_complete = after.kind == V::Kind::object && final.kind == V::Kind::object;
    const bool metadata_equal =
        metadata_complete && encode(before) == encode(after) && encode(before) == encode(final);
    const bool stable = bindings_ok && metadata_equal && replay_equal && profile_equal &&
                        selected && observation.fields.at("applicable").boolean;
    if (!bindings_ok || !metadata_equal || !replay_equal || !profile_equal || !selected) {
        observation.put("applicable", flag(false))
            .put("binding_diagnostic", V::string(!profile_equal ? "ntfs_file_profile_disagreement"
                                                 : !selected    ? "ntfs_file_profile_unresolved"
                                                             : "ntfs_file_binding_disagreement"));
    }
    const auto profile = selected ? V::string(request.minor ? "3.1" : "3.0") : V{};
    auto domain = V::object()
                      .put("provider", V::string("ntfs-file-prototype"))
                      .put("process_id", exact(pid))
                      .put("process_created", exact(process_created))
                      .put("sequence", exact(request.epoch))
                      .put("source", before)
                      .put("volume_offset", exact(request.volume_offset))
                      .put("volume_bytes", exact(request.volume_bytes))
                      .put("selector", V::string(selector))
                      .put("selected_profile", profile)
                      .put("limits", limits_value(request.limits));
    const auto capture_domain = digest(domain);
    auto capture = V::object()
                       .put("source_before", before)
                       .put("source_after", after)
                       .put("source_final", final)
                       .put("parent_generations", generations)
                       .put("source_identity_digest", V::string(request.source_id))
                       .put("process_id", exact(pid))
                       .put("process_created", exact(process_created))
                       .put("sequence", exact(request.epoch))
                       .put("capture_domain", V::string(capture_domain))
                       .put("domain", std::move(domain))
                       .put("selector", V::string(selector))
                       .put("selected_profile", profile)
                       .put("profile_probe_minor",
                            exact(probe.fields.at("requested_minor").text == "0" ? 0 : 1))
                       .put("profile_probe_diagnostic", probe.fields.at("diagnostic"))
                       .put("profile_selection_equal", flag(profile_equal))
                       .put("replay_equal", flag(replay_equal))
                       .put("retained_replays", exact(replay_passes))
                       .put("replay_calls", exact(replay_calls))
                       .put("metadata_complete", flag(metadata_complete))
                       .put("metadata_equal", flag(metadata_equal))
                       .put("binding_checks_ok", flag(bindings_ok))
                       .put("binding_checks", exact(checks))
                       .put("binding_error", V::string(binding_error))
                       .put("binding_platform_error", exact(binding_platform))
                       .put("cancel_observed", flag(cancelled))
                       .put("observed_stable", flag(stable))
                       .put("atomic_snapshot", flag(false))
                       .put("source_consistency", V::string("live-uncoordinated"));
    NtfsFileRead result;
    result.result = V::object()
                        .put("schema", V::string("org.disked.ntfs-file-capture/1"))
                        .put("observation", std::move(observation))
                        .put("capture", std::move(capture))
                        .put("authorizes_effects", flag(false))
                        .put("product_dispatch_admitted", flag(false));
    for (auto &region : regions)
        result.regions.push_back(std::move(region));
    encode(result.result);
    return result;
}
} // namespace
NtfsFileRead capture_ntfs_file_owned(const NtfsFileRequest &request,
                                     const std::function<bool()> &stop) {
    return capture(request, stop
#ifdef DISKED_NTFS_FILE_TESTING
                   ,
                   nullptr
#endif
    );
}
#ifdef DISKED_NTFS_FILE_TESTING
NtfsFileRead capture_ntfs_file_testing(const NtfsFileRequest &request,
                                       const std::function<bool()> &stop,
                                       const NtfsFileTestControl &control) {
    return capture(request, stop, &control);
}
#endif
} // namespace disked
