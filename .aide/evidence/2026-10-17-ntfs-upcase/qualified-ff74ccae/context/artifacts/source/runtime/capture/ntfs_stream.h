#pragma once
#include "portable/primitives/view.h"
#include "runtime/command/json.h"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace disked {
// Capture assertions only. Native acquisition must establish their provenance.
struct NtfsStreamContext {
    std::string source_id;
    std::uint64_t epoch = 0, volume_offset = 0, volume_bytes = 0;
};
struct NtfsCapturedRecord {
    NtfsStreamContext context;
    std::uint64_t number = 0;
    de_view bytes{}; // Readable, stable borrowed original protected FILE bytes.
};
struct NtfsStreamJoinLimits {
    std::size_t records = 64, record_bytes = 262144, attributes = 512;
    std::size_t list_entries = 512, runs = 512, output_bytes = 1048576;
    std::size_t list_bytes = 262144;
};
struct NtfsStreamJoinRequest {
    NtfsStreamContext context;
    std::uint64_t base_reference = 0, volume_clusters = 0;
    std::uint32_t cluster_bytes = 4096, record_bytes = 1024, type = 0x80;
    unsigned major = 3, minor = 1;
    std::vector<unsigned char> name;
    NtfsStreamJoinLimits limits;
};
struct NtfsStreamRun {
    std::uint64_t vcn, clusters, lcn;
};
struct NtfsStreamPart {
    std::uint64_t reference, lowest_vcn, highest_vcn;
    unsigned instance;
};
struct NtfsJoinedStream {
    bool resident = false;
    std::uint32_t type = 0;
    std::vector<unsigned char> name, value;
    std::uint64_t allocated_bytes = 0, data_bytes = 0, initialized_bytes = 0;
    std::vector<NtfsStreamPart> parts;
    std::vector<NtfsStreamRun> runs;
};
struct NtfsStreamJoinResult {
    // Nonnull only for a complete supplied ordinary stream. Contains no views.
    std::unique_ptr<const NtfsJoinedStream> stream;
    // Unique unresolved selected references; neither retries nor source-access grants.
    std::vector<std::uint64_t> required_records;
    json::Value observation;
};
struct NtfsCapturedAttributeList {
    NtfsStreamContext context;
    std::uint64_t base_reference = 0;
    unsigned instance = 0;
    std::string base_record_sha256;
    de_view value{}; // Exact initialized logical value, with native provenance checked by caller.
};
NtfsStreamJoinResult join_ntfs_stream(const NtfsStreamJoinRequest &,
                                      const std::vector<NtfsCapturedRecord> &,
                                      const NtfsCapturedAttributeList * = nullptr);
} // namespace disked
