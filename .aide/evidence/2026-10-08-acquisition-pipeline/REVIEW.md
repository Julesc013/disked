# W033 implementing-agent component review

Reviewed `99d9befbddc1be89dc0a717ecf4fb0cb7a9d2302` against `e7032bf092070aa227f626139f672e07d9b53b80` and DE-103's private profile. This is agent
review under the owner's continuation policy, not owner acceptance or independent
safety qualification. W033 remains incomplete and active.

The runtime depends inward on JSON and portable hashing, not Windows or a concrete
provider. SHA-256 moved to a shared static library without changing its algorithm;
all existing native groups pass from a fresh checkout. The ordinary product does
not link the acquisition engine or admit the public acquisition command.

Definition/grant/resource checks precede provider creation. Geometry and map bounds
use exact bounded integers. Output creation errors retain failed partial state;
only a provider-proven creation refusal claims no effects. Identity/epoch checks
guard dependent boundaries. The provider still bears responsibility for real
locks, alias completeness, fresh capacity and output-location correspondence.

Intention is flushed before an effect. Readback verification and map flush precede
coverage advancement. Counters distinguish returned reads, successful source,
substitution, writes and readback. Pending receipts retain uncertainty. Map budget
is reserved before dispatch. Bad provider error IDs cannot create nonresumable
receipts: the reproduced failure and unchanged passing regression are retained.
Unicode identities and valid error IDs are bound losslessly by the private bytes.

Resume reads one bounded record at a time and rejects mismatched definitions,
resources, sequences, digests, geometry, unknown records and incorrect coverage.
It validates completed destination/source policy coverage and observes unrecorded
effects before bounded replay. Truncated final rows do not authorize discarding
bad complete rows. A sealed applicable resume appends/writes nothing. Stops do
not pretend to retire a running asynchronous worker; that integration is pending.

207 native cases include independently generated exact bytes and Python SHA-256,
fresh/late mutations of all six bindings, alias/grant refusals, Unicode, boundaries,
retry/read substitution, partial/corrupt writes, map tampering, stops and modeled
interruptions. Full native and spec tests, import observations and source-bound
artifact hashes are retained. These tests establish the private in-memory port
profile only. Continue the actual file provider next; no file, hardware, snapshot,
production journal, owner acceptance or full-product claim follows from this review.
