#include "verification_observation.h"
namespace disked {
WatchProfile verification_watch_profile(const json::Value& h) {
    verification_operation::validate_header(h);
    return {"verify-op:","org.disked.verification-operation-event/1","verify.operation",[h](const json::Value& row) {
        verification_operation::validate_record(row,h);
    },verification_operation::validate_progress,67584,8256};
}
}
