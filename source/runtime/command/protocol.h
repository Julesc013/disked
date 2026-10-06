#pragma once
#include "command.h"
#include <cstdio>
#include <functional>

namespace disked {
struct Outcome {
    json::Value response;
    int exit_code=0;
};
using Handler = std::function<Outcome(const std::string&,const std::string&,const json::Value&)>;
json::Value diagnostic(const std::string& code,json::Value parameters=json::Value::object());
Outcome completed(const std::string& request_id,json::Value result);
Outcome refused(const std::string& request_id,const std::string& code,int exit_code=2);
Outcome process_request(const Registry& registry,const std::string& frame,const Handler& handler);
bool write_response(FILE* output,const json::Value& response);
int serve(FILE* input,FILE* output,bool ndjson,const Registry& registry,const Handler& handler);
// Compatible observational reader. Retains the supplied value, including extensions.
// Returns an empty string only when known fields and required features are valid.
std::string validate_response(const json::Value& response);
int response_exit(const json::Value& response);
}
