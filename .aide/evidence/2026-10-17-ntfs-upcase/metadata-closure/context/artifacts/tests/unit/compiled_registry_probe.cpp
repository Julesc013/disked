#include "runtime/command/command.h"
#include <iostream>
#include <stdexcept>

int main() {
    try {
        const std::string item(4096, 'x');
        std::string metadata="{\"records\":[";
        for (unsigned i=0; i<20; ++i) {
            if (i) metadata+=',';
            metadata+='"'+item+'"';
        }
        metadata+="]}";
        if (metadata.size()<=65536 || metadata.size()>262144) throw std::runtime_error("fixture_size");
        const auto registry=disked::compiled_registry("[{\"id\":\"fixture\"}]","{}",metadata);
        if (!registry.command("fixture") || registry.parameter_schemas.find("records")->items.size()!=20)
            throw std::runtime_error("compiled_catalog");
        unsigned checks=1;
        try {disked::json::parse(metadata);throw std::runtime_error("wire_budget_relaxed");}
        // The JSON codec reports frame_limit_exceeded; protocol framing uses
        // message_too_large before invoking that codec.
        catch (const disked::json::Error& e) {if (e.code!="frame_limit_exceeded")throw; ++checks;}
        try {disked::compiled_registry("[]","{}",std::string(262145,' '));throw std::runtime_error("compiled_budget_relaxed");}
        catch (const disked::json::Error& e) {if (e.code!="frame_limit_exceeded")throw; ++checks;}
        std::string values="{\"values\":[";
        for (unsigned i=0; i<33000; ++i) {if (i)values+=',';values+='0';}
        values+="]}";
        try {disked::compiled_registry("[]","{}",values);throw std::runtime_error("compiled_value_budget_relaxed");}
        catch (const disked::json::Error& e) {if (e.code!="value_limit_exceeded")throw; ++checks;}
        std::cout<<"{\"passed\":true,\"checks\":"<<checks<<"}\n";
        return checks==4 ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr<<error.what()<<'\n';return 1;
    }
}
