#pragma once
#include "case_report.h"
#include <cstdint>

namespace disked { namespace evidence { namespace proposal {
// Typed selected content only; no constructor accepts arbitrary JSON/bytes.
class SupportArtifact final {
    std::string bytes_,digest_;json::Value description_;
public:
    SupportArtifact(const Case&,const json::Value& policy);
    const std::string& bytes() const {return bytes_;}
    const std::string& digest() const {return digest_;}
    const json::Value& description() const {return description_;}
};
class ExportDefinition final {
    SupportArtifact artifact_;json::Value definition_;std::string digest_;
public:
    ExportDefinition(const SupportArtifact&,const json::Value& resources);
    const SupportArtifact& artifact() const {return artifact_;}
    const json::Value& value() const {return definition_;}
    const std::string& digest() const {return digest_;}
};
struct ExportGrant {std::string definition_digest;bool report_write=false,host_effects=false;};
// Only an adapter which proves creation did not occur may throw this type.
struct CreationRefusal : Error {explicit CreationRefusal(const char* code):Error(code) {}};
class ExportPorts {
public:
    virtual ~ExportPorts()=default;
    virtual json::Value observe()=0;
    virtual void create()=0;
    virtual std::uint32_t write(std::uint64_t offset,const char* bytes,std::uint32_t size)=0;
    virtual void flush()=0;
    virtual std::string read(std::uint64_t offset,std::uint32_t size)=0;
    virtual std::uint64_t size()=0;
    virtual bool stop_requested()=0;
};
struct ExportOutcome {
    std::string status="refused",diagnostic,phase="admission",output_state="not_created",flush_state="not_attempted";
    std::uint64_t submitted=0,written=0,read=0,verified=0;
    bool written_known=true,uncertain_effect=false;
    json::Value view() const;
};
json::Limits export_definition_limits();
std::string export_digest(const std::string& bytes);
ExportOutcome execute_export(const ExportDefinition&,const ExportGrant&,ExportPorts&);
}}}
