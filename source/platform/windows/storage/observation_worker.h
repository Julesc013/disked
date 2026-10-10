#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include "json.h"
#include <functional>
#include <memory>

namespace disked { namespace nt_inventory {
// Compiled private reader policy, never selected from an external role/schema.
struct ObservationWorkerProfile {
    const char* prefix;const char* scope;const char* input_schema;const char* reply_schema;const char* observation_schema;
    const wchar_t* role;const char* attempt_prefix;const char* records_field;
    std::size_t input_mapping_bytes;json::Limits input_limits,provider_limits,reply_limits;
    std::function<void(const json::Value&)> validate_request;
    std::function<void(const json::Value&,const json::Value&)> validate_result;
};
using ObservationCollector=std::function<json::Value(const std::function<bool()>&)>;
using ObservationFactory=std::function<ObservationCollector(const json::Value&,const std::function<void()>&)>;
class ObservationWorker final {
    struct Impl;std::unique_ptr<Impl> impl_;
    explicit ObservationWorker(std::unique_ptr<Impl>);
public:
    ~ObservationWorker();ObservationWorker(const ObservationWorker&)=delete;ObservationWorker& operator=(const ObservationWorker&)=delete;
    // Complete allocation/pinning/serialization before any child is created.
    static std::unique_ptr<ObservationWorker> prepare(const json::Value& request,const ObservationWorkerProfile&);
    // The caller owns this object before launch, including any post-spawn throw.
    void launch();bool never_launched() const;
    json::Value observe(DWORD wait_ms=0);void release();void cancel();
    json::Value retire(DWORD wait_ms=2000);bool wait_entered(DWORD wait_ms);
};
int observation_worker_role(int,wchar_t**,const ObservationWorkerProfile&,const ObservationFactory&);
}}
