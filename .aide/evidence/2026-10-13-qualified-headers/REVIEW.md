# Implementer review: qualified private headers

Reviewed the mechanical include-only C/C++ change and actual CMake ownership/
compile-usage declarations at 3598ac40. Paired headers follow their implementing
targets; header-only roles and Windows inline mechanism have explicit owners.
JSON-only consumers expose only JSON; private link dependencies do not grant
transitive header access. Source hierarchy/public IDs/commands/schema/algorithm/
effect/resource behavior is preserved. Header smoke includes use exact qualified
names. Shared Windows mechanism preserves per-executable macro isolation.

29 checker fixtures and85 native groups pass;7 headers compile independently.
20 standalone Windows adapter targets compile without device execution. The
inactive journal fixture dependency is governed by its actual configured flag,
not an added dependency merely to satisfy lexical checking. Conservative scope
and source search-root limitations are explicit. No full preprocessing, ABI,
other-target/hardware or public SDK admission is claimed.

One implementer review; owner/independent-person acceptance remains pending.
Broader source decomposition is a named-responsibility follow-up, not grounds
for another whole-tree rewrite. Continue full programme/recovery work and keep
physical/elevation/customer/install/sign/release gates separate.
