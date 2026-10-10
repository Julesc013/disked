#include "definitions.h"
#include <algorithm>
#include <functional>
#include <limits>
#include <map>
#include <set>

namespace disked { namespace journal { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code) {throw DefinitionError(code);}
const V& field(const V& v,const std::string& k) {const auto p=v.find(k);if(!p)fail("definition_shape");return *p;}
void keys(const V& v,const std::vector<std::string>& names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())fail("definition_shape");
    for(const auto& n:names)field(v,n);
}
std::string text(const V& v) {if(v.kind!=V::Kind::string)fail("definition_string");return v.text;}
std::string text(const V& v,const char* k) {return text(field(v,k));}
bool flag(const V& v,const char* k) {const auto& f=field(v,k);if(f.kind!=V::Kind::boolean)fail("definition_boolean");return f.boolean;}
std::string id(const V& v) {
    const auto s=text(v);if(s.empty() || s.size()>128 || s.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:/@+-")!=s.npos)fail("definition_identifier");return s;
}
std::string id(const V& v,const char* k) {return id(field(v,k));}
std::string digest(const V& v) {
    const auto s=text(v);if(s.size()!=71 || s.compare(0,7,"sha256:") || s.find_first_not_of("0123456789abcdef",7)!=s.npos || s.substr(7)==std::string(64,'0'))fail("definition_digest");return s;
}
std::string digest(const V& v,const char* k) {return digest(field(v,k));}
std::uint64_t integer(const V& v,const char* k,bool positive=false) {
    const auto s=text(v,k);if(!json::decimal_u64(s))fail("definition_integer");const auto n=std::stoull(s);if(positive && !n)fail("definition_integer");return n;
}
const std::vector<V>& array(const V& v,std::size_t maximum,bool empty=true) {
    if(v.kind!=V::Kind::array || v.items.size()>maximum || (!empty && v.items.empty()))fail("definition_array_limit");return v.items;
}
std::vector<std::string> ids(const V& v,std::size_t maximum,bool empty=true) {
    std::vector<std::string> out;for(const auto& x:array(v,maximum,empty)) {
        const auto s=id(x);if(!out.empty() && out.back()>=s)fail("definition_set_order");out.push_back(s);
    }return out;
}
void choice(const std::string& s,std::initializer_list<const char*> allowed) {
    for(const auto x:allowed)if(s==x)return;fail("definition_enum");
}
Bytes encode_payload(const V& v) {
    json::Limits limits;limits.bytes=max_payload;limits.string_bytes=1024;
    try {const auto s=json::dump(v,limits);return Bytes(s.begin(),s.end());}catch(const json::Error&) {fail("definition_payload_limit");}
}
Digest domain(const char* prefix,const V& v) {
    const std::string p=prefix;auto b=encode_payload(v);b.insert(b.begin(),p.begin(),p.end());return hash(b);
}
bool contains(const std::vector<std::string>& a,const std::string& v) {return std::binary_search(a.begin(),a.end(),v);}
bool intersects(const std::vector<std::string>& a,const std::vector<std::string>& b) {
    for(const auto& v:a)if(contains(b,v))return true;return false;
}
int access(const std::string& s) {choice(s,{"observe","read","write"});return s=="write"?2:s=="read"?1:0;}
struct Resource {const V* value;std::string purpose;int mode;std::uint64_t begin,end;std::vector<std::string> domains;};
using Resources=std::map<std::string,Resource>;
Resources resources(const V& v) {
    Resources out;std::set<std::string> aliases;std::string previous;
    for(const auto& r:array(field(v,"resources"),32,false)) {
        keys(r,{"id","identity","identity_digest","state_digest","epoch","purpose","access","begin","end","aliases","failure_domains","verification","persistent"});
        const auto name=id(r,"id"),identity=id(r,"identity");if(!previous.empty() && previous>=name)fail("definition_set_order");previous=name;
        if(identity.compare(0,5,"fake:"))fail("definition_fake_identity");digest(r,"identity_digest");digest(r,"state_digest");integer(r,"epoch",true);flag(r,"persistent");
        auto names=ids(field(r,"aliases"),16,false);if(!contains(names,identity))fail("definition_identity_alias");
        for(const auto& n:names)if(!aliases.insert(n).second)fail("definition_aliased_resources");
        const auto purpose=text(r,"purpose");choice(purpose,{"target","scratch","journal","backup","executable","provider"});
        const auto mode=access(text(r,"access"));const auto begin=integer(r,"begin"),end=integer(r,"end");
        if(begin>end || (mode==2 && begin==end))fail("definition_footprint");
        choice(text(r,"verification"),{"identity-epoch","readback-sha256","independent-postcondition"});
        out.emplace(name,Resource{&r,purpose,mode,begin,end,ids(field(r,"failure_domains"),8,false)});
    }return out;
}
const Resource& resource(const Resources& r,const std::string& name) {const auto p=r.find(name);if(p==r.end())fail("definition_resource_reference");return p->second;}
const V& step(const V& plan,const std::string& name) {
    for(const auto& s:field(plan,"steps").items)if(text(s,"id")==name)return s;fail("definition_step_reference");
}
std::vector<std::string> selected(const V& plan,const V& v) {
    auto out=ids(v,32,false);for(const auto& s:out)step(plan,s);return out;
}
std::map<std::string,int> scope(const V& plan,const std::vector<std::string>& steps) {
    std::map<std::string,int> out;out[text(plan,"journal_resource")]=2;
    for(const auto& name:steps) {
        const auto& s=step(plan,name);for(const auto n:{"provider","executor"})out[text(s,n)]=(std::max)(out[text(s,n)],1);
        for(const auto& e:field(s,"effects").items) {const auto r=text(e,"resource");out[r]=(std::max)(out[r],access(text(e,"access")));}
        for(const auto& r:field(field(s,"recovery"),"reconstruction_resources").items)out[text(r)]=(std::max)(out[text(r)],1);
    }return out;
}
const std::vector<std::string> traits={"replayable","resumable","rollback_before_boundary","rollback_after_boundary","external_backup_required","cancellable_at_checkpoint","irreversible_after","forensic_best_effort"};
V validate_plan(const V& v) {
    keys(v,{"schema","id","basis_digest","policy_digest","environment","required_acknowledgements","journal_resource","resources","steps"});
    if(text(v,"schema")!="org.disked.plan-definition-prototype/1" || text(v,"environment")!="fake-model")fail("definition_version");
    id(v,"id");digest(v,"basis_digest");digest(v,"policy_digest");ids(field(v,"required_acknowledgements"),16);
    const auto rs=resources(v);const auto journal=id(v,"journal_resource");const auto& jr=resource(rs,journal);
    if(jr.purpose!="journal" || jr.mode!=2 || !flag(*jr.value,"persistent"))fail("definition_journal_dependency");
    std::set<std::string> used{journal},protected_resources{journal};std::map<std::string,std::size_t> positions;
    const auto& ss=array(field(v,"steps"),32,false);std::vector<std::map<std::string,const V*>> effects(ss.size());
    std::string previous;auto summary=V::object();auto checkpoints=V::array();
    for(const auto n:{"replayable","resumable","rollback_before_boundary","rollback_after_boundary"})summary.put(std::string("all_")+n,V::boolean_value(true));
    for(const auto n:{"external_backup_required","irreversible_after","forensic_best_effort"})summary.put(std::string("any_")+n,V::boolean_value(false));
    for(std::size_t i=0;i<ss.size();++i) {
        const auto& s=ss[i];keys(s,{"id","operation","provider","executor","depends_on","effects","preconditions_digest","postconditions_digest","recovery"});
        const auto name=id(s,"id");if(!previous.empty() && previous>=name)fail("definition_set_order");previous=name;positions.emplace(name,i);
        if(text(s,"operation")!="fake.range-transition")fail("definition_operation");digest(s,"preconditions_digest");digest(s,"postconditions_digest");ids(field(s,"depends_on"),32);
        for(const auto n:{"provider","executor"}) {
            const auto dep=id(s,n);const auto& r=resource(rs,dep);
            if(r.purpose!=(std::string(n)=="provider"?"provider":"executable") || r.mode!=1 || !flag(*r.value,"persistent"))fail("definition_code_dependency");
            used.insert(dep);protected_resources.insert(dep);
        }
        std::string last;bool writes=false;
        for(const auto& e:array(field(s,"effects"),32,false)) {
            keys(e,{"resource","access","begin","end","before_digest","after_digest"});const auto r=id(e,"resource");const auto& bound=resource(rs,r);
            if(!last.empty() && last>=r)fail("definition_set_order");last=r;
            if(bound.purpose!="target" && bound.purpose!="scratch")fail("definition_effect_role");
            const auto mode=access(text(e,"access"));const auto begin=integer(e,"begin"),end=integer(e,"end");
            if(mode>bound.mode || begin<bound.begin || end>bound.end || begin>end || (mode==0?begin!=end:begin==end))fail("definition_effect_footprint");
            const auto before=digest(e,"before_digest"),after=digest(e,"after_digest");if(mode!=2 && before!=after)fail("definition_read_effect");
            writes=writes || mode==2;used.insert(r);effects[i].emplace(r,&e);
        }
        if(!writes)fail("definition_mutation_model");
        const auto& recovery=field(s,"recovery");auto names=traits;names.push_back("reconstruction_resources");keys(recovery,names);
        for(const auto& n:traits)flag(recovery,n.c_str());
        if(flag(recovery,"irreversible_after") && flag(recovery,"rollback_after_boundary"))fail("definition_recovery_contradiction");
        const auto backups=ids(field(recovery,"reconstruction_resources"),32);
        if((flag(recovery,"external_backup_required") || flag(recovery,"rollback_before_boundary") || flag(recovery,"rollback_after_boundary")) && backups.empty())fail("definition_reconstruction_required");
        for(const auto& backup:backups) {
            const auto& r=resource(rs,backup);if(r.purpose!="backup" || r.mode!=1 || !flag(*r.value,"persistent") || text(*r.value,"verification")=="identity-epoch")fail("definition_backup_dependency");
            used.insert(backup);protected_resources.insert(backup);
        }
        for(const auto n:{"replayable","resumable","rollback_before_boundary","rollback_after_boundary"})summary.fields[std::string("all_")+n].boolean=summary.fields[std::string("all_")+n].boolean && flag(recovery,n);
        for(const auto n:{"external_backup_required","irreversible_after","forensic_best_effort"})summary.fields[std::string("any_")+n].boolean=summary.fields[std::string("any_")+n].boolean || flag(recovery,n);
        if(flag(recovery,"cancellable_at_checkpoint"))checkpoints.items.push_back(V::string(text(s,"id")));
    }
    if(used.size()!=rs.size())fail("definition_unused_resource");
    std::vector<std::vector<bool>> ancestors(ss.size(),std::vector<bool>(ss.size(),false));
    for(std::size_t i=0;i<ss.size();++i)for(const auto& dep:field(ss[i],"depends_on").items) {
        const auto found=positions.find(text(dep));if(found==positions.end())fail("definition_step_reference");ancestors[i][found->second]=true;
    }
    std::vector<unsigned char> colors(ss.size(),0);std::vector<std::string> stack;
    std::function<void(std::size_t)> visit=[&](std::size_t i) {
        if(colors[i]==2)return;if(colors[i]==1) {
            const auto at=std::find(stack.begin(),stack.end(),text(ss[i],"id"));std::vector<std::string> cycle(at,stack.end());cycle.push_back(text(ss[i],"id"));throw DefinitionError("definition_dependency_cycle",cycle);
        }
        colors[i]=1;stack.push_back(text(ss[i],"id"));for(std::size_t j=0;j<ss.size();++j)if(ancestors[i][j])visit(j);stack.pop_back();colors[i]=2;
    };
    for(std::size_t i=0;i<ss.size();++i)visit(i);
    for(std::size_t k=0;k<ss.size();++k)for(std::size_t i=0;i<ss.size();++i)for(std::size_t j=0;j<ss.size();++j)ancestors[i][j]=ancestors[i][j] || (ancestors[i][k] && ancestors[k][j]);
    for(std::size_t i=0;i<ss.size();++i)for(const auto& pair:effects[i]) {
        const auto& e=*pair.second;
        for(std::size_t j=i+1;j<ss.size();++j) {
            const auto other=effects[j].find(pair.first);if(other!=effects[j].end() && (text(e,"access")=="write" || text(*other->second,"access")=="write") && !ancestors[i][j] && !ancestors[j][i])fail("definition_unordered_effects");
        }
        std::size_t latest=ss.size();
        for(std::size_t j=0;j<ss.size();++j) {
            const auto pred=effects[j].find(pair.first);if(ancestors[i][j] && pred!=effects[j].end() && text(*pred->second,"access")=="write" && (latest==ss.size() || ancestors[j][latest]))latest=j;
        }
        const auto before=latest==ss.size()?digest(*resource(rs,pair.first).value,"state_digest"):digest(*effects[latest].at(pair.first),"after_digest");
        if(digest(e,"before_digest")!=before)fail("definition_intermediate_state");
        if(text(e,"access")=="write")for(const auto& dep:protected_resources)if(intersects(resource(rs,pair.first).domains,resource(rs,dep).domains))fail("definition_dependency_failure_domain");
    }
    return summary.put("cancellation_checkpoints",checkpoints).put("qualifies_recovery",V::boolean_value(false));
}
void validate_receipt(const Definition& definition,const V& v) {
    const auto& plan=definition.value();const auto kind=text(v,"kind");choice(kind,{"review","grant","admission","execution"});
    std::vector<std::string> names={"schema","id","kind","plan_digest","issuer","evidence_digest"};
    std::vector<std::string> extra;
    if(kind=="review")extra={"step_ids","decision"};
    if(kind=="grant")extra={"step_ids","permissions","acknowledgements","host_effects"};
    if(kind=="admission")extra={"step_ids","operation_id","attempt_id","worker_identity","worker_epoch","review_id","grant_id","policy_digest","provider_closure_digest","observations"};
    if(kind=="execution")extra={"operation_id","attempt_id","worker_identity","worker_epoch","admission_id","sequence","step_id","event","observation_digest"};
    names.insert(names.end(),extra.begin(),extra.end());keys(v,names);
    if(text(v,"schema")!="org.disked.plan-receipt-prototype/1")fail("receipt_version");id(v,"id");id(v,"issuer");digest(v,"evidence_digest");
    if(digest(v,"plan_digest")!=digest_text(definition.digest()))fail("receipt_plan_mismatch");
    if(kind=="review") {selected(plan,field(v,"step_ids"));choice(text(v,"decision"),{"reviewed","rejected"});}
    if(kind=="grant") {
        const auto steps=selected(plan,field(v,"step_ids"));const auto expected=scope(plan,steps);const auto acks=ids(field(v,"acknowledgements"),16);
        if(acks!=ids(field(plan,"required_acknowledgements"),16))fail("receipt_acknowledgements");flag(v,"host_effects");std::map<std::string,int> actual;std::string last;
        for(const auto& p:array(field(v,"permissions"),32,false)) {
            keys(p,{"resource","access"});const auto name=id(p,"resource");if(!last.empty() && last>=name)fail("definition_set_order");last=name;actual[name]=access(text(p,"access"));
        }if(actual!=expected)fail("receipt_permission_scope");
    }
    if(kind=="admission" || kind=="execution") {
        for(const auto name:{"operation_id","attempt_id","worker_identity"})id(v,name);integer(v,"worker_epoch",true);
    }
    if(kind=="admission") {
        selected(plan,field(v,"step_ids"));id(v,"review_id");id(v,"grant_id");
        if(digest(v,"policy_digest")!=digest(plan,"policy_digest") || digest(v,"provider_closure_digest")!=digest_text(definition.providers_digest()))fail("receipt_closure_mismatch");
        const auto rs=resources(plan);const auto& os=array(field(v,"observations"),32,false);if(os.size()!=rs.size())fail("receipt_observation_scope");auto expected=rs.begin();
        for(const auto& o:os) {
            keys(o,{"resource","epoch","identity_digest","state_digest"});
            if(id(o,"resource")!=expected->first || integer(o,"epoch",true)!=integer(*expected->second.value,"epoch",true) || digest(o,"identity_digest")!=digest(*expected->second.value,"identity_digest") || digest(o,"state_digest")!=digest(*expected->second.value,"state_digest"))fail("receipt_observation_mismatch");++expected;
        }
    }
    if(kind=="execution") {
        id(v,"admission_id");integer(v,"sequence",true);const auto& s=step(plan,id(v,"step_id"));const auto event=text(v,"event");
        choice(event,{"intention","verified_completion","cancellation_request","recovery_observation"});const auto observed=digest(v,"observation_digest");
        if((event=="intention" && observed!=digest(s,"preconditions_digest")) || (event=="verified_completion" && observed!=digest(s,"postconditions_digest")))fail("receipt_observation_mismatch");
    }
}
}
std::string digest_text(const Digest& d) {const char* a="0123456789abcdef";std::string s="sha256:";for(const auto c:d) {s+=a[c>>4];s+=a[c&15];}return s;}
Definition::Definition(const V& v) {
    payload_=encode_payload(v);summary_=validate_plan(v);value_=v;digest_=hash(payload_);resources_=domain("DiskEd.plan.resources/1\n",field(value_,"resources"));
    auto providers=V::array();for(const auto& r:field(value_,"resources").items)if(text(r,"purpose")=="provider" || text(r,"purpose")=="executable")providers.items.push_back(r);
    providers_=domain("DiskEd.plan.providers/1\n",providers);
}
Receipt::Receipt(const Definition& d,const V& v) {payload_=encode_payload(v);validate_receipt(d,v);value_=v;digest_=hash(payload_);}
V inspect_receipts(const Definition& d,const std::vector<V>& values) {
    if(values.size()>128)fail("receipt_count_limit");std::vector<Receipt> receipts;receipts.reserve(values.size());std::map<std::string,const Receipt*> by_id;
    std::map<std::string,std::uint64_t> sequences;auto matched=V::array();
    for(const auto& v:values) {
        receipts.emplace_back(d,v);const auto& receipt=receipts.back();const auto& row=receipt.value();const auto name=text(row,"id");const auto found=by_id.find(name);
        if(found!=by_id.end()) {if(found->second->payload()!=receipt.payload())fail("receipt_identity_reused");continue;}
        const auto reference=[&](const char* field_name,const char* kind)->const V& {
            const auto p=by_id.find(text(row,field_name));if(p==by_id.end() || text(p->second->value(),"kind")!=kind)fail("receipt_reference");return p->second->value();
        };
        const auto kind=text(row,"kind");
        if(kind=="admission") {
            const auto& review=reference("review_id","review");const auto& grant=reference("grant_id","grant");const auto steps=ids(field(row,"step_ids"),32,false);
            if(text(review,"decision")!="reviewed" || !flag(grant,"host_effects") || steps!=ids(field(grant,"step_ids"),32,false))fail("receipt_admission_scope");
            const auto reviewed=ids(field(review,"step_ids"),32,false);for(const auto& s:steps)if(!contains(reviewed,s))fail("receipt_admission_scope");
            const auto attempt=text(row,"attempt_id");for(const auto& p:by_id)if(text(p.second->value(),"kind")=="admission" && text(p.second->value(),"attempt_id")==attempt)fail("receipt_attempt_reused");
        }
        if(kind=="execution") {
            const auto& admitted=reference("admission_id","admission");for(const auto n:{"operation_id","attempt_id","worker_identity","worker_epoch"})if(text(row,n)!=text(admitted,n))fail("receipt_attempt_mismatch");
            if(!contains(ids(field(admitted,"step_ids"),32,false),text(row,"step_id")))fail("receipt_execution_scope");
            auto& previous=sequences[text(row,"attempt_id")];const auto n=integer(row,"sequence",true);
            if(previous==(std::numeric_limits<std::uint64_t>::max)() || n!=previous+1)fail("receipt_sequence");previous=n;
        }
        by_id.emplace(name,&receipt);matched.items.push_back(V::object().put("id",V::string(name)).put("kind",V::string(kind)).put("digest",V::string(digest_text(receipt.digest()))));
    }
    return V::object().put("scope",V::string("private-fake-definition-receipt-binding")).put("matches_declared_bindings",V::boolean_value(true))
        .put("authenticated",V::boolean_value(false)).put("authorizes_effects",V::boolean_value(false)).put("validates_durability",V::boolean_value(false)).put("receipts",matched);
}
}}}
