# DE-W099 supplied NTFS table review

The implementing agent reviewed source `ff74ccae18764ef54a6ad16a472ec59779e87b1c`, the independent
preimplementation contract/oracle and actual native results. This is agent source
review, not owner acceptance or independent provider/safety qualification.

One new private production file, `portable/ntfs/upcase.c`, joins the existing NTFS
target. Its declarations stay in `ntfs.h`; no new directory, opener, command,
frontend or public ABI is introduced. All256 descriptors are checked before any
mapping or result publication. Offsets stay within512-byte pages; names are bounded
to255 units. Raw and supplied-mapped orders are computed independently, including
zero/surrogate words, without normalization, host fallback or an implicit tie-break.
Borrowed descriptors/bytes and valid disjoint control objects are explicit private
API prerequisites. The complete envelope is not semantic or source validation.

Exact clean-source x64 all-target build passes. All21 selected groups of170 pass,
including327680 mapping observations,2520 independently expected comparisons and78
guard/control cases. All67 standalone headers, strict C90 source/header checks,
four executable PE/import observations,249 tooling tests(two skips), generated
freshness, manifest and context checks pass. Both isolated Win32/WOW64 groups and
two C/C++ headers pass with the same source and expected recipes. Source inputs
remain unchanged. Full current-native,full Win32 product,historical and other-host
qualification are not claimed.

The expected recipe/table/order digests were retained before native implementation.
Native results match those exact digests. Each supplied table maps all65536 units;
the deliberately nonstandard ASCII/non-idempotent/zero/maximum mappings prevent a
host shortcut or recursive mapping from satisfying the oracle. Readonly guarded,
noncontiguous and alternating unaligned pages constrain reads; invalid controls
preserve sentinel outputs. Exact source bytes and borrowed handle fields remain
unchanged. No ordinary image or physical source is opened by these helpers.

The first clean `1aec097e` x64 campaign built every target, then correctly failed
the exact build-source check because its canonical NTFS set omitted the newly
specified file. Twenty selected groups were not run. The correction adds only
that intended source; a retained diagnostic still rejects missing and extra source
mutations, and all32 checker tests pass. Production and independently expected
mapping/comparison inputs are unchanged; the original failure remains failed.
The candidate Win32 pass remains separately retained at its own revision.

The initial structural activation failed because its work status used an invalid
label. It was corrected to the existing `active` enum without changing the schema
or expected behaviour; the error is retained. Prior W095-W098 intermittent native
availability failures remain failures with unresolved original causes. This pure
primitive neither diagnoses nor declares them fixed.

The paged representation avoids requiring a contiguous128KiB C object or large
page-size arithmetic. That design rationale does not qualify an untested16-bit
compiler. Upstream code is a functional reference only; none was adopted or run.
No new external dependency or licensing resolution follows.

Source integration is suitable under the persistent dev/main grant after metadata
closure. Owner acceptance and every original0.1.0/storage/platform/release gate
remain separate. Next collect actual FILE10 unnamed DATA through the existing
stream/MFT closure, bind exact table bytes to the same capture/volume and settle
namespace/index/alias policy before lookup. Do not promote mapped equality into
filesystem uniqueness or current-source authority.
