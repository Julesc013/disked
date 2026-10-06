#include "protocol.h"
#include <iostream>
#include <fcntl.h>
#include <io.h>
int main() {
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
    std::string input;char byte;
    while(input.size()<=65536 && std::cin.get(byte))input+=byte;
    try {
        const auto value=disked::json::parse(input);
        const auto error=disked::validate_response(value);
        auto out=disked::json::Value::object().put("error",disked::json::Value::string(error))
            .put("exit",disked::json::Value::number(std::to_string(disked::response_exit(value))));
        if(error.empty())out.put("preserved",value);
        std::cout<<disked::json::dump(out)<<'\n';return 0;
    } catch(const std::exception&) {return 2;}
}
