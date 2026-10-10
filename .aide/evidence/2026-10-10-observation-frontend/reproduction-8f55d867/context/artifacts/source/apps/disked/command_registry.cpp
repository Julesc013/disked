#include "command_registry.h"
#include "bootstrap_registry.h"
namespace disked {
const Registry& command_registry() {
    static const Registry registry{
        json::parse(bootstrap::command_catalog_json),
        json::parse(bootstrap::syntax_json),
        json::parse(bootstrap::parameter_schemas_json)};
    return registry;
}
}
