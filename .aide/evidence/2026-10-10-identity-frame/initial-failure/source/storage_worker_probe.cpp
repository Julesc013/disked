#include "storage_graph.h"
#include "namespace_graph.h"
#include "storage_fixture.h"
#include "volume_fixture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
#include <set>
namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
#if defined(DISKED_NT_IDENTITY_FRAME_TESTING)
const auto selected_profile=n::StorageFrameProfile::IdentityLayout;
#else
const auto selected_profile=n::StorageFrameProfile::Metadata;
#endif
std::unique_ptr<n::StorageGraphAdapter> adapter_for(disked::ObservationCapture& c,const char* source,const n::StorageQueryPolicy&){return std::unique_ptr<n::StorageGraphAdapter>(new n::StorageGraphAdapter(c,source,selected_profile));}
std::unique_ptr<n::NamespaceGraphAdapter> adapter_for(disked::ObservationCapture& c,const char* source,const n::InventoryPolicy&){return std::unique_ptr<n::NamespaceGraphAdapter>(new n::NamespaceGraphAdapter(c,source));}
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* k){const auto& x=get(v,k);if(x.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return x.text;}
V view(const disked::ObservationCapture& capture){
    const auto s=capture.snapshot();auto rows=V::array();for(const auto& source:s->sources)rows.items.push_back(V::object().put("id",V::string(source.id)).put("state",V::string(disked::source_state_name(source.state)))
        .put("outstanding",V::boolean_value(source.outstanding)).put("reason",V::string(source.reason)).put("attempt_capture",V::string(std::to_string(source.attempt.capture))).put("attempt_worker",V::string(std::to_string(source.attempt.worker))));
    return V::object().put("capture",V::string(std::to_string(s->capture))).put("sequence",V::string(std::to_string(s->sequence))).put("sources",rows).put("graph",disked::GraphSnapshot::create(s->graph,s->capture)->value());
}
void print(V v){v.put("pointer_bytes",V::string(std::to_string(sizeof(void*))));disked::json::Limits l;l.bytes=8388608;l.values=524288;std::puts(disked::json::dump(v,l).c_str());std::fflush(stdout);}
template<class Adapter,class Policy>V exercise(const V& input,const char* source,const Policy& policy){
    const auto mode=text(input,"mode");disked::ObservationCapture capture({source,"peer"},disked::GraphProfile::Observations);
    const auto peer=capture.start("peer");disked::GraphInput peer_graph;peer_graph.nodes.push_back({"fake:peer","block-device","fixture:peer","1","peer","current","4096",{}});capture.finish(peer,peer_graph);
    auto owner=adapter_for(capture,source,policy);Adapter& adapter=*owner;auto samples=V::array();auto errors=V::array();std::vector<std::shared_ptr<const disked::CaptureView>> retained;
    auto sample=[&](V worker){samples.items.push_back(V::object().put("worker",std::move(worker)).put("capture",view(capture)));};
    const auto& stages=get(input,"stages");if(stages.kind!=V::Kind::array || stages.items.empty() || stages.items.size()>8)throw std::invalid_argument("fixture_stages");
    for(auto stage:stages.items){
        if(!retained.empty())capture.next_capture();
        if(mode=="startup" || mode=="namespace-startup"){
            bool threw=false;try{adapter.start(policy,stage);}catch(const std::exception& e){threw=true;errors.items.push_back(V::string(e.what()));}
            if(!threw)throw std::runtime_error("fixture_expected_startup_error");sample(adapter.poll());
            if(capture.snapshot()->sources.front().outstanding){
                bool refused=false;try{adapter.start(policy,stage);}catch(const std::invalid_argument&){refused=true;}if(!refused)throw std::runtime_error("fixture_startup_replacement_allowed");sample(adapter.retire());
            }
            if(capture.snapshot()->sources.front().outstanding)throw std::runtime_error("fixture_startup_not_reconciled");
            capture.next_capture();stage.put("startup_fault",V::string(""));adapter.start(policy,stage);sample(adapter.poll());adapter.release();sample(adapter.poll(1000));
        }else{
            adapter.start(policy,stage);sample(adapter.poll());if(mode=="cancel-before")adapter.cancel();adapter.release();
            if(mode=="late" || mode=="superseded" || mode=="retire" || mode=="cancel-during" || mode=="disconnect"){
                if(!adapter.wait_entered(1000))throw std::runtime_error("fixture_not_entered");
                if(mode=="superseded")capture.next_capture();else adapter.timeout();sample(adapter.poll(1));
            }
            if(mode=="disconnect"){print(samples.items.back());Sleep(INFINITE);}
            if(mode=="cancel-during")adapter.cancel();
            if(mode=="held"){
                const auto end=GetTickCount64()+1000;for(;;){auto w=adapter.poll();if(text(w,"status")=="completed"){sample(w);break;}if(GetTickCount64()>=end)throw std::runtime_error("fixture_reply_missing");Sleep(1);}
                const auto before=disked::json::dump(view(capture),n::storage_worker_limits());sample(adapter.poll());if(before!=disked::json::dump(view(capture),n::storage_worker_limits()))throw std::runtime_error("fixture_duplicate_publication");
                bool refused=false;try{adapter.start(policy,stage);}catch(const std::invalid_argument&){refused=true;}if(!refused)throw std::runtime_error("fixture_replacement_allowed");
            }
            sample(mode=="retire"?adapter.retire():adapter.poll(1000));
        }
        if(capture.snapshot()->sources.front().outstanding)throw std::runtime_error("fixture_reader_not_retired");retained.push_back(capture.snapshot());
    }
    auto old=V::array();for(const auto& x:retained)old.items.push_back(disked::GraphSnapshot::create(x->graph,x->capture)->value());
    return V::object().put("samples",samples).put("start_errors",errors).put("retained",old);
}
}
int wmain(int argc,wchar_t** argv){
#if defined(DISKED_NT_IDENTITY_FRAME_TESTING)
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
#endif
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_storage_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);});
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_fixture::api(v,notify);});
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try{
        char b[524289];const auto size=std::fread(b,1,sizeof(b),stdin);if(!size || size==sizeof(b) || std::ferror(stdin))return 2;
        auto l=n::storage_worker_limits();l.bytes=524288;const auto input=disked::json::parse(std::string(b,size),l);n::StorageQueryPolicy policy;
        const auto mode=text(input,"mode");std::set<std::string> modes={"sequence","startup","namespace-startup","read","late","superseded","retire","cancel-before","cancel-during","held","disconnect"};
#if defined(DISKED_NT_IDENTITY_FRAME_TESTING)
        modes.insert("read-legacy");
        if(const auto p=input.find("detail_policy")){
            const auto ids=text(*p,"identifiers"),parts=text(*p,"partitions");if(!disked::json::decimal_u64(ids) || !disked::json::decimal_u64(parts) || std::stoull(ids)>32 || std::stoull(parts)>64)throw std::invalid_argument("fixture_policy");
            policy.identifiers=static_cast<DWORD>(std::stoull(ids));policy.partitions=static_cast<DWORD>(std::stoull(parts));
        }
#endif
        if(!modes.count(mode))throw std::invalid_argument("fixture_mode");
        if(mode=="read" || mode=="read-legacy"){
            const auto frame=n::read_storage_frame(get(input,"snapshot"),get(input,"fixture"),1,policy,mode=="read-legacy"?n::StorageFrameProfile::Metadata:selected_profile);print(V::object().put("snapshot",frame->value()));return 0;
        }
        if(text(input,"mode")=="namespace-startup")print(exercise<n::NamespaceGraphAdapter>(input,"namespace",n::InventoryPolicy{}));
        else print(exercise<n::StorageGraphAdapter>(input,"storage",policy));return 0;
    }catch(const std::exception& e){print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
