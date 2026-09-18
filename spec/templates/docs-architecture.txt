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

## Durable sources

The repository's `spec/` tree owns normative requirements, schema files, catalogs and work definitions. `docs/` is the readable publication layer. `.aide/` retains selected work and evidence; `.aide-local/` holds disposable contexts and caches. The implementation layout grows with actual modules instead of starting with hundreds of empty folders.

## Read further

[System boundaries](../spec/architecture/system.md), [resource identity](../spec/storage/identity-and-graph.md), [planning](../spec/safety/planning.md), [recovery](../spec/safety/journal-and-recovery.md), and [target compositions](../spec/delivery/composition.md) define the detailed contracts.
