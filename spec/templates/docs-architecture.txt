# Architecture overview

DiskEd is one product with several presentations and replaceable storage providers. The target-specific `disked` executable is intended to contain the CLI, machine interface, TUI and one native GUI. Additional process instances may isolate privileged or risky roles. Some target compositions may still require bundles, runtime dependencies or external providers; those properties must be declared accurately.

```text
CLI / JSON / TUI / native GUI
            |
      semantic actions
            |
capture -> observations -> resource graph
intent + policy -> desired graph -> action plan
            |
  simulation and bounded admission
            |
 re-identification -> journal -> executor
            |
 independent verification -> result/recovery/evidence
```

A graphical partition rectangle does not own a safety rule. A provider's exit code is not independent verification. A storage object is not identified only by a disk number. These boundaries allow new interfaces and platforms without creating competing semantics.

## Windows first

The first implemented slices will use fake providers, then image readers, then native read-only Windows capture. Native Win32 is the reference GUI proposal. Console-versus-desktop startup behavior must be measured on the target systems rather than assumed from one PE flag.

## Startup, failure and native integration

Essential help, build identity and saved-report inspection precede device discovery. Observation workers publish incremental, bounded results; an unavailable provider, corrupt preference or hung probe must not erase already available information. Cancellation requests do not prove I/O stopped. A possibly active writer remains fenced until its state is independently established.

The first composition uses a small static manifest. GUI adapters and optional providers declare their loader dependencies separately: a library required before process startup cannot honestly be called optional. Native MMC/shell adapters are thin clients of the same semantic actions and host-bound identities; they do not embed a second storage engine. Remote execution and public extension machinery remain staged work.

Portable, zero-install, managed and cleanup modes declare their writes and servicing owner. Product and Setup payloads form a finite graph; nested carriers must not recursively contain or hash one another. Formatting has its own planned postconditions and independent verification, separate from secure erase claims.

## Durable sources

The repository's `spec/` tree owns normative requirements, schema files, catalogs and work definitions. `docs/` is the readable publication layer. `.aide/` retains selected work and evidence; `.aide-local/` holds disposable contexts and caches. The proposed implementation prefix is `source/`, with portable, runtime, platform, providers, apps and integrations ownership added only as actual code needs it. DE-DEC-010 records the change from the original root-level map; final review remains pending.

## Read further

[System boundaries](../spec/architecture/system.md), [resource identity](../spec/storage/identity-and-graph.md), [planning](../spec/safety/planning.md), [recovery](../spec/safety/journal-and-recovery.md), and [target compositions](../spec/delivery/composition.md) define the detailed contracts. See also [components](../spec/architecture/component-model.md), [execution roles](../spec/architecture/execution-topology.md), [degraded operation](../spec/safety/degraded-operation.md), [native integration](../spec/interaction/native-integration.md), and the [development plan](development-plan.md).
