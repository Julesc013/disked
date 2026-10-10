#include "storage_inventory.h"
#include "volume_inventory.h"
#include <algorithm>
#include <set>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)throw std::invalid_argument("nt_storage_frame");return *p;}
std::string text(const V& v,const char* k) {return get(v,k).text;}
bool identifier(const std::string& s) {if(s.empty() || s.size()>64)return false;return s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")==std::string::npos;}
bool observed(const V& v) {return text(v,"state")=="observed";}
V empty(const char* component,const char* state) {return V::object().put("component",V::string(component)).put("state",V::string(state)).put("platform_code",V::string("0")).put("data",V{}).put("receipts",V::array());}
const V* data(const V& row,const char* component) {const auto& p=get(get(row,"components"),component);return observed(p)?&get(p,"data"):nullptr;}
std::string capacity(const V& row) {
    const auto length=data(row,"length"),geometry=data(row,"geometry");const auto a=length?text(*length,"length_bytes"):"",b=geometry?text(*geometry,"disk_size_bytes"):"";
    if(!a.empty() && !b.empty() && a!=b)return "";return !a.empty()?a:b;
}
bool whole_disk_number(const V& row) {const auto p=data(row,"number");return text(row,"kind")=="disk" && p && text(*p,"device_type")=="7" && text(*p,"partition_raw")=="0";}
std::string serial(const V& row) {const auto p=data(row,"descriptor");if(!p)return "";const auto& s=get(*p,"serial");return text(s,"state")=="present" && get(s,"ascii_conformant").boolean?text(s,"original_hex"):"";}
V claims() {return V::object().put("physical_identity",V::string("unknown")).put("capture_consistency",V::string("sequential-not-atomic"))
    .put("full_topology",V::string("not_observed")).put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false))
    .put("complete_alias_proof",V::boolean_value(false)).put("media_preservation",V::string("not_established"));}
