# Read-only carrier fixtures and servicing review

These private tools exercise finite H/D/S construction and servicing constraints
without implementing a second installer. `fixture.py` constructs a stored ZIP
from finalized independently selected H/D bytes. H is a product-bound read-only
native source-consumer fixture; D remains the exact dev.36 DiskEd executable.
The ZIP is an offline fixture, not a native Setup carrier or live consumer.
Embedded H and generic lifecycle remain unavailable.

H is compiled independently with `DISKED_BUILD_HOST_FIXTURE=ON` in the separate
`tests/setup/native` CMake project. Its `host.inspect` reports exact source,
Setup pin, product binding and unavailable lifecycle without creating a context.
An explicit native campaign creates the caller-selected H input receipt. The
builder only checks that receipt against H bytes; it never launches supplied
code. Receipts and checksums do not establish publisher authentication or
independent native qualification by themselves.

```text
python release/carriers/fixture.py assemble --package QUALIFIED_PACKAGE --inventory ORIGINAL_D_INVENTORY.json --build-info ORIGINAL_BUILD_INFO.json --host VERIFIED_H.exe --host-input ORIGINAL_H_INPUT.json --output NEW_FIXTURE_ROOT
python release/carriers/fixture.py verify --root FIXTURE_ROOT --inventory ORIGINAL_D_INVENTORY.json --build-info ORIGINAL_BUILD_INFO.json --host-input ORIGINAL_H_INPUT.json
python release/carriers/servicing_preview.py --view GENERATED_OWNERSHIP_VIEW.json --request REVIEW_REQUEST.json
python -m unittest discover -s tests/composition -v
```

The inner carrier metadata binds only H/D descendants. Final S is bound by an
external file. Exact content inventory and decoded-byte verification remain
mandatory. Every existing root refuses; incomplete output is retained. No
configuration, case, evidence, recovery or foreign ownership is acquired.
Quiescent local fixture paths are required; this is not hostile-filesystem
isolation or an endpoint trust/admission system.

`servicing_preview.py` reads explicit generated views and prints a review
result. It discovers no installed state and performs no effect. It preserves
accepted selections/exclusions/policy, rejects competing owners and protects
externally owned data. Active/uncertain/recovery-required dependencies retain
their exact generations. Incomplete/stale captures and unreachable workers
defer all requested retirement because scope is unknown. Cancellation is not
release evidence. A proposed withdrawal denies new work only for the selected
provider generations and applies no authority policy.

`eligible` means the private constraint model passed. It always reports
`authorizes_lifecycle: false`, `authorizes_storage: false` and
`requires_atomic_recheck: true`. Live ownership, aliases, capture authenticity,
atomic servicing, installed SDK/CoreShared, owner transfer and release require
separate implementation and qualification. The profiles under `spec/catalog`
are provisional review models, not stable public ABIs.
