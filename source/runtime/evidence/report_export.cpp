#include "report_export.h"
#include "image_observation.h"
#include "image_collection.h"
#include "sha256.h"
#include <algorithm>

namespace disked { namespace evidence { namespace proposal {
using V=json::Value;
namespace {
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw Error("export_shape");return *p;}
void shape(const V& v,std::initializer_list<const char*> keys) {
    if(v.kind!=V::Kind::object || v.fields.size()!=keys.size())throw Error("export_shape");for(const auto key:keys)field(v,key);
}
void token(const V& v,std::size_t limit=256) {
    if(v.kind!=V::Kind::string || v.text.empty() || v.text.size()>limit || !json::valid_utf8(v.text))throw Error("export_identity");
    for(const auto c:v.text)if(static_cast<unsigned char>(c)<32 || c==127)throw Error("export_identity");
}
void digest(const V& v) {
    if(v.kind!=V::Kind::string || v.text.size()!=71 || v.text.substr(0,7)!="sha256:" || v.text.find_first_not_of("0123456789abcdef",7)!=v.text.npos)throw Error("export_digest");
}
std::string encode(const V& v) {return json::dump(v,export_definition_limits());}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
void resources(const V& v) {
    shape(v,{"destination","producer"});const auto& d=field(v,"destination");const auto& p=field(v,"producer");
    shape(d,{"identity","epoch","location","access","verification"});shape(p,{"identity","epoch","location","access","digest"});
    for(const auto role:{"destination","producer"}) {const auto& r=field(v,role);token(field(r,"identity"));digest(field(r,"epoch"));token(field(r,"location"),960);token(field(r,"access"));}
    token(field(d,"verification"));
    if(field(d,"access").text!="create-write" || field(d,"verification").text!="readback-sha256" || field(p,"access").text!="read")throw Error("export_access");
    digest(field(p,"digest"));
    if(field(d,"identity").text==field(p,"identity").text || field(d,"location").text==field(p,"location").text)throw Error("export_alias");
    encode(v);
}
}
std::string export_digest(const std::string& bytes) {
    unsigned char out[32];sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),out);const char* hex="0123456789abcdef";
    std::string s="sha256:";for(const auto b:out) {s+=hex[b>>4];s+=hex[b&15];}return s;
}
json::Limits export_definition_limits() {json::Limits l;l.bytes=16384;l.depth=12;l.values=512;l.string_bytes=960;return l;}
SupportArtifact::SupportArtifact(const Case& report,const V& policy) {
    bytes_=json::dump(report.support(policy),case_limits())+'\n';if(bytes_.size()>1048577)throw Error("export_artifact_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",number(bytes_.size())).put("digest",V::string(digest_)).put("policy",policy)
        .put("encoding",V::string("private-case-json-utf8-lf/1")).put("scope",V::string("fixture-case-support"));
}
SupportArtifact::SupportArtifact(const AcquisitionCase& report,const V& policy) {
    bytes_=json::dump(report.support(policy),case_limits())+'\n';if(bytes_.size()>1048577)throw Error("export_artifact_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",number(bytes_.size())).put("digest",V::string(digest_)).put("policy",policy)
        .put("encoding",V::string("private-case-json-utf8-lf/1")).put("scope",V::string("recorded-acquisition-case-support"));
}
SupportArtifact::SupportArtifact(const ImageVerificationObservation& report,const V& policy) {
    bytes_=json::dump(report.support(policy),case_limits())+'\n';if(bytes_.size()>1048577)throw Error("export_artifact_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",number(bytes_.size())).put("digest",V::string(digest_)).put("policy",policy)
        .put("encoding",V::string("private-case-json-utf8-lf/1")).put("scope",V::string("recorded-image-verification-support"));
}
SupportArtifact::SupportArtifact(const ImageVerificationCollection& report,const V& policy) {
    bytes_=json::dump(report.support(policy),case_limits())+'\n';if(bytes_.size()>1048577)throw Error("export_artifact_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",number(bytes_.size())).put("digest",V::string(digest_)).put("policy",policy)
        .put("encoding",V::string("private-case-json-utf8-lf/1")).put("scope",V::string("recorded-image-verification-collection-support"));
}
ExportArtifact::ExportArtifact(const SupportArtifact& artifact):bytes_(artifact.bytes()),digest_(artifact.digest()),description_(artifact.description()) {}
ExportArtifact::ExportArtifact(const CollectionRetentionArtifact& artifact):bytes_(artifact.bytes()),digest_(artifact.digest()),description_(artifact.description()) {}
ExportDefinition::ExportDefinition(const ExportArtifact& artifact,const V& bindings):artifact_(artifact) {
    resources(bindings);definition_=V::object().put("schema",V::string("org.disked.report-export-definition-prototype/1"))
        .put("artifact",artifact.description()).put("resources",bindings);digest_=export_digest(encode(definition_));
}
V ExportOutcome::view() const {
    return V::object().put("schema",V::string("org.disked.report-export-outcome-prototype/1")).put("status",V::string(status))
        .put("diagnostic",diagnostic.empty()?V{}:V::string(diagnostic)).put("phase",V::string(phase)).put("output_state",V::string(output_state))
        .put("submitted_bytes",number(submitted)).put("written_bytes",written_known?number(written):V{}).put("read_bytes",number(read)).put("verified_bytes",number(verified))
        .put("flush",V::string(flush_state)).put("uncertain_effect",V::boolean_value(uncertain_effect)).put("worker_exit",V::string("unobserved"))
        .put("physical_backing_qualified",V::boolean_value(false)).put("power_loss_persistence",V::string("not_established"))
        .put("source_preservation",V::string("not_established")).put("authenticity",V::string("not_established"));
}
ExportOutcome execute_export(const ExportDefinition& definition,const ExportGrant& grant,ExportPorts& ports) {
    ExportOutcome out;
    const bool private_content=field(definition.artifact().description(),"scope").text=="recorded-image-verification-collection-private";
    if(grant.definition_digest!=definition.digest() || !grant.report_write || !grant.host_effects || (private_content && !grant.private_metadata)) {out.diagnostic="export_grant";return out;}
    const auto& expected=field(definition.value(),"resources");const auto& bytes=definition.artifact().bytes();
    bool creating=false;
    auto fresh=[&] {const auto current=ports.observe();resources(current);if(encode(current)!=encode(expected))throw Error("export_binding_changed");};
    auto cancelled=[&] {if(!ports.stop_requested())return false;out.status="cancelled";out.diagnostic="export_cancelled";return true;};
    try {
        out.status="failed";out.phase="revalidation";fresh();if(cancelled())return out;
        out.phase="creation";creating=true;out.output_state="uncertain";out.uncertain_effect=true;
        ports.create();creating=false;out.output_state="created";fresh();
        out.phase="write";
        for(std::size_t offset=0;offset<bytes.size();) {
            if(cancelled())return out;fresh();const auto n=static_cast<std::uint32_t>(std::min<std::size_t>(65536,bytes.size()-offset));
            out.submitted+=n;out.written_known=false;const auto got=ports.write(offset,bytes.data()+offset,n);
            if(got>n)throw Error("export_write_acknowledgement");out.written+=got;out.written_known=true;
            if(got!=n)throw Error("export_short_write");offset+=n;
        }
        out.phase="flush";if(cancelled())return out;fresh();out.flush_state="uncertain";ports.flush();out.flush_state="api_confirmed";
        out.phase="readback";if(ports.size()!=bytes.size())throw Error("export_output_length");std::string verified;verified.reserve(bytes.size());
        for(std::size_t offset=0;offset<bytes.size();) {
            if(cancelled())return out;fresh();const auto n=static_cast<std::uint32_t>(std::min<std::size_t>(65536,bytes.size()-offset));const auto read=ports.read(offset,n);
            if(read.size()>n)throw Error("export_read_acknowledgement");out.read+=read.size();
            if(read.size()!=n)throw Error("export_short_read");if(bytes.compare(offset,n,read)!=0)throw Error("export_readback_mismatch");
            out.verified+=n;verified+=read;offset+=n;
        }
        out.phase="verification";fresh();if(ports.size()!=bytes.size())throw Error("export_output_length");if(cancelled())return out;
        if(export_digest(verified)!=definition.artifact().digest())throw Error("export_readback_mismatch");
        out.status="completed";out.uncertain_effect=false;out.phase="completed";
    } catch(const CreationRefusal& e) {
        out.diagnostic=e.what();if(creating) {out.status="refused";out.output_state="not_created";out.uncertain_effect=false;}
    } catch(const std::exception& e) {out.diagnostic=e.what();}
    return out;
}
}}}
