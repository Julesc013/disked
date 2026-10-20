# Bounded cooperative child-tree control

The next DE-W105 capture prerequisite passes in the existing Windows 10 guest.
The private primitive can repaint a bounded tree of windows on its owning UI
thread, while preserving lazy GUI dependencies. It is still **not linked into
DiskEd**. Real product controls, product request/reply, six product PNG cases and
full current native qualification remain open.

The source working-tree base is `fe86e9ceec4a1557e3bf23707958c817bb974804`.
[Expected outcomes](expected.json) were fixed before tree implementation and
native evaluation. The new run retains all five original modes, eleven original
scope/epoch/geometry refusals, eight raw-I/O controls and the current 32 MiB
capacity/confinement/canary/interruption proof. No original pixel recipe, timeout,
resource limit or refusal was weakened. The first native attempt passed.

The implementation snapshots at most 64 descendants and eight levels. Each
descendant must have the expected parent and the root's actual process and UI
thread. It records the ordered HWND, parent, thread/process, rectangle, visibility,
style and class, then checks that snapshot again after rendering. Missing object
names also fail closed. All USER32/GDI32 calls in the primitive now resolve lazily
from System32; its static library links only Kernel32. The existing GUI loader
ownership is retained.

In tree mode, the root paints black. Two child windows alone paint the left and
right halves of the independently specified 240×96 tile pattern. Both phases
match all **23,040 RGB pixels**, so parent-only painting cannot pass this case.
The capture uses same-process `WM_PRINT` with client, erase and children flags;
it does not request nonclient or owned-popup rendering and never reads a display
DC. Four additional controls pass:

- An actual child window on another UI thread is refused before rendering.
- A tree containing 65 children is refused before rendering.
- A child rectangle changed during rendering returns no pixels.
- A child hidden during rendering returns no pixels.

The two successful tree captures have four GDI objects before and after.
Both retained tree PNGs were visually inspected: distinct four-by-four colour
patterns, without desktop or console content. The two-tile-window case establishes
custom child rendering; it does not establish native Button/Edit/ListBox glyphs,
complete layouts, accessibility, nonclient or compositor rendering. The depth
bound is implemented; this run's explicit traversal-boundary case is the count
limit, not a nine-level native test.

A second, capture-only CUI probe compiles and links without USER32/GDI32 libraries.
Its retained imports contain neither DLL. Actual execution checks that an invalid
request leaves both module identities unchanged, returns no pixels and prints
`capture-lazy-startup-ok`. This establishes the primitive's import/startup boundary,
not a fresh full-product essential-command qualification.

The run uses the existing Agents coordinator and a fresh restricted,
non-elevated Medium-integrity ordinary renderer on its private desktop. It retains
the same compiler 19.44.35228/toolset 14.44.35207, SDK 10.0.19041.0, x64 and static
CRT. Query-only handles are duplicated before the assigned child resumes; the
unnamed supervisor handle is not exposed to it. Blank/stale rejection, the
three-second hung-paint deadline and controller-handle-loss retirement all pass
again. Every one of **20** native-port calls reaches verified retirement.

[Replay](replay.json) verifies all **32** entries and rejects altered data, missing
frames and a coherently rehashed false capability report. The selected archive
is **9,452 bytes** for 638,879 uncompressed bytes. The 169,669-byte run receipt is
retained as a verified **12,508-byte** XZ file. No executable, object tree or test
image is retained. Owned guest actor/profile, source transport and scratch are
removed; unrelated processes were not killed. Guest C: has 96,849,580,032 bytes
free after cleanup. The backing file's logical length is unchanged; allocated
backing growth was not measured.

Replay with:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-21-cooperative-capture/replay.py --tree
```

The native invocation is the existing managed `campaign.py` with the strictly
bounded `--cooperative-tree-proof` mode and a fresh verified DE-W105 context.
Old desktop-DC and sent/queued-hook paths remain closed.

Next: implement a private product receiver and coordinator transport with explicit
owned capabilities and per-case identities. Keep public commands and essential
startup unchanged, qualify real native controls and the six product cases, then
run the current full native suite before main integration. Owner/release,
reference/sanitizer, historical-platform and the original all-platform/storage
0.1.0 gates remain separate.

The complete [host validation](validation.json.xz) passes **555 tests run, eight
skipped**: 253 specification, 218 tooling and 84 differential tests. It also
replays the new archive and the unchanged original client archive, passes 1,327
structural checks, covers all 329 source files once and verifies manifest
freshness. Tested source inputs remain unchanged. The compatibility replay is
retained separately in `backward-replay.json`; the prior review receipt is
preserved. The managed host workspace peaks at 55,463,339 bytes and is removed.
Skips retain unavailable symlink, PowerShell 5.1 execution-policy and Linux
external-runner checks as unverified. These are host tooling results, not a
full native product pass.
