# Independent caller job memory admission

Qualified source `98a5b593f410ae1f63994e7c07c9c138ecd26b0e`, prior verified baseline `eb9b49d38e9fda06915f5da1f5ec12c8a10c5f4e`. Implementer review.

Independent compatible Windows frontend caller jobs at 98a5b593f410ae1f63994e7c07c9c138ecd26b0e: verified fresh child retains256MiB per-process cap and every inherited host restriction; shared worker4/128MiB/512MiB quotas unchanged. Twelve native memory/real-product/guard cases and one focused disconnected-client quota test pass, plus78parallel product groups,213toolpasses/twoskips/1079structure and exact current build/launch/import/source evidence. No storage privilege, worker relocation, arbitrary/older-host, owner or full0.1.0 admission.

The original controlled test against6b025fdc passes its then-canonical refusal:
a live matching named memory job under callerA makes callerB's assignment fail
with platform5. This matches the earlier observed separate-tool-session failure.
The owning DE-045/015 amendment was committed ataece8baa before implementation.
Original refusal is retained as an old-policy observation, never reclassified.

The amended constructor prefers the matching shared per-user/session job. Only
actual ERROR_ACCESS_DENIED and verified absent membership permit a fresh unnamed
current-user-protected child. Configure/query the exact256MiB process-only limit,
assign this process and verify membership before readiness. No fallback after
mutex busy, mismatched limits, bootstrap/query/API failure or unresolved membership.
Fresh assignment failure remains typed refusal; no breakaway, foreign policy
rewrite, aggregate/active-process/UI/priority/kill flags or privilege is introduced.
Successful fallback clears the failed-step platform code. The unchanged shared
worker job still caps four processes/128MiB each/512MiB aggregate. Frontend readiness
does not guarantee worker admission under another incompatible ancestry or free
a still-live worker slot.

Existing-file tests keep mismatch,250ms mutex contention, actual allocation denial,
stricter inherited limits/UI policy,128GUI inspections, restored text hosts and256
NDJSON requests. New tests directly query the actual fresh child limit/flags under
a64MiB host while an independent first caller remains live; actual commit pressure
hits the inherited64MiB ceiling and leaves host flags unchanged. Scoped simulated
both-assignment failure retains the actual-signaled/guard refusal. Product ignores
both allocation and assignment test controls. Real product protocol underA returns
a completed build request, stays alive while product discovery underB completes,
then exits only on owned input EOF. Both host policies remain exact; one caller
never terminates the other. A separate file object observes live stdout so reading
cannot seek/change the child's shared output offset.

The standalone private memory probe calls the real implementation and native job
query. It has no storage/provider ports or product command. Initial dirty-source
memory runs pass; their build-input catalog was extended after that initial build,
so they are diagnostic rather than a clean-source identity. Fresh committed-source
qualification binds current product/fault/probe hashes, compiler/configuration and
all source/blob inputs. Existing actual four-worker disconnected-client capacity,
fifth refusal, memory limits and retained quota behavior pass unchanged. Three PEs
stay local, raw evidence bytes remain exact with lossless gzip where needed.

TestedWindows10Enterprise10.0.19045x64, ordinary BLACKGLASS-WIN1\Jules,
MSVC19.44/v14314.44.35207/SDK10.0.19041.0/static runtime/Python3.14.7. This admits
the measured compatible modern caller hierarchies, not arbitrary policies or
legacy systems. Incompatible fresh jobs still refuse. No provider/physical/storage/
writer/recovery/install/sign/release/owner admission follows. The earlier unrelated
parallel joined-report exit delay remains unexplained; this passing campaign does
not diagnose it.

- [Actual validation](validation-summary.json)
- [Exact retained bytes](inventory.json)
- [Clean reproduction](reproduce.py)
- [Read-only audit](audit_retention.py)

Next: Review/fetch the overdue AIDE weekly dev source update and passive schema compatibility, recording the published Lite1.0.0 constrained release separately from full AIDE/runtime/consumer qualification. Continue full all-platform/storage0.1.0 implementation with owner/journal/writer/physical/elevation/customer/install/sign/release gates separate. The older parallel joined-report exit-delay cause remains unknown.
