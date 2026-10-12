#pragma once
#include "runtime/operation/gpt_execution.h"

namespace disked { namespace recovery { namespace proposal {
using Bytes=execution::proposal::Bytes;
// Distinct recovery adapter contract: old artifacts remain read-only, new journal
// is CREATE_NEW, and only a separately granted known fixture image is writable.
class GptRestorationPort:public execution::proposal::GptFixturePort {
public:
    virtual const json::Value& restoration_store() const=0;
    virtual Bytes read_original_journal()=0;
};
class GptFixtureRestoration final {
    execution::proposal::GptFixtureExecution original_;
    Bytes basis_,observed_,backup_,old_journal_;
    json::Value manifest_,definition_,inspection_;
    std::string digest_;
    std::vector<planner::proposal::GptRepairPatch> patches_;
public:
    // Read-only preparation. Stores owned immutable observed/original bytes.
    GptFixtureRestoration(const execution::proposal::GptFixtureExecution&,const Bytes& original_image,
        execution::proposal::GptFixturePort& readonly,const json::Value& original_review,
        const json::Value& original_grant,const std::string& attempt_id);
    const json::Value& definition() const {return definition_;}
    const std::string& digest() const {return digest_;}
    const std::string& journal_name() const;
    const json::Value& original_manifest() const {return manifest_;}
    json::Value prepare() const;
    // Pure validation must run before a recovery adapter can create its journal.
    void validate_grant(const json::Value& review,const json::Value& grant) const;
    json::Value execute(GptRestorationPort&,const json::Value& review,const json::Value& grant) const;
    // History/current observations only. The port must hold read-only file rights.
    json::Value inspect(GptRestorationPort&,const json::Value& review,const json::Value& grant) const;
};
// Reconstruct the historical proposal from retained immutable evidence, without
// observing today's image as the historical pre-restoration state.
GptFixtureRestoration retained_gpt_restoration(const execution::proposal::GptFixtureExecution&,
    const Bytes& original_image,const Bytes& observed_before,const Bytes& original_journal,
    const json::Value& manifest,const json::Value& original_review,const json::Value& original_grant,
    const json::Value& definition,const std::string& expected_digest);
}}}
