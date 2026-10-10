#pragma once
#include "image_observation.h"
namespace disked { namespace evidence { namespace proposal {
json::Limits image_collection_limits();
std::string image_collection_hex(const std::string& bytes);
std::string image_collection_bytes(const std::string& hex);
// A new append produces a new snapshot. Restore validates historical contracts;
// it cannot authenticate an actor, dereference a retained path or grant access.
class ImageVerificationCollection final {
    struct Entry {ImageVerificationObservation observation;json::Value observer,record;};
    AcquisitionCase original_;std::string request_,history_,id_,context_;
    std::vector<Entry> entries_;json::Value view_;std::string revision_;
    json::Value full() const;
    void refresh();
public:
    ImageVerificationCollection(const std::string& collection_id,const AcquisitionCase&,
        const std::string& raw_request,const std::string& raw_history);
    ImageVerificationCollection with_observation(const ImageVerificationObservation&,const json::Value& observer) const;
    static ImageVerificationCollection restore(const std::string& bytes);
    const json::Value& view() const {return view_;}
    const std::string& revision() const {return revision_;}
    json::Value support(const json::Value& policy) const;
};
// Private complete retention, distinct from selected support. The effect port
// additionally requires an explicit private_metadata grant for this artifact.
class CollectionRetentionArtifact final {
    std::string bytes_,digest_;json::Value description_;
public:
    explicit CollectionRetentionArtifact(const ImageVerificationCollection&);
    const std::string& bytes() const {return bytes_;}
    const std::string& digest() const {return digest_;}
    const json::Value& description() const {return description_;}
};
}}}
