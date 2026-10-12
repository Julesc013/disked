# Evidence-preparation diagnostics

These are metadata-preparation failures after the clean native/tooling campaigns
passed. They are not product qualification failures.

The attempted `specctl.py validate-json ... --schema ...` command exited1:
the CLI has no validate-json command. Handoff validation instead uses the actual
Draft202012Validator and schema in the retained read-only auditor.

The first staged audit exited1 at its new assertion
`binding==value['dispatches'][0] and len(value['dispatches'])==1`.
Inspection of the exact retained receipts shows the shell chooser first issues
target.list with empty parameters and the original snapshot revision, then the
single deferred target.inspect. The committed native tests already require exactly
one inspect and bind the original request/result; they passed without alteration.
The auditor now checks exactly one inspect and exact binding, plus exactly one
completed read-only target.list on that same original basis for shell, and zero
other requests for GUI/TUI. This aligns its expectation with the existing interface
contract; no original result, identity, timeout or product criterion was weakened.
