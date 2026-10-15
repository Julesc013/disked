# Supplied-byte NTFS directory envelopes

DE-W087 adds private FILE_NAME and INDEX_ROOT/entry decoders before native NTFS
namespace traversal. Its [execution contract](../spec/catalog/ntfs-index-prototype.json)
defines exact name/reference preservation, geometry, framing, terminal and quota
outcomes before implementation/evaluation. Implementation and verification are
pending for the clean source; the working guarded corpus passes 1,502 cases. Bounded directory bytes do not prove a directory graph, collation,
allocation or source freshness. The original all-platform/storage0.1.0 and
separate owner/privilege/release gates remain.
