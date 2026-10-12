# Structure and release review reconciliation

The four supplied files are retained byte-for-byte under `inputs/`; `inputs.json`
records their original locations and hashes. They are advisory data, not execution
instructions, baseline acceptance or publication authority. The older UI discussion
describes an earlier specification state; its “no executable” and empty-alias
observations do not describe the current implementation.

Independent local inspection confirms the existing TUI rename and dedicated CLI
folder. The source map covers all 196 current files once and routes planned growth.
Directories identify ownership; short basenames identify responsibility. Keep the
tree, command identities and historical evidence. CLI formatting, persistent shell
state, text/graphical models, shared command/action semantics and native terminal/
window mechanics have distinct owners. No artificial CLI model or complete empty
future hierarchy was added.

The contributor-clarity phase replaces the stale AGENTS first-task paragraph with
the programme/work/grant route, including a specification-export fallback. Root
and bootstrap templates share the new editor/formatter policy. Existing general
two-space and Python four-space conventions remain; C/C++ uses four spaces, and
historical evidence is excluded from editor normalization. The installed Visual
Studio clang-format 19.1.5 parses the configuration. This does not claim that the
whole existing implementation is formatter-clean.

Registering formatter inputs exposed a synthetic test setup conflict: bootstrap
fixtures contained a file the tool correctly refused to overwrite. Removing every
bootstrap destination from all fixtures then deprived context tests of their
required formatter inputs. The corrected fixture keeps complete context inputs
and prepares absent output destinations only for bootstrap tests. The production
bootstrap no-overwrite rule and context freshness/budget assertions are unchanged;
both failed runs are retained alongside the corrected result.

`spec/catalog/source-maintenance-prototype.json` records each review finding.
Build-target narrowing, actual header/dependency enforcement and demonstrated
GUI/TUI completion/availability consolidation remain pending. The review did not
reproduce wrong-header selection. Source-map coverage is not dependency conformance
or a line-by-line correctness certification. No universal frontend framework or
arbitrary source decomposition is justified by the current evidence.

The preceding native history checkpoint is source
`6c4393b9122a3151b997bde8228e6cd2ffe909c7`, integrated at
`51a8d516c293b2476a6a83489b855f83525e2a04`: 121 dedicated inspection cases,
124 inspections within 138 restoration cases, 190 execution cases and all 82 native
groups passed. Its exact logs, imports, context, source and PE hashes remain in
`../2026-10-12-gpt-restoration-inspection/`. That evidence qualifies the named source
and fixture scope, not production writers, physical recovery or full 0.1.0.
The clarity phase changes documentation/configuration/test fixtures; it does not
claim a new native build or change product command behaviour.

Read-only GitHub metadata independently confirms Universal Setup main `c048f7f`
and dev `2b7a4d0` have the same tree. Draft PR #237 remains open at `b6dff645`, with
exact-head run 38221243094 completed in failure. Its Windows maintenance and
downstream qualification remain unfinished. The recorded GitHub release lists for
both repositories are empty; this says nothing about every private artifact/tag.
No Universal Setup files, settings, PR state or releases were changed.

DiskEd main was observed unprotected; required owner-selected branch/check policy
remains a governance gap. Ordinary verified development merges under the standing
grant are separate from release qualification/publication. Full specified platform/
operation scope, original-code licensing, exact target/provider compatibility,
production recovery and signing/publication authority remain open. No reliable
calendar release date or “enterprise-grade” qualification follows from these tests.

Continue the bounded maintenance findings alongside the existing full programme.
Keep naming/formatting, dependency changes and behavioural changes separately
reviewable, with evidence applicable to each exact source revision.
