# Agent review of the partial recursive backend

Preparation consumes the complete held-source namespace without output. Compact
nodes and ordered event commitments bind original parent/entry metadata and exact
name policy. The immutable definition declares all six resources, identity/epoch,
known aliases, access, footprints, verification and observed failure domains;
source and code/parent handles persist. Missing/wrong grants and preflight name,
budget, alias or existing-path refusals produce no destination/ledger effect.

NtCreateFile uses constant FILE_CREATE relative to ordinary held parents, with
no existing-object fallback. Newly owned objects keep file-ID/path/type/alias
checks. Ledger identity is checked too. Every destination effect has a flushed
intention; chunks are flushed and read back before checkpoint records. Original
metadata/namespace/allocation observations stay in the canonical hash chain.
Directory metadata is deferred, and creation-time changes do not invalidate the
file-ID ownership check. Unspecified/invalid/raw-only fields remain unapplied.

Completed read preparation is explicitly reinspected on the same held source
with a fresh capture identity. Imported frames do not create source membership.
Execution compares original commitments before admitting entries/content. Source
read agreement is not called an atomic snapshot or global filesystem health.

The review identified and fixed a concrete completion-observation issue: a
notification exception after the final outcome was flushed initially could
append a contradictory partial outcome. The completion flag now commits before
notification and the actual failure/exit cases retain one completed outcome.
Verified bytes, durable checkpoints and completion counters update at their own
observed boundaries; embedded outcome counters explicitly refer to their prefix.

Normal/fault dependency isolation and related native regressions pass. The two
new files have the existing image-provider owner; old plans/selectors/commands
retain their meaning. This is a private synchronous backend, not a qualified
contained writer or UI command. Keep DE-W056 active and finish its remaining
controller, retained-evidence inspection and exact-source qualification gates.
Owner/physical/elevation/customer/install/sign/release authority stays separate.
