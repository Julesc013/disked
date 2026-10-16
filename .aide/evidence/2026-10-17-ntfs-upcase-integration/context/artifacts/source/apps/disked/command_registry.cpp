#include "command_registry.h"
#include "bootstrap_registry.h"
namespace disked {
const Registry& command_registry() {
    static const Registry registry=compiled_registry(bootstrap::command_catalog_json,
        bootstrap::syntax_json,bootstrap::parameter_schemas_json);
    return registry;
}
}
