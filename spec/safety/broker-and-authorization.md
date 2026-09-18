---
type: DiskEd Specification
title: Broker identity and bounded authorization
description: Authenticate the request, exact executable, operator intent and live target.
resource: disked://spec/de-041
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-041
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-040
  - DE-030
  - DE-022
  requirements:
  - DE-REQ-041-01
  - DE-REQ-041-02
  - DE-REQ-041-03
---

# Broker identity and bounded authorization

## Session establishment

The normal GUI and CLI remain unelevated. Applying an admitted plan starts a short-lived privileged broker, preferably another instance of the same exact native binary. Use target-native authenticated IPC with restrictive endpoint permissions, fresh challenge/session binding and replay protection. A secret on the command line can leak and is not an authentication design. Do not accept caller-supplied process IDs as proof of peer identity.

Resolve the executable through the running image identity and approved package policy. Portable files in writable directories can be replaced between observation and elevation. Hash comparison alone still has a race if execution reopens the path. The Windows implementation spike must establish a protected staging or equally justified exact-image launch mechanism; a same-binary promise does not remove this obligation. Refuse on unresolved substitution risk.

## Request admission

Validate schema, plan digest, command identity, approval scope, policy digest, provider closure, expected revision and resource limits. Reopen the target, establish its identity and acquire necessary locks. Establish recovery storage outside affected ranges. Re-evaluate live mount/concurrency state and the step's expected intermediate state. Only then create the durable transition authorizing the next bounded effect.

An approval binds a plan and scope, not arbitrary future changes. Two-person approval is optional organizational policy but may be required for high-risk profiles. Signing is meaningful only with trusted keys and a validation policy; a self-generated signature in a workspace is not independent approval.

## Outcome and lifetime

The broker owns a durable operation identity and can outlive the frontend where the OS supports it. Client loss does not cause abrupt termination during an unsafe step. Cancellation takes effect only at documented checkpoints. Access denial, malformed request, stale state and unknown outcome are separate stable errors. The broker has no update client, network fetching, UI customization or automatic user-plugin discovery.

Legacy platforms without enforceable separation use a constrained execution profile and explicit lower assurance claim. They do not silently receive the modern broker's certification label.

## Normative requirements

### DE-REQ-041-01

Broker admission MUST authenticate the client/session and bind exact plan, policy, executable/provider identities and live target state.

**Verification:** Replay, endpoint spoofing, swapped-binary and stale-plan adversarial tests.

### DE-REQ-041-02

Approval MUST be content-bound and MUST NOT authorize altered parameters or later plans.

**Verification:** Mutate one plan field after approval and require denial.

### DE-REQ-041-03

Frontend disconnection MUST NOT be interpreted as safe cancellation of an admitted effect.

**Verification:** Kill client during a fake irreversible stage and inspect durable operation state.

## Related specifications

- [DE-040](threat-model.md)
- [DE-030](../storage/identity-and-graph.md)
- [DE-022](../interaction/protocol.md)
