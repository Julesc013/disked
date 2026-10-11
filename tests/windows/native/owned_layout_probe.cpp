#include "image_layout_worker.h"
#include "storage_graph.h"
#include "layout_provenance.h"
#include "storage_fixture.h"
#include "local_file.h"
#include "memory_budget.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;namespace f=disked::local_file;
const V& get(const V& v,const char* k){auto p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return p.text;}
std::uint64_t integer(const V& v,const char* k){auto s=text(v,k);if(!disked::json::decimal_u64(s))throw std::invalid_argument("fixture_integer");return std::stoull(s);}
void print(V value){value.put("pointer_bytes",V::string(std::to_string(sizeof(void*))));auto l=n::storage_worker_limits();l.bytes=4194304;l.values=200000;l.depth=30;std::puts(disked::json::dump(value,l).c_str());}
V metadata(const std::string& input){
    const auto path=f::path_for(input);auto parents=f::pin_parents(path);const auto generation=f::parent_generations(parents);
    f::Handle h(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    if(h.value==INVALID_HANDLE_VALUE)throw f::Error("fixture_open",GetLastError());f::bind_path(h.value,path);f::check_parents(path,parents,generation);return f::metadata(h.value).value;
}
void mutate(const std::string& input,const std::string& mode){
    if(mode=="replace"){const auto path=f::path_for(input);const auto old=f::path_for(input+".old");if(!MoveFileExW(path.c_str(),old.c_str(),0) || !CopyFileW(old.c_str(),path.c_str(),TRUE))throw f::Error("fixture_replace",GetLastError());return;}
    const auto path=f::path_for(input);f::Handle h(CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    if(h.value==INVALID_HANDLE_VALUE)throw f::Error("fixture_mutate_open",GetLastError());f::ordinary(h.value,false);f::bind_path(h.value,path);
    DWORD wrote=0;const unsigned char b=0xa5;if(!WriteFile(h.value,&b,1,&wrote,nullptr) || wrote!=1)throw f::Error("fixture_mutate",GetLastError());
    if(mode=="size"){LARGE_INTEGER end{};end.QuadPart=513;if(!SetFilePointerEx(h.value,end,nullptr,FILE_BEGIN) || !SetEndOfFile(h.value))throw f::Error("fixture_mutate",GetLastError());}
    if(!FlushFileBuffers(h.value))throw f::Error("fixture_mutate",GetLastError());
}
template<class T> V finish(T& worker){
    auto samples=V::array();samples.items.push_back(worker.observe());if(!worker.wait_entered(1000))throw std::runtime_error("fixture_not_entered");worker.release();
    const auto end=GetTickCount64()+3000;V last;
    do{last=worker.observe(10);if(text(get(last,"worker"),"observation")=="exited")break;}while(GetTickCount64()<end);
    samples.items.push_back(last);if(text(get(last,"worker"),"observation")!="exited")samples.items.push_back(worker.retire());return samples;
}
V exercise(const V& input){
    if(const auto* p=input.find("binding"))if(p->find("domain") && text(*p,"domain")!="missing" && text(*p,"domain")!="foreign")throw std::invalid_argument("fixture_domain");
    const auto mode=text(input,"mode");if(mode!="compare" && mode!="image" && mode!="pending" && mode!="construction")throw std::invalid_argument("fixture_mode");
    disked::FileLayoutInput r;r.path=text(input,"image");const auto unit=integer(input,"unit");if(unit>0xffffffffULL)throw std::invalid_argument("fixture_unit");r.unit=static_cast<std::uint32_t>(unit);
    r.capture_epoch=input.find("file_capture")?integer(input,"file_capture"):1;r.expected_source=metadata(r.path);
    if(const auto p=input.find("expected_source"))r.expected_source=*p;
    if(const auto p=input.find("expected_content_digest"))r.expected_content_digest=p->text;
    if(const auto p=input.find("fixture"))r.fixture=*p;
    if(const auto p=input.find("policy")){const auto parts=integer(*p,"partitions"),nodes=integer(*p,"ebr_nodes");if(parts>0xffffffffULL || nodes>0xffffffffULL)throw std::invalid_argument("fixture_policy");r.policy.partitions=static_cast<unsigned>(parts);r.policy.ebr_nodes=static_cast<unsigned>(nodes);}
    auto image=n::ImageLayoutWorker::prepare(r);if(mode=="construction")return V::object().put("prepared",V::boolean_value(true)).put("never_launched",V::boolean_value(image->never_launched()));
    auto out=V::object();
    try{image->launch();}catch(const std::exception& e){out.put("startup_error",V::string(e.what())).put("never_launched",V::boolean_value(image->never_launched())).put("image_worker",image->observe());
        if(!image->never_launched())out.put("retirement",image->retire());return out;}
    f::Handle writer;if(const auto* p=input.find("source_fault")){
        const auto fault=p->text;if(fault=="writer_open"){const auto path=f::path_for(r.path);writer=f::Handle(CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));if(writer.value==INVALID_HANDLE_VALUE)throw f::Error("fixture_writer",GetLastError());}
        else if(fault=="content" || fault=="size" || fault=="replace")mutate(r.path,fault);else throw std::invalid_argument("fixture_source_fault");
    }
    if(mode=="pending"){
        if(!image->wait_entered(1000))throw std::runtime_error("fixture_not_entered");image->release();const auto before=image->observe(50);
        if(input.find("cancel")){image->cancel();out.put("cancelled",image->observe(10));}out.put("before",before).put("has_snapshot",V::boolean_value(bool(image->snapshot()))).put("retirement",image->retire());return out;
    }
    if(input.find("cancel"))image->cancel();out.put("image_samples",finish(*image));const auto file=image->snapshot();out.put("has_file_snapshot",V::boolean_value(bool(file)));
    if(file)out.put("raw",file->raw().value()).put("file_receipt",file->receipt()).put("file_context",file->context());
    if(mode=="image" || !file)return out;
    disked::ObservationCapture capture({"storage"},disked::GraphProfile::Observations);n::StorageGraphAdapter storage(capture,"storage",n::StorageFrameProfile::IdentityLayout);
    n::StorageQueryPolicy policy;const auto& fixture=get(input,"storage");storage.start(policy,fixture);const auto key=storage.key();
    auto samples=V::array();samples.items.push_back(storage.poll());
    if(input.find("timeout_storage"))storage.timeout();if(input.find("advance_before_storage"))capture.next_capture();storage.release();
    const auto end=GetTickCount64()+3000;V last;
    do{last=storage.poll(10);if(text(get(last,"worker"),"observation")=="exited")break;}while(GetTickCount64()<end);
    samples.items.push_back(last);if(text(get(last,"worker"),"observation")!="exited")samples.items.push_back(storage.retire());out.put("storage_samples",samples);
    const auto frame=storage.frame();auto sources=V::array();for(const auto& s:capture.snapshot()->sources)sources.items.push_back(V::object().put("id",V::string(s.id)).put("state",V::string(disked::source_state_name(s.state))).put("outstanding",V::boolean_value(s.outstanding)));
    out.put("capture_sources",sources).put("has_storage_snapshot",V::boolean_value(bool(frame)));if(!frame)return out;
    out.put("frame",frame->frame().value()).put("storage_context",frame->context()).put("capture_epoch",V::string(std::to_string(capture.snapshot()->capture)));
    n::OwnedLayoutBinding binding;binding.comparison={key,text(input,"subject"),n::storage_layout_frame_digest(frame->frame()),n::raw_layout_digest(file->raw())};
    binding.file_capture_digest=n::file_layout_capture_digest(*file);binding.file_context_digest=disked::digest_sha256(disked::json::dump(file->context()));binding.storage_context_digest=disked::digest_sha256(disked::json::dump(frame->context()));
    if(const auto* p=input.find("binding")){
        if(p->find("source"))binding.comparison.capture.source=text(*p,"source");if(p->find("capture"))binding.comparison.capture.capture=integer(*p,"capture");if(p->find("worker"))binding.comparison.capture.worker=integer(*p,"worker");
        if(p->find("domain")){if(text(*p,"domain")=="missing")binding.comparison.capture.domain.reset();else{disked::ObservationCapture foreign({"storage"},disked::GraphProfile::Observations);binding.comparison.capture.domain=foreign.epoch_domain();}}
        if(p->find("subject"))binding.comparison.subject=text(*p,"subject");if(p->find("frame_digest"))binding.comparison.frame_digest=text(*p,"frame_digest");if(p->find("raw_digest"))binding.comparison.raw_digest=text(*p,"raw_digest");
        for(const auto k:{"file_capture_digest","file_context_digest","storage_context_digest"})if(p->find(k)){if(std::string(k)=="file_capture_digest")binding.file_capture_digest=text(*p,k);else if(std::string(k)=="file_context_digest")binding.file_context_digest=text(*p,k);else binding.storage_context_digest=text(*p,k);}
    }
    const auto raw_hash=n::raw_layout_digest(file->raw()),frame_hash=n::storage_layout_frame_digest(frame->frame());V comparison;
    try{comparison=n::compare_owned_layout(*frame,*file,binding);}catch(const std::invalid_argument& e){out.put("status",V::string("refused")).put("join_error",V::string(e.what()));return out;}
    if(raw_hash!=n::raw_layout_digest(file->raw()) || frame_hash!=n::storage_layout_frame_digest(frame->frame()))throw std::runtime_error("fixture_changed_input");out.put("comparison",comparison).put("comparison_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
    if(input.find("advance_capture")){capture.next_capture();out.put("old_frame_available",V::boolean_value(bool(storage.frame())));}
    return out;
}
}
int wmain(int argc,wchar_t** argv){
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_image_layout_fixture_worker")return n::image_layout_worker_role(argc,argv);
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try{disked::WindowsMemoryBudget budget;if(!budget.ready())throw std::runtime_error(budget.error());std::vector<char> bytes(1048577);const auto got=std::fread(bytes.data(),1,bytes.size(),stdin);if(!got || got==bytes.size() || std::ferror(stdin))return 2;
        auto limits=n::storage_worker_limits();limits.bytes=1048576;limits.values=65536;limits.string_bytes=32768;auto out=exercise(disked::json::parse(std::string(bytes.data(),got),limits));const auto status=out.find("status");const bool refused=status && status->text=="refused";print(std::move(out));return refused?3:0;
    }catch(const std::exception& e){print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
