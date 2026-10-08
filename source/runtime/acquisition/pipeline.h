#pragma once
#include "json.h"
#include <cstdint>
#include <string>
#include <vector>

namespace disked { namespace acquisition {
// Private prototype values/ports. Not a public ABI or production journal format.
struct Error : std::runtime_error { using std::runtime_error::runtime_error; };
// Only output creation may use this type, after proving no output was created.
struct CreationRefusal : Error { using Error::Error; };
struct Plan {
    json::Value definition;
    std::string digest;
    std::uint64_t bytes=0;
    std::uint32_t chunk_bytes=0,retries=0;
    bool substitute=false,failing_media=false;
};
struct Grant {
    std::string plan_digest;
    bool source_read=false,destination_write=false,map_write=false,host_effects=false;
};
struct Read {
    std::vector<unsigned char> bytes;
    // Nonempty errors are bounded UTF-8 identifiers (<=256 bytes, no controls).
    std::string error;
};
struct Record {
    std::string bytes;
    bool complete=true,end=false;
};
struct Outcome;
// A provider owns locks and fresh identity checks throughout a call. It must
// reject aliases/no-clobber races before creating outputs. Each record is <=16KiB.
class Ports {
public:
    virtual ~Ports()=default;
    virtual json::Value observe()=0;
    virtual json::Value create_outputs(const Plan&)=0;
    virtual void open_resume()=0;
    virtual Record next_record()=0;
    // Before repairing a map tail or replaying an intent, reject destination
    // coverage that neither the checkpoint prefix nor pending range explains.
    virtual void validate_output_coverage(std::uint64_t checkpoint_end,std::uint64_t pending_end)=0;
    virtual void discard_incomplete_tail()=0;
    virtual void append_record(const std::string&)=0;
    virtual void flush_map()=0;
    virtual Read read_source(std::uint64_t,std::uint32_t)=0;
    virtual void write_destination(std::uint64_t,const std::vector<unsigned char>&)=0;
    virtual void flush_destination()=0;
    virtual Read read_destination(std::uint64_t,std::uint32_t)=0;
    virtual bool stop_requested()=0;
    // Private record v2 adds original capture provenance outside immutable plan.
    virtual json::Value capture_evidence() {return json::Value::object().put("clock",json::Value::string("unobserved")).put("started",json::Value{}).put("attempt_id",json::Value::string("fixture"));}
    virtual void original_capture(const json::Value&) {}
    // Only after destination verification and the complete checkpoint/map flush.
    virtual void checkpoint_observed(const Outcome&) {}
};
struct Outcome {
    std::string status="failed",diagnostic;
    std::uint64_t checkpoint_bytes=0,source_bytes=0,substituted_bytes=0;
    std::uint64_t attempt_read_bytes=0,attempt_written_bytes=0,attempt_verified_bytes=0;
    std::uint64_t records=0;
    bool uncertain_effect=false;
    json::Value report() const;
};
// Pure validation/definition: invokes no provider and creates no output.
Plan prepare(const json::Value&);
Outcome execute(const Plan&,const Grant&,Ports&,bool resume);
}}
