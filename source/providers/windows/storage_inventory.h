#pragma once
#include "storage_queries.h"
#include "capture.h"
namespace disked { namespace nt_inventory {
enum class StorageSubjectKind {Disk,Volume};
struct StorageSubject {std::string key;std::wstring label;HANDLE handle=INVALID_HANDLE_VALUE;StorageSubjectKind kind=StorageSubjectKind::Disk;};
class StorageFrame;
std::shared_ptr<const StorageFrame> collect_storage_frame(const StorageQueryApi&,const std::vector<StorageSubject>&,std::uint64_t,
    const StorageQueryPolicy&,const std::function<bool()>& stop={});
// Immutable locally produced value, with no deserialization or public ABI.
class StorageFrame final {
    const json::Value value_;
    explicit StorageFrame(json::Value v):value_(std::move(v)) {}
    friend std::shared_ptr<const StorageFrame> collect_storage_frame(const StorageQueryApi&,const std::vector<StorageSubject>&,std::uint64_t,const StorageQueryPolicy&,const std::function<bool()>&);
public:
    const json::Value& value() const {return value_;}
};
// The digest binds fixture context, not an authenticated worker or media owner.
GraphInput project_storage_frame(const StorageFrame&,const CaptureKey&,const std::string& fixture_context_digest);
}}
