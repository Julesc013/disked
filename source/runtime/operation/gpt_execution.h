#pragma once
#include "runtime/planner/gpt_repair.h"
#include "runtime/journal/codec.h"

namespace disked { namespace execution { namespace proposal {
using Bytes=planner::proposal::Bytes;
struct FixtureError:std::runtime_error {using std::runtime_error::runtime_error;};
// Private experiment port. Its concrete adapter can create new owned files only;
// the read-only reopen variant cannot execute these write methods.
class GptFixturePort {
public:
    virtual ~GptFixturePort()=default;
    virtual const json::Value& manifest() const=0;
    virtual void check_ownership()=0;
    virtual Bytes read_image(std::uint64_t offset,std::size_t bytes)=0;
    virtual void write_image(std::uint64_t offset,const Bytes&)=0;
    virtual void flush_image()=0;
    virtual Bytes read_backup()=0;
    virtual void write_backup(const Bytes&)=0;
    virtual void flush_backup()=0;
    virtual Bytes read_journal()=0;
    virtual void append_journal(const Bytes&)=0;
    virtual void flush_journal()=0;
};
// Immutable preparation and effect policy; no OS or concrete-provider imports.
// Controller declarations are test-fixture scope, never production authority.
class GptFixtureExecution final {
    planner::proposal::GptRepairCapture basis_;
    planner::proposal::GptRepairPlan plan_;
    Bytes backup_;
public:
    GptFixtureExecution(const planner::proposal::GptRepairCapture&,const std::string& expected_capture_digest,
        const planner::proposal::GptRepairSelection&);
    const planner::proposal::GptRepairPlan& plan() const {return plan_;}
    const Bytes& backup_bytes() const {return backup_;}
    json::Value prepare(const json::Value& manifest) const;
    json::Value execute(GptFixturePort&,const json::Value& review,const json::Value& grant,
        const std::string& cancel_at="none") const;
    // Current observations plus a strictly validated historical prefix. No writes.
    json::Value inspect(GptFixturePort&,const json::Value& review,const json::Value& grant) const;
};
}}}
