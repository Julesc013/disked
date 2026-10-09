#include "worker_files.h"
#include <cstdio>

// Owned ordinary-directory fixture only. No worker role, device or privilege.
int wmain(int argc,wchar_t** argv) {
    using namespace disked::worker_files;
    try {
        if(argc!=2)return 2;
        Directory directory(narrow(argv[1]));
        auto held=Value::object().put("event",Value::string("directory-held"))
            .put("pid",Value::string(std::to_string(GetCurrentProcessId())))
            .put("directory_id",Value::string(directory.identity));
        const auto message=disked::json::dump(held);std::puts(message.c_str());std::fflush(stdout);
        if(std::getchar()!='x')return 2;
        directory.empty();
        auto file=directory.open(L"fixture.records",GENERIC_READ|GENERIC_WRITE,0,CREATE_NEW);
        if(!file.valid())fail("operation_fixture_open");
        const std::string bytes="owned-worker-store\n";
        write_file(file.value,bytes,"directory_probe");
        if(read_file(file.value,1024)!=bytes)fail("operation_fixture_readback");
        auto result=Value::object().put("status",Value::string("completed"))
            .put("directory_id",Value::string(directory.identity))
            .put("held_directory_path",Value::string(narrow(final_path(directory.pinned.back().value))))
            .put("output_path",Value::string(narrow(final_path(file.value))));
        const auto output=disked::json::dump(result);std::puts(output.c_str());return 0;
    } catch(const Failure& error) {
        const auto result=Value::object().put("status",Value::string("refused"))
            .put("code",Value::string(error.what())).put("platform_code",Value::string(std::to_string(error.platform)));
        const auto output=disked::json::dump(result);std::puts(output.c_str());return 3;
    }
}
