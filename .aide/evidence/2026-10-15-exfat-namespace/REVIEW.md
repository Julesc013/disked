# Implementing-agent review: capture-local exFAT namespace

The candidate source is `2545d078b8dd6fc5335cf38314013be3d4c2fc7c`.
This review is by the implementing agent, not an independent reviewer or owner
acceptance. Exact-source qualification completed. The bounded local implementation is ready for development integration and owner review.

The portable entry-set, NameHash and mapped-unit equality helpers remain the
format authority. The existing runtime upcase decoder/automatic selection has
one shared implementation; root observations keep their existing facts, budget
callbacks and explicit ambiguity policy. The new immutable map owns supplied
bytes and records invalid or budget-incomplete interpretation rather than
accepting a caller's assertion that a map is valid.

The namespace interprets only supplied logical directory records. It validates
capture-local identities, finite input shapes and nonoverlapping u64 byte ranges,
retains exact raw records/UTF-16 units, and distinguishes association, hash,
encoding, stream geometry and timestamp validity. A matching hash is followed
by full comparison using the volume table. Lookup cannot infer unique selection
or absence from incomplete or inapplicable coverage. Measured duplicate names
remain ambiguous even when later coverage is unavailable.

Limits bound the supplied record counts, comparison calls, retained findings and
encoded JSON. The conservative output reservation is a logical output budget,
not a claim about total process memory. Query results describe completed query
observations; exhaustion on a later query may make the overall model incomplete
without rewriting an earlier fully completed query result. No lookup result
confers stream, live-source, path-opening or mutation authority.

Independent fixtures cover all 1..255 name lengths, non-ASCII volume mapping,
surrogate pairs and malformed units, canonical-equivalent spellings without
normalization, NameHash collisions, duplicate names, corrupt/truncated/orphan
records, root-only records, map ambiguity and budget/coverage exhaustion. The
first omitted-findings failure found unspecified C++14 nested evaluation order;
the implementation now measures before moving, retaining the original assertions.

The code follows existing `runtime/capture`, `portable/exfat` and test ownership.
New modules have narrow CMake targets, qualified cross-module includes and
standalone header checks. Existing root/file/worker/frontend checks must pass
at the candidate revision because decoder extraction affects those consumers.

Coherent fragmented/NoFatChain stream collection, bitmap/allocation agreement,
recursive ownership/cycle checks, ValidDataLength-aware content, held-source,
contained-worker and frontend admission remain subsequent gates. Other hosts,
physical storage, owner acceptance, production writing/recovery, Setup and the
original all-platform/storage 0.1.0 release remain unqualified.

The full clean `2545d078` campaign passes all 142 native groups, 50 standalone
headers, 242 tooling tests (two skipped), source freshness, manifest/context and
recorded imports. The probe-only correction at `84d0c227` passes the same303
namespace cases plus13 independent integer-boundary cases and two standalone
headers on both x64 and Win32. Its kernel/header inputs match the full campaign;
product/runtime/library code is unchanged. PE headers confirm x64/x86 machines.

The original private Win32 probe shows 11 boundary mismatches against unchanged
kernel code, including an oversized budget and a query ID wrapping to a unique
lookup. The corrected probes reject those inputs. The original303 expectations
were unchanged. This supplement qualifies supplied-data namespace code, not the
full x86 product, physical storage or historical platforms.

The supplement's first runner stopped before compilation on CMake's ZERO_CHECK
utility dependency. The corrected runner distinguishes that regeneration edge
and still requires the exact six-library closure. Its failed log is retained.
No compiler flag, quota, timeout or semantic expected result was loosened.
