#include "layout_provenance.h"

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k){auto p=v.find(k);if(!p)throw std::invalid_argument("layout_provenance_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("layout_provenance_shape");return p.text;}
std::string context_digest(const V& v){return digest_sha256(json::dump(v));}
}
std::string file_layout_capture_digest(const FileLayoutSnapshot& file){
    auto v=V::object().put("receipt",file.receipt()).put("context",file.context()).put("raw_digest",V::string(raw_layout_digest(file.raw())));
    return digest_sha256(json::dump(v,file_layout_snapshot_limits()));
}
V compare_owned_layout(const StorageFrameSnapshot& storage,const FileLayoutSnapshot& file,const OwnedLayoutBinding& binding){
    const auto& key=storage.key();const auto& expected=binding.comparison.capture;
    if(storage.frame().profile()!=StorageFrameProfile::IdentityLayout || text(storage.context(),"storage_profile")!="identity-layout" || text(file.context(),"image_profile")!="ordinary-image-layout")throw std::invalid_argument("layout_provenance_profile");
    if(key.source!=expected.source || key.capture!=expected.capture || key.worker!=expected.worker || text(file.receipt(),"capture_epoch")!=std::to_string(key.capture) ||
        text(file.context(),"capture_epoch")!=std::to_string(key.capture) || binding.file_context_digest!=context_digest(file.context()) ||
        binding.storage_context_digest!=context_digest(storage.context()) || binding.file_capture_digest!=file_layout_capture_digest(file))throw std::invalid_argument("layout_provenance_binding");
    if(text(file.context(),"pid")==text(storage.context(),"pid") && text(file.context(),"created")==text(storage.context(),"created"))throw std::invalid_argument("layout_provenance_same_process");
    const auto pure=compare_storage_layout(storage.frame(),file.raw(),binding.comparison);
    const auto& stable=get(file.receipt(),"observed_stable");const auto& partial=get(file.receipt(),"partial_final_block");
    if(stable.kind!=V::Kind::boolean || partial.kind!=V::Kind::boolean)throw std::invalid_argument("layout_provenance_capture");
    auto out=V::object().put("schema",V::string("org.disked.nt-owned-layout-comparison-prototype/1"))
        .put("state",V::string(stable.boolean && !partial.boolean?text(pure,"state"):"incomparable")).put("file_observed_stable",stable)
        .put("common_fields",pure).put("file_context",file.context()).put("storage_context",storage.context())
        .put("file_capture_digest",V::string(binding.file_capture_digest)).put("file_context_digest",V::string(binding.file_context_digest)).put("storage_context_digest",V::string(binding.storage_context_digest))
        .put("scope",V::string("verified owned reader bindings and declared fixture correlation; common_fields retains its pure no-authentication scope"))
        .put("claims",V::object().put("owned_process_bindings_verified",V::boolean_value(true)).put("physical_identity",V::string("unknown"))
            .put("physical_association",V::string("unproven")).put("current_resource_freshness",V::string("unknown")).put("source_consistency",V::string("live-uncoordinated"))
            .put("atomic_snapshot",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false)));
    json::dump(out,layout_comparison_limits());return out;
}
}}
