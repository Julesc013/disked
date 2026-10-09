#include "acquisition_verification.h"
#include "report_export.h"
namespace disked { namespace evidence { namespace proposal {
namespace {using V=json::Value;
const V& get(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw Error("verification_case_shape");return *p;}
V claims() {return V::object().put("historical_verification",V::string("recorded"))
    .put("authenticity",V::string("not_established")).put("custody_authentication",V::string("not_established"))
    .put("current_image_state",V::string("not_established")).put("worker_exit",V::string("not_observed"))
    .put("power_loss_persistence",V::string("not_established")).put("physical_admission",V::boolean_value(false))
    .put("mutation_authority",V::boolean_value(false));}
V policy(unsigned n) {auto v=V::object();unsigned bit=1;for(const auto key:{"identifiers","raw_values","interpretations","customer_data"}) {v.put(key,V::boolean_value((n&bit)!=0));bit<<=1;}return v;}
}
json::Limits acquisition_verification_limits() {auto l=acquisition_case_limits();l.bytes=2097152;l.string_bytes=1048576;l.depth=64;l.values=262144;return l;}
AcquisitionVerificationReport::AcquisitionVerificationReport(const AcquisitionCase& acquisition,const std::string& request,
    const std::string& history,const ImageVerificationCollection& verification):acquisition_(acquisition),verification_(verification) {
    if(request.empty() || request.size()>32768 || history.size()>1048576)throw Error("verification_case_input_limit");
    auto limits=acquisition_operation::row_limits();limits.bytes=32768;limits.depth=24;limits.values=4096;
    const AcquisitionCase rebuilt(json::parse(request,limits),history);const auto& collection=verification_.view();
    const auto& records=get(collection,"records");if(records.kind!=V::Kind::array || records.items.empty())throw Error("verification_case_empty_collection");
    const auto selected=json::dump(acquisition_.view(),acquisition_case_limits());
    if(rebuilt.revision()!=acquisition_.revision() || json::dump(rebuilt.view(),acquisition_case_limits())!=selected ||
       json::dump(get(collection,"original_case"),acquisition_case_limits())!=selected ||
       get(collection,"case_revision").text!=acquisition_.revision() || get(collection,"request_raw").text!=request ||
       image_collection_bytes(get(collection,"history_hex").text)!=history)throw Error("verification_case_original_mismatch");
    view_=V::object().put("schema",V::string("org.disked.acquisition-verification-report-prototype/1"))
        .put("acquisition",V::object().put("revision",V::string(acquisition_.revision())).put("view",acquisition_.view()))
        .put("verification",V::object().put("revision",V::string(verification_.revision())).put("view",collection)).put("claims",claims());
    revision_=export_digest(json::dump(view_,acquisition_verification_limits()));
    for(unsigned n=0;n<16;++n)json::dump(support(policy(n)),case_limits());
}
json::Value AcquisitionVerificationReport::support(const V& selected) const {
    auto v=V::object().put("schema",V::string("org.disked.acquisition-verification-support-prototype/1"))
        .put("scope",V::string("recorded-acquisition-verification")).put("policy",selected)
        .put("acquisition",acquisition_.support(selected)).put("verification",verification_.support(selected)).put("claims",claims());
    json::dump(v,case_limits());return v;
}
SupportArtifact::SupportArtifact(const AcquisitionVerificationReport& report,const V& selected) {
    bytes_=json::dump(report.support(selected),case_limits())+'\n';if(bytes_.size()>1048577)throw Error("export_artifact_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",V::string(std::to_string(bytes_.size()))).put("digest",V::string(digest_)).put("policy",selected)
        .put("encoding",V::string("private-case-json-utf8-lf/1")).put("scope",V::string("recorded-acquisition-verification-support"));
}
}}}
