#include "fat_file.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <atomic>
#include <deque>
#include <limits>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
std::string hex(const unsigned char *p, std::size_t n) {
    const char h[] = "0123456789abcdef";
    std::string out;
    for (std::size_t i = 0; i < n; ++i) {
        out += h[p[i] >> 4];
        out += h[p[i] & 15];
    }
    return out;
}
std::string digest(const unsigned char *p, std::size_t n) {
    unsigned char h[32];
    sha256(p, n, h);
    return "sha256:" + hex(h, 32);
}
std::string digest(const std::string &s) {
    return digest(reinterpret_cast<const unsigned char *>(s.data()), s.size());
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::runtime_error("fat_file_extent");
    return std::stoull(text);
}
struct Read {
    Bytes bytes;
    DWORD error = 0;
};
Read read(HANDLE file, std::uint64_t start, std::size_t count) {
    Read out;
    if (start > static_cast<std::uint64_t>(MAXLONGLONG) || count > 4096)
        throw std::runtime_error("fat_file_extent");
    LARGE_INTEGER at{};
    at.QuadPart = static_cast<LONGLONG>(start);
    if (!SetFilePointerEx(file, at, nullptr, FILE_BEGIN)) {
        out.error = GetLastError();
        return out;
    }
    out.bytes.resize(count);
    DWORD got = 0;
    if (count && !ReadFile(file, out.bytes.data(), static_cast<DWORD>(count), &got, nullptr))
        out.error = GetLastError();
    out.bytes.resize(out.error ? 0 : static_cast<std::size_t>(got));
    return out;
}
struct Region {
    std::uint64_t start;
    std::size_t count;
    Read first;
};
} // namespace

