#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "invocation.h"
#include "app.h"
#include "fake_worker.h"
#include "acquisition_worker.h"
#include "report_worker.h"
#include "verification_worker.h"
#include "output.h"
#include <cwchar>
#include <cstdio>
namespace disked {
#ifdef DISKED_CAPTURE_CAMPAIGN
int run_capture_campaign_producer(int argc,wchar_t** argv);
#endif
int windows_entry(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_verification_worker")==0)return run_verification_worker(argc,argv);
    if(argc>1 && std::wcscmp(argv[1],L"__disked_report_worker")==0)return run_report_worker(argc,argv);
    if(argc>1 && std::wcscmp(argv[1],L"__disked_acquisition_worker")==0)return run_acquisition_worker(argc,argv);
#ifdef DISKED_CAPTURE_CAMPAIGN
    if(argc>1 && std::wcscmp(argv[1],L"__disked_capture_probe")==0)return run_capture_campaign_producer(argc,argv);
#endif
    if(argc>1 && std::wcscmp(argv[1],L"__disked_fake_worker")==0)return run_fake_worker(argc,argv);
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
        return run_disked(arguments,host);
    } catch(const std::exception&) {
        if(host.error_usable)WindowsOutput(stderr).write("disked: internal_error\n");
        return 4;
    }
}
}
