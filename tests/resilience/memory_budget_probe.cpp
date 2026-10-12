#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "platform/windows/memory_budget.h"
#include "runtime/command/json.h"
#include <iostream>
int main() {
    using V=disked::json::Value;disked::WindowsMemoryBudget budget;auto value=V::object()
        .put("ready",V::boolean_value(budget.ready())).put("private_job",V::boolean_value(budget.uses_private_job()))
        .put("platform_code",V::string(std::to_string(budget.platform_error())))
        .put("allocation_bytes",V::string(std::to_string(budget.probe_bytes())))
        .put("error",budget.error()?V::string(budget.error()):V{});
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION actual{};
    if(budget.ready() || budget.uses_private_job()) {
        if(!QueryInformationJobObject(nullptr,JobObjectExtendedLimitInformation,&actual,sizeof(actual),nullptr))return 4;
        value.put("flags",V::string(std::to_string(actual.BasicLimitInformation.LimitFlags)))
            .put("process_bytes",V::string(std::to_string(actual.ProcessMemoryLimit)))
            .put("job_bytes",V::string(std::to_string(actual.JobMemoryLimit)))
            .put("active_limit",V::string(std::to_string(actual.BasicLimitInformation.ActiveProcessLimit)));
    }
    std::cout<<disked::json::dump(value)<<'\n';return budget.ready()?0:3;
}
