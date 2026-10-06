# DE-W017 partial local agent review

Reviewed `eb042ca0172920182b3427378adab13c18802e40` against `d468dad06425371a884a862ef8fc5bf341799dc1` and the DE-023/045 capture contract.
This is implementing-agent review under the continuation grant, not owner
acceptance or independent security review. The acceptance ledger stays empty.

- The coordinator has no process, effect or writer authority. Completion requires
  an exact outstanding key. A timeout keeps it outstanding; a prior-capture
  completion retires only its own slot and never contributes new graph data.
- Validation builds a candidate state first. Invalid fragments mark only the
  source malformed with old content stale; no candidate identity bindings leak.
  Allocation failures precede no-throw publication swaps. Rejected/removed data
  cannot reset the lifetime identity ceiling.
- Notice sequence is monotonic and bounded, distinct from capture and worker
  epochs. Eight notices retain at most fixed source metadata. Gaps and prior-
  capture cursors require a snapshot; a current epoch with a pre-reset cursor
  cannot retrieve old-capture notices. No operation truth is placed in this ring.
- Session refresh acknowledges a source pointer only after successful publication.
  Inspect dispatch uses one admitted snapshot. Selection and staged revision stay
  unchanged by refresh. The native allocation sweep checks retained old snapshots
  and a later explicit publication of the same update.
- The native fixture callbacks own process/pipe/job handles and no frontend
  references. Jobs are assigned atomically, with no breakaway or kill-on-close.
  A failed OS observation waits for actual exit rather than freeing an uncertain
  slot. Completed adapter results remain retained across throwing publication.
- The campaign's finite fixed-state pipe is not a generic provider API. Its
  internal executable role and mode report are compiled out of the product.
  Healthy product fixture bytes remain unchanged and essential commands do not
  initialize a provider. Producer denial is explicitly synthetic.
- Native campaign evidence spans stdio, Win32, TUI and shell and records actual
  process exits, job membership and cached-input timing. Superseded worker and
  notification-gap tests are serialized native reducer tests, not claims of
  OS/kernel-hang, public streaming or production journal qualification.
- Clean source reproduces all 29 native groups and response/graph/operation
  producer checks. Explicit build/context closures include the new implementation,
  tests and imported fixture helpers. Documentation retains remaining gates.

Continue local DE-W012/017 event-stream development. Neither DE-W017 nor the full
0.1.0 programme is complete.
