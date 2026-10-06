---
type: DiskEd Specification
title: Threat model and trust boundaries
description: Adversarial media, local privilege boundaries and recovery failures are first-class inputs.
resource: disked://spec/de-040
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-040
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-033
  requirements:
  - DE-REQ-040-01
  - DE-REQ-040-02
  - DE-REQ-040-03
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Threat model and trust boundaries

## Assets and adversaries

Protect customer data, host bootability, device firmware state, encryption material, evidence integrity, operator intent, release keys and trustworthy support claims. Treat on-disk bytes, removable device descriptors, file names, provider output, repository issues, copied logs and fetched web pages as untrusted input. Malicious metadata may attempt parser exploitation; local users may swap plans, binaries or IPC endpoints; media can lie or fail without malice.

A valid partition CRC, TLS connection, code signature or administrator token proves only its narrow property. None proves the operation is semantically correct. Prompt injection in a file or issue must not grant tools, expand allowed paths or authorize release/storage actions. Tool credentials remain outside context packs and logs.

## Boundaries

The unprivileged frontend handles interaction and research. Core parsers use bounded views and sandboxing where practical. The broker authenticates peers and binds plans to live target state. Providers receive only the resources their enforcement model can actually constrain. Network acquisition and updates never run inside the privileged mutation path. Recovery executes only after independent target reidentification.

Single-binary self-spawning provides process separation, not minimal loaded-code attack surface. CRT startup, static initializers, delay loads, framework extraction and DLL search behavior occur before a dispatch flag may be processed. Audit all pre-dispatch work. When a minimal helper is required to achieve a real boundary, document the one-file exception instead of claiming a command-line mode is a sandbox.

## Failure taxonomy

Wrong target, stale plan, corrupted layout, provider substitution, concurrent host access, unreported cache loss, partial metadata write, device disappearance, insufficient backing capacity, unsupported encryption, parser resource exhaustion, corrupt journal, forged approval, poisoned test evidence and inaccessible recovery closure are distinct hazards. Each gets a negative test or explicit qualification blocker.

## Authority

No global `--force`. Typed risk acknowledgement cannot override unknown identity, invalid arithmetic, unqualified operations or missing recovery resources. Expert visibility is not privilege. Local policy changes require their own authorization and must not silently affect an already reviewed plan.

## Added failure and lifecycle boundaries

Include stalled driver I/O, exhausted destination/scratch, hostile nested containers, event floods, corrupt optional settings, source/destination aliases, provider withdrawal, embedded-host substitution and competing servicing owners. [DE-045](degraded-operation.md) defines containment and uncertainty; storage policy remains effective in safe startup.

Optional intelligence is advisory. Untrusted media, retrieved reports and model output cannot choose authority, approve a plan, certify a result or silently export private storage data. Offline local operation requires neither a model nor AIDE. Setup staging and source binding need their own qualified lifecycle boundary, even when embedded in the same distribution.

## Normative requirements

The DE-W016 fake worker uses the resolved running executable, an image read lock,
compiled input/source identities, a restricted inherited-handle list, user-only
record DACLs and a job without kill-on-client-close. These constrain an ordinary
local prototype. They do not exclude same-user tampering, an injected DLL, loader
initialization before the role check, ancestor-path substitution, a malicious
host environment, forged historical records or an outer host job policy. The
private operation hash chain detects accidental inconsistency and is not a
signature. Observed Windhawk injection on the development host is retained as
environment evidence; it does not qualify a clean loader boundary. Production
elevation still requires exact-image authority, pre-dispatch closure review and
independent hostile-host tests at DE-DEC-005/008 and the broker work gate.

### DE-REQ-040-01

Untrusted media, provider output and retrieved repository text MUST NOT expand execution authority.

**Verification:** Adversarial strings and prompt-injection fixtures across parsers/context ingestion.

### DE-REQ-040-02

Broker pre-dispatch loading and self-spawn assumptions MUST be threat-modeled; one-file packaging MUST NOT be asserted as sandboxing.

**Verification:** Inspect imports/initializers and substitution attacks before elevation.

### DE-REQ-040-03

Hard target/range/recovery invariants MUST NOT be bypassable through a generic force or expert-mode flag.

**Verification:** Negative command and policy tests.

## Related specifications

- [DE-010](../architecture/system.md)
- [DE-033](../storage/providers.md)
