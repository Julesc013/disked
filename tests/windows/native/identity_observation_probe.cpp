#include "storage_identity.h"
#include "storage_graph.h"
#include "storage_fixture.h"
#include "memory_budget.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
#include <set>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
#ifdef DISKED_NT_COMPOSITE_METADATA_PROBE
constexpr auto profile=n::StorageFrameProfile::Metadata;
#else
constexpr auto profile=n::StorageFrameProfile::IdentityLayout;
#endif
const V& get(const V& v,const char* k){const auto* p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return p.text;}
std::uint64_t number(const V& v,const char* k){const auto s=text(v,k);if(!disked::json::decimal_u64(s))throw std::invalid_argument("fixture_number");return std::stoull(s);}
bool on(const V& v,const char* k){const auto* p=v.find(k);if(p && p->kind!=V::Kind::boolean)throw std::invalid_argument("fixture_shape");return p && p->boolean;}
void allowed(const V& v,const std::set<std::string>& keys){if(v.kind!=V::Kind::object)throw std::invalid_argument("fixture_shape");for(const auto& x:v.fields)if(!keys.count(x.first))throw std::invalid_argument("fixture_shape");}
void print(V value){auto limits=n::storage_identity_limits();limits.bytes=4194304;limits.values=200000;limits.depth=30;value.put("pointer_bytes",V::string(std::to_string(sizeof(void*))));std::puts(disked::json::dump(value,limits).c_str());}
V view(const disked::ObservationCapture& capture){const auto s=capture.snapshot();auto sources=V::array();for(const auto& source:s->sources)sources.items.push_back(V::object().put("state",V::string(disked::source_state_name(source.state))).put("outstanding",V::boolean_value(source.outstanding)));
    return V::object().put("capture",V::string(std::to_string(s->capture))).put("sources",sources);}
