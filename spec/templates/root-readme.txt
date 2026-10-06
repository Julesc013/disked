# DiskEd

**One native tool for understanding, managing and recovering storage.**

DiskEd is being designed as a Windows-first storage workbench: a unified command-line interface, machine-readable API, terminal interface and native graphical interface, with portable target-specific builds and optional managed installation through Universal Setup.

The initial target is useful inspection, imaging and verification on Windows XP, 7, 10 and 11. DOS, JC-DOS, Project Carbon, OS/2 and other underserved systems are part of the longer-term architecture. Destructive operations will be introduced only through independently reviewed, tested providers with explicit recovery limits.

## Project status

This repository contains a **proposed specification, working specification tooling and an initial native Windows bootstrap**. The prototype exposes help, build identity, static command discovery, native mode inspection, inspectable fake storage graphs and bounded JSON/NDJSON requests with a fake-only composition. Storage operations and the full interface remain under development; no target or storage-mutation capability is qualified. See [build instructions and limits](docs/native-bootstrap.md).

## Start here

- [Specification entrypoint](spec/START-HERE.md) and [complete specification index](spec/index.md).
- [Development plan](docs/development-plan.md) and [TODO](TODO.MD) for the amended roadmap and outstanding decisions.
- [Getting started](docs/getting-started.md) for local validation and the first work unit.
- [Architecture overview](docs/architecture.md), [contribution workflow](docs/contributing.md), and [compatibility policy](docs/compatibility.md).

## Direction

A target should expose one `disked` entrypoint with CLI, JSON, TUI and its native GUI. Implementations can be replaced behind stable contracts. The one-file preference must never conceal dependency extraction, platform limitations or privilege-isolation requirements.

DiskEd keeps storage intent, planned effects, execution and independent verification distinct. A journal is not a promise of rollback; every operation must disclose the recovery it can actually provide.

## Contributing

Begin with [AGENTS.md](AGENTS.md), which is shared by human and automated contributors. Work is decomposed into bounded units with acceptance criteria and explicit limits. The scoped baseline review and native bootstrap lead into the remaining fake-provider interface work. Owner acceptance and implementation acceptance remain separate review steps.

The original-code license is still an owner decision. No license grant or third-party redistribution rights should be inferred from the proposed design. See [licensing decision](spec/delivery/licensing-and-supply-chain.md).
