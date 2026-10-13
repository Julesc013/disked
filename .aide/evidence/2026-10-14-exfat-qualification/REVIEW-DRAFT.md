# DE-W058 review notes — qualification pending

Evaluated source: `38b6683ab037a092d07375c1d6391033b3287306`.

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

Working oracle, guard, C90 and full-build/tooling results passed. Clean-source full
native/header/import/regression qualification is still running. These review notes
do not complete the work unit, record owner acceptance or qualify other hosts,
physical storage, writers, recovery, release or full all-platform/storage0.1.0.
