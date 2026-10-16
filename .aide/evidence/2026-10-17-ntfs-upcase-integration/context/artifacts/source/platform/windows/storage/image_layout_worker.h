#pragma once
#include "observation_worker.h"
#include "providers/image/file_layout.h"

namespace disked { namespace nt_inventory {
class ImageLayoutWorker final {
    struct Impl;std::unique_ptr<Impl> impl_;
    explicit ImageLayoutWorker(std::unique_ptr<Impl>);
public:
    ~ImageLayoutWorker();ImageLayoutWorker(const ImageLayoutWorker&)=delete;ImageLayoutWorker& operator=(const ImageLayoutWorker&)=delete;
    static std::unique_ptr<ImageLayoutWorker> prepare(const FileLayoutInput&);
    void launch();void release();void cancel();bool never_launched() const;bool wait_entered(DWORD);
    json::Value observe(DWORD wait_ms=0);json::Value retire(DWORD wait_ms=2000);
    // Actual owned-session result only; a JSON record cannot construct this type.
    std::shared_ptr<const FileLayoutSnapshot> snapshot();
};
int image_layout_worker_role(int,wchar_t**);
}}
