#pragma once
#include "fat_tree_snapshot.h"

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
};
} // namespace disked
