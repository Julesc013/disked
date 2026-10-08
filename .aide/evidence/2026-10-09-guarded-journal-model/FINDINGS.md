# Findings and retained failed runs

All probes use generated fake declarations and explicit fake stable/volatile
memory. No physical media, elevated process or host durability test was involved.
Failures below are local model/harness findings, not service restrictions.

The initial 36-scenario campaign failed two fixtures because they simultaneously
violated capture freshness and transition ordering. The model refused on the
earlier freshness guard. The fixtures now establish a fresh capture before testing
the intended ordering guard; no successful completion was substituted for a
refusal. `working-initial-cases.*` retains the failure. The repaired run passed
36 scenarios/324 actions in `working-ordering-cases.*`.

The first expanded harness checked every action's valid shape, including deliberate
unknown/extra/missing-field negative cases, and failed before running the probe.
`working-recovery-cases.log` retains that precheck failure. Only those deliberately
invalid shapes are excluded from the valid-shape precheck; native refusal and
unchanged-state checks remain. The repaired 127-scenario campaign passed 3762
actions in `working-recovery-cases-shape-repaired.*`.

Nine of the next 136 scenarios exposed three native defects. Dispatch checked
only the current step's effects and missed a changed future target. Target flush
did not revalidate target identity/epoch/availability. Journal flush could
acknowledge an unavailable or substituted journal resource. Expectations remained
unchanged. The repair checks every participating resource's expected state,
revalidates target flush closure/postconditions and guards journal append/flush
against changed dependencies. `working-dependency-regressions-before.*` and
`before-dependency-guards.cpp` retain the old observations/source; the corresponding
after run passed 136 scenarios/3825 actions.

Journal-generation, tail-retention and unstarted-versus-possibly-executed recovery
fixtures then passed 150 scenarios/4063 actions. Additional selected-budget,
exact-bootstrap-byte, shape and u64 cases passed 164 scenarios/4079 actions.
These remain separate historical working runs.

Three added late-result cases exposed simulated writes through a replaced target's
current alias. The model now checks bound target identity/epoch/availability before
applying a callback's fake write; an unavailable/replaced target leaves the old
bounded effect uncertain. It does not prove that effect absent or authorize a
replacement. `working-late-target-regressions-before.*` and
`before-late-result-target-guard.cpp` retain the defect. The repaired run passed
167 scenarios/4100 actions in `working-late-target-regressions-after.*`.

Final review found that a valid 65536-byte definition exceeded the history reader's
limit after wrapping it as an event. The new fixture independently constructs an
exact-limit definition with 32 participating resources, then executes, crashes
and reconciles its history. `working-wrapped-payload-regression-before.*` and
`before-wrapped-event-limit.cpp` retain the failure. An attempted multi-file patch
was rejected because a documentation hunk did not match; it changed no source.
Consequently the initially named `working-wrapped-payload-regression-after.*` also
failed and remains retained. After applying the actual source repair, event
history uses the profile's 131072-byte bound while actions retain a 65536-byte
bound. `working-wrapped-payload-regression-repaired.*` passed all 168 scenarios
and 4117 actions. Neither failed result was overwritten.

The first retention helper used two incorrect specification paths in its
`files_read` list. Its existence check stopped before writing the handoff. The
paths were corrected to the actual broker/degraded-operation owners and the
helper made resumable after its programme update. Handoff schema/semantic
validation then passed. This bookkeeping repair did not change runtime source
or any test expectation.

Durability is only the selected closed fake-memory assumption: acknowledged stable
prefixes/states survive the chosen crashes. Fake worker exit is an explicit input,
not an OS observation. A complete fake prefix without intention can establish an
unstarted step only under that model; missing physical journal bytes cannot.
Changed resource identities remain quarantined; the model does not represent old
and new device contents concurrently or qualify real alias/fencing behavior.
Hash-chained JSON histories are separate from the binary framing codec. Semantic
binary integration, actual flush adapters, authenticated admission, independent
safety review and physical power-loss qualification remain unfinished.
