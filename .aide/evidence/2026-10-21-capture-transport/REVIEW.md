# Owned capture receiver and transport

DE-W105 now has a private product-side receiver in source and a passing native
cross-process transport control. The actual GUI translation unit compiles. The
full DiskEd executable has **not** been rebuilt or captured by this run; the
product coordinator, six product PNGs and current full native qualification remain
the next gates. Main and the original full 0.1.0 objective remain unchanged.

Base: `2e95adc2f05938c902ade719aea1ed94dd836490`.
[Expected outcomes and offsets](expected.json) were recorded before evaluation.
The explicit replay refusal was added before evaluating the native probe. A first
preflight found a path used where the input graph requires a stable catalog ID;
the existing ID was retained and the reference corrected. The first native
compile found a byte-fill narrowing warning; it was corrected with an explicit
byte value under the unchanged `/W4 /WX` policy. Failed receipts and cleanup are
retained. The subsequent native run passes.

The GUI source routes `WM_COPYDATA` to the receiver only when its private
`DISKED_GUI_CAPTURE_TEST=owned-client-tree/1` setting is selected. The CMake
bootstrap products reference the capture library. These are source integration
facts, not fresh execution of a complete product. Public commands, discovery and
frontend models are unchanged.

The private request is exactly 640 bytes with explicit little-endian offsets.
It binds nonce, sequence, window/process/UI thread, queried job, output section,
image volume/file ID, case ID, desktop and frame bounds. There are no sender
pointers, paths or rendering colours in the packet. The receiver copies message
data before parsing, checks scope and bounds, and borrows the transferred handles
without closing them. Its state permits eight attempts, one nonce, the next
sequence and no reentrant capture. A caller-created anonymous section receives a
bounded 4096-byte header and client BGRA; the publication length is written last.
No GDI handle crosses processes. Rendering remains the qualified owning-thread
client-tree primitive.

The guest coordinator verifies the actual process image, token/user/integrity,
job membership, private desktop ACLs and window/thread/bounds before sending.
The existing independent supervisor job remains private. The section handle is
duplicated with write rights only and is not inheritable. Local views and handles
are released after the owned job reaches proven quiescence; a sender timeout is
not treated as retirement or as permission to retry.

Native results:

- All **20** packet/scope controls refuse invalid input without painting or
  changing the sentinel output. They also verify that borrowed handles remain
  open: disabled mode, tag/length/magic/padding, empty case ID, nonce/sequence and
  replay, window/process/thread/job/image/desktop/bounds, invalid/small sections,
  busy state and the exhausted request allowance.
- Two real cross-process requests reach one owned renderer through Windows
  message marshalling and anonymous sections. They have distinct cases and
  sequences, bind the actual producer, and match every one of the **23,040 RGB
  pixels** in both independent phases. Both actual retained PNGs were visually
  inspected as the expected distinct tile patterns. Replay also binds the packet,
  publication, frame metadata and pixels.
- A deliberately hung receiver times out the sender with Windows error 1460
  after its 500 ms allowance, without publication. The independent three-second
  job deadline retires it (3.0383 seconds observed including retirement). The
  receiver's normal two-request run takes 0.0925 seconds.
- All six earlier modes, eleven original scope/transition refusals, four child
  controls, lazy imports/startup, eight byte-I/O controls and the current 32 MiB
  capacity/confinement/canary/interruption proof pass again. Every one of **23**
  native calls reaches verified retirement. The actual GUI source compiles to an
  object; this does not establish full product linking or GUI behaviour.

The tested host is the existing Windows 10 guest, with the Agents coordinator
and a fresh restricted, non-elevated Medium-integrity ordinary renderer.
MSVC 19.44.35228/toolset 14.44.35207, SDK 10.0.19041.0, x64 and static CRT remain
the selected configuration. Historical Windows, other architectures/platforms,
accessibility/DPI and native Button/Edit/ListBox product capture remain unverified.

[Replay](replay.json) verifies all **44** archive entries and rejects changed raw
data, missing evidence and a coherently rehashed false capability claim.
The 867,971 selected bytes are retained in a **12,524-byte** archive; the raw
216,947-byte receipt is a verified **15,172-byte** XZ file. Executables, objects,
test media and transported guest source are removed. Guest actor/profile and
process cleanup is verified; unrelated processes were not killed. Guest C: has
96,848,691,200 bytes free after cleanup. The backing file's logical length is
unchanged; allocated backing growth was not measured.

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-21-cooperative-capture/replay.py --transport
```

The native campaign is the managed `campaign.py --capture-transport-proof`,
using a freshly verified DE-W105 context. Closed desktop-DC/hook paths remain
closed. This control does not admit them or qualify real DiskEd screenshots.

Next: connect the existing GUI fixture to a trusted cooperative product
coordinator. Keep its exact code-object pin, user/job/desktop ACL checks,
per-case receipts and caption/client/inert-review checks. Keep the supervisor
handle private when transferring a membership-job query capability. Represent
client pixels and frame coordinates explicitly, then qualify the six distinct
product cases and the current native suite before main integration. Owner,
release, reference/sanitizer and all original platform/storage gates stay separate.

The complete [host validation](validation.json.xz) passes **558 tests run, eight
skipped**: 253 specification, 221 tooling and 84 differential tests. It replays
the new transport archive and both unchanged earlier control archives without
rewriting historical receipts, passes 1,327 structural checks, covers all 329
source files once and verifies manifest freshness. Tested source inputs remain
unchanged. The managed host workspace peaks at 55,579,669 bytes and is removed.
Skips retain unavailable symlink, PowerShell 5.1 execution-policy and Linux
external-runner checks as unverified. These are host tooling results, not a
full native product pass.
