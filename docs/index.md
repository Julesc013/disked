# DiskEd documentation

This is the publication layer for people using and developing DiskEd. The normative specification lives in [`spec/`](../spec/index.md); command fields and target declarations have one canonical owner there.

| Guide | Purpose |
|---|---|
| [Native bootstrap](native-bootstrap.md) | Build and test the Windows image/fake prototype. |
| [Getting started](getting-started.md) | Validate the baseline and choose bounded work. |
| [Development plan](development-plan.md) | Follow the amended roadmap, review boundaries and AIDE cadence. |
| [Architecture](architecture.md) | Understand the product and process boundaries. |
| [Contributing](contributing.md) | Work safely with humans, agents and evidence. |
| [Command and terminal experience](command-experience.md) | Understand planned CLI prompts, shell, aliases and terminal fallbacks. |
| [Compatibility](compatibility.md) | Read target and capability claims correctly. |
| [Agent and chat workflow](agent-workflow.md) | Resume from GitHub or a portable context pack. |
| [Specification maintenance](specification-maintenance.md) | Edit, index, review and export the source of truth. |

**Current status:** the native Windows prototype implements the [bootstrap, fake interface and initial raw-file commands](native-bootstrap.md). Broader product behavior remains planned unless accompanied by scoped implementation evidence.
