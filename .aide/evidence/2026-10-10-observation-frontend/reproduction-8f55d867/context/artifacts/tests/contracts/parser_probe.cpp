#include "command_registry.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <string>
#include <vector>

int main(int argc,char** argv_native) {
    using namespace disked;
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
    std::string input;int c=0;
    while(input.size()<=65536 && (c=std::fgetc(stdin))!=EOF)input.push_back(static_cast<char>(c));
    try {
        const auto value=json::parse(input);std::vector<std::string> argv;
        if(value.kind!=json::Value::Kind::array)return 2;
        for(const auto& word:value.items) {if(word.kind!=json::Value::Kind::string)return 2;argv.push_back(word.text);}
        json::Value result;
        if(argc==2 && std::string(argv_native[1])=="--complete") {
            if(argv.empty())return 2;
            const auto fragment=argv.back();argv.pop_back();
            result=complete_static(command_registry(),argv,fragment);
        } else result=parse_invocation(command_registry(),argv).normalized();
        const auto output=json::dump(result);
        if(std::fwrite(output.data(),1,output.size(),stdout)!=output.size() || std::fflush(stdout)!=0)return 4;
        return 0;
    } catch(const json::Error& error) {std::fprintf(stderr,"%s",error.code.c_str());return 2;}
}
