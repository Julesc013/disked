# AIDE

![coverage](https://badgen.net/static/coverage/not%20much/F73)
![code style](https://badgen.net/static/code%20style/mine/999)

**AIDE is a portable agentic development control plane for real repositories.**

AIDE helps repositories develop and maintain themselves. It turns development
work into protocol objects, evidence packets, event records, and
OKF-compatible knowledge so humans, agents, tests, IDEs, scripts, and legacy
environments can coordinate through one repo-native control plane.

```text
                    +--------------------------+
                    |        AIDE Core         |
                    | protocol / evidence /    |
                    | events / capabilities    |
                    +------------+-------------+
                                 |
          +----------------------+----------------------+
          |                      |                      |
 +--------v---------+   +--------v---------+   +--------v---------+
 | OKF Knowledge    |   | Worker runtime   |   | Conformance      |
 | markdown graph   |   | Service later    |   | admission gates  |
 +--------+---------+   +--------+---------+   +--------+---------+
          |                      |                      |
          +----------------------+----------------------+
                                 |
        +------------------------+------------------------+
        |                        |                        |
 +------v------+          +------v------+          +------v------+
 | Agents      |          | IDE /       |          | Tests / CI  |
 | workers     |          | Workshop    |          | evidence    |
 +-------------+          +-------------+          +-------------+
```

AIDE is not an AI editor, a VS Code competitor, a Codex wrapper, a prompt pack,
a RAG system, or a project-management tool.

**AIDE is the system around agents.**

## Status

AIDE has implemented repo-native control-plane, local Windows lifecycle and
bounded runtime foundations. Source was synchronized between `main` and `dev`
at `3d186d05`; later documentation integration is separate from stable
certification.

The source includes the self-hosting queue, context and evidence tools,
portable import/update, project-owned customization, owned repair,
rollback/removal and partial-import recovery. A bounded maintainer runner
provides explicit storage admission, finite resource limits and retirement;
real build/test use requires configured local pools. Worker, isolation and
integration-broker foundations also have source and focused test evidence.

The local Lite candidate has recorded technical review and delivered-consumer
evidence, but remains unpublished. Its unchanged ZIP predates the scoped host
adapter. The restricted worker has recorded validation and retirement evidence;
the outer client's editing/filesystem routes and read isolation remain
unqualified. Actual model usage, matched efficiency and exact release effects
retain separate gates. Service, Commander, Workshop/Workbench and
broader host/provider interfaces remain later work. The candidate local
Windows Lite profile and its limits are defined in
[product scope and profiles](specs/control-plane/product/scope-and-profiles.md).

AIDE's short doctrine:

```text
Protocol executes.
Evidence proves.
References identify.
Events remember.
OKF knowledge explains.
Reconciler detects drift.
Capabilities declare.
Conformance admits.
Patch transactions mutate only when authorized.
Adapters perform only after admission.
Context packs prevent rediscovery.
Runtime foundations coordinate bounded work.
```

## Why AIDE Exists

Modern AI coding tools are powerful, but most are still session-shaped:

- a model receives a prompt
- it edits files
- it may run checks
- the useful context often disappears into chat history
- later agents rediscover the same repo facts again

AIDE is designed around a different model. The repository keeps durable state:

- what work exists
- which worker attempted it
- what was tested
- what evidence supports a claim
- what is blocked
- what is accepted
- what the repo currently knows about itself

Agents become bounded workers inside that control plane.

AIDE's promise is not that agents never fail. AIDE's promise is that failures
become structured work, claims require evidence, knowledge compounds, and safe
progress can continue without tying the whole repo to one fragile agent
session.

## Core Idea

The target operating loop is below. Current bounded foundations do not establish
whole-session containment or a continuously productive unattended service.

```text
AIDE runs continuously.
Agents run transactionally.
Tests run asynchronously.
Failures become work.
Dev absorbs progress.
Checkpoints restore coherence.
Main receives truth.
```

AIDE is intended to coordinate:

- humans
- coding agents
- CI jobs
- test runners
- IDE hosts
- local scripts
- legacy environments
- visual workspaces
- knowledge bundles

## Quick Example

For a goal such as "refresh the public README":

```text
goal
-> intent packet
-> bounded WorkUnit
-> WorkerRun attempt record
-> TestJob validation record
-> EvidencePacket
-> EventRecord
-> OKF knowledge update
-> PatchTransaction review later
```

The current repository models these objects and includes bounded local process,
transaction, lifecycle and worker foundations. Declaration/schema/projection
checks do not qualify a general scheduler, async test broker or unattended
promotion loop. See the scope and evidence in the current reconciliation report.

## How AIDE Works

AIDE models development as typed, reviewable objects:

| Object | Purpose | Current repo status |
| --- | --- | --- |
| `ContractEnvelope` | Versioned protocol wrapper for AIDE objects | Implemented for review |
| `WorkUnit` | Bounded unit of intended work | Implemented for review |
| `WorkerRun` | Attempt record, with separate bounded local execution bindings | Source and recorded scoped reviews; operational scope varies |
| `TestJob` | Validation record, with registered local process bindings | Source and recorded scoped reviews; no general async broker claim |
| `EvidencePacket` | Proof record for claims, checks, artifacts, and limitations | Implemented for review |
| `ReferenceID` | Stable `aide://...` identity across files, reports, events, and views | Implemented for review |
| `EventRecord` | Projection-only append/history vocabulary | Implemented for review |
| `OKF Knowledge Page` | Human/agent-readable explanation of repo truth | Implemented for review as projection |
| `CapabilityManifest` | Declared capability surface for tools, adapters, and subsystems | Implemented declaration/schema; recorded review with warnings |
| `ConformanceProfile` | Declares checks and acceptance obligations | Implemented profile/result projections; not automatic trust |
| `PatchTransaction` | Controlled mutation proposal with evidence and boundaries | Schema and bounded executor source; no general apply authority |
| `AdapterManifest` | Provider, tool, and host adapter declarations | Implemented declaration/schema; not adapter admission |
| `ContextPack` | Compact agent context from OKF, protocol, and evidence | Implemented v2 projection; not model dispatch |

## What Makes AIDE Different

| Category | What it does | How AIDE differs |
| --- | --- | --- |
| AI coding assistant | Helps edit code in a session | AIDE records durable work, evidence, events, and repo knowledge |
| IDE extension | Adds AI UI to one editor | AIDE is host-agnostic and can support old and new hosts through adapters |
| Prompt pack | Gives agents instructions | AIDE defines protocol objects, evidence, queues, conformance, and knowledge |
| RAG or wiki system | Retrieves project docs | AIDE maintains OKF-compatible compiled repo knowledge tied to work and evidence |
| CI system | Runs checks | AIDE uses checks as evidence inside a broader development control plane |

AIDE is not the agent. AIDE is the system around the agent.

## OKF Knowledge Plane

AIDE uses an OKF-compatible knowledge bundle because project knowledge should be
portable, readable, versionable, and useful to both humans and agents.

Instead of forcing every agent to rediscover repo facts from raw files, AIDE
compiles what the repo knows into markdown concept pages with YAML frontmatter.
That gives the repo a shared explanation layer:

- current state
- architecture decisions
- protocol objects
- accepted capabilities
- known risks
- evidence links
- stale or contradictory claims

AIDE follows this boundary:

```text
Protocol executes.
Evidence proves.
OKF knowledge explains.
```

OKF pages are readable markdown with YAML frontmatter. They help humans and
agents understand the repo, but they do not replace protocol objects, queue
truth, EventRecords, ReferenceIDs, or EvidencePackets.

Current local bundle shape:

```text
.aide/knowledge/okf/
|-- index.md
|-- log.md
|-- current-state/
|-- protocol/
|-- capabilities/
|-- decisions/
`-- risks/
```

The knowledge plane is influenced by the LLM Wiki pattern: maintain a
persistent, interlinked markdown wiki that accumulates synthesis over time
instead of repeatedly retrieving raw files for every question. In AIDE, that
wiki is not the source of execution truth. It is the repo's compiled explanation
layer.

## Agentic Development Workflow

AIDE is designed to support this loop:

```text
goal
-> wave
-> WorkUnits
-> WorkerRuns
-> TestJobs
-> EvidencePackets
-> EventRecords
-> OKF knowledge
-> PatchTransactions
-> repair or blocker records
-> checkpoint
-> promotion
```

AIDE should not rely on one long-running agent session. The durable process is
AIDE. Agents are disposable workers.

## Multi-IDE And Legacy Support

AIDE is designed to work beyond one editor.

The long-term target is to support:

- Visual Studio, including older versions
- VS Code
- JetBrains IDEs
- Xcode
- RAD Studio and Borland-era environments
- CodeWarrior-style hosts
- generic file-system-only projects
- CI-only environments
- remote or weak machines that cannot run modern AI binaries directly

AIDE's intended host topology:

```text
legacy IDE / workspace
-> thin bridge or file watcher
-> AIDE service / control node
-> modern compute or gateway node
-> agent / provider / test runner
-> PatchTransaction / EvidencePacket
-> host-side review / apply
```

The old IDE does not need to run a first-party agent binary. It only needs a
bridge. The current repo has host-lane proof records and skeletons, not complete
legacy IDE products.

## Workshop / Workbench Vision

AIDE is also intended to support visual development.

For a game, engine, or complex software project, a first-class
Workshop/Workbench module should show:

- WorkUnits
- WorkerRuns
- TestJobs
- EvidencePackets
- patch previews
- engine subsystem maps
- asset/code relationships
- OKF knowledge graph
- risk graph
- capability graph
- checkpoint readiness

The Workshop should be a visual operating surface over AIDE, not a separate
authority layer. It is planned, not implemented.

## Safety And Truth Model

AIDE is built around bounded autonomy.

Agents should not:

- silently mutate broad repo state
- claim implementation without evidence
- hide failed validation
- bypass patch review
- force-push protected branches
- modify secrets
- run unsafe operations without approval

Unsafe work should be quarantined. Safe unrelated work should continue.

Repository truth follows this order:

```text
governance and policy
-> filesystem queue
-> protocol and evidence records
-> generated reports
-> OKF explanation
-> chat history
```

Generated downstream artifacts are outputs, not source-of-truth records, unless
a reviewed policy explicitly says otherwise.

## Current Roadmap

Existing declaration and projection foundations include:

```text
OKF knowledge and report-only Reconciler
CapabilityManifest and ConformanceProfile/Result
PatchTransaction and AdapterManifest schemas
ContextPack v2 projection
```

Later:

```text
Test Broker runtime
Patch engine
WorkUnit lifecycle CLI
leases
scheduler
Service
Commander
Workshop / Workbench module
IDE hosts
provider adapters
checkpoint / promotion runtime
```

The [staged development plan](docs/roadmap/staged-expansion-roadmap.md) separates
dependency-ready local work from host/model/network qualification and larger
deployments. The [full reconciliation report](.aide/queue/AIDE-ARCHITECTURE-RECONCILIATION-01/REPORT.md)
links current claims to source and recorded evidence. Candidates are not admitted
runtime work or calendar promises.

## Implementation Status

| Area | Status | Notes |
| --- | --- | --- |
| Self-hosting queue | Implemented | Filesystem queue is the canonical routing surface for non-trivial work |
| AIDE Lite helper CLI | Implemented for review | Local deterministic helper commands; not a full service runtime |
| Contract envelope | Implemented for review | Versioned object shape and validation surface |
| EvidencePacket | Implemented for review | Proof object for claims and validation |
| WorkUnit | Implemented for review | Queue and CLI surfaces exist with bounded mutation controls |
| WorkerRun | Bounded local foundations | Metadata, durable attempt/process source and scoped worker evidence; outer client remains unqualified |
| TestJob | Local validation foundations | Metadata and registered validation bindings; general async broker remains unqualified |
| ReferenceID | Implemented for review | Stable `aide://...` identity syntax and projection reports |
| EventRecord | Implemented for review | Projection-only event vocabulary; no append-only runtime event store |
| OKF knowledge bundle | Implemented for review | Deterministic markdown/YAML projection under `.aide/knowledge/okf/` |
| Reconciler reports | Implemented report-only | Drift detection and recorded review; no automatic repair |
| CapabilityManifest | Implemented declaration/schema | Does not execute or qualify a capability |
| ConformanceProfile/Result | Implemented projections | Does not establish operational conformance by itself |
| PatchTransaction | Schema and bounded executor source | Scope/ownership/review still control every effect |
| AdapterManifest | Implemented declaration/schema | Does not install, admit or activate adapters |
| ContextPack v2 | Implemented projection | No automatic inference or provider dispatch |
| Runtime scheduler | Limited local foundations | Generalized scheduling and fleet guarantees remain unqualified |
| Test Broker runtime | Registered local validation bindings | General asynchronous broker remains unqualified |
| Workshop / Workbench | Not started | Later |
| Legacy IDE adapters | Lane-specific proofs/bindings | Exact inventory, tier and capability ceiling apply; no family-wide parity |
| Live model/provider operation | Unqualified | Offline metadata and opt-in host-binding source exist; actual usage/efficiency qualification remains pending |

## Getting Started

This repo is still pre-product. Start by inspecting the local control plane:

```powershell
py -3 .aide/scripts/aide_lite.py doctor
py -3 .aide/scripts/aide_lite.py validate
py -3 .aide/scripts/aide_lite.py task status
py -3 .aide/scripts/aide_lite.py okf status
py -3 .aide/scripts/aide_lite.py okf validate
```

For non-trivial work, use the filesystem queue under `.aide/queue/` or compile
an intent packet before implementation:

```powershell
py -3 .aide/scripts/aide_lite.py intent compile --prompt "<bounded task>"
```

## Repository Layout

Durable repo contract:

```text
.aide/
|-- protocol/
|-- queue/
|-- policies/
|-- evidence/
|-- reports/
|-- knowledge/okf/
|-- decisions/
`-- generated/
```

Local/runtime state should stay outside committed source control:

The following illustrates roles, not a directory-creation instruction. Each
qualified deployment selects approved local roots and one authoritative writer;
database and event-file examples cannot independently own the same objects.
The current maintainer runner uses its existing ignored execution configuration
and approved shared storage. A new task reuses that selection rather than
creating another pool, clone or root layout.

```text
.aide.local/
|-- state.sqlite
|-- event_log.jsonl
|-- leases/
|-- locks/
|-- runs/
|-- temp/
|-- logs/
`-- artifacts/
```

Other important roots:

- `core/`: protocol, knowledge, harness, compatibility, gateway, provider, and apply foundations
- `shared/`: bootstrap-era shared implementation and tests
- `hosts/`: host-lane proofs, skeletons, blocked records, and lane-local wrappers
- `bridges/`: bridge metadata and target expectations
- `governance/`: repository law, support policy, naming law, and capability doctrine
- `docs/`: reference docs, roadmaps, decisions, charters, and planning material
- `inventory/` and `matrices/`: exact version, support, capability, and verification records
- `environments/`, `labs/`, `evals/`, and `packaging/`: environment, prototype, verification, and release-shape records

Committed `.aide/` content should describe repo truth and portable project law.
Volatile runtime state should remain outside normal committed source control.

## Design Principles

```text
Boring core, flexible edges.
Portable files before services.
Evidence before claims.
Conformance before trust.
Report-only before mutation.
Adapters before provider lock-in.
Runtime after protocol.
Surfaces after truth.
```

## What AIDE Is Not

AIDE is not:

- a replacement for Git
- a replacement for CI
- a replacement for your IDE
- a single-agent autopilot
- a proprietary knowledge service
- a VS Code-only extension
- a Codex-only tool

AIDE can generate repo guidance and context for tools such as Codex, Claude
Code, Gemini CLI, local scripts, CI, and human workers. Provider-specific
integrations are adapters. They are not the AIDE architecture.

## Influences And References

- [Open Knowledge Format introduction](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
- [Open Knowledge Format specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Codex `AGENTS.md` guidance](https://developers.openai.com/codex/guides/agents-md)

OKF is useful to AIDE because it is portable markdown plus frontmatter, not a
new mandatory runtime. The LLM Wiki pattern is useful because it treats
knowledge as a persistent, compounding artifact. `AGENTS.md` is useful as a
tool guidance export target, not as AIDE's internal ontology.

## Contributing

AIDE is being built slice by slice.

Good contributions are:

- narrow
- evidence-backed
- protocol-compatible
- tested
- explicit about non-capabilities
- careful not to overclaim implemented behavior

Each non-trivial change should produce:

- a bounded task
- implementation or check evidence
- validation output
- changed-file summary
- remaining risks
- next recommended task

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before
making substantial changes.

## License

AIDE is licensed under the Apache License, Version 2.0 (`Apache-2.0`).

You may use, modify, fork, redistribute, package, integrate, and build on AIDE,
including for personal, research, nonprofit, educational, commercial, and hosted
uses, subject to the license terms.

AIDE project names, logos, and branding are not licensed for misleading or
official use. See [NOTICE.md](NOTICE.md) and [TRADEMARKS.md](TRADEMARKS.md).

Generated outputs are addressed in [GENERATED_OUTPUTS.md](GENERATED_OUTPUTS.md):
your repo content remains yours, and AIDE does not claim ownership over
repo-local outputs generated from your own project.
