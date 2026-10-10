#pragma once
#include "json.h"
namespace disked {
// Private policy model. Platform adapters must supply observed facts and exact
// composition availability; the fixture defaults are not runtime observations.
json::Value route_invocation(const json::Value& input);
struct InvocationHost {
    json::Value observations=json::Value::object();
    json::Value policy=json::Value::object();
    bool input_usable=false,output_usable=false,error_usable=false;
};
json::Value invocation_inputs(const InvocationHost& host,const json::Value& controls,bool command);
json::Value explain_invocation(const InvocationHost& host,const json::Value& inputs);
}