GraphNode node(const CaptureKey& key,const std::string& context,const std::string& frame,const char* kind,const std::string& label,V payload) {
    GraphNode n;n.kind=kind;n.label=label;n.state="unknown";n.scope=GraphNodeScope::Observation;
    n.observation.source=key.source;n.observation.capture=key.capture;n.observation.worker=key.worker;n.observation.context_digest=context;n.observation.frame_digest=frame;n.observation.payload=std::move(payload);
    n.id=observation_node_id(n);return n;
}
}
std::shared_ptr<const StorageFrame> collect_storage_frame(const StorageQueryApi& api,const std::vector<StorageSubject>& subjects,std::uint64_t capture,
    const StorageQueryPolicy& policy,const std::function<bool()>& stop) {
    if(!capture || subjects.empty() || subjects.size()>16)throw std::invalid_argument("nt_storage_subjects");std::set<std::string> keys;
    // Validate the entire request before dispatching any resource query.
    for(const auto& s:subjects) {
        if(!identifier(s.key) || !keys.insert(s.key).second || s.label.size()>256 || (s.kind!=StorageSubjectKind::Disk && s.kind!=StorageSubjectKind::Volume))throw std::invalid_argument("nt_storage_subjects");
        StorageQueryPort check(api,s.handle,policy);
    }
    auto rows=V::array();bool partial=false,cancelled=false,unresolved=false;std::size_t extent_budget=128;
    for(const auto& s:subjects) {
        auto row=V::object().put("key",V::string(s.key)).put("kind",V::string(s.kind==StorageSubjectKind::Disk?"disk":"volume")).put("label",lossless_name(s.label));
        auto components=V::object();StorageQueryPolicy selected=policy;selected.extents=static_cast<DWORD>(std::min<std::size_t>(policy.extents,std::max<std::size_t>(extent_budget,1)));
        StorageQueryPort port(api,s.handle,selected,stop);
        for(const auto c:{"descriptor","number","geometry","length","extents"}) {
            V v;const std::string name=c;const bool in_scope=s.kind==StorageSubjectKind::Disk?name!="extents":name=="number" || name=="length" || name=="extents";
            if(!in_scope)v=empty(c,"not_selected");
            else if(cancelled || unresolved)v=empty(c,"not_attempted");
            else if(name=="extents" && !extent_budget) {v=empty(c,"budget_exhausted");partial=true;}
            else {
                try {v=name=="descriptor"?port.descriptor():name=="number"?port.device_number():name=="geometry"?port.geometry():name=="length"?port.length():port.extents();}
                catch(const std::bad_alloc&) {throw;}
                catch(const std::exception&) {v=empty(c,"adapter_exception");unresolved=true;}
                const auto state=text(v,"state");cancelled=state=="cancelled";unresolved=unresolved || port.unresolved();partial=partial || state!="observed";
                if(name=="extents" && observed(v))extent_budget-=get(v,"data").items.size();
            }
            components.put(c,std::move(v));
        }
        row.put("components",components).put("conflicts",V::object().put("capacity_disagreement",V::boolean_value(false)).put("duplicate_serial_candidate",V::boolean_value(false)).put("duplicate_device_number",V::boolean_value(false)));
        const auto length=data(row,"length"),geometry=data(row,"geometry");
        if(length && geometry && text(*length,"length_bytes")!=text(*geometry,"disk_size_bytes")) {row.fields["conflicts"].put("capacity_disagreement",V::boolean_value(true));partial=true;}
        if(const auto descriptor=data(row,"descriptor"))for(const auto n:{"vendor","product","revision","serial"})if(!get(get(*descriptor,n),"ascii_conformant").boolean)partial=true;
        rows.items.push_back(std::move(row));
    }
    for(std::size_t i=0;i<rows.items.size();++i)for(std::size_t j=0;j<i;++j) {
        auto& a=rows.items[i];auto& b=rows.items[j];const auto serial_a=serial(a),serial_b=serial(b);
        if(!serial_a.empty() && serial_a==serial_b) {a.fields["conflicts"].put("duplicate_serial_candidate",V::boolean_value(true));b.fields["conflicts"].put("duplicate_serial_candidate",V::boolean_value(true));partial=true;}
        if(whole_disk_number(a) && whole_disk_number(b) && text(*data(a,"number"),"device_number")==text(*data(b,"number"),"device_number")) {
            a.fields["conflicts"].put("duplicate_device_number",V::boolean_value(true));b.fields["conflicts"].put("duplicate_device_number",V::boolean_value(true));partial=true;
        }
    }
    for(auto& row:rows.items) {
        auto& extents=row.fields["components"].fields["extents"];if(!observed(extents))continue;
        for(auto& extent:extents.fields["data"].items) {
            auto candidates=V::array();const V* unique=nullptr;
            for(const auto& disk:rows.items)if(whole_disk_number(disk) && text(*data(disk,"number"),"device_number")==text(extent,"disk_number")) {candidates.items.push_back(get(disk,"key"));unique=&disk;}
            const auto count=candidates.items.size();extent.put("candidate_subjects",candidates).put("lookup_state",V::string(count==1?"unique-number-observation-only":count?"ambiguous":"unresolved"));
            std::string range="unknown";if(count==1) {const auto cap=capacity(*unique);if(!cap.empty())range=std::stoull(text(extent,"end_bytes"))<=std::stoull(cap)?"within-observed-capacity":"exceeds-observed-capacity";}
            extent.put("range_state",V::string(range));if(count!=1 || range=="exceeds-observed-capacity")partial=true;
        }
    }
    auto value=V::object().put("schema",V::string("org.disked.nt-storage-observation-prototype/1")).put("capture_epoch",V::string(std::to_string(capture)))
        .put("scope",V::string("selected-borrowed-storage-handles")).put("api_binding",V::string("injected-win32-table"))
        .put("status",V::string(unresolved?"unresolved":cancelled?"cancelled":partial?"partial":"selected_queries_complete"))
        .put("resources",rows).put("claims",claims());json::dump(value,storage_observation_limits());
    return std::shared_ptr<const StorageFrame>(new StorageFrame(std::move(value)));
}
GraphInput project_storage_frame(const StorageFrame& frame,const CaptureKey& key,const std::string& fixture_context_digest) {
    const auto& v=frame.value();if(text(v,"capture_epoch")!=std::to_string(key.capture) || !key.worker)throw std::invalid_argument("nt_storage_capture_binding");
    GraphInput graph;graph.profile=GraphProfile::Observations;const auto frame_digest=digest_sha256(json::dump(v,storage_observation_limits()));
    for(const auto& row:get(v,"resources").items) {
        auto components=V::object();
        for(const auto& p:get(row,"components").fields) {
            auto summary=V::object().put("state",get(p.second,"state")).put("platform_code",get(p.second,"platform_code"));auto d=get(p.second,"data");
            if(d.kind==V::Kind::object)d.fields.erase("raw_properties_hex");
            // Extents get their own bounded nodes below; receipts stay in frame.
            summary.put("data",p.first=="extents"?V{}:d);components.put(p.first,std::move(summary));
        }
        auto payload=V::object().put("subject_key",get(row,"key")).put("name",get(row,"label")).put("components",components).put("conflicts",get(row,"conflicts"))
            .put("binding_scope",V::string("fixture-context-only")).put("capture_consistency",V::string("sequential-not-atomic"));
        auto n=node(key,fixture_context_digest,frame_digest,text(row,"kind")=="disk"?"storage-device-observation":"storage-volume-observation",text(get(row,"label"),"display"),payload);
        const auto parent=n.id;graph.nodes.push_back(std::move(n));const auto extents=data(row,"extents");
        if(extents)for(const auto& e:extents->items) {
            auto p=V::object().put("subject_key",get(row,"key")).put("parent_observation",V::string(parent)).put("extent",e)
                .put("binding_scope",V::string("fixture-context-only")).put("capture_consistency",V::string("sequential-not-atomic"));
            auto child=node(key,fixture_context_digest,frame_digest,"storage-extent-observation","extent "+text(e,"ordinal"),p);
            graph.edges.push_back({parent,child.id,"contains"});graph.nodes.push_back(std::move(child));
        }
    }
    if(text(v,"status")!="selected_queries_complete")graph.omissions.push_back("storage:"+text(v,"status"));
    GraphSnapshot::create(graph,key.capture);return graph;
}
}}
