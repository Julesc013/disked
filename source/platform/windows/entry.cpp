#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "invocation.h"
#include "cli.h"
#include <cstdio>
namespace disked {
int windows_entry(int argc,wchar_t** argv) {
    InvocationHost host;
    try {
        host=observe_windows_invocation();
        std::vector<std::string> arguments;
        for(int i=1;i<argc;++i) {
            const int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,nullptr,0,nullptr,nullptr);
            // Preserve an encoding error for the complete parser pass so later
            // valid --json controls still select structured error output.
            if(size==0) {arguments.emplace_back(1,static_cast<char>(0xff));continue;}
            std::string word(static_cast<std::size_t>(size),'\0');
            if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,&word[0],size,nullptr,nullptr))
                arguments.emplace_back(1,static_cast<char>(0xff));
            else {word.pop_back();arguments.push_back(std::move(word));}
        }
        return run_cli(arguments,host);
    } catch(const std::exception&) {
        if(host.error_usable)std::fputs("disked: internal_error\n",stderr);
        return 4;
    }
}
}
