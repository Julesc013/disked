#pragma once
#include "observation_worker.h"
#include "providers/image/fat_tree_extraction.h"

namespace disked {
namespace nt_inventory {
class FatTreeExtractionWorker;
class FatTreeStore;
class FatTreeExtractionPreparation final {
    const json::Value definition_, owner_;
    const std::string digest_, publication_digest_;
    FatTreeExtractionPreparation(json::Value definition, json::Value owner, std::string digest,
                                 std::string publication)
        : definition_(std::move(definition)), owner_(std::move(owner)), digest_(std::move(digest)),
          publication_digest_(std::move(publication)) {
    }
    friend class FatTreeExtractionWorker;

  public:
    const json::Value &definition() const {
        return definition_;
    }
    const json::Value &owner() const {
        return owner_;
    }
    const std::string &digest() const {
        return digest_;
    }
};
// One owned prepare/approve/execute session. Publication and actual exit are
// distinct; unresolved owners retain all dependency handles and aggregate quota.
class FatTreeExtractionWorker final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit FatTreeExtractionWorker(std::unique_ptr<Impl>);

  public:
    ~FatTreeExtractionWorker();
    FatTreeExtractionWorker(const FatTreeExtractionWorker &) = delete;
    FatTreeExtractionWorker &operator=(const FatTreeExtractionWorker &) = delete;
    static std::unique_ptr<FatTreeExtractionWorker>
    prepare(const FatTreeExtractionRequest &, const json::Value &fixture = json::Value::object());
    void launch();
    // Attach the observed store before launch. It remains in the same passive
    // dependency closure if actual worker exit cannot be established.
    void retain_store(std::shared_ptr<const FatTreeStore>);
    void release();
    void cancel();
    bool never_launched() const;
    json::Value observe(DWORD wait_ms = 0);
    std::shared_ptr<const FatTreeExtractionPreparation> prepared() const;
    void grant(const FatTreeExtractionGrant &);
    json::Value retire(DWORD wait_ms = 2000);
    static std::size_t reap_retained();
};
int fat_tree_extraction_worker_role(int, wchar_t **);
json::Value fat_tree_extraction_worker_request(const FatTreeExtractionRequest &);
} // namespace nt_inventory
} // namespace disked
