#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <process.h>
#include <io.h>
#include <atomic>
#include <memory>
#include "output.h"

namespace disked {
namespace {
struct Handle {
    HANDLE value=nullptr;
    ~Handle() {if(value && value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
};
struct Write {
    Handle output;
    std::string bytes;
    std::atomic<bool> stop{false},success{false};
    explicit Write(std::string value):bytes(std::move(value)) {}
    static unsigned __stdcall run(void* parameter) noexcept {
        std::unique_ptr<std::shared_ptr<Write>> owner(static_cast<std::shared_ptr<Write>*>(parameter));
        const auto state=*owner;owner.reset();
        std::size_t offset=0;
        while(offset<state->bytes.size() && !state->stop.load()) {
            DWORD written=0;
            if(!WriteFile(state->output.value,state->bytes.data()+offset,static_cast<DWORD>(state->bytes.size()-offset),&written,nullptr) ||
                written==0 || written>state->bytes.size()-offset)return 1;
            offset+=written;
        }
        state->success.store(offset==state->bytes.size());return 0;
    }
};
}
bool WindowsOutput::write(std::string bytes) noexcept {
    if(failed_)return false;
    failed_=true;
    try {
        if(bytes.size()>1048576)return false;
        const int descriptor=_fileno(stream_);if(descriptor<0)return false;
        const auto original=reinterpret_cast<HANDLE>(_get_osfhandle(descriptor));
        if(!original || original==INVALID_HANDLE_VALUE)return false;
        auto state=std::make_shared<Write>(std::move(bytes));
        if(!DuplicateHandle(GetCurrentProcess(),original,GetCurrentProcess(),&state->output.value,0,FALSE,DUPLICATE_SAME_ACCESS))return false;
        auto owner=std::unique_ptr<std::shared_ptr<Write>>(new std::shared_ptr<Write>(state));
        Handle thread;thread.value=reinterpret_cast<HANDLE>(_beginthreadex(nullptr,0,Write::run,owner.get(),0,nullptr));
        if(!thread.value)return false;owner.release();
        const auto observed=WaitForSingleObject(thread.value,3000);
        if(observed==WAIT_OBJECT_0 && state->success.load()) {failed_=false;return true;}
        state->stop.store(true);
        // This is only the presentation writer, never an operation worker.
        // Cancellation is a request and may lose a race with normal completion.
        // Shared state keeps the handle/buffer alive until actual thread exit.
        CancelSynchronousIo(thread.value);return false;
    } catch(...) {return false;}
}
}
