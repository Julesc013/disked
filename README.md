# DiskEd

**One native tool for understanding, managing and recovering storage.**

DiskEd is being designed as a Windows-first storage workbench: a unified command-line interface, machine-readable API, terminal interface and native graphical interface, with portable target-specific builds and optional managed installation through Universal Setup.

The initial target is useful inspection, imaging and verification on Windows XP, 7, 10 and 11. DOS, JC-DOS, Project Carbon, OS/2 and other underserved systems are part of the longer-term architecture. Destructive operations will be introduced only through independently reviewed, tested providers with explicit recovery limits.

## Project status

This repository starts with a **proposed specification and working specification tooling**, not a released partition manager. There is no DiskEd binary or qualified storage-mutation implementation yet. Importing the specification does not imply hardware safety, runtime compatibility or owner acceptance.

## Start here

- [Specification entrypoint](spec/START-HERE.md) and [complete specification index](spec/index.md).
- [Getting started](docs/getting-started.md) for local validation and the first work unit.
- [Architecture overview](docs/architecture.md), [contribution workflow](docs/contributing.md), and [compatibility policy](docs/compatibility.md).

## Direction

A target should expose one `disked` entrypoint with CLI, JSON, TUI and its native GUI. Implementations can be replaced behind stable contracts. The one-file preference must never conceal dependency extraction, platform limitations or privilege-isolation requirements.

DiskEd keeps storage intent, planned effects, execution and independent verification distinct. A journal is not a promise of rollback; every operation must disclose the recovery it can actually provide.

## Contributing

Begin with [AGENTS.md](AGENTS.md), which is shared by human and automated contributors. Work is decomposed into bounded units with acceptance criteria and explicit limits. The first task is baseline review, followed by a fake-provider native vertical slice.

The original-code license is still an owner decision. No license grant or third-party redistribution rights should be inferred from the proposed design. See [licensing decision](spec/delivery/licensing-and-supply-chain.md).
