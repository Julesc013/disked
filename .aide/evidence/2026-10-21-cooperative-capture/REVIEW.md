# Cooperative owned-client control

DE-W105 remains partial. The separately compiled cooperative repaint control
passes on the existing Windows 10 guest. It establishes exact pixels from its
own client renderer without reading a desktop DC or injecting a hook. The new
private source library is **not linked into DiskEd**. Product capture, the six
named product PNG cases, full current native qualification and main integration
remain open.

The working-tree base is `3837a23c52246fbf8673b53db38c1d982dbcb36a`.
[Expected outcomes](expected.json) were fixed before evaluation. The pixel recipe
remains the original version 1 recipe; no expectation, refusal or deadline was
relaxed after a failure. [Raw results](result.json.xz), the
[verified observation archive](observations.tar.xz) and [host replay](replay.json)
bind the actual implementation and observations. These are engineering evidence,
not owner acceptance or release authority.

The renderer and capture primitive are separate C++ translation units. The
primitive receives the exact owned window/process/UI-thread/job/desktop/nonce,
held executable file identity and bounds; it does not receive colours or the
challenge seed. It creates a memory DC and DIB in the owning process and asks
that same UI thread to repaint its client. Identity and geometry are checked
before and after rendering. An outer job deadline bounds a blocked renderer;
the synchronous Windows call itself has no independent timeout.

The initial two native attempts exposed compiler defects (DPI context type and
SID string conversion), repaired under the unchanged `/W4 /WX` contract.
Two subsequent attempts stopped before rendering when the child could not open
a test job by name; the diagnostic attempt records `ERROR_FILE_NOT_FOUND`.
That result does not establish a complete namespace diagnosis. The final
implementation uses anonymous jobs and explicitly duplicates two non-inheritable
`JOB_OBJECT_QUERY` handles into the already assigned, suspended child. Its bounded
stdin is finalized before its first instruction. No GDI handle crosses processes.
Earlier failed receipts and owned cleanup remain here, compressed where material.

The final native run used MSVC compiler 19.44.35228/toolset 14.44.35207,
SDK 10.0.19041.0, x64 and static CRT. It compiled the control, compiled its
standalone header and recorded imports. The coordinator was guest
`BLACKGLASS-HYPE\Agents`; renderers used a fresh restricted Medium-integrity
ordinary account, with no administrator elevation or AppContainer token.

- Both phases match all **23,040 RGB pixels** independently reconstructed from
  the frozen seed recipe. All **eleven** wrong-identity, wrong-thread, epoch and
  geometry controls refuse pixels. Successful captures retain two GDI objects
  before and after; no GDI object growth was observed.
- Blank output and stale phase A substituted for B fail the pixel oracle.
  The blank renderer's successful capture status therefore does not qualify it.
- A hung repaint reaches the unchanged three-second deadline (3.0303 seconds
  observed including retirement). Closing the independent unnamed supervisor
  handle alone retires another hung renderer in 0.0354 seconds while it holds
  its membership-job query handle. The supervisor handle is never exposed to
  that child. This is a handle-loss fault control, not a real VM crash.
- Attempts to obtain assign/set/terminate job authority are denied. Write and
  delete opens of the pinned executable are refused. Source/image identities
  remain unchanged. Invalid mode exits 2 without creating a window.
- The original 32 MiB capacity/confinement/canary/interruption proof and all
  eight byte-I/O controls also pass. All **16** native-port calls reach verified
  retirement and remove their stdio files.
- Host replay verifies all **21** archived entries and rejects altered raw data,
  missing frame data and a false capability report even after its retained hash
  is recomputed. Both actual retained PNGs were visually inspected: distinct
  four-by-four colour tiles, with no desktop or console content.

The archive is **8,180 bytes** for 431,959 bytes of selected entries; the raw
138,729-byte receipt is retained as an **11,412-byte** verified XZ file. No
executable, object tree or generated image is retained. Guest owned
account/profile, source transport and virtual scratch are removed; unrelated
processes were not killed. The VM backing file's logical length remains
34,144,780,288 bytes. Allocated backing growth was **not measured**; zero logical
length change is not a physical-allocation claim. The guest C: volume had
96,849,743,872 bytes free after cleanup.

Replay through the managed runner:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-21-cooperative-capture/replay.py
```

The native control requires a freshly verified DE-W105 context, the existing
authenticated guest route and the current original proof. Its bounded invocation
is `campaign.py --cooperative-capture-proof` through `tools/workspace.py run`.
Old foreign-DC and sent/queued-hook routes remain closed.

Next: define and implement the private product-side owning-thread request and
reply boundary, and separately qualify child-control/client-tree rendering.
The current primitive captures only a cooperating client's own repaint; it does
not establish complete child-control, nonclient, compositor or product rendering.
Bind each actual product case to its own request, then qualify the required six
PNGs and current native suite before promoting dev to main. Retain the original
all-platform/storage 0.1.0 objective and separate owner/release gates.

The complete [host validation](validation.json.xz) passes **554 tests run, eight
skipped**: 253 specification, 217 tooling and 84 differential tests. Structural
validation passes 1,327 checks; the source map covers all 329 source files once.
The run also replays this archive and verifies manifest freshness. Tested inputs
remain unchanged. The managed host workspace peaks at 55,392,285 bytes and is
removed. Skips retain unavailable symlink, PowerShell 5.1 execution-policy and
Linux external-runner checks as unverified. These are host tooling results,
not a full native product pass. The older validation helper now binds the real
`docs/source-map.md`; historical input maps are preserved.
