#pragma once
#include "raw_layout.h"
#include <cstdint>
#include <functional>
#include <string>

namespace disked {
namespace nt_inventory {class ImageLayoutWorker;}
struct FileLayoutInput {
    std::uint64_t capture_epoch=0;
    std::string path,expected_content_digest;
    std::uint32_t unit=512;
    json::Value expected_source;
    RawLayoutPolicy policy;
    json::Value fixture=json::Value::object();
};
struct FileLayoutRead {std::vector<unsigned char> bytes;json::Value snapshot;};
constexpr std::size_t file_layout_payload_bytes=16U*1024U*1024U;
void validate_file_layout_input(const FileLayoutInput&);
FileLayoutRead read_file_layout(const FileLayoutInput&,const std::function<bool()>& stop={});
json::Value file_layout_unavailable(const std::string& code,std::uint32_t platform=0);
// Pure reconstruction over copied bytes; authenticates no process by itself.
std::shared_ptr<const RawPartitionLayout> verify_file_layout_snapshot(const json::Value&,const FileLayoutInput&,const std::vector<unsigned char>&);
json::Limits file_layout_snapshot_limits();
class FileLayoutSnapshot final {
    const std::shared_ptr<const RawPartitionLayout> raw_;
    const json::Value receipt_,context_;
    FileLayoutSnapshot(std::shared_ptr<const RawPartitionLayout> r,json::Value receipt,json::Value context):
        raw_(std::move(r)),receipt_(std::move(receipt)),context_(std::move(context)) {}
    friend class nt_inventory::ImageLayoutWorker;
public:
    const RawPartitionLayout& raw() const{return *raw_;}
    const json::Value& receipt() const{return receipt_;}
    const json::Value& context() const{return context_;}
};
}
