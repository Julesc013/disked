# Contributing

Start from a named work unit and an exact Git revision. Keep the change bounded enough that another contributor can review its intent, implementation and evidence without reconstructing the entire project history.

## Workflow

Read `AGENTS.md`, the work definition and its context pack. Confirm the request's allowed changes and restrictions. Work in an isolated branch or worktree. Make the smallest coherent change, run relevant checks, and hand it to a separate reviewer with actual results and unresolved issues.

Specification edits update canonical concepts or structured catalogs. Refresh generated views with `specctl index`, then check and test. Do not hand-edit generated requirement catalogs. Public documentation should explain the resulting behavior without redefining command fields or safety rules.

## Review

A successful schema check means a record has the expected shape. It does not prove the behavior described. A test that was not run stays `not_run`; an unbuilt Windows target stays unqualified. An AI-generated review does not become a human approval. Original code cannot be published under an assumed license while that decision remains unresolved.

High-risk mutation and recovery changes need independent semantic review and target-specific evidence. Ordinary development uses fake providers and disposable images, not customer media or administrator privileges.

## Evidence and handoff

Use the [handoff schema](../spec/schemas/handoff.schema.json). Include exact sources, changed files, actual commands, observed exit codes, artifact hashes, blockers and next safe action. Preserve useful negative findings rather than repeating failed approaches in later sessions.

Acceptance records are content-bound and reviewed separately. Local metadata is not cryptographic authentication or an operating-system permission system.
