#include "namespace_worker.h"
#include "volume_fixture.h"
#include "capture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
void print(const V& v) {std::puts(disked::json::dump(v,n::namespace_worker_limits()).c_str());std::fflush(stdout);}
V view(const disked::ObservationCapture& capture) {
    const auto s=capture.snapshot();const auto& source=s->sources.front();
    return V::object().put("capture",V::string(std::to_string(s->capture))).put("sequence",V::string(std::to_string(s->sequence)))
        .put("state",V::string(disked::source_state_name(source.state))).put("outstanding",V::boolean_value(source.outstanding))
        .put("reason",V::string(source.reason)).put("attempt_capture",V::string(std::to_string(source.attempt.capture)))
        .put("attempt_worker",V::string(std::to_string(source.attempt.worker)))
        .put("graph",disked::GraphSnapshot::create(s->graph,s->capture)->value());
}
bool replacement_refused(disked::ObservationCapture& capture) {
    try {capture.start("namespace");}
    catch(const std::invalid_argument& e) {if(std::string(e.what())=="capture_worker_outstanding")return true;throw;}
    return false;
}
// This is a test adapter for lifecycle only. An empty graph is deliberately
// used: namespace-to-node projection and physical identity are not qualified.
void consume(disked::ObservationCapture& capture,const disked::CaptureKey& key,const V& observed) {
    const auto& result=field(observed,"result");
    if(result.kind==V::Kind::object) {
        const auto status=field(result,"status").text;
        if(status=="complete")capture.update(key,{});
        else if(status=="partial" || status=="cancelled")capture.update(key,{},disked::SourceState::Partial,"namespace_"+status);
        else capture.update_failure(key,status=="denied"?disked::SourceState::Denied:disked::SourceState::Unavailable,"namespace_"+status);
    } else if(field(observed,"status").text=="unknown")capture.update_failure(key,disked::SourceState::Unavailable,"worker_result_unknown");
    // The owned session derives this from its bound process handle. A reply or
    // cancellation flag alone is never used as evidence of actual worker exit.
    if(field(field(observed,"worker"),"observation").text=="exited")capture.retired(key);
}
}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify) {
        return disked::nt_fixture::api(v,notify);
    });
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc!=1)return 2;
    try {
        char buffer[65536];const auto bytes=std::fread(buffer,1,sizeof(buffer),stdin);if(!bytes || bytes==sizeof(buffer) || std::ferror(stdin))return 2;
        disked::json::Limits limits;limits.bytes=65535;limits.values=16384;limits.depth=24;
        const auto input=disked::json::parse(std::string(buffer,bytes),limits);const auto mode=field(input,"mode").text;
        if(mode!="published" && mode!="superseded" && mode!="late" && mode!="before" && mode!="crash" && mode!="retire")throw std::invalid_argument("fixture_mode");
        disked::ObservationCapture capture({"namespace"});const auto key=capture.start("namespace");
        n::NamespaceInput request;request.capture_epoch=key.capture;request.provider_input=field(input,"fixture");
        auto session=n::NamespaceWorker::start(request);auto samples=V::array();
        auto sample=[&](const V& observed) {consume(capture,key,observed);samples.items.push_back(V::object().put("worker",observed).put("capture",view(capture)));};
        sample(session->observe());if(mode=="before")session->cancel();session->release();
        if(mode=="published") {
            const auto end=GetTickCount64()+1000;
            for(;;) {const auto observed=session->observe();if(field(observed,"status").text=="completed") {sample(observed);break;}
                if(GetTickCount64()>=end)throw std::runtime_error("fixture_reply_not_observed");Sleep(1);}
            const bool blocked=replacement_refused(capture);if(!blocked)throw std::runtime_error("fixture_replacement_not_refused");
            const auto before=view(capture);sample(session->observe());const bool duplicate_unchanged=disked::json::dump(before)==disked::json::dump(view(capture));
            sample(session->observe(1000));
            print(V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("samples",samples)
                .put("replacement_refused",V::boolean_value(blocked)).put("duplicate_unchanged",V::boolean_value(duplicate_unchanged)));return 0;
        }
        if(mode=="late" || mode=="superseded" || mode=="retire") {
            if(!session->wait_entered(1000))throw std::runtime_error("fixture_query_not_observed");
            if(mode=="superseded")capture.next_capture();else capture.timeout(key);
            sample(session->observe(1));if(!replacement_refused(capture))throw std::runtime_error("fixture_replacement_not_refused");
        }
        sample(mode=="retire"?session->retire():session->observe(1000));
        bool next_started=false;
        if(mode=="superseded") {const auto next=capture.start("namespace");next_started=next.capture==2 && next.worker==2;}
        print(V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("samples",samples).put("next_started",V::boolean_value(next_started)));return 0;
    }catch(const std::exception& e) {print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
