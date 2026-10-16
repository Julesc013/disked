# Implementing-agent review: captured NTFS filename instances

DE-W094; base `df1754652a89eb6751a95f7440c65cba7fd64468`; exact native source, fixtures and recipes `189801696f022929257873c394e9a6b8d7d49dfc`.
The retained user grant permits local implementation, tests, repair and reviewed
dev/main synchronization across units. This review is by the implementing agent;
owner acceptance, independent qualification and storage/release privileges remain
separate. Original 0.1.0 scope is unchanged.

`ntfs_names.*` collects distinct FILE_NAME instances; `ntfs_stream.*` still joins
one ordinary stream. Their real shared FILE and attribute-list selection moved
into `ntfs_attributes_detail.*` within the existing library. The four added files
have actual consumers and source-map ownership; 321 production files retain the
five ownership roots. No public command, source opener, worker role, scheduler,
SDK ABI or future directory hierarchy was added.

The filename request fixes the selector to unnamed type0x30 and owns its controls.
Every selected FILE retains exact context, full reference/sequence/base/instance
checks and protected original hash. Resident or explicitly bound nonresident
lists use the same complete framing, generation and missing-dependency rules.
The filename-only mode permits multiple resident instances and a complete empty
inventory. It preserves list encounter order, distinct identical values, alias
names, parent references, namespace bytes and raw UTF16LE units. Original value,
opaque duplicated-information and suffix bytes survive; display or normalization
does not change identity. Unknown/malformed names, unsupported forms or quotas
yield no complete typed inventory. Known bad values override missing suggestions.
Reports retain bounded valid prefixes with explicit unverified membership,
collation and namespace. All authority/snapshot flags remain false.

Existing count, byte, list, attribute, run and output caps remain unchanged.
Additional name charging precedes retention; final serialization enforces the
selected cap. Returned vectors/values own their bytes after protected borrowed
input buffers are released. This is supplied-record validation; native source
acquisition and directory-entry correspondence still require implementation.

The clean all-target x64 build passes all 164 registered native groups, including
247 new filename cases, the unchanged 298 stream cases, 100 directory-command
checks and 58 bootstrap-command checks. It compiles 65 standalone C++ headers,
strict C90 NTFS sources/two C headers, records thirteen distinct PE/import
closures, and passes 247 tooling tests with two coordinator symlink skips.
[Exact campaign](qualified-18980169/summary.json) retains source/input hashes,
commands, JUnit, build configuration, compiler/SDK/runtime and executable hashes.
The private Win32/WOW64 supplement passes nine groups, eight headers and seven
executable import checks, including the same 247 filename and 298 stream cases.
[Exact supplement](win32-18980169/summary.json). It does not qualify the full
Win32 product, new public features, historical Windows or DOS.

The independent fixtures exercise both versions, empty/multiple names, aliases
and hard-link parents, identical values with distinct instances, maximum/raw
control/NUL/surrogate names, opaque suffixes, resident/nonresident lists, reordered
inputs/descriptors, missing/stale/conflicting/unlisted metadata, exact 64/256
record counts, global quotas and exact output boundaries. Guarded immutable
buffers and release-before-inspection verify result ownership. The original
stream fixture bytes remain unchanged.

The first native working evaluation passed both groups. Earlier preflight defects
remain retained: duplicate fixture labels, an unsupported registry kind, ignored
Python bytecode mistakenly included in an evidence inventory, and an overbroad
extra-root byte comparison. The extra .gitignore has checkout-only CRLF conversion;
all 1,114 declared qualification inputs and all production/specification inputs
match the clean checkpoint. No Git settings, product expectations, quotas or
deadlines were relaxed. The final campaigns independently verify unchanged inputs
and a clean checkout. These preflight failures are not native test failures.

The first clean campaign at `d2e51792` failed two groups: the large directory
NDJSON request returned request_wait_expired, and the boundary check found
missing direct portable-NTFS dependencies in the filename probe and private
header-check target. That run was deliberately stopped: 26 groups passed, two
failed, one was interrupted and 135 did not start. The raw running-status summary
and the separate interrupted-campaign observation remain preserved in
[original evidence](failed-d2e51792/observation-summary.json).

The two actual test/header consumers now declare disked_ntfs directly; the
stream library public dependencies were not broadened. Four focused groups,
including both boundary checks and unchanged 247 filename/298 stream cases,
passed. No production C++ or fixture bytes changed. Qualifiers now stop on the
first native failure, record actual partial coverage and still require every
registered group for a pass. The fresh x64 and Win32 qualification processes
were serialized rather than overlapped; no deadline or expected outcome changed.

A targeted [100-case recheck](directory-timeout-recheck-d2e51792/summary.json)
on the unchanged original executable passed. The bounded
[serial NDJSON comparison](ndjson-profile-d2e51792.json) completed six requests
per old/new binary with identical stable results, without a consistent slowdown.
The original timeout cause remains unknown, and those measurements do not turn
the original failure into a pass or establish host-independent timing guarantees.

This supports ordinary source integration after metadata/staged-byte closure.
Next implement source-bound target FILE/name correspondence under the existing
finite capture/replay/source rules, then collation, namespace/tree and content.
A complete captured name inventory is not proof of current-source membership or
full NTFS. All original platforms/storage, writer/recovery, Setup, licensing,
owner acceptance and release gates remain open as applicable.
