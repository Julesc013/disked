# Implementing-agent review: read-only Setup source candidate

The local fixture slice is ready for continued development under the existing
programme grant. Full DE-W060, generic consumer integration, production
qualification and owner acceptance remain open. This is an implementing-agent
review; it does not impersonate an owner or independent safety reviewer.

## Exact scope and evidence

Base: `aaec12c034fdcf4413a71ed219ac666d00d0f471`. Qualified source:
`23079a5a0d7c18d30706491b5862f9c675724e24`. Setup pin:
`2e64f654b370f500ddbab45ae097df63352c3c25`, tree
`b836676ca8f487d48063071733ca5ff5c5c8abab`. This is an exact local observation,
not a remote freshness claim.

The 84-input closure contains the original CoreStatic 22 C/C++ sources,
six inflate-only Zlib C sources, public/private headers, four schemas and
original build/ABI/license/provenance inputs. All bytes came from pinned Git
blobs. The export includes original MIT and Zlib notices. The standalone
DiskEd build executes no upstream CMake/Python/scripts and does not change
upstream repositories, install an SDK or link Setup into `disked.exe`.

The selected toolchain is CMake 4.2.3, MSVC 19.44.35228.0/toolset 14.44.35207,
SDK 10.0.19041.0, Release x64 with `/MT`; the private provider uses C++17 and
the consumer uses C11. Generated project and compiler files are retained.
The actual host is `BLACKGLASS-WIN1\Jules`, unelevated. No other host or
platform is qualified.

The native campaign's 33 executions and 223 assertions passed, including six
C-level layout/size/allocator/ownership checks. Four public C ABI functions
compiled, linked and executed. The undersized-response check uses a valid-size
request, so request rejection cannot mask that guard. Supplier response bytes
are copied before another call and destruction; no invalidated borrowed pointer
is read. Custom context allocation balances without claiming all provider
allocations use it.

All 30 package/export tests passed. The 215-tooling suite passed with two skips.
The two skips concern symlink fixtures unavailable on this unprivileged
coordinator. The tested runner is Python 3.14.7 with jsonschema 4.26.0 and
PyYAML 6.0.3; older runner environments are not qualified by this receipt.
Structural validation passed 1,037 checks over 72 concepts, 150 requirements,
36 work units and 76 DiskEd schemas; nine upstream schemas are separate.
Context verification bound the complete declared closure without truncation.
The product native suite was not rerun or rebuilt: its previously qualified
dev.36 source/bytes are unchanged and independently retained.

## Conclusions and limits

- Policy and command discovery reported the source's read-only/planned state.
  Discovery also exposes mutable commands in the upstream library; it does not
  admit those commands to this consumer. Seven consumer refusal executions
  rejected unselected commands or empty/oversized/NUL requests before context
  creation. Binary stdin/stdout avoids Windows text translation of request bytes.
- Exact DiskEd ZIP hash, size, entry set and totals matched the separately
  selected original inventory. Stored and deflated fixtures passed structural
  inspection. Traversal, case collision, empty/truncated/missing archives,
  count/size/depth/ratio limits and invalid request shapes refused.
- A structurally valid payload-corrupt ZIP passed supplier inspection, retaining
  its exact changed source hash. Independent decoded-content verification
  rejected it as `archive_content`. Inspection is not CRC/content, extraction,
  authenticity or compatibility qualification.
- Generic `package.verify` and `package.audit` returned supplier code/status 1
  and `package_verification_refused`: required metadata is missing. Source
  inspection confirms FacMan manifest/component and Factorio binding
  assumptions. Generic DiskEd product/recipe conformance does not satisfy that
  verifier. No FacMan disguise, source patch or private fallback installer exists.
- Unconfigured `install_local.plan` returned `live_target_acceptance_required`.
  Null state, acceptance-root and activation are deliberate. No plan, installed
  state or live authority was manufactured. Source/case/evidence/recovery/foreign
  fixture paths and bytes remained exact after all calls.
- A zero probe process exit captures a supplier observation. It is distinct
  from the supplier return/status and JSON refusal. Raw expected process exits
  2 are retained separately; the campaign assertion harness exits zero only
  when their refusal expectations hold.

PE headers confirm an x64 executable. The observed direct import table contains
`KERNEL32.dll` and no VC runtime DLL import, consistent with `/MT`. The linked
static source closure includes dormant lifecycle/write routines. Imports alone
neither prove that all code is read-only nor establish transitive OS/dynamic
lookup compatibility. The whitelist, absent lifecycle configuration, actual
source inspection and fixture observations establish this narrow execution
scope. They are not a hostile-process sandbox or global filesystem trace.

## Corrections retained

An exploratory campaign invocation selected a nonexistent inventory filename
and failed before native execution. The correct separately retained inventory
was selected; input existence checks now precede campaign-root creation. The
partial first root was retained, and the subsequent campaign used a new root.
No expected native result was changed to remove a failure.

The initial exploratory self-test used an undersized request alongside an
undersized response; that could mask the response guard. The frozen source
corrects the request size before that check. Early raw observations predate
this correction and the binary-stdio adjustment; clean qualification uses
only the frozen corrected source.

Git whitespace checking initially reported raw CRLF evidence as trailing
whitespace. Evidence bytes are retained unchanged; a scoped `cr-at-eol`
attribute recognizes their line endings. Authored source whitespace and all
test expectations remain checked. Raw compiler output and generated build
configuration also retain original whitespace; binary request fixtures include
an intentional 8,193-space over-budget request. Scoped artifact attributes
exclude those data bytes from source-formatting checks without altering them.
No service block occurred in these builds;
the quoted Daybreak notice is not diagnosed from this evidence.

## Next safe action

Continue a bounded DE-W060/062 fixture carrier/servicing slice using exact
portable bytes, explicit ownership and active/unknown dependency refusals.
Keep the generic callable Setup verifier unavailable until a compatible exact
upstream consumer is separately qualified. No upstream mutation, actual
installation, physical storage, elevation, signing or publication is authorized
by this review. Retain the full 0.1.0 platform/storage scope and open owner gates.
