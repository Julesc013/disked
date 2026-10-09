#include "watch.h"
#include <limits>

namespace disked {
using json::Value;
namespace {
void require(bool value,const char* reason) {if(!value)throw std::invalid_argument(reason);}
const std::string& text(const Value& value,const char* field) {
    const auto* p=value.find(field);require(p && p->kind==Value::Kind::string,"watch_event_shape");return p->text;
}
bool hex(const std::string& value,std::size_t count) {
    return value.size()==count && value.find_first_not_of("0123456789abcdef")==std::string::npos;
}
bool identity(const std::string& value,const std::string& prefix) {
    return value.compare(0,prefix.size(),prefix)==0 && hex(value.substr(prefix.size()),32);
}
std::uint64_t number(const std::string& value) {require(json::decimal_u64(value),"watch_sequence_invalid");return std::stoull(value);}
std::string optional(const Value& value,const char* key,const std::string& fallback="") {
    return value.find(key)?text(value,key):fallback;
}
Value event(const Value& record,const std::string& request,const std::string& observer,bool snapshot,const WatchProfile& profile) {
    const auto& state=*record.find("state");
    return Value::object().put("schema",Value::string("org.disked.event/1"))
        .put("operation_id",*state.find("binding")->find("operation_id")).put("sequence",*state.find("sequence"))
        .put("type",Value::string(snapshot?profile.event_prefix+".snapshot":profile.event_prefix+".record"))
        .put("payload",Value::object().put("schema",Value::string(profile.payload_schema))
            .put("request_id",Value::string(request)).put("observer_epoch",Value::string(observer)).put("record",record));
}
}
std::string validate_watch_parameters(const Value& parameters) {
    try {
        const auto after=number(optional(parameters,"after_sequence","0"));
        const auto worker=optional(parameters,"worker_epoch"),digest=optional(parameters,"after_digest");
        if(!worker.empty() && !identity(worker,"worker:"))return "invalid_parameter";
        if(!digest.empty() && !hex(digest,64))return "invalid_parameter";
        if(after && (worker.empty() || digest.empty()))return "watch_cursor_incomplete";
        if(!after && !digest.empty())return "watch_cursor_conflict";
        const auto* snapshot=parameters.find("snapshot");
        if(snapshot && snapshot->kind!=Value::Kind::boolean)return "invalid_parameter";
        if(snapshot && snapshot->boolean && after)return "watch_cursor_conflict";
        if(number(optional(parameters,"follow_ms","0"))>2000)return "invalid_parameter";
        return "";
    } catch(const std::invalid_argument&) {return "invalid_parameter";}
}
std::string validate_watch_event(const Value& value,const WatchProfile& profile) {
    try {
        json::Limits limits;limits.bytes=profile.event_byte_limit;limits.values=profile.event_value_limit;json::dump(value,limits);
        require(text(value,"schema")=="org.disked.event/1","watch_event_schema");
        if(const auto* required=value.find("required_features"))
            require(required->kind==Value::Kind::array && required->items.empty(),"unsupported_feature");
        const auto type=text(value,"type");require(type==profile.event_prefix+".record" || type==profile.event_prefix+".snapshot","watch_event_type");
        const auto* payload=value.find("payload");require(payload && payload->kind==Value::Kind::object,"watch_event_shape");
        require(text(*payload,"schema")==profile.payload_schema,"watch_event_schema");
        if(const auto* required=payload->find("required_features"))
            require(required->kind==Value::Kind::array && required->items.empty(),"unsupported_feature");
        const auto request=text(*payload,"request_id");require(!request.empty() && request.size()<=128 && request.find('\0')==std::string::npos,"watch_request_identity");
        require(identity(text(*payload,"observer_epoch"),"watch:"),"watch_observer_identity");
        const auto* record=payload->find("record");require(record && record->kind==Value::Kind::object && record->fields.size()==4,"watch_record_shape");
        profile.validate_record(*record);
        const auto* state=record->find("state");
        require(number(text(value,"sequence"))==number(text(*state,"sequence")) && text(value,"operation_id")==text(*state->find("binding"),"operation_id"),"watch_event_identity");
        return "";
    } catch(const json::Error& error) {return error.code;}
      catch(const std::invalid_argument& error) {return error.what();}
}
WatchProfile fake_watch_profile() {
    return {"fake-op:","org.disked.fake-operation-event/1","fake.operation",[](const Value& record) {
        require(record.kind==Value::Kind::object && record.fields.size()==4,"watch_record_shape");
        require(text(record,"schema")=="org.disked.fake-operation-record/1" && hex(text(record,"previous"),64) && hex(text(record,"digest"),64),"watch_record_shape");
        const auto* state=record.find("state");require(state && state->kind==Value::Kind::object,"watch_record_shape");fake_operation::validate_state(*state);
        auto unsigned_record=record;unsigned_record.fields.erase("digest");
        require(fake_operation::hash(json::dump(unsigned_record))==text(record,"digest"),"watch_record_digest");
    },{}};
}
std::string validate_fake_event(const Value& value) {return validate_watch_event(value,fake_watch_profile());}
WatchCursor::WatchCursor(const std::string& operation,const std::string& request,const std::string& observer,const Value& parameters,WatchProfile profile):
    operation_(operation),request_(request),observer_(observer),worker_(optional(parameters,"worker_epoch")),
    digest_(optional(parameters,"after_digest",std::string(64,'0'))),sequence_(number(optional(parameters,"after_sequence","0"))),profile_(std::move(profile)) {
    const auto error=validate_watch_parameters(parameters);require(error.empty(),error.c_str());
    require(identity(operation,profile_.operation_prefix),"watch_operation_identity");
    snapshot_=parameters.find("snapshot") && parameters.find("snapshot")->boolean;
}
std::vector<Value> WatchCursor::project(const fake_operation::History& history) {return project(history.state,history.records,history.digest);}
std::vector<Value> WatchCursor::project(const Value& state,const std::vector<Value>& records,const std::string& last_digest) {
    for(const auto& record:records)profile_.validate_record(record);
    const auto& binding=*state.find("binding");const auto worker=text(binding,"worker_epoch");
    require(text(binding,"operation_id")==operation_,"operation_identity_mismatch");
    require(worker_.empty() || worker_==worker,"watch_epoch_mismatch");
    require(sequence_<=records.size(),"watch_cursor_ahead");
    if(sequence_)require(text(records[static_cast<std::size_t>(sequence_-1)],"digest")==digest_,"watch_cursor_conflict");
    std::vector<Value> values;auto next=sequence_;auto digest=digest_;
    if(snapshot_) {require(!records.empty(),"operation_history_empty");values.push_back(event(records.back(),request_,observer_,true,profile_));next=records.size();digest=last_digest;}
    else for(std::size_t i=static_cast<std::size_t>(sequence_);i<records.size();++i) {
        values.push_back(event(records[i],request_,observer_,false,profile_));next=i+1;digest=text(records[i],"digest");
    }
    auto next_worker=worker;worker_.swap(next_worker);digest_.swap(digest);sequence_=next;snapshot_=false;return values;
}
WatchReader::WatchReader(const std::string& operation,const std::string& worker,const std::string& sequence,const std::string& digest,bool snapshot_allowed,WatchProfile profile):
    operation_(operation),worker_(worker),digest_(digest),sequence_(number(sequence)),snapshot_allowed_(snapshot_allowed),profile_(std::move(profile)) {
    require(identity(operation,profile_.operation_prefix) && (worker.empty() || identity(worker,"worker:")) && hex(digest,64),"watch_reader_identity");
    require(!sequence_ || !worker.empty(),"watch_cursor_incomplete");
    require(!snapshot_allowed || !sequence_,"watch_cursor_conflict");
    require(sequence_ || digest==std::string(64,'0'),"watch_cursor_conflict");
}
bool WatchReader::accept(const Value& value) {
    const auto error=validate_watch_event(value,profile_);require(error.empty(),error.c_str());
    const auto& payload=*value.find("payload");const auto& record=*payload.find("record");const auto& binding=*record.find("state")->find("binding");
    auto worker=text(binding,"worker_epoch"),digest=text(record,"digest"),observer=text(payload,"observer_epoch"),request=text(payload,"request_id");
    require(text(value,"operation_id")==operation_ && (worker_.empty() || worker_==worker),"watch_event_identity");
    require(binding_.kind==Value::Kind::null || json::dump(binding_)==json::dump(binding),"watch_event_binding_changed");
    require(observer_.empty() || (observer_==observer && request_==request),"watch_observer_changed");
    const auto next=number(text(value,"sequence"));
    if(next==sequence_) {require(digest==digest_,"watch_duplicate_conflict");return false;}
    if(text(value,"type")==profile_.event_prefix+".snapshot")require(snapshot_allowed_,"watch_snapshot_unrequested");
    else {
        require(sequence_!=(std::numeric_limits<std::uint64_t>::max)() && next==sequence_+1,"watch_sequence_gap");
        require(text(record,"previous")==digest_,"watch_cursor_conflict");
    }
    const auto& next_state=*record.find("state");
    if(state_.kind!=Value::Kind::null && profile_.validate_progress)profile_.validate_progress(state_,next_state);
    auto next_binding=binding;
    auto accepted_state=next_state;
    worker_.swap(worker);digest_.swap(digest);observer_.swap(observer);request_.swap(request);binding_=std::move(next_binding);state_=std::move(accepted_state);sequence_=next;snapshot_allowed_=false;return true;
}
json::Limits watch_event_limits(const Value& value) {
    const auto type=value.find("type");json::Limits limits;limits.bytes=16384;
    if(type && type->kind==Value::Kind::string) {
        if(type->text=="acquisition.operation.record" || type->text=="acquisition.operation.snapshot")limits.bytes=32768;
        else if(type->text=="report.operation.record" || type->text=="report.operation.snapshot") {limits.bytes=67584;limits.values=8256;}
    }
    return limits;
}
bool WatchQueue::push(const Value& value) {
    const auto limits=watch_event_limits(value);
    const auto bytes=json::dump(value,limits).size();
    std::lock_guard<std::mutex> lock(mutex_);if(closed_)return false;
    require(total_count_<64 && bytes<=1048576-total_bytes_,"watch_queue_limit");
    events_.push_back(value);++total_count_;total_bytes_+=bytes;return true;
}
bool WatchQueue::pop(Value& value) {
    std::lock_guard<std::mutex> lock(mutex_);if(events_.empty())return false;
    value=std::move(events_.front());events_.pop_front();return true;
}
void WatchQueue::close() {std::lock_guard<std::mutex> lock(mutex_);closed_=true;events_.clear();}
}
