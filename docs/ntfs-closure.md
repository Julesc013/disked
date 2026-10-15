# Source-bound NTFS record closure

DE-W086 extends the existing supplied-reader, ordinary-file, owned-worker and
inspection path with resident/nonresident lists and reachable MFT/Volume FILE
dependencies. The [execution contract](../spec/catalog/ntfs-closure-prototype.json)
defines identities, quotas, original-byte binding, rereads and projection.

Native source `540043c3` passes134 new closure cases and all runtime groups
in a157-group campaign. That campaign has156 passes and one stale dependency
declaration failure; metadata `fb562480` corrects only three transitive
closures and passes both boundary groups without changing source/build/test
inputs or native artifact hashes. The original full run remains failed.
60 standalone headers and244 tooling tests(two skips) pass.
[Evidence and implementing-agent review](../.aide/evidence/2026-10-16-ntfs-closure/REVIEW.md)
preserve both phases, exact commands, hashes and original failures.

Reads require complete known coverage inside initialized bounds. Protected
originals and list values stay owned and bound to full references and source
context. Every region enters exact parent replay and final source rereads.
Missing/stale/unsupported/quota outcomes remain incomplete. New detail uses
bounded prefixes and original counts/hashes; the MFT run summary stays scalar.

General records/namespace/content, original all-platform/storage0.1.0, physical
devices, production writers/recovery, other hosts, Setup, owner acceptance and
release qualification remain separate work and gates. No remote CI qualification
is claimed.
