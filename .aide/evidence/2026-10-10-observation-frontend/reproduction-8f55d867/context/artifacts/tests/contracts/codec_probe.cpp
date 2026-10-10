#include "json.h"
#include <cstdio>
#include <string>
#include <io.h>
#include <fcntl.h>

int main() {
    using namespace disked::json;
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
    std::string input;int byte=0;
    while(input.size()<=65536 && (byte=std::fgetc(stdin))!=EOF) input.push_back(static_cast<char>(byte));
    try {
        const std::string out=dump(parse(input));
        return std::fwrite(out.data(),1,out.size(),stdout)==out.size() && std::fflush(stdout)==0 ? 0 : 4;
    } catch(const Error& error) {
        const auto response=Value::object().put("code",Value::string(error.code))
            .put("offset",Value::number(std::to_string(error.offset)));
        const auto text=dump(response);std::fwrite(text.data(),1,text.size(),stdout);return 2;
    }
}
