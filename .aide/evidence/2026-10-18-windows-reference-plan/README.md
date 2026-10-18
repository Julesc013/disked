# Windows reference-method planning review

The owner asked to incorporate the supplied 18 October REA/reference-method
proposal and assess Windows components, services, MMC, Computer Management and
Explorer integration. The attachment is reference material, not an execution
grant. Its SHA-256, reviewed revision and limitations are recorded in
`spec/references/sources.json` as `windows-reference-review-2026-10-18`.

Inspected source base: `099b3fc076dfdf34758c8662a710d3d40dd0993c` on `dev`.
The current native DE-W105 work remains active. This change adds planned
DE-W106 evidence/workspace corrections and a subsequent DE-W107 four-case
Windows API/UI reference pilot. Existing provider/integration and target gates
retain ownership. No target expansion, REA installation, Windows reference run,
clean-room qualification, owner acceptance or release qualification is claimed.

## Independent recheck

Run `review.py` through the existing managed runner:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-windows-reference-plan/review.py
```

`review.json` binds the exact comparator and probe recipe. All three synthetic
pure-function probes reproduced the supplied review's evidence-boundary gaps:
missing observations return passing controls with zero comparisons; a mismatched
fixture hash returns passing controls; duplicate records return passing controls
with two comparisons. These establish current validation defects. They do not
establish that a historical real campaign was incomplete or incorrect.

The managed run exited zero, reported 898 peak work bytes and removed its
workspace. It generated no disk images, native binaries or reference-app output.
The comparator and coordinator are not repaired by this planning change; the
obsolete `.aide-local` recipe is explicitly suspended in its instructions until
DE-W106 repairs and qualifies its execution profile.

Primary Microsoft documentation was inspected for saved consoles, snap-ins,
service control, storage API coverage, shell handlers and UI Automation. REA's
README and installation guide were inspected online as unpinned documentation;
no installer or remote script was executed. Neither marketing coverage nor the
attachment's ArtCraft narrative is adopted as product evidence.

The first specification check correctly refused out-of-bundle Markdown links
and an unregistered required input. Its compact original receipt is retained as
`specification-link-refusals.json.xz`. The authored specs now use repository path
references, and the new required inputs are explicitly registered for context
binding. Final validation is retained under the guest-build checkpoint's
`specification-checks.json`; that is specification tooling, not native Windows
reference evidence.
