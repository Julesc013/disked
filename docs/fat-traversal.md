# Paged FAT directory traversal

DE-W053 implements a private directory traversal in
`runtime/capture/fat_traversal.*`. The runtime owns continuation, page meaning,
source bindings and resource outcomes. Existing portable FAT algorithms decode
the supplied allocation cells, directory records and long names. No file path,
OS handle or filesystem effect is introduced into the runtime.

The iterative traversal retains one active allocation cursor, a global bitmap of
observed directory storage and a bounded queue of child directories. It emits
bounded pages instead of retaining all entries in one JSON result. It can cover
trees larger than 128 entries and directory chains longer than 1,024 clusters.
Bitmap memory, queued directories, depth and each page's reads, records, events
and bytes remain explicit resources. Exhaustion is an incomplete observation.

Entry identities use their exact source-record offset within a binding containing
source ID, capture ID, epoch, source size, volume window and selected FAT copy.
Each call requires the same binding. The mandatory applicability callback runs
before and after reads and before page publication. Withdrawal permanently stops
reads; prior pages remain historical observations. The callback and page hashes
do not authenticate a source or establish an atomic snapshot. Held native source
and contained worker qualification remain separate.

Original short-record bytes, timestamps, attributes, cluster words and sizes stay
separate from decoded meaning. Pending long-name slots and their source offsets
survive pages, sectors and clusters. Original UTF-16 units remain intact; display
escapes control and malformed units. Deleted entries carry their original bytes
without invented live metadata. Interrupted and orphan name fragments remain
observable. Contradictory directory attributes, cluster words or file state are
preserved but explicitly prevent descent. Dot entries are never followed.

Directory cycles and reused storage stop repeated expansion. File allocation,
global cross-links, consumer name rules, payload extraction and destination
metadata restoration require further work. This traversal grants none of them.
Old monolithic captures, selectors and extraction versions retain their meaning.

Pages bind an ordered event stream through a sequence and chained private SHA-256
digest. Output exhaustion retains pending events. Missing pages or altered events
are detectable by an independent reader; hashes alone grant no authority.

Focused native development tests pass, including a 17,601-entry tree with a
1,100-cluster directory chain, deep parents, cross-page names, scope refusal,
reader faults and independent page-hash reconstruction. Exact clean source
qualification is pending. The [expected contract](../spec/catalog/fat-traversal-prototype.json)
and [source map](source-map.md) retain the ownership and qualification boundaries.
