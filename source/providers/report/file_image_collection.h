#pragma once
#include "image_collection.h"
#include <memory>
namespace disked {
// Explicit selected ordinary file only; never opens paths in retained records.
// Current file applicability is separate from the immutable historical snapshot.
// One owning coordinator serializes checks on the seek-based read handle.
class FileImageVerificationCollection final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileImageVerificationCollection(const std::string& path,const std::string& expected_artifact_digest);
    ~FileImageVerificationCollection();
    FileImageVerificationCollection(const FileImageVerificationCollection&)=delete;
    FileImageVerificationCollection& operator=(const FileImageVerificationCollection&)=delete;
    const evidence::proposal::ImageVerificationCollection& snapshot() const;
    json::Value binding() const;
    void check() const;
};
}
