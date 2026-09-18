# Maintaining the specification

## Authored and generated content

Authored concepts use OKF v0.2 Markdown with a namespaced `disked` extension. The Markdown owns normative requirement prose; JSON Schema owns wire-field constraints; command and target catalogs own their structured declarations. A conflict is a specification defect, not permission to select whichever source is convenient.

Generated indexes, requirement/test views and command-reference output are rebuildable. Edit the canonical owner, then:

```text
python spec/tools/specctl.py index
python spec/tools/specctl.py check
python -m unittest discover -s spec/tools/tests -v
python spec/tools/specctl.py manifest
python spec/tools/specctl.py verify-manifest
```

A changed digest after an intentional edit is expected; regenerate integrity metadata only after reviewing the change. The digest is not a signature or an approval.

## Find and assess impact

```text
python spec/tools/specctl.py search "broker identity"
python spec/tools/specctl.py show DE-041
python spec/tools/specctl.py impact runtime/journal/writer.cpp
```

Impact routing is conservative and reports unknown ownership rather than pretending no tests are needed. Stable logical IDs survive file moves. Update the path registry and links when moving a concept; never silently reuse a retired ID.

## Publishing

These human-written guide pages link to the specification. A command reference can be generated from the command catalog and published as a clearly marked generated page. Other prose remains editorially reviewed. Do not mechanically turn all normative text into the README or overwrite its product introduction after an implementation task.

## Returning to the project

Commit the reviewed archive to GitHub once. Future sessions can start from the root instructions and selected work ID rather than the original long discussion. Record new decisions, failed experiments and handoffs in the repository so progress survives a change of model or service.
