#pragma once
#include "runtime/recovery/gpt_restoration.h"
#include <memory>

namespace disked { namespace image { namespace fixture {
struct Fault {std::string stage,action;};
// Test-only ordinary-file adapter. Execution factory is CREATE_NEW only.
// Read-only reopen requires the original prepared file/root generations.
class GptFiles final:public recovery::proposal::GptRestorationPort {
    struct Impl;std::unique_ptr<Impl> impl_;
    explicit GptFiles(std::unique_ptr<Impl>);
public:
    ~GptFiles();
    static std::unique_ptr<GptFiles> create(const std::string& parent,const execution::proposal::Bytes& image,
        const std::string& source_revision,const Fault& fault={});
    static std::unique_ptr<GptFiles> reopen_readonly(const json::Value& expected,const Fault& fault={});
    // Separate granted restoration route. Original backup/journal stay read-only;
    // the image alone gains write rights and the recovery journal is CREATE_NEW.
    static std::unique_ptr<GptFiles> reopen_for_restoration(const json::Value& expected,
        const std::string& new_journal_name,const Fault& fault={});
    static std::unique_ptr<GptFiles> reopen_restoration_readonly(const json::Value& expected,
        const json::Value& expected_store,const Fault& fault={});
    const json::Value& manifest() const override;
    json::Value events() const;
    bool fault_fired() const;
    void check_ownership() override;
    execution::proposal::Bytes read_image(std::uint64_t,std::size_t) override;
    void write_image(std::uint64_t,const execution::proposal::Bytes&) override;
    void flush_image() override;
    execution::proposal::Bytes read_backup() override;
    void write_backup(const execution::proposal::Bytes&) override;
    void flush_backup() override;
    execution::proposal::Bytes read_journal() override;
    void append_journal(const execution::proposal::Bytes&) override;
    void flush_journal() override;
    const json::Value& restoration_store() const override;
    execution::proposal::Bytes read_original_journal() override;
};
}}}
