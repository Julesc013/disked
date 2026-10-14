#pragma once
#include "runtime/capture/region_reader.h"
#include "exfat_upcase.h"
#include "runtime/command/json.h"
#include "portable/exfat/exfat.h"
#include <cstdint>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace disked {
struct ExfatCaptureLimits {
    std::size_t read_requests = 8192, read_bytes = 2097152;
    std::size_t clusters = 4096, records = 4096, retained_bytes = 1048576;
    std::size_t output_bytes = 1048576;
};
struct ExfatCaptureRequest {
    std::string source_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    ExfatUpcaseFormat upcase_format = ExfatUpcaseFormat::Compressed;
    ExfatCaptureLimits limits;
};
// Supplied-reader observations only; no native opening or current-source grant.
void validate_exfat_capture_request(const ExfatCaptureRequest &);
json::Value observe_exfat_volume(const ExfatCaptureRequest &, const RegionReader &);
struct ExfatCapturedRegion {
    std::uint64_t start = 0;
    std::vector<unsigned char> bytes;
};
// Owned root/system observations, not a current-source or effect grant.
// Construction repeats the existing validated root capture, including rereads.
class ExfatVolumeCapture final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit ExfatVolumeCapture(std::unique_ptr<Impl>);

  public:
    static ExfatVolumeCapture read(const ExfatCaptureRequest &, const RegionReader &);
    ~ExfatVolumeCapture();
    ExfatVolumeCapture(ExfatVolumeCapture &&) noexcept;
    ExfatVolumeCapture &operator=(ExfatVolumeCapture &&) noexcept;
    ExfatVolumeCapture(const ExfatVolumeCapture &) = delete;
    ExfatVolumeCapture &operator=(const ExfatVolumeCapture &) = delete;
    bool valid() const;
    const ExfatCaptureRequest &request() const;
    const json::Value &report() const;
    const de_exfat_boot &boot() const;
    const std::vector<unsigned char> &bitmap() const;
    const std::vector<unsigned char> &upcase() const;
    unsigned long upcase_checksum() const;
    const std::set<std::uint32_t> &system_clusters() const;
    const std::vector<ExfatCapturedRegion> &regions() const;
};
} // namespace disked
