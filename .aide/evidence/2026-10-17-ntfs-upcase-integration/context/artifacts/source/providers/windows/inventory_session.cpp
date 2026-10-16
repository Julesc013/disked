#include "inventory_session.h"

namespace disked { namespace nt_inventory {
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
void inventory_publication_checkpoint();
#endif
struct InventoryPortState {std::shared_ptr<const InventoryPublication> publication;};
namespace {
using V=json::Value;
bool matches(const GraphObservation& observation,const CaptureKey& key,const std::string& frame,const std::string& context){
    return key.domain && observation.domain==key.domain && observation.source==key.source && observation.capture==key.capture &&
        observation.worker==key.worker && observation.frame_digest==frame && observation.context_digest==context;
}
const V& field(const V& value,const std::string& name){const auto* p=value.find(name);if(!p)throw std::invalid_argument("inventory_reference");return *p;}
std::string text(const V& value,const char* name){const auto& p=field(value,name);if(p.kind!=V::Kind::string)throw std::invalid_argument("inventory_reference");return p.text;}
bool storage_source(InventorySource source){
    if(source!=InventorySource::Namespace && source!=InventorySource::Storage)throw std::invalid_argument("inventory_source");return source==InventorySource::Storage;
}
}
InventoryPublication::InventoryPublication(std::shared_ptr<const CaptureView> view,std::shared_ptr<const NamespaceGraphEvidence> ns,
    std::shared_ptr<const StorageFrameEvidence> storage,std::shared_ptr<const StorageGraphEvidence> identity):
    view_(std::move(view)),namespace_(std::move(ns)),storage_(std::move(storage)),identity_(std::move(identity)){
    if(!view_ || view_->graph.profile!=GraphProfile::Observations)throw std::invalid_argument("inventory_publication");
    for(const auto& n:view_->graph.nodes){
        frame(n.id);
        if(n.kind=="storage-identity-observation")for(const auto& ref:field(n.observation.payload,"references").fields)resolve(n.id,ref.first);
    }
}
const GraphNode& InventoryPublication::node(const std::string& id)const{
    for(const auto& n:view_->graph.nodes)if(n.id==id){if(n.scope!=GraphNodeScope::Observation)break;return n;}
    throw std::invalid_argument("inventory_node");
}
const V& InventoryPublication::frame(const std::string& id)const{
    const auto& n=node(id);const auto& o=n.observation;
    if(o.source=="namespace" && namespace_)for(const auto& f:{namespace_->current(),namespace_->last_complete()})
        if(f && matches(o,f->key(),f->frame_digest(),f->context_digest()))return f->value();
    if(o.source=="storage" && storage_)for(const auto& f:{storage_->current(),storage_->last_complete()})
        if(f && matches(o,f->key(),f->frame_digest(),f->context_digest()))return f->frame().value();
    throw std::invalid_argument("inventory_frame_binding");
}
const V& InventoryPublication::resolve(const std::string& id,const std::string& name)const{
    const auto& n=node(id);frame(id);
    if(n.kind!="storage-identity-observation" || n.observation.source!="storage" || !identity_)throw std::invalid_argument("inventory_reference");
    const auto& reference=field(field(n.observation.payload,"references"),name);
    return identity_->resolve(text(reference,"kind"),text(reference,"digest"));
}
std::shared_ptr<const InventoryPublication> InventoryPort::publication()const{return state_->publication;}
std::shared_ptr<const GraphInput> InventoryPort::graph()const{
    const auto owner=state_->publication;return std::shared_ptr<const GraphInput>(owner,&owner->view()->graph);
}
InventorySession::InventorySession(StorageFrameProfile profile,StorageGraphProjection projection):
    capture_({"namespace","storage"},GraphProfile::Observations),namespace_(capture_,"namespace"),storage_(capture_,"storage",profile,projection),
    state_(std::make_shared<InventoryPortState>()){publish();}
void InventorySession::release(InventorySource source){if(storage_source(source))storage_.release();else namespace_.release();}
void InventorySession::cancel(InventorySource source){if(storage_source(source))storage_.cancel();else namespace_.cancel();}
bool InventorySession::timeout(InventorySource source){return storage_source(source)?storage_.timeout():namespace_.timeout();}
bool InventorySession::wait_entered(InventorySource source,DWORD ms){return storage_source(source)?storage_.wait_entered(ms):namespace_.wait_entered(ms);}
V InventorySession::poll(InventorySource source,DWORD ms){return storage_source(source)?storage_.poll(ms):namespace_.poll(ms);}
V InventorySession::retire(InventorySource source,DWORD ms){return storage_source(source)?storage_.retire(ms):namespace_.retire(ms);}
bool InventorySession::needs_publication()const{return !state_->publication || state_->publication->view()!=capture_.snapshot();}
bool InventorySession::publish(){
    if(!needs_publication())return false;
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
    // Separate fixture build arms the actual allocator; never a runtime option.
    inventory_publication_checkpoint();
#endif
    auto prepared=std::shared_ptr<const InventoryPublication>(new InventoryPublication(capture_.snapshot(),namespace_.frames(),storage_.frames(),storage_.evidence()));
    state_->publication.swap(prepared);return true;
}
}}
