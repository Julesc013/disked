# DE-W019 native shell evidence

Source: `9ba3311ff948319841fe881a7e0c8a4ec5036312`. Independent local clone, build and execution commands are in
`reproduction-9ba3311f/clean-commands.json`, with identities and host in
`reproduction-9ba3311f/clean-results.json`.

The local development executable is `.aide-local/artifacts/DE-W019-9ba3311f/disked.exe`,
779776 bytes, `sha256:994076fe77f860ff899c0d75f8dc0cf2d6b9fdee8e483a86792105e870848fc4`. It is not a release artifact.

All 19 native CTest groups passed in the clean clone. The shell contributes
13 native model/tokenizer tests and 15 actual-console/static-entry tests. The
specification suite ran 169 tests: 167 passed, two existing Windows symlink
privilege checks skipped. Structural validation reports 900 checks and 39 schemas.
Actual response/graph/terminal/fake-operation producer-schema checks passed.
Passive AIDE validation still covers 36 records at the existing source pin;
live AIDE integration remains unrun.

The shell admits literal quoted input through the shared command parser, separate
F9 review/submission, cached completion, opt-in bounded session history and exact
fake identities. Tests exercise aliases, error correction, Unicode scalar editing,
held keys and inert Enter, transcript limits, secret annotations, stale revisions,
console restoration, linear/narrow output, and worker reconnect after shell exit.
`clean-shell-console-observations.json` retains real console frames and synthetic
input traces with session offsets, waits, correction and history actions. These
measure injected input and polling, including deliberate waits; they are not human
entry time, keyboard or screen-reader qualification.

The first working-tree full run found two obsolete GUI catalog-count assertions.
The preserved root `native-tests.log` records that failure. The tests now compare
canonical IDs and reject shell-only commands inside the GUI; `working-final/`
records the passing repaired run. The source commit also adds timing instrumentation;
the clean run, not earlier working logs, proves that exact committed state.

Direct PE headers/imports/dependencies and actual launches are retained separately
from host-loaded modules in worker observations. The tested host is Windows 10 x64
build 19045, non-elevated BLACKGLASS-WIN1\Jules. Host Windhawk injection prevents
clean-loader qualification. Other systems, human usability, remote terminals,
real storage, production journals, privilege isolation, Setup/signing/publication
and owner acceptance remain unverified or separately gated.

DE-W017: run and repair the combined fake-provider/frontend resilience campaign, with explicit worker/resource/event ceilings and stale-observation guards. Preserve unknown outcomes and separate production storage/privilege gates.