json::Value capture_fat_file(const std::string &input, std::uint64_t offset, std::uint64_t bytes,
                             std::uint32_t copy, const FatCaptureLimits &limits,
                             bool allocation_scan, bool auxiliary_checks,
                             const FatNameConsumer *namespace_consumer,
                             const std::vector<FatNameQuery> &namespace_queries,
                             const FatNamespaceLimits &namespace_limits) {
    const auto path = local_file::path_for(input);
    auto ancestors = local_file::pin_parents(path);
    const auto generations = local_file::parent_generations(ancestors);
    local_file::Handle file(CreateFileW(
        path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_RANDOM_ACCESS,
        nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw local_file::Error("fat_file_open", GetLastError());
    auto check = [&] {
        local_file::check_parents(path, ancestors, generations);
        local_file::ordinary(file.value, false);
        local_file::bind_path(file.value, path);
    };
    check();
    const auto before = local_file::metadata(file.value);
    static std::atomic<std::uint64_t> sequence{0};
    auto previous = sequence.load();
    for (;;) {
        if (previous == std::numeric_limits<std::uint64_t>::max())
            throw std::runtime_error("fat_capture_epoch_exhausted");
        if (sequence.compare_exchange_weak(previous, previous + 1))
            break;
    }
    const auto serial = previous + 1;
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
        throw local_file::Error("fat_capture_process", GetLastError());
    const auto process_created =
        (static_cast<std::uint64_t>(created.dwHighDateTime) << 32) | created.dwLowDateTime;
    const auto label = digest(json::dump(before.value));
    FatCaptureRequest request;
    request.source_id = label;
    request.epoch = serial;
    request.source_bytes = before.size;
    request.volume_offset = offset;
    request.volume_bytes = bytes;
    request.fat_copy = copy;
    request.limits = limits;
    request.allocation_scan = allocation_scan;
    request.auxiliary_checks = auxiliary_checks;
    request.namespace_consumer = namespace_consumer;
    request.namespace_queries = namespace_queries;
    request.namespace_limits = namespace_limits;
    std::deque<Region> regions;
    bool overlaps = true;
    auto observation = observe_fat_volume(request, [&](const de_byte_extent &extent) {
        check();
        const auto start = native(extent.start), end = native(extent.end);
        if (end < start || end - start > 4096 || end > before.size)
            throw std::runtime_error("fat_file_extent");
        Region region{start, static_cast<std::size_t>(end - start),
                      read(file.value, start, static_cast<std::size_t>(end - start))};
        for (const auto &prior : regions) {
            const auto first = std::max(start, prior.start),
                       last = std::min(start + region.first.bytes.size(),
                                       prior.start + prior.first.bytes.size());
            if (first < last &&
                !std::equal(region.first.bytes.begin() + static_cast<std::size_t>(first - start),
                            region.first.bytes.begin() + static_cast<std::size_t>(last - start),
                            prior.first.bytes.begin() +
                                static_cast<std::size_t>(first - prior.start)))
                overlaps = false;
        }
        regions.push_back(std::move(region));
        const auto &result = regions.back().first.bytes;
        return de_view{result.data(), result.size()};
    });
    auto manifest = V::array();
    bool equal = overlaps;
    std::size_t verified_bytes = 0;
    for (const auto &region : regions) {
        check();
        auto reread = read(file.value, region.start, region.count);
#ifdef DISKED_FAT_FILE_TESTING
        if (&region == &regions.front() &&
            GetEnvironmentVariableW(L"DISKED_FAT_TEST_VERIFY_CHANGED", nullptr, 0) &&
            !reread.bytes.empty())
            reread.bytes[0] ^= 1;
        if (&region == &regions.front() &&
            GetEnvironmentVariableW(L"DISKED_FAT_TEST_VERIFY_ERROR", nullptr, 0)) {
            reread.error = ERROR_READ_FAULT;
            reread.bytes.clear();
        }
#endif
        const bool matches = !region.first.error && !reread.error &&
                             region.first.bytes.size() == region.count &&
                             region.first.bytes == reread.bytes;
        equal = equal && matches;
        verified_bytes += reread.bytes.size();
        manifest.items.push_back(
            V::object()
                .put("source_offset", exact(region.start))
                .put("requested_bytes", exact(region.count))
                .put("captured_bytes", exact(region.first.bytes.size()))
                .put("sha256",
                     V::string(digest(region.first.bytes.data(), region.first.bytes.size())))
                .put("reread_sha256", V::string(digest(reread.bytes.data(), reread.bytes.size())))
                .put("reread_bytes", exact(reread.bytes.size()))
                .put("error", exact(region.first.error))
                .put("reread_error", exact(reread.error))
                .put("matches", V::boolean_value(matches)));
    }
    check();
    auto after = local_file::metadata(file.value);
#ifdef DISKED_FAT_FILE_TESTING
    if (GetEnvironmentVariableW(L"DISKED_FAT_TEST_METADATA_CHANGED", nullptr, 0))
        after.value.put("test_only_changed", V::boolean_value(true));
#endif
    const bool same = json::dump(before.value) == json::dump(after.value);
    const bool stable = !regions.empty() && equal && same;
    if (!stable && namespace_consumer) {
        // Preserve measured names/matches; a failed recapture withdraws lookup applicability.
        auto &names = observation.fields.at("namespace");
        names.put("capture_applicable", V::boolean_value(false));
        names.fields.at("diagnostics").items.push_back(V::string("file_recapture_not_applicable"));
        for (auto &directory : names.fields.at("directories").items)
            directory.put("model_complete", V::boolean_value(false));
        for (auto &query : names.fields.at("queries").items) {
            const auto status = query.fields.at("status").text;
            if (status == "unique" || status == "not_found") {
                query.put("status", V::string("incomplete"));
                query.fields.erase("entry_id");
            }
        }
    }
    auto receipt =
        V::object()
            .put("source_before", before.value)
            .put("source_after", after.value)
            .put("metadata_equal", V::boolean_value(same))
            .put("source_identity_digest", V::string(label))
            .put("capture_domain",
                 V::string(digest(json::dump(V::object()
                                                 .put("process", exact(GetCurrentProcessId()))
                                                 .put("process_created", exact(process_created))
                                                 .put("sequence", exact(serial))
                                                 .put("source", before.value)))))
            .put("path", V::string(input))
            .put("resolved_path", V::string(local_file::utf8(path)))
            .put("regions", std::move(manifest))
            .put("reread_bytes", exact(verified_bytes))
            .put("overlaps_equal", V::boolean_value(overlaps))
            .put("regions_equal", V::boolean_value(equal))
            .put("observed_stable", V::boolean_value(stable))
            .put("source_consistency", V::string("live-uncoordinated"))
            .put("atomic_snapshot", V::boolean_value(false))
            .put("whole_file_hashed", V::boolean_value(false));
    return V::object()
        .put("schema", V::string("org.disked.fat-file-capture/1"))
        .put("observation", observation)
        .put("capture", std::move(receipt))
        .put("authorizes_effects", V::boolean_value(false))
        .put("product_dispatch_admitted", V::boolean_value(false));
}
} // namespace disked
