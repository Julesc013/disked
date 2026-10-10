#pragma once
#include "storage_queries.h"
#include "capture.h"
namespace disked { namespace nt_inventory {
enum class StorageSubjectKind {Disk,Volume};
struct StorageSubject {std::string key;std::wstring label;HANDLE handle=INVALID_HANDLE_VALUE;StorageSubjectKind kind=StorageSubjectKind::Disk;};
class StorageFrame;
std::shared_ptr<const StorageFrame> collect_storage_frame(const StorageQueryApi&,const std::vector<StorageSubject>&,std::uint64_t,
    const StorageQueryPolicy&,const std::function<bool()>& stop={});
// Immutable private value. Collection (also used for receipt reconstruction)
// owns construction; there is no public storage ABI.
class StorageFrame final {
    const json::Value value_;
    explicit StorageFrame(json::Value v):value_(std::move(v)) {}
    friend std::shared_ptr<const StorageFrame> collect_storage_frame(const StorageQueryApi&,const std::vector<StorageSubject>&,std::uint64_t,const StorageQueryPolicy&,const std::function<bool()>&);
public:
    const json::Value& value() const {return value_;}
};
// Pure projection authenticates no producer/process/media owner. The caller
// supplies fixture context or separately validated owned-session context.
GraphInput project_storage_frame(const StorageFrame&,const CaptureKey&,const std::string& context_digest,const json::Value& worker_context={});
}}
