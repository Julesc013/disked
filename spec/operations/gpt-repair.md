---
type: DiskEd Specification
title: Explicit GPT-copy repair
description: Independent operation contract for table.gpt.repair.
resource: disked://spec/de-104
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-104
  profile: disked-spec/1
  version: 0.1.1-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-104-01
---

# Explicit GPT-copy repair

## Identity and availability

Semantic ID: `table.gpt.repair`. Operation specification: `DE-OP-004`. Earliest phase: **M5 images only**. Initial target scope: selected unambiguous damaged copy on disposable image. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Both map copies captured, exact current source fingerprint, explicit selected authoritative candidate, original metadata backup, exclusive image access and admitted writer. Two valid disagreeing copies require a separate selection decision. No hidden boot/array metadata may be overwritten.

## Planned procedure

Construct exact expected repaired bytes and region list; validate address/CRC invariants in memory; journal according to accepted encoding; write only approved regions in provider-defined order; flush, reread and independently decode both copies. Do not claim a universal atomic swap.

## Postconditions and evidence

The intended copy is valid and agrees as planned. Untouched bytes remain unchanged. Identity, GUIDs and partition names are preserved unless separately authorized. Evidence includes before/after region hashes and provider closure.

## Interruption, cancellation and recovery

Recovery examines each copy and journal state. Never blindly assumes primary or backup newest. A metadata backup aids reconstruction but does not replace an external data backup or prove whole-device atomicity.

## Required adversarial cases

Crash before/after each metadata write/flush, altered backup, shortened device, overlapping entry arrays, wrong sector size and unrelated-byte changes.

## Normative requirements

### DE-REQ-104-01

`table.gpt.repair` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Crash before/after each metadata write/flush, altered backup, shortened device, overlapping entry arrays, wrong sector size and unrelated-byte changes.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)

## DE-W041 private supplied-capture planning contract

[The bounded preview profile](../catalog/gpt-repair-planning-prototype.json)
implements the first pure planning boundary in `source/runtime/planner/`. Its
caller supplies both copies and PMBR, exact geometry, image/capture bindings, an
independently expected capture digest and explicit source selection. It constructs
owned immutable byte patches and validates the modeled postcondition without any
file, provider, journal or effect port. No public command becomes available.

Recognizable target metadata must establish an unambiguous compatible footprint;
only target-header checksum damage is accepted as a header defect. A destroyed
header or changed layout requires a separately specified ownership/footprint
selection before reconstruction; no canonical array offset is guessed. Valid
disagreeing copies require a separately bound selection declaration. Its digest
does not authenticate an operator or grant storage authority. Source/PMBR and
unrelated header fields, names, GUIDs, attributes and padding remain exact.

Preview identity binds immutable input, patches, order and policy. The shared-parser
simulation is scoped to captured byte-overlay consistency/agreement. Independent
Python byte/CRC oracles qualify this calculation, not an actual writer, whole-image
safety, recovery or power-loss durability. Freshness/exclusivity/backup/journal/
provider/review/grant/admission/verification remain explicit execution requirements.
DE-DEC-004 and all production mutation gates remain unresolved. DE-W041 is partial.
