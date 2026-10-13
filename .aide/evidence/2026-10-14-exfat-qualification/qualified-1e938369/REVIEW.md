# DE-W058 implementing-agent review

Evaluated source: `1e93836989ea2a9a4e163d0c9644511877455d0e`.

The decoder operates on borrowed bytes and uses the existing checked limb-based
integer layer. It has no host callbacks, dynamic allocation, native64 requirement,
mount action or product-dispatch path. Invalid calls and overlong views preserve
the output. Media contradictions return explicit observations, with geometry
usable only after the complete region, checksum and selected profile checks pass.
The raw view remains caller-owned and must outlive any use of that observation.

The main/backup role is supplied by the caller; this function does not prove the
region's location on a volume. Backup mutable fields remain stale. TwoFAT geometry
is observed without proving TexFAT transaction consistency. FAT cells retain raw
values; zero alone does not establish allocation or free space. Chain cycles,
allocation bitmaps, upcase, directories and source coherence remain later work.

This is an intentionally narrow revision1.00 profile. Other minor revisions and
nonzero reserved bytes are conservatively excluded from usable geometry; that is
a private prototype admission choice, not a claim that every such volume is
corrupt under the general exFAT specification. General compatible-reader behavior
must be settled before mounted/provider admission. Volume byte conversions beyond
the internal u64 address model produce an overflow issue even though the on-disk
sector-count field can represent that number. No structure is a persisted ABI.

The exact clean-source campaign passed130native groups,42standalone headers,
242tooling tests with2skips, generated target/header boundaries, actual product
launch/discovery, compiler/import/artifact/source identities and context freshness.
The executed four-criterion audit passed. The prior129/130failed campaign and
successful exact-focus frontend fixture repair remain retained separately.

This records local implementing-agent review, not independent human review or
owner acceptance. No physical/provider/mount/writer/recovery/otherhost or full
all-platform/storage0.1.0 release qualification follows.
