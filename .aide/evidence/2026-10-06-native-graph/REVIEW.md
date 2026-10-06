# DE-W013 development review

Base: `fbba22c25ad614bd3d0c3a9976987d10319d1c70`.
Authority: the explicit local 0.1.0 programme grant in
`.aide/programmes/disked-0.1.0.json`. This is agent review, not independent
safety qualification, owner acceptance or permission for release/storage effects.

The slice implements immutable graph captures and a serialized frontend service.
CLI and stdio use that service for list, inspect, topology and capability reads.
The private typed action API supports inspection, identity selection and clearing
selection; test-only publication exercises replacement, removal and reordering.
No real provider, raw handle, external file, worker thread, durable operation,
GUI/TUI or mutation executor is admitted.

Reviewed boundaries:

- Provider initialization is lazy, after complete argument/request validation.
  Essential commands and malformed reads run under an initialization trap.
- Snapshot construction validates bounded copies before publication. Capture
  epochs distinguish refreshes; the digest binds exact content and capture.
  Public snapshot references are const; old captures remain independently owned.
- Publication validates retained ID/identity/generation mappings before swapping
  any state. Missing selection retains its original ID, never another row.
- Cached observations are separate from storage permission. Unknown capacity is
  null. Capability qualification remains unknown and all execution grants false.
- Human output escapes all controls/non-ASCII values; JSON retains underlying
  labels, including adversarial terminal data. Alias strings are never handles.
- Build inputs bind the new code, schemas and native test harnesses. Prototype
  discovery reports implemented handlers without promoting global descriptors.

The first independent revision comparison failed because the contract had not
specified short versus six-byte control escapes. Native SHA-256 vectors passed;
Python's default JSON serialization used a different newline representation.
DE-023 now specifies every escape, and an independent encoder checks fresh
captures with quotes, backslashes, control characters and Unicode. No digest
was hardcoded to replace that check. The initial native failure log is retained.

An additional schema test initially placed a state loop in the wrong method
(`NameError`); the initial full-suite failure is retained. The aggregate byte-limit
test initially expected the parser's input-limit name. Publication correctly
returned the existing writer's `output_limit_exceeded`; the corrected test checks
that output boundary and proves the prior snapshot survives. These were test
construction defects, not justification to weaken limits or skip scenarios.

Limitations: publication/actions are serialized and private to this development
profile; a real concurrent provider needs admission serialization and independent
capture/worker epochs. Deterministic fake captures restart at `fake:1`; this is
not cross-process or physical-media freshness. Selection refresh is tested through
a private probe, not a hidden product command. GUI/TUI parity and accessibility,
async operations, physical identity, real storage, other hosts and clean-VM
qualification remain unverified. Production wire/storage ABI is not frozen.

Final build/test identities and clean reproduction are recorded separately in
`working-results.json` and `clean-results.json`. The next local work is DE-W014,
using these shared actions without moving eligibility logic into the frontend.
