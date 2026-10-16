#pragma once
#include "fat_tree_snapshot.h"
#include "runtime/capture/fat_content_stream.h"
#include "runtime/acquisition/fat_metadata.h"

namespace disked {
// One held ordinary Windows file/ancestor closure. No mount or output creation.
// Calls are synchronous and require owned process containment for UI admission.
class FatTreeFile {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    explicit FatTreeFile(const FatTreeInput &);
    ~FatTreeFile();
    FatTreeFile(const FatTreeFile &) = delete;
    FatTreeFile &operator=(const FatTreeFile &) = delete;
    json::Value next(const std::function<bool()> &stop = {});
    bool finished() const;
    // The key must name a file observed in this adapter's latest tree page.
    // Content stays bound to the same held source; no imported-frame admission.
    void start_content(const std::string &key);
    json::Value next_content(const FatContentStreamBudget & = FatContentStreamBudget{},
                             const std::function<bool()> &stop = {});
    bool content_finished() const;
    // Reobserve the exact record/long slots from this adapter's latest page.
    // Returns mapping candidates and source receipts, never destination effects.
    json::Value metadata_candidates(const std::string &key, const FatMetadataPolicy &,
                                    const std::function<bool()> &stop = {});
    // Explicit reinspection after a completed phase on the same held source.
    // Mints a fresh capture identity; never resumes an unfinished/uncertain read.
    void begin_reinspection();
};
json::Limits fat_tree_content_json_limits();
} // namespace disked
