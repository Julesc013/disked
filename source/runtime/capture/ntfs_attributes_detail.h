#pragma once
// Private shared selection for ordinary streams and distinct FILE_NAME instances.
#include "ntfs_stream.h"
#include "portable/ntfs/ntfs.h"
#include <map>
#include <memory>
#include <vector>

namespace disked {
namespace ntfs_attributes_detail {
using V = json::Value;
struct Stop {
    const char *code;
};
[[noreturn]] void stop(const char *);
void checked(int);
std::uint64_t native(const de_u64 &);
de_u64 portable(std::uint64_t);
std::uint64_t add(std::uint64_t, std::uint64_t);
std::uint64_t mul(std::uint64_t, std::uint64_t);
V exact(std::uint64_t);
V flag(bool);
std::string hex(const unsigned char *, std::size_t);
std::string digest(const de_view &);
void validate(const NtfsStreamJoinRequest &, const std::vector<NtfsCapturedRecord> &,
              const NtfsCapturedAttributeList *);
struct Record {
    const NtfsCapturedRecord *input;
    de_ntfs_record header{};
    std::vector<unsigned char> logical;
    std::vector<de_ntfs_attribute> attributes;
};
struct Selected {
    Record *record;
    const de_ntfs_attribute *attribute;
};
class Selection {
  protected:
    const NtfsStreamJoinRequest request_;
    const std::vector<NtfsCapturedRecord> &inputs_;
    const NtfsCapturedAttributeList *external_list_;
    std::map<std::uint64_t, const NtfsCapturedRecord *> available_;
    std::map<std::uint64_t, std::unique_ptr<Record>> loaded_;
    std::vector<Selected> selected_;
    std::vector<std::uint64_t> missing_;
    V record_facts_ = V::array();
    std::size_t attributes_ = 0, entries_ = 0, runs_ = 0, charged_ = 4096;
    bool list_ = false, context_matches_ = false;
    bool external_list_bound_ = false;
    const bool filenames_;

    void charge(std::size_t);
    void prepare();
    Record &load(std::uint64_t);
    bool matches(const de_ntfs_attribute &) const;
    std::uint64_t low(const de_ntfs_attribute &) const;
    de_view list_value(const Record &, const de_ntfs_attribute &);
    void select();
    Selection(const NtfsStreamJoinRequest &, const std::vector<NtfsCapturedRecord> &,
              const NtfsCapturedAttributeList *, bool filenames);
};
} // namespace ntfs_attributes_detail
} // namespace disked