V exercise(const V& input){
    allowed(input,{"stages","comparison","reverse","same_capture","previous_subject","current_subject"});const auto& stages=get(input,"stages");if(stages.kind!=V::Kind::array || stages.items.empty() || stages.items.size()>8)throw std::invalid_argument("fixture_stages");
    on(input,"reverse");on(input,"same_capture");for(const auto k:{"previous_subject","current_subject"})if(input.find(k))text(input,k);
    if(const auto* p=input.find("comparison")){allowed(*p,{"previous_digest","current_digest","previous_subject","current_subject"});for(const auto& x:p->fields)text(*p,x.first.c_str());}
    for(const auto& stage:stages.items){allowed(stage,{"fixture","cancel","supersede","timeout","retire","pending","binding","live"});for(const auto k:{"cancel","supersede","timeout","retire","pending","live"})on(stage,k);
        if(const auto* p=stage.find("binding")){allowed(*p,{"source","capture","worker","frame_digest","context_digest"});for(const auto& x:p->fields)if(x.first=="capture" || x.first=="worker")number(*p,x.first.c_str());else text(*p,x.first.c_str());}
        n::StorageInput r;r.capture_epoch=1;r.profile=profile;r.provider_input=get(stage,"fixture");n::validate_storage_input(r);}
    disked::ObservationCapture capture({"storage"},disked::GraphProfile::Observations);n::StorageGraphAdapter adapter(capture,"storage",profile);
    auto observed=V::array();std::vector<std::shared_ptr<const n::StorageIdentityObservation>> retained;bool refused=false;
    for(const auto& stage:stages.items){
        if(!observed.items.empty() && !on(input,"same_capture"))capture.next_capture();auto row=V::object();
        try{adapter.start(n::StorageQueryPolicy{},get(stage,"fixture"));}catch(const std::exception& e){row.put("startup_error",V::string(e.what()));auto sample=adapter.poll();row.put("worker",sample);if(text(get(sample,"worker"),"observation")!="not_started")row.put("retirement",adapter.retire());row.put("capture",view(capture)).put("identity_available",V::boolean_value(false));observed.items.push_back(std::move(row));retained.push_back({});continue;}
        auto samples=V::array();samples.items.push_back(adapter.poll());if(on(stage,"cancel"))adapter.cancel();adapter.release();
        if(on(stage,"live")){
            const auto deadline=GetTickCount64()+1000;V live;do{live=adapter.poll(1);if(text(live,"status")=="completed")break;}while(GetTickCount64()<deadline);
            row.put("live_worker",live);const auto frame=adapter.frame();if(!frame)throw std::runtime_error("fixture_live_frame_missing");
            const auto before=disked::json::dump(view(capture));n::IdentityBinding binding{frame->key(),disked::digest_sha256(disked::json::dump(frame->frame().value(),n::storage_observation_limits())),disked::digest_sha256(disked::json::dump(frame->context()))};
            const auto identity=n::observe_storage_identity(*frame,binding);if(before!=disked::json::dump(view(capture)))throw std::runtime_error("fixture_derivation_changed_capture");
            row.put("live_identity_digest",V::string(n::storage_identity_digest(*identity))).put("live_capture",view(capture));
        }
        if(on(stage,"pending") || on(stage,"retire") || on(stage,"supersede") || on(stage,"timeout")){if(!adapter.wait_entered(1000))throw std::runtime_error("fixture_not_entered");
            if(on(stage,"supersede"))capture.next_capture();if(on(stage,"timeout"))adapter.timeout();samples.items.push_back(adapter.poll(1));}
        if(on(stage,"retire"))samples.items.push_back(adapter.retire());else{
            const auto end=GetTickCount64()+3000;V last;do{last=adapter.poll(10);if(text(get(last,"worker"),"observation")=="exited")break;}while(GetTickCount64()<end);
            samples.items.push_back(last);if(text(get(last,"worker"),"observation")!="exited")samples.items.push_back(adapter.retire());
        }
        row.put("samples",samples).put("capture",view(capture));const auto frame=adapter.frame();row.put("identity_available",V::boolean_value(bool(frame)));
        if(!frame){observed.items.push_back(std::move(row));retained.push_back({});continue;}
        const auto original_frame_digest=disked::digest_sha256(disked::json::dump(frame->frame().value(),n::storage_observation_limits()));
        row.put("frame",frame->frame().value()).put("context",frame->context());n::IdentityBinding binding{frame->key(),original_frame_digest,disked::digest_sha256(disked::json::dump(frame->context()))};
        if(const auto* p=stage.find("binding")){allowed(*p,{"source","capture","worker","frame_digest","context_digest"});if(p->find("source"))binding.capture.source=text(*p,"source");if(p->find("capture"))binding.capture.capture=number(*p,"capture");if(p->find("worker"))binding.capture.worker=number(*p,"worker");if(p->find("frame_digest"))binding.frame_digest=text(*p,"frame_digest");if(p->find("context_digest"))binding.context_digest=text(*p,"context_digest");}
        try{const auto identity=n::observe_storage_identity(*frame,binding);row.put("identity",identity->value()).put("identity_digest",V::string(n::storage_identity_digest(*identity)));retained.push_back(identity);}
        catch(const std::invalid_argument& e){row.put("construction_error",V::string(e.what())).put("identity_available",V::boolean_value(false));refused=true;retained.push_back({});}
        if(original_frame_digest!=disked::digest_sha256(disked::json::dump(frame->frame().value(),n::storage_observation_limits())))throw std::runtime_error("fixture_changed_frame");
        row.put("derivation_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));observed.items.push_back(std::move(row));
    }
    auto out=V::object().put("observations",observed).put("comparison",V{});if(retained.size()>1 && retained.front() && retained.back()){
        const auto previous=on(input,"reverse")?retained.back():retained.front(),current=on(input,"reverse")?retained.front():retained.back();
        n::IdentityComparisonBinding binding{n::storage_identity_digest(*previous),n::storage_identity_digest(*current),input.find("previous_subject")?text(input,"previous_subject"):"disk",input.find("current_subject")?text(input,"current_subject"):"disk"};
        if(const auto* p=input.find("comparison")){allowed(*p,{"previous_digest","current_digest","previous_subject","current_subject"});for(const auto k:{"previous_digest","current_digest","previous_subject","current_subject"})if(p->find(k)){if(std::string(k)=="previous_digest")binding.previous_digest=text(*p,k);else if(std::string(k)=="current_digest")binding.current_digest=text(*p,k);else if(std::string(k)=="previous_subject")binding.previous_subject=text(*p,k);else binding.current_subject=text(*p,k);}}
        try{const auto a=n::storage_identity_digest(*previous),b=n::storage_identity_digest(*current);out.put("comparison",n::compare_storage_identity(*previous,*current,binding));if(a!=n::storage_identity_digest(*previous) || b!=n::storage_identity_digest(*current))throw std::runtime_error("fixture_changed_identity");}
        catch(const std::invalid_argument& e){out.put("comparison_error",V::string(e.what()));refused=true;}
    }
    out.put("status",V::string(refused?"refused":"observed")).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));return out;
}
}
int wmain(int argc,wchar_t** argv){
#ifdef DISKED_NT_COMPOSITE_METADATA_PROBE
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_storage_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);});
#else
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
#endif
    if(argc!=1)return 2;if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try{disked::WindowsMemoryBudget budget;if(!budget.ready())throw std::runtime_error(budget.error());std::vector<char> bytes(1048577);const auto got=std::fread(bytes.data(),1,bytes.size(),stdin);if(!got || got==bytes.size() || std::ferror(stdin))return 2;
        auto limits=n::storage_identity_limits();limits.bytes=1048576;limits.values=65536;auto out=exercise(disked::json::parse(std::string(bytes.data(),got),limits));const bool refused=text(out,"status")=="refused";print(std::move(out));return refused?3:0;
    }catch(const std::exception& e){print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
