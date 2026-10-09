Source `1f80711f9bfe9d8a18a1cf92878f98a117c8f0d9` passed clean native product report export:
67/67 native groups, 107 focused actual-product checks,
977 structural checks and 183 tooling tests (181 passed,
two skipped). Five actual frontends and one private held callback produced six
independently checked reports. See REVIEW.md and reproduction-1f80711f/clean-results.json
for exact commands, hashes, tested host, qualification boundaries and limitations.

Reproduce from this exact source with already installed pinned tools and fresh
owned paths, without concurrent standalone native harnesses:

```text
python .aide/evidence/2026-10-09-product-export/reproduce.py --source 1f80711f9bfe9d8a18a1cf92878f98a117c8f0d9
```

Product dev.31 advertises 19 runtime command identities. evidence.export covers
retained ordinary-file acquisition case metadata and support JSON only; public
contracts remain proposed. Full DE-W034 and all specified platforms/storage are
incomplete. Only sample-support.json is the selected default-redacted payload.
No current acquired-image verification, authenticated custody, physical/power-loss
or other-platform qualification is claimed. Owner and privileged/release gates
remain separate. Working failures and preserved fixtures are recorded explicitly.
