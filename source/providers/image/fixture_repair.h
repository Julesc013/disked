#pragma once
#include "gpt_execution.h"
#include <memory>

namespace disked { namespace image { namespace fixture {
struct Fault {std::string stage,action;};
// Test-only ordinary-file adapter. Execution factory is CREATE_NEW only.
// Read-only reopen requires the original prepared file/root generations.
class GptFiles final:public execution::proposal::GptFixturePort {
    struct Impl;std::unique_ptr<Impl> impl_;
    explicit GptFiles(std::unique_ptr<Impl>);
public:
    ~GptFiles();
    static std::unique_ptr<GptFiles> create(const std::string& parent,const execution::proposal::Bytes& image,
        const std::string& source_revision,const Fault& fault={});
    static std::unique_ptr<GptFiles> reopen_readonly(const json::Value& expected,const Fault& fault={});
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
};
}}}
