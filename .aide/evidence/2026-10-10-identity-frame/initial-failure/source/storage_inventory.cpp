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
    const StorageQueryPolicy& policy,const std::function<bool()>& stop,StorageFrameProfile profile) {
    if(profile!=StorageFrameProfile::Metadata && profile!=StorageFrameProfile::IdentityLayout)throw std::invalid_argument("nt_storage_profile");
    const bool identity=profile==StorageFrameProfile::IdentityLayout;
    if(!identity && (policy.identifiers!=32 || policy.partitions!=64))throw std::invalid_argument("nt_storage_profile_policy");
    if(!capture || subjects.empty() || subjects.size()>16)throw std::invalid_argument("nt_storage_subjects");std::set<std::string> keys;
    // Validate the entire request before dispatching any resource query.
    for(const auto& s:subjects) {
        if(!identifier(s.key) || !keys.insert(s.key).second || s.label.size()>256 || (s.kind!=StorageSubjectKind::Disk && s.kind!=StorageSubjectKind::Volume))throw std::invalid_argument("nt_storage_subjects");
        StorageQueryPort check(api,s.handle,policy);
    }
    auto rows=V::array();bool partial=false,cancelled=false,unresolved=false;std::size_t extent_budget=128,detail_budget=128;
    std::vector<const char*> queries={"descriptor","number","geometry","length","extents"};
    if(identity)queries.insert(queries.end(),{"identifiers","alignment","layout"});
    for(const auto& s:subjects) {
        auto row=V::object().put("key",V::string(s.key)).put("kind",V::string(s.kind==StorageSubjectKind::Disk?"disk":"volume")).put("label",lossless_name(s.label));
        auto components=V::object();const auto initial_budget=identity?detail_budget:extent_budget;
        auto selected_extent_limit=std::min<std::size_t>(policy.extents,initial_budget);std::size_t selected_identifier_limit=0,selected_partition_limit=0;
        for(const auto c:queries) {
            StorageQueryPolicy selected=policy;const auto available=identity?detail_budget:extent_budget;
            selected.extents=static_cast<DWORD>(std::min<std::size_t>(policy.extents,std::max<std::size_t>(available,1)));
            selected.identifiers=static_cast<DWORD>(std::min<std::size_t>(policy.identifiers,std::max<std::size_t>(detail_budget,1)));
            selected.partitions=static_cast<DWORD>(std::min<std::size_t>(policy.partitions,std::max<std::size_t>(detail_budget,1)));
            StorageQueryPort port(api,s.handle,selected,stop);
            V v;const std::string name=c;const bool in_scope=s.kind==StorageSubjectKind::Disk?name!="extents":name=="number" || name=="length" || name=="extents";
            if(identity && name=="extents")selected_extent_limit=std::min<std::size_t>(policy.extents,detail_budget);
            if(identity && in_scope && name=="identifiers")selected_identifier_limit=std::min<std::size_t>(policy.identifiers,detail_budget);
            if(identity && in_scope && name=="layout")selected_partition_limit=std::min<std::size_t>(policy.partitions,detail_budget);
            if(!in_scope)v=empty(c,"not_selected");
            else if(cancelled || unresolved)v=empty(c,"not_attempted");
            else if((name=="extents" && !available) || (identity && (name=="identifiers" || name=="layout") && !detail_budget)) {v=empty(c,"budget_exhausted");partial=true;}
            else {
                try {v=name=="descriptor"?port.descriptor():name=="number"?port.device_number():name=="geometry"?port.geometry():name=="length"?port.length():name=="extents"?port.extents():name=="identifiers"?port.identifiers():name=="alignment"?port.alignment():port.layout();}
                catch(const std::bad_alloc&) {throw;}
                catch(const std::exception&) {v=empty(c,"adapter_exception");unresolved=true;}
                const auto state=text(v,"state");cancelled=state=="cancelled";unresolved=unresolved || port.unresolved();partial=partial || state!="observed";
                if(name=="extents" && observed(v))extent_budget-=get(v,"data").items.size();
                if(identity && observed(v)) {
                    if(name=="extents")detail_budget-=get(v,"data").items.size();
                    if(name=="identifiers")detail_budget-=get(get(v,"data"),"identifiers").items.size();
                    if(name=="layout")detail_budget-=get(get(v,"data"),"partitions").items.size();
                }
            }
            components.put(c,std::move(v));
        }
        row.put("selected_extent_limit",V::string(std::to_string(selected_extent_limit))).put("components",components).put("conflicts",V::object().put("capacity_disagreement",V::boolean_value(false)).put("duplicate_serial_candidate",V::boolean_value(false)).put("duplicate_device_number",V::boolean_value(false)));
        if(identity)row.put("selected_identifier_limit",V::string(std::to_string(selected_identifier_limit))).put("selected_partition_limit",V::string(std::to_string(selected_partition_limit)));
        const auto length=data(row,"length"),geometry=data(row,"geometry");
        if(length && geometry && text(*length,"length_bytes")!=text(*geometry,"disk_size_bytes")) {row.fields["conflicts"].put("capacity_disagreement",V::boolean_value(true));partial=true;}
        if(const auto descriptor=data(row,"descriptor"))for(const auto n:{"vendor","product","revision","serial"})if(!get(get(*descriptor,n),"ascii_conformant").boolean)partial=true;
        if(identity) {
            bool alignment_conflict=false,range_conflict=false,layout_conflict=false,duplicate=false;
            if(const auto a=data(row,"alignment"))if(geometry)alignment_conflict=text(*a,"logical_sector_bytes")!=text(*geometry,"logical_sector_bytes");
            const auto cap=capacity(row);
            if(const auto table=data(row,"layout")) {
                layout_conflict=!get(*table,"issues").items.empty();
                for(const auto& p:get(*table,"partitions").items) {
                    layout_conflict=layout_conflict || !get(p,"issues").items.empty();
                    if(get(p,"active").boolean && !cap.empty() && std::stoull(text(p,"end_bytes"))>std::stoull(cap))range_conflict=true;
                }
                if(!cap.empty() && text(*table,"partition_style")=="1")range_conflict=range_conflict || std::stoull(text(*table,"usable_start_bytes"))+std::stoull(text(*table,"usable_length_bytes"))>std::stoull(cap);
            }
            if(const auto ids=data(row,"identifiers"))for(const auto& id:get(*ids,"identifiers").items)duplicate=duplicate || get(id,"duplicate_in_reply").boolean;
            row.fields["conflicts"].put("alignment_disagreement",V::boolean_value(alignment_conflict)).put("partition_range_disagreement",V::boolean_value(range_conflict))
                .put("reported_layout_conflict",V::boolean_value(layout_conflict)).put("duplicate_identifier_candidate",V::boolean_value(duplicate)).put("duplicate_layout_identifier_candidate",V::boolean_value(false));
            partial=partial || alignment_conflict || range_conflict || layout_conflict || duplicate;
        }
        rows.items.push_back(std::move(row));
    }
    for(std::size_t i=0;i<rows.items.size();++i)for(std::size_t j=0;j<i;++j) {
        auto& a=rows.items[i];auto& b=rows.items[j];const auto serial_a=serial(a),serial_b=serial(b);
        if(!serial_a.empty() && serial_a==serial_b) {a.fields["conflicts"].put("duplicate_serial_candidate",V::boolean_value(true));b.fields["conflicts"].put("duplicate_serial_candidate",V::boolean_value(true));partial=true;}
        if(whole_disk_number(a) && whole_disk_number(b) && text(*data(a,"number"),"device_number")==text(*data(b,"number"),"device_number")) {
            a.fields["conflicts"].put("duplicate_device_number",V::boolean_value(true));b.fields["conflicts"].put("duplicate_device_number",V::boolean_value(true));partial=true;
        }
        if(identity) {
            const auto ids_a=data(a,"identifiers"),ids_b=data(b,"identifiers");
            if(ids_a && ids_b)for(const auto& x:get(*ids_a,"identifiers").items)for(const auto& y:get(*ids_b,"identifiers").items)
                if(text(x,"association")=="0" && !text(x,"original_hex").empty() && text(x,"comparison_key")==text(y,"comparison_key")) {
                    a.fields["conflicts"].put("duplicate_identifier_candidate",V::boolean_value(true));b.fields["conflicts"].put("duplicate_identifier_candidate",V::boolean_value(true));partial=true;
                }
            const auto layout_a=data(a,"layout"),layout_b=data(b,"layout");bool duplicate_layout=false;
            if(layout_a && layout_b && text(*layout_a,"partition_style")==text(*layout_b,"partition_style")) {
                if(text(*layout_a,"partition_style")=="0")duplicate_layout=text(*layout_a,"mbr_signature_raw")!="0" && text(*layout_a,"mbr_signature_raw")==text(*layout_b,"mbr_signature_raw");
                if(text(*layout_a,"partition_style")=="1") {
                    const auto guid=text(*layout_a,"gpt_disk_guid_hex");duplicate_layout=guid.find_first_not_of('0')!=std::string::npos && guid==text(*layout_b,"gpt_disk_guid_hex");
                    for(const auto& x:get(*layout_a,"partitions").items)for(const auto& y:get(*layout_b,"partitions").items)
                        if(get(x,"active").boolean && get(y,"active").boolean && text(x,"gpt_partition_guid_hex").find_first_not_of('0')!=std::string::npos && text(x,"gpt_partition_guid_hex")==text(y,"gpt_partition_guid_hex"))duplicate_layout=true;
                }
            }
            if(duplicate_layout){a.fields["conflicts"].put("duplicate_layout_identifier_candidate",V::boolean_value(true));b.fields["conflicts"].put("duplicate_layout_identifier_candidate",V::boolean_value(true));partial=true;}
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
    auto value=V::object().put("schema",V::string(identity?"org.disked.nt-storage-observation-prototype/2":"org.disked.nt-storage-observation-prototype/1")).put("capture_epoch",V::string(std::to_string(capture)))
        .put("scope",V::string("selected-borrowed-storage-handles")).put("api_binding",V::string("injected-win32-table"))
        .put("policy",V::object().put("descriptor_bytes",V::string(std::to_string(policy.descriptor_bytes))).put("string_bytes",V::string(std::to_string(policy.string_bytes)))
            .put("extents_per_subject",V::string(std::to_string(policy.extents))).put("subjects",V::string("16")).put("frame_extents",V::string("128")))
        .put("status",V::string(unresolved?"unresolved":cancelled?"cancelled":partial?"partial":"selected_queries_complete"))
        .put("resources",rows).put("claims",claims());json::dump(value,storage_observation_limits());
    if(identity) {
        value.fields["policy"].put("identifiers_per_subject",V::string(std::to_string(policy.identifiers))).put("partitions_per_subject",V::string(std::to_string(policy.partitions))).put("frame_details",V::string("128"));
        value.fields["claims"].put("raw_metadata_independently_verified",V::boolean_value(false)).put("identity_scope",V::string("reported-evidence-only"));
        json::dump(value,storage_observation_limits());
    }
    return std::shared_ptr<const StorageFrame>(new StorageFrame(std::move(value),profile));
}
GraphInput project_storage_frame(const StorageFrame& frame,const CaptureKey& key,const std::string& context_digest,const V& worker_context) {
    const auto& v=frame.value();if(text(v,"capture_epoch")!=std::to_string(key.capture) || !key.worker)throw std::invalid_argument("nt_storage_capture_binding");
    GraphInput graph;graph.profile=GraphProfile::Observations;const auto frame_digest=digest_sha256(json::dump(v,storage_observation_limits()));
    for(const auto& row:get(v,"resources").items) {
        auto components=V::object();
        for(const auto& p:get(row,"components").fields) {
            auto summary=V::object().put("state",get(p.second,"state")).put("platform_code",get(p.second,"platform_code"));auto d=get(p.second,"data");
            if(d.kind==V::Kind::object)d.fields.erase("raw_properties_hex");
            if(d.kind==V::Kind::object && p.first=="identifiers") {const auto count=get(d,"identifiers").items.size();d.fields.erase("identifiers");d.put("identifier_count",V::string(std::to_string(count)));}
            if(d.kind==V::Kind::object && p.first=="layout")d.fields.erase("partitions");
            // Extents get their own bounded nodes below; receipts stay in frame.
            summary.put("data",p.first=="extents"?V{}:d);components.put(p.first,std::move(summary));
        }
        auto payload=V::object().put("subject_key",get(row,"key")).put("name",get(row,"label")).put("components",components).put("conflicts",get(row,"conflicts"))
            .put("binding_scope",V::string("fixture-context-only")).put("capture_consistency",V::string("sequential-not-atomic"));
        if(worker_context.kind!=V::Kind::null)payload.put("binding_scope",V::string("owned-reader-context")).put("worker_context",worker_context);
        auto n=node(key,context_digest,frame_digest,text(row,"kind")=="disk"?"storage-device-observation":"storage-volume-observation",text(get(row,"label"),"display"),payload);
        const auto parent=n.id;graph.nodes.push_back(std::move(n));const auto extents=data(row,"extents");
        if(extents)for(const auto& e:extents->items) {
            auto p=V::object().put("subject_key",get(row,"key")).put("parent_observation",V::string(parent)).put("extent",e)
                .put("binding_scope",V::string("fixture-context-only")).put("capture_consistency",V::string("sequential-not-atomic"));
            if(worker_context.kind!=V::Kind::null)p.put("binding_scope",V::string("owned-reader-context")).put("worker_context",worker_context);
            auto child=node(key,context_digest,frame_digest,"storage-extent-observation","extent "+text(e,"ordinal"),p);
            graph.edges.push_back({parent,child.id,"contains"});graph.nodes.push_back(std::move(child));
        }
        if(frame.profile()==StorageFrameProfile::IdentityLayout)for(const auto field:{"identifiers","layout"}) {
            const auto details=data(row,field);if(!details)continue;const bool ids=std::string(field)=="identifiers";
            for(const auto& item:get(*details,ids?"identifiers":"partitions").items) {
                auto p=V::object().put("subject_key",get(row,"key")).put("parent_observation",V::string(parent)).put(ids?"identifier":"partition",item)
                    .put("binding_scope",V::string("fixture-context-only")).put("capture_consistency",V::string("sequential-not-atomic"));
                if(worker_context.kind!=V::Kind::null)p.put("binding_scope",V::string("owned-reader-context")).put("worker_context",worker_context);
                auto child=node(key,context_digest,frame_digest,ids?"storage-identifier-observation":"storage-partition-observation",std::string(ids?"identifier ":"partition ")+text(item,"ordinal"),p);
                graph.edges.push_back({parent,child.id,"contains"});graph.nodes.push_back(std::move(child));
            }
        }
    }
    if(text(v,"status")!="selected_queries_complete")graph.omissions.push_back("storage:"+text(v,"status"));
    GraphSnapshot::create(graph,key.capture);return graph;
}
}}
