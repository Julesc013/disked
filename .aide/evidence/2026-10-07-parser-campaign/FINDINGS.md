# W023 findings and retained differences

The 35 predefined native image-view cases passed before external comparison.
The first two installed util-linux profiles and GPT fdisk produced 162 retained
invocations and 92 table-projection comparisons, including 19 discrepancies.
These numbers describe this bounded initial corpus, not independent correctness
votes or all supported formats.

- Both sfdisk versions emit out-of-source MBR/GPT ranges that DiskEd retains as
  invalid observations and excludes from its valid-extent projection. They also
  emit an MBR type-zero record that DiskEd marks inactive. The original metadata
  is retained by DiskEd; it is not silently normalized into a valid partition.
- On the EBR cycle, both sfdisk versions repeat the logical entries to their
  partition-count cap, with a diagnostic. DiskEd reports the repeated address
  and incomplete coverage after visiting each unique EBR once.
- A bad EBR signature causes sfdisk to prefix its JSON output with diagnostic
  prose. The strict adapter retains that output as no machine projection. It
  does not discard the prefix and manufacture a clean producer response.
- A malformed GPT surrogate is emitted by both sfdisk versions as invalid UTF-8.
  The final adapter retains original bytes as hex and a SHA-256 digest, alongside
  escaped display text. It does not repair the name or treat the output as valid
  JSON. The initial adapter retained escaped text only; that evidence limitation
  was corrected before final verification.
- With both GPT header checksums invalid, sfdisk reports the protective MBR as a
  DOS table. DiskEd's independently retained GPT header failures are not converted
  into a selected GPT layout. The differing label projection is retained.
- GPT fdisk can report a table after in-memory reconstruction or selection. The
  pretend/print/verify invocation and unchanged-file hashes are retained; its
  selected table is never authority to select or repair a DiskEd candidate.

No native reader defect has been demonstrated by these initial comparisons.
Raw outputs and fixture hashes remain in comparisons-initial.json and the two
initial external-tool receipts. A matching projection says nothing about parity
of validation depth, name fidelity or independent backup verification.

The first Linux compiler attempt stopped at Git's ownership check because the
Windows-owned checkout is read by the explicitly unprivileged Linux account.
The runner now uses a per-command exception for this exact local checkout on
read-only Git metadata calls, without changing user Git settings.

The first combined-sanitizer positive control was caught by UBSan's object-size
check before the expected ASan message. Its failed receipt/log is retained in
initial-control-failure. Separate single-sanitizer controls now prove each
detector, while the actual parser campaign keeps both enabled and fatal.

The initial 2535-case sanitizer run passed. Review found that its coverage summary
incorrectly labeled four small system-header records with their translation-unit
name. The raw gcov JSON was correct and is retained; the final summary records
both the actual source path and the translation unit. The initial summary must
not be used as a per-file aggregate without consulting its raw records.

The first full specification suite detected a stale generated index after the
owning documentation was edited. Its failed log is retained. Regeneration,
without changing expectations, precedes the final specification suite.

Final adapter review found that closing both output streams could bypass the
process deadline while the child was still running. The loop now monitors the
process as well as its streams, tolerates an exit/kill race, and has a regression
that closes both streams before sleeping. Fourteen adapter controls pass. Invalid
UTF-8 is explicitly excluded from normalized projections, and the standalone
sanitizer runner now rechecks its source-input hashes after the campaign.

The final clean campaign retains 20 discrepancies. Comparing disk GUIDs adds
sgdisk on gpt-both-crc: it reports a newly generated in-memory GUID rather than
the original invalid headers. The source file remains unchanged; empty row lists
alone previously concealed this difference. Raw tool output and both candidates
remain in the final comparison receipt.
