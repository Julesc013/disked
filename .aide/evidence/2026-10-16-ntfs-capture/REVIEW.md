# Implementing-agent review: supplied-reader NTFS bootstrap

Work DE-W079, base `cb8c291f7837c4001c839b7f709b4aacdc23231c`.
Reviewed implementation: exact `000ecb77359bad835522f6a5d488c13baea0ef94`.
Authority: existing explicit local implementation/testing grant across units after
agent review; generated/supplied bytes only. No owner acceptance is manufactured.

The contract was recorded before implementation/evaluation. The collector owns
controls before callbacks, validates source/window/limits, uses existing portable
decoders and RegionReader, binds MFT data to the seed, and reads FILE3 through
actual mappings. The independent corpus covers record3 split across runs, backward
physical deltas, supported geometries/headers/versions, high exact offsets,
readonly guard buffers, caller-control mutation, physical aliases, malformed
records/attributes/runs, mirror USA/slack/payload distinctions, observed version,
global budgets, source mutation and actual attempted callback accounting.

Pre-qualification review reproduced three false-applicability cases at e37848a5:
known mapping errors2/32 survived in additional MFT/Volume metadata while the
bootstrap reported complete/applicable. The old artifact's 150-case/16-group
pipeline passed, but that does not qualify the missed behaviour. Its complete
stage results, exact input/probe output and working source snapshots remain.
The correction explicitly distinguishes header completion and mapping validity,
propagates known ordinary-mapping failure to the containing record, and retains
typed prefix diagnostics. The expanded154 cases include all baseline cases and
four regressions; the old expected failure is made more precise, not weakened.

Exact000ecb77 passes all16 selected x64 native groups,154 bootstrap cases,
259 attribute/632 mapping/1729 boot/964 record cases, three standalone headers,
242 tooling tests(two skipped), dependency/import/security/context/manifest/source
freshness checks and GCC/Clang C90/C++14 syntax checks. All1011 registered/build
inputs are present in a clean sparse checkout. Source/input hashes remain
unchanged. This is not a full archive checkout or full native product campaign.

Supplementary exact-source x86 probes pass the same154/259/632/1729/964 cases,
five NTFS groups and two headers on the recorded Windows x64 host/WOW64, with
kernel32-only imports, x86 PE/security observations and unchanged clean source.
This does not qualify the full Win32 product, old Windows or other original hosts.
Raw logs, commands, compiler/CMake configurations, per-case receipts and hashes
are retained in the two source-bound campaign directories.

An initial attempt to use the product preset for x86 was refused by its intended
x64-only gate; the failed configure/log remains in win32-product-refusal. The
successful x86 fixture derives ten shared translation units, four probe sources
and two header translation units from the exact-source qualified CMake codemodel,
pins the compiler/SDK, and preserves C90/C++14, static runtime and security flags.
The root product gate and production source bytes were not changed to obtain
this supplementary result. Its generated fixture and source closure are retained.

Applicability is limited to this bootstrap and the finite reread regions. It is
neither an atomic snapshot nor current-source/effect permission, allocation
ownership, filesystem health, complete MFT mirror, namespace/content, native
held-file/provider/worker/frontend admission or recovery qualification. Mirror
failure never selects a replacement primary. Attribute-list/continuation joins
and opaque payloads remain original required work; no public/durable ABI is frozen.

Available-scope conclusion: this bounded implementation reaches agent review and
is suitable for continued authorized development on dev. Original all-platform/
storage0.1.0, licensing/owner, physical writer/recovery and release gates remain.
W075/report-preparation failures still withhold whole-branch main promotion.
Continue actual held-source/profile binding and original NTFS interpretation,
alongside diagnosis of that retained integration failure.
