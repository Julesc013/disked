# W033 pipeline development observations

The work starts at `e7032bf092070aa227f626139f672e07d9b53b80`, under the
recorded local continuation grant. W033 and full DiskEd 0.1.0 remain incomplete.

The initial native component build and 153 independent cases passed. Review then
added capacity reservation before a chunk's intent/effect, retained uncertainty
while parsing a pending receipt, and explicit handling of output creation that
fails after creating files but before recording a header. A provider's dedicated
creation-refusal type may claim no effects only after proving no outputs were
created. Other errors retain failed partial work; no automatic new capture may
clobber those outputs. The expanded native build and 199 cases passed before
the final Unicode/integer/map-budget cases were added.

The initial structural check before regeneration reported stale generated index
and schema index files. Index/manifest regeneration was performed before the
full validation run; no structural check or expected result was weakened.

An initial `specctl show DE-W033` lookup returned `Unknown concept`: `show`
resolves concept IDs, while work IDs are records in `spec/work/units.json`.
The exact work record and source-bound context were then read. Several guessed
schema/template paths were absent; actual owners were resolved locally. These
lookup failures changed no product files or authentication state.

Tests use the separately compiled in-memory port probe. Interruptions model
pre/post API exceptions and explicitly incomplete map tails. They do not run
a persistent file provider, power-loss campaign, physical device or active
writer replacement. Source/destination bytes and chunk/map SHA-256 expectations
come from Python rather than the executor's success status. Actual file controls,
capacity/sharing/no-clobber races, process termination and frontend lifecycle
remain the next implementation steps.

The SHA-256 translation unit moved into an independent static library so the
acquisition engine depends on portable hashing and JSON, without depending on
fake presentation or a concrete OS/provider. Existing consumers retain the same
implementation; the full native suite must verify that build-boundary change.

The first source revision `7a16a564ccf0e8e43b6b236fd4747894a27b0944`
passed a fresh full build, all 41 native groups, 203 pipeline cases and 171 spec
tests (two existing skips). A later review found that a provider returning a
control-containing or oversized error could produce a failure receipt rejected
by resume's stricter identifier rules. That original reproduction is retained
as revision-specific evidence, not admission of the corrected component.

The added regression failed against the original engine, as recorded in
`target-provider-error-regression-cases.log`: the engine appended a failure row
instead of rejecting invalid provider error text. The fix validates bounded
UTF-8/no-control identifiers before retry or map append and leaves only the
header when the provider violates its contract. The corrected component passes
207 cases, including preserved Unicode error IDs and subsequent resume. The
regression expectation was retained unchanged. Final source reproduction is
recorded separately; no original log was deleted or promoted to a later revision.
