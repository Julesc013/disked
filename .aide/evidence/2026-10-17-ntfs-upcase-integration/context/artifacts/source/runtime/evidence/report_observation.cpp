#include "report_observation.h"
namespace disked {
WatchProfile report_watch_profile(const json::Value& header) {
    report_operation::validate_header(header);
    return {"report-op:","org.disked.report-operation-event/1","report.operation",[header](const json::Value& row) {
        report_operation::validate_record(row,header);
    },report_operation::validate_progress,67584,8256};
}
}
