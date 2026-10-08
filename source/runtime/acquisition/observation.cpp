#include "observation.h"
namespace disked {
WatchProfile acquisition_watch_profile(const json::Value& definition) {
    const auto plan=definition.find("plan");if(!plan)throw std::invalid_argument("acquisition_definition_shape");
    acquisition::prepare(*plan);
    return {"image-op:","org.disked.acquisition-operation-event/1","acquisition.operation",[definition](const json::Value& row) {
        acquisition_operation::validate_record(row,definition);
    },[](const json::Value& previous,const json::Value& next) {
        if(previous.find("phase")->text=="finished" ||
            std::stoull(next.find("checkpoint_bytes")->text)<std::stoull(previous.find("checkpoint_bytes")->text))
            throw std::invalid_argument("acquisition_worker_history_order");
    }};
}
}
