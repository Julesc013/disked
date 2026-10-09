Source `dd4cf58046d34ee4dae09a604be7b899b5c6ddd1` passed a clean local Windows reproduction of the provisional
inward export service. It is 0.1.0-dev.29 with 18 public commands; evidence.export
remains planned, its syntax is defined and its product handler is null.

65/65 native groups, 188 focused export checks,
970 structural checks and 178 tooling tests (176 passed,
two skipped) passed. The runner independently checked 317 build inputs, generated
acquisition bytes/map, actual report bytes, retained state and six selected native
artifacts. See REVIEW.md and reproduction-dd4cf580/clean-results.json for scope,
commands, logs, hashes and limitations. working-failures.json preserves failures.

Reproduce with the already installed pinned toolchain and dependencies from the
exact committed source using a fresh owned path:

```text
python .aide/evidence/2026-10-09-export-command/reproduce.py --source dd4cf58046d34ee4dae09a604be7b899b5c6ddd1
```

The runner refuses existing clone/artifact paths. Preserve failures and their
dependencies; do not delete or retry an uncertain attempt. Private parser/request/
form checks do not qualify actual product frontends, bounded product watch or full
DE-W034. Definitions/receipts contain generated private routing metadata; only
sample-support.json is the selected default-redacted payload. Stored transcripts
use repository line endings; hashes bind the retained bytes.

No physical/customer media, elevation, installation, signing, publication, owner
acceptance, authenticated custody, current-image verification, other-platform or
power-loss qualification. The all-platform/storage 0.1.0 goal remains active.
