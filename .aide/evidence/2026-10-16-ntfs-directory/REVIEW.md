# Implementing-agent review: source-bound NTFS directory indexes

DE-W089; base `5a009d5692279e06571d6270c88f3e87bc0bc5e7`; exact tested native source `7bb6153a9bc86710dff9972f493c9ff14280caed`.
The existing grant permits local implementation, testing/repair and reviewed
dev/main synchronization across units. This is implementing-agent review, not
owner acceptance, independent safety qualification or release/storage authority.

The private directory entrypoint reuses the capture Observer's immutable source
controls, boot/MFT/Volume checks, checked mappings, source-bound attribute-list
closure, read/retention/output quotas and final rereads. The new directory
collector owns graph/bitmap meaning through three narrow callbacks. It stays in
the existing capture target; no duplicate opener, parser, scheduler, frontend,
public ABI or speculative directory hierarchy is introduced. The source map
accounts for all 317 current files and the measured maximum source path remains
62 characters. The existing five source owners remain appropriate.

The selected full FILE reference and exact raw UTF16LE $I30 streams bind every
directory observation. Zero selects only reserved root ordinal5 and discovers
its sequence from that mapped FILE. Directory bases require flags3; extension
records retain separate full-owner/reference validation. Supported boot index
geometry is checked before the directory FILE read. Each INDX block binds its
expected VBN/size, restores only into a separate buffer and preserves original
and restored hashes. Header quotas are global; queue and bitmap bounds are
checked before extra work. Breadth-first child acquisition requires initialized
coverage and a set allocation bit, rejects repeated/cyclic/shared child VBNs
and inconsistent leaf depths, and reconciles reachable blocks with all set bits.
Every key's parent must match the full directory reference. Exact names and
target references survive without target-record reads or display normalization.

Static review covered failure-prefix ownership, callback/request copies,
checked offset/length arithmetic, alias checks against prior/new mappings,
cursor lifetime, terminal-at-budget handling, bitmap bounds and the distinction
between local collection completeness and final source applicability. Supplied
source identity remains an assertion; finite equal rereads are not atomicity.
No namespace, collation, target membership, global cluster allocation or effect
authority is inferred from this collection. Default bootstrap semantics and read
order remain unchanged. Header/source/build boundary checks retain the same owners.

The independently constructed sparse corpus passes 227 cases, including both
versions, fragmented/split streams and source-bound extension lists, old/new
FILE headers, multiple geometries, multi-level/sibling/empty/preallocated indexes,
raw names/namespaces, full references, offsets above 4GiB and 2^53, the 128-block
and 64KiB bitmap limits, exact read/quota boundaries, malformed records/USA/keys,
aliases, cycles, leaf depth, every source-response fault/reread change and caller
control mutation. Expected bytes, reads, hashes and diagnostics precede native
evaluation. Sources are guarded and returned JSON owns its data after buffers end.

One clean Windows x64 Release campaign passes 160/160 registered native groups,
63 standalone C++ headers, nine NTFS C sources and two C headers under strict
GCC C90, and 244 tooling tests (two known symlink skips). Build/header boundaries,
source map, compiler/SDK/runtime, seven PE/import observations, context/manifest
and all 1089 original registered/build input hashes
pass with a clean checkout before/after. [Exact campaign](qualified-7bb6153a/summary.json).
This is the complete registered campaign, with no selected-suite substitution
or changed timeout. Existing bootstrap/closure/stream and prior NTFS corpora pass.

The isolated Win32/WOW64 fixture passes four groups: 155 bootstrap, 298 stream,
134 closure and 227 directory cases, four standalone headers and two probe PE/
import observations. [Corrected supplement](win32-corrected-7bb6153a/summary.json)
uses the unchanged native source above with receipt recipe `8ac4faa2ac413ddb20f281058c028f5ff00180cc`,
whose exact hash is retained. The original supplement passed native groups,
then failed because its receipt expected 154 bootstrap cases. The independent
fixture and preceding retained campaign both establish 155. Only that assertion
changed; product code, native expectations and build settings did not. The
[original failure](win32-failed-7bb6153a/summary.json) remains failed. The corrected
recipe does not qualify a native source build at 8ac4faa2, a full Win32 product,
historical Windows or another host. Post-campaign metadata binds that sole
recipe exception separately from the unchanged x64 source inputs.

Ordinary source integration is appropriate after metadata/staged-byte closure.
Next, extend the existing held-file/replay and worker path for this directory
mode, with a pre-evaluation contract for profile selection and exact replay.
Bootstrap automatic3.0 selection cannot simply relabel a directory run which
stopped before directory reads. Do not add another file opener or weaken replay.
Complete namespace/content, original platforms/storage0.1.0, writer/recovery,
Setup, licensing, owner and release/privilege gates remain open. Earlier failed
campaigns retain their original outcomes and unknown historical delay causes.
