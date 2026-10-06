#include "policy.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
int main() {
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
    std::string input;int byte;
    while(input.size()<=65536 && (byte=std::getchar())!=EOF)input+=static_cast<char>(byte);
    try {
        const auto value=disked::json::parse(input);
        if(value.kind!=disked::json::Value::Kind::object)return 2;
        const auto text=disked::json::dump(disked::route_invocation(value));
        return std::fwrite(text.data(),1,text.size(),stdout)==text.size() && std::fflush(stdout)==0?0:4;
    } catch(const std::exception&) {return 2;}
}
