# Shared FAT image inspection evidence: 2026-10-13

Native source `57cfd1132a3544a4a4ca393e0666ee4489fa5644`; preceding integration `fcd43399881b34de4506e578afc80822b4b5a942`. The expected
DE-W038 contract was committed at `6e9a4bb7` before evaluation. Standing local
implementation/tests/implementer review and tested dev/main synchronization
grants apply. Owner acceptance and full all-platform/storage 0.1.0 remain separate.

Product `0.1.0-dev.43` retains 21 command identities. Existing `image.inspect`
defaults to its compatible map view. Explicit `--view fat` requires an explicit
byte window; FAT copy, allocation/auxiliary checks and CP437/850/932 lookup are
typed controls. Invalid/conflicting controls and expected fake revisions fail
before source access. Essential help/build/discovery perform no source reads.
The ordinary-file source is read-only; names never become paths. No mount,
physical-device access, elevation, installation or release is involved.

The runtime port owns request interpretation, coverage/change outcomes and the
bounded projection. The Windows adapter holds source identity and owns the
contained reader's launch, result binding and actual retirement. The process
role reuses DE-W037's independently reconstructed captures. Logical publication,
actual process exit and frontend request wait remain separate. An uncertain
reader retains the executing callback/slot until exit; no replacement is inferred.
Soft four-second request expiry gives unknown6 and no durable operation ID;
the slot remains busy and no late unsolicited response is emitted.

Requested analysis coverage and source consistency determine outcomes. Complete
observations do not qualify filesystem health or mounted-consumer behavior.
Incomplete coverage and observed source changes can both be reported. Included
original names/metadata stay lossless. Full original observation/capture values
are hash-bound; bounded nodes, detail bindings, namespace rows and capture rows
have explicit returned/omitted counts. Display omissions do not change complete
analysis/query outcomes. Capture retrieval and extraction remain unimplemented.
The response stays within 512 KiB/65536 values/depth40 and existing worker limits.

Actual focused command tests passed 62 cases: independently generated FAT12/16/32
with 512/4096 units, original names/offsets/queries, selected copy/allocation/
auxiliary/model controls, invalid/partial media, large detail omissions and
machine parity, invalid-before-open inputs, source/refusal/recapture/binding
outcomes, and actual GUI/TUI/shell journeys for all three families. Review is
inert; owned consoles/windows close and source hashes/inventory stay unchanged.
Separate fault builds exercise capture/worker/callback controls; normal builds
ignore those private controls. Stable observations match across frontends while
process IDs, capture epochs and their hashes remain attempt-specific.

The first focused test expected a node-budget failure from a FAT12 fixture that
actually declared only 16 root entries. The reader correctly returned those
entries. The corrected FAT32 fixture declares a real chain covering 130 entries;
the missing coverage is now exercised. A separate fully captured long-name tree
proves explicit detail omissions. The first schema-test attempt also wrongly
expected 16 valid names to exceed the byte cap; the UTF-16/count bounds already
keep their UTF-8 size below it. The corrected case accepts the maximum valid
names and still rejects invalid count/encoding/bounds. The build boundary checker
caught the new entrypoint include lacking its module prefix; that was corrected.
Available failed logs are retained alongside repairs, without changing production
limits or weakening coverage, encoding or dependency expectations.

The first full source `dae710b0` passed 94/97 native groups in 593.58 seconds.
Both build-information variants failed because the expected object omitted the
selected FAT provider already declared by the composition/profile. The corrected
test binds that identity to the canonical profile and still compares exact output.
The old image GUI gate case also edited control201, which now represented logical
block size after the new mode discriminator. It now locates the semantic path
label across actual form pages and keeps the same busy/late-isolation assertions.
The first native source's 61 FAT cases passed; no downstream tooling/context/launch
qualification completed because the campaign correctly stopped on native failure.
Original commands, input/blob identities, build graph and complete native logs are
retained in `development-diagnostics/first-native-campaign-dae710b0.zip`.

Review also found that the GUI's private presentation limits and shell's record
classification needed to admit a full bounded FAT response. GUI now recognizes
FAT in the existing expanded display path, with its declared depth/value limits;
a real large-response GUI journey passes. Shell reuses its existing expanded
transcript budget; 14 model tests include a synthetic large FAT record with its
last row preserved. The private record flag is named expanded, reflecting all
observational families using it. No public wire or storage/process guard is raised.
Focused existing map/table journeys pass 126 cases after the field-label repair.

The clean unprivileged Windows x64 campaign passed 97 native groups, including
prior 1335 allocation, 6790 name/directory, 149 capture, 86 allocation-scan,
257 auxiliary, 171 namespace and 109 contained-reader cases. Seventeen private
headers compile independently. Tooling: 221 passed and two skipped (223 run).
Structural/index/manifest/context/source-map, actual launch/imports and generated
build/header dependency checks pass. The map covers all 218 source files.
MSVC 19.44.35228/toolset14.44.35207, SDK10.0.19041.0, CMake4.2.3,
Python3.14.7; GCC15.2 strict C90 syntax only, with no GCC runtime/ABI/legacy claim.
527 SHA/Git-blob bindings, 482 build
inputs, 155 targets and 4201 quoted
include edges are retained. Hash binding is not semantic review of every input.

The actual product closure includes the normal FAT reader/inspection modules.
Private GPT execution/restoration/journal and fault reader modules remain excluded.
Raw commands/logs, projects/codemodel, context and artifact hashes are retained.
Local artifacts: `.aide-local/artifacts/DE-W038-fat-command-57cfd113/`.

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-command/reproduce.py --source-revision 57cfd1132a3544a4a4ca393e0666ee4489fa5644 --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-command-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-command/audit_retention.py
```

Use a fresh output and clean owned clone. Retention audit does not rerun native
tests. Integration adds evidence/metadata to the tested source. Continue larger/
chunked FAT coverage, capture retrieval, extraction and further consumer/host/
platform/storage work. Production journal/recovery, owner, physical, elevation,
customer-data, installation, signing and release gates remain separate.
The full all-platform/storage 0.1.0 goal is active and unfinished.
