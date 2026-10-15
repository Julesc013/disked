# Implementing-agent review: supplied NTFS filename and directory index

DE-W087; base `1e6728c72b908467da3ffcb83fa2bc35a32938c7`.
Native source `3df1a1c7c30dabb39bba394321eff993b0e3431f`; tooling-fixture correction `cd65edcce290e02bd58c9712999033ebb70dc4f9`.
Existing authority permits local development,
test/repair and reviewed dev/main source synchronization across units. This is
implementing-agent review; owner acceptance and storage/release grants remain
separate. Original all-platform/storage 0.1.0 is unfinished.

The private C90 `portable/ntfs/filename.c` preserves a full parent reference,
opaque duplicated-information bytes, exact raw UTF16LE name and bounded suffix.
It separates safe nonempty field framing from unknown namespace/zero sequence
issues. It performs no normalization, lookup, Unicode-legality decision or claim
that duplicated metadata is current file state. `index.c` calls that decoder
while validating supplied directory-root and entry envelopes. It checks explicit
block/cluster geometry, 8-byte entry framing, key/trailer separation, node flags,
full references and terminal placement. Child VBNs remain exact observations;
no source offset is calculated or opened.

The cursor counts every complete header, including terminal and bad headers.
Quota checks precede the next header access. Exact terminal-at-limit succeeds;
missing/truncated terminals, unsupported entries and resource limits stop with
bounded observations. Repeated DE_EMPTY preserves both objects. No heap allocation,
I/O, callback, source identity, provider admission or public command is introduced.
Only new private types/functions are appended to the existing NTFS header/target;
existing structures, signatures and function implementations stay unchanged.
Qualified includes, source ownership and the complete311-file map remain checked.

Bounds review: the root must contain its fixed32-byte header before any fields
are read. All declared u32 boundaries are compared against the supplied span
before narrowing to size_t. Entry lengths are checked before subtracting a child
trailer or publishing key/padding views. Filename length is at most255 UTF16
units; safe subtraction precedes view construction. Original buffers stay
borrowed and readonly for their documented lifetime. Unknown root profile bits
and malformed keys never become a directory graph or traversal grant.

Clean Windows x64 Release native source passes **1,502 guarded cases**, **27
selected native groups**, **9 standalone C++ headers**, a separate strict
C90 header and all seven NTFS C sources on the recorded MinGW GCC.
The corrected tooling fixture passes **244 tooling tests(two skipped)**
in its separate clean checkout. Existing NTFS list/record/boot/attribute/
run/stream/closure/file/worker/frontend and selected checked/GPT/MBR/FAT/exFAT
regressions pass. Five probe/product import/PE/dependency observations, actual
compiler/SDK/static-runtime, graph/header usage, source map, manifest and source
context checks pass. All 1069 registered/build inputs
remain unchanged during the original clean campaign.
[Original exact commands and hashes](failed-3df1a1c7/summary.json).
That campaign remains **failed**: full tooling encountered four errors and one
failure from positive bootstrap contexts exceeding their default artifact budget.
The production tool correctly refused; no context was truncated. Correction
`cd65edcc` explicitly budgets both delivery channels from
the copied fixture footprint in two test files. The100-byte content refusal,
one-byte artifact refusal, freshness, determinism and existing-destination checks
retain their original meaning; content error matching and the unchanged marker
assertion are stronger. All seven focused cases and the full tooling suite pass.
Production tool/default limits, native source/build/domain test inputs and all
native library/executable/header-object hashes remain unchanged. The artifact
keeps its actual source identity`3df1a1c7`; it was not rebuilt for the fixture
correction. [Clean correction evidence](tooling-correction-cd65edcc/summary.json).
This is an explicit selection, not a new complete product campaign or qualification
of other hosts, ABI consumers, native directory acquisition or a whole filesystem.
The prior complete product campaign and its corrected declaration failure retain
their separate source-bound evidence; no deadline or test limit was weakened.

Independent recipes cover every name length in both profiles, raw controls and
surrogates, full48/16 references, geometry units, all truncations around fixed
headers and entry bodies, unsupported metadata, key/child separation, maximum
aligned u16 entry lengths, terminal/quota boundaries through4096 headers and
unchanged original/invalid-output controls. Native readonly/guard pages detect
out-of-span reads or source writes; scalar facts do not prove allocation, name
collation, sortedness, uniqueness, membership or source freshness.

Preparation errors remain in `working/`: new source rows used a registry
kind absent from the schema, corrected to the existing build classification;
recipe preflight found regex/header-string escaping and now checks warning-free
Python syntax and the exact generated C include before execution. Original
snapshots and the failed structural check remain. No schema rule or expected
native result was relaxed. The additional context-fixture capacity failure and
all original tracebacks remain; the original summary is never relabeled green.

Next implement protected INDX block/header restoration and bounded source-bound
record/index acquisition before admitting large-directory traversal. Namespace/
content, original platforms/storage, remote CI, Setup, physical/production writer
and recovery, owner acceptance and release qualification remain open. Eligible
for ordinary source integration after current metadata/context/staged-byte checks;
record actual Git writes separately.
