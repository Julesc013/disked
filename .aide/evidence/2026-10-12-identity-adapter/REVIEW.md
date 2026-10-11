# Implementing-agent review of owned identity graph publication

Source `4666c6f7aa30cbadb60e7724cf14806f652b70bc` qualifies a partial DE-W030 slice. This is the implementing
worker's review, not independent or owner acceptance. The complete all-platform/
storage 0.1.0 programme remains active and incomplete.

The private execution contract was recorded before evaluation. Existing
`StorageGraphAdapter` now explicitly selects `Identity` projection with the
existing owned /2 IdentityLayout query profile. Original /1 and /2 frame
projection remains the default. Before coordinator publication it prepares the
actual immutable frame, native identity, compact graph and sealed matching
evidence owners. After the exact attempt's graph is accepted, owners swap
without allocation. A state change alone is insufficient: malformed/rejected
source state cannot admit prepared owners. Duplicate polls preserve the owners.

`StorageGraphEvidence` retains current and last selected-query-complete native
projections and resolves complete exact-kind/digest values without polling,
launching, file/path/network lookup or deserialized ownership. Complete captures
replace both; partial captures replace current while carrying forward stale rows
from the actual last complete projection. Repeated partial results do not replace
that complete evidence with another partial. Comparison selections explicitly
name previous/current disk subjects and the exact retained prior digest before
launch. Current digests derive from actual results. No comparisons are inferred
from matching names; more than 16, duplicate current subjects, absent previous
content, incorrect digests and invalid previous subjects refuse before registration
or launch. Invalid current subjects refuse after the owned result without replacing
published evidence. Previous values are retained directly, not as projection chains.

Actual held-reader tests establish publication and reader retirement are separate.
Timeout, cancellation, cached model inspection and reference retrieval do not
permit premature replacement. Superseded results retain earlier owners and stale
rows. Selected actual allocation failures before owned derivation and coordinator
publication preserve snapshot/owners. A failure in retirement after publication
retains the new graph and matching owners with the exact attempt still outstanding;
retry retires that owned handle. A coordinator aggregate-graph budget refusal keeps
the earlier evidence and explicit malformed/stale source state. No limits were
widened and no complete content was truncated. Native evidence retained by a caller
still resolves after adapter destruction, without a persistence/reconnect guarantee.

Clean x64 and Win32 builds on Windows 10 Enterprise 19045 x64 pass 26 campaigns:
2168 controller/reader processes and 70406 assertions. The new adapter
campaign contributes 34 controllers, 60 actual readers and 4338 assertions per
architecture. It covers complete/repeated partial/recovered captures, explicit
unchanged/changed/incomparable comparisons, duplicate/cloned hints, all 16
comparisons, original maximum detail, prelaunch refusal, unknown/crashed readers,
timeout/cancellation/supersession, live duplicate publication, retained callers,
allocation boundaries and aggregate-graph rejection. Complete native references
and every owned row are independently checked through CLI/shell/TUI/GUI models.
Existing owned-frame, identity, projection, raw-layout, namespace, capture-domain
and frontend regressions pass. These identity fixtures qualify models rather than live GUI-window/terminal
integrations. Product regressions separately test their established fake-only
scope. Other host OSes remain unverified; Win32 runs on the x64 tested host.

Two failing uncommitted test attempts are retained. The first oracle invented a
frame schema label instead of using the existing /2 prototype contract. The second
expected complete coverage for duplicate/cloned candidates, whereas the existing
frame contract marks those conflicts partial. Corrected expectations were checked
against the canonical owner and existing implementation; ambiguity and every full
reference remain asserted. These diagnostics are excluded from clean source-bound
qualification totals. No product behavior or safety checks were weakened.

Fresh x64 dev.41 build/launch/import observations and all 77 product groups pass.
The 25 reducer tests come from that same run without a duplicate campaign.
478 exact source/blob/checkout inputs, 1069 structural checks and
215 tooling tests (213 passes/2 skips)
qualify this scope. Retained inventories bind 30 local PE artifacts and byte-exact,
optionally lossless-gzip receipts. Executables and generated images are not in Git.
The injected allocation checkpoints are compiled only into the separate adapter
probe; other private probes and the shipped fake product have no such selection.

DE-W030 remains partial. Live/provider/public/product integration, physical
identity/association/freshness, other historical hosts, owner/full-unit admission
and storage/release gates remain open. The adapter/coordinator are serialized
private owners, not a stable external/concurrent API. No physical device, elevation,
customer media, installation, signing or release artifact publication was used.
Repository dev/main synchronization is separately authorized by the user.

Connect accepted owned inventory and retained native evidence to the existing serialized frontend observation port, including mixed namespace/storage captures, consumer publication failure and retry without polling during presentation or losing matching evidence. Preserve /1 and /2 defaults, native domains, bounded owners, explicit comparisons and existing budgets. Keep the full all-platform/storage 0.1.0 scope and separate live/physical/provider/public/product/historical-host/owner/storage/release gates.
