#include "namespace_graph.h"
#include "volume_fixture.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return p.text;}
V view(const disked::ObservationCapture& capture) {
    const auto s=capture.snapshot();auto sources=V::array();
    for(const auto& source:s->sources)sources.items.push_back(V::object().put("id",V::string(source.id)).put("state",V::string(disked::source_state_name(source.state)))
        .put("outstanding",V::boolean_value(source.outstanding)).put("reason",V::string(source.reason)).put("platform",V::string(source.platform))
        .put("attempt_capture",V::string(std::to_string(source.attempt.capture))).put("attempt_worker",V::string(std::to_string(source.attempt.worker))));
    return V::object().put("capture",V::string(std::to_string(s->capture))).put("sequence",V::string(std::to_string(s->sequence)))
        .put("sources",sources).put("graph",disked::GraphSnapshot::create(s->graph,s->capture)->value());
}
n::InventoryPolicy policy(const V& v) {
    n::InventoryPolicy p;if(const auto q=v.find("policy")) {
        p.volumes=static_cast<std::uint32_t>(std::stoul(text(*q,"volumes")));p.mounts=static_cast<std::uint32_t>(std::stoul(text(*q,"mounts")));
        p.mount_units=static_cast<std::uint32_t>(std::stoul(text(*q,"mount_units")));p.include_mounts=field(*q,"include_mounts").boolean;
    }return p;
}
V context() {
    return V::object().put("attempt_id",V::string("namespace-attempt:"+std::string(32,'1'))).put("observer_epoch",V::string("observer:"+std::string(32,'2')))
        .put("worker_epoch",V::string("worker:"+std::string(32,'3'))).put("request_digest",V::string(std::string(64,'4')))
        .put("code_sha256",V::string(std::string(64,'5'))).put("pid",V::string("6")).put("created",V::string("7"));
}
void print(const V& v) {disked::json::Limits limits;limits.bytes=8388608;limits.values=524288;std::puts(disked::json::dump(v,limits).c_str());std::fflush(stdout);}
}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify) {return disked::nt_fixture::api(v,notify);});
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;if(argc!=1)return 2;
    try {
        char buffer[262145];const auto bytes=std::fread(buffer,1,sizeof(buffer),stdin);if(!bytes || bytes==sizeof(buffer) || std::ferror(stdin))return 2;
        disked::json::Limits limits;limits.bytes=262144;limits.values=65536;limits.depth=24;
        const auto input=disked::json::parse(std::string(buffer,bytes),limits);const auto mode=text(input,"mode");
        if(mode=="project") {
            V snapshot;const auto p=policy(input);
            if(const auto supplied=input.find("snapshot"))snapshot=*supplied;
            else {disked::nt_inventory::VolumeCursor cursor(disked::nt_fixture::api(field(input,"fixture")));snapshot=n::collect_volume_namespace(cursor,1,p,[] {return false;});}
            auto binding=n::NamespaceGraphBinding{{"namespace",1,1},input.find("context")?field(input,"context"):context(),p};
            const auto graph=n::project_namespace_snapshot(snapshot,binding);
            print(V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("snapshot",snapshot).put("context",binding.worker_context)
                .put("graph",disked::GraphSnapshot::create(graph,1)->value()));return 0;
        }
        if(mode!="sequence" && mode!="held" && mode!="late" && mode!="superseded" && mode!="cancel" && mode!="retire")throw std::invalid_argument("fixture_mode");
        disked::ObservationCapture capture({"namespace","peer"},disked::GraphProfile::Observations);
        const auto peer=capture.start("peer");disked::GraphInput peer_graph;
        peer_graph.nodes.push_back({"fake:peer","block-device","fixture:peer","1","peer","current","4096",{}});capture.finish(peer,peer_graph);
        n::NamespaceGraphAdapter adapter(capture,"namespace");auto samples=V::array();auto retained=V::array();std::vector<std::shared_ptr<const disked::CaptureView>> prior;
        auto sample=[&](const V& worker) {samples.items.push_back(V::object().put("worker",worker).put("capture",view(capture)));};
        const auto& stages=field(input,"stages").items;if(stages.empty() || stages.size()>8)throw std::invalid_argument("fixture_stages");
        for(const auto& stage:stages) {
            if(!prior.empty())capture.next_capture();adapter.start(policy(stage),field(stage,"fixture"));sample(adapter.poll());
            if(mode=="cancel")adapter.cancel();adapter.release();
            if(mode=="held") {
                const auto end=GetTickCount64()+1000;
                for(;;) {const auto w=adapter.poll();if(text(w,"status")=="completed") {sample(w);break;}if(GetTickCount64()>=end)throw std::runtime_error("fixture_reply_not_observed");Sleep(1);}
                const auto before=view(capture);sample(adapter.poll());if(disked::json::dump(before,disked::graph_limits(disked::GraphProfile::Observations))!=disked::json::dump(view(capture),disked::graph_limits(disked::GraphProfile::Observations)))throw std::runtime_error("fixture_duplicate_changed");
                bool refused=false;try {adapter.start(policy(stage),field(stage,"fixture"));}catch(const std::invalid_argument&) {refused=true;}if(!refused)throw std::runtime_error("fixture_replacement_allowed");
            }
            if(mode=="late" || mode=="superseded" || mode=="retire") {
                if(!adapter.wait_entered(1000))throw std::runtime_error("fixture_not_entered");if(mode=="superseded")capture.next_capture();else adapter.timeout();sample(adapter.poll(1));
            }
            sample(mode=="retire"?adapter.retire():adapter.poll(1000));
            if(capture.snapshot()->sources.front().outstanding)throw std::runtime_error("fixture_reader_not_retired");prior.push_back(capture.snapshot());
        }
        for(const auto& s:prior)retained.items.push_back(disked::GraphSnapshot::create(s->graph,s->capture)->value());
        print(V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("samples",samples).put("retained",retained));return 0;
    }catch(const std::exception& e) {print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
