#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "cli.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>

int wmain(int argc,wchar_t** argv) {
    // Machine bytes and framing never depend on the active Windows code page.
    _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);_setmode(_fileno(stderr),_O_BINARY);
    std::vector<std::string> arguments;
    for(int i=1;i<argc;++i) {
        const int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,nullptr,0,nullptr,nullptr);
        if(size==0) {std::fputs("disked: invalid_argument_encoding\n",stderr);return 2;}
        std::string word(static_cast<std::size_t>(size),'\0');
        if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,&word[0],size,nullptr,nullptr))return 2;
        word.pop_back();arguments.push_back(std::move(word));
    }
    DWORD input_mode=0,output_mode=0;
    const bool prompt_channel=GetConsoleMode(GetStdHandle(STD_INPUT_HANDLE),&input_mode) &&
        GetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE),&output_mode);
    return disked::run_cli(arguments,prompt_channel);
}
