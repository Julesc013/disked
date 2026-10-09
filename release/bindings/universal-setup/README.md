# DiskEd / Universal Setup fixture binding

`package_fixture.py` maps reviewed local payload bytes to the exact upstream
product-package and recipe schemas. It constructs a deterministic stored ZIP,
verifies it with DiskEd's independent completeness checker, and can extract into
a **new marker-owned fixture directory**. It neither calls Setup nor installs,
repairs, updates or removes software. There is no competing installed-state
record, host integration, generic acquisition or storage authority here.

The authored expectations are in
[`setup-fixture-prototype.json`](../../../spec/catalog/setup-fixture-prototype.json).
Five unmodified schemas and MIT notices are retained under
[`external/universal-setup`](../../../external/universal-setup/README.md).
References resolve offline. All references, topology and component entries are
checked against the independent inventory; accepting each field's type alone
is insufficient. Unknown metadata, stale bindings and unsupported mode claims
refuse. Checksums identify bytes; they do not authenticate a publisher.

Typical commands (with explicit already reviewed staging and native build info):

```text
python release/bindings/universal-setup/package_fixture.py init-fixtures --root NEW_DIRECTORY
python tools/release/artifact_check.py inventory --staging STAGING --required disked.exe --output INVENTORY.json
python release/bindings/universal-setup/package_fixture.py assemble --workspace NEW_DIRECTORY --staging STAGING --inventory INVENTORY.json --build-info BUILD_INFO.json --output package
python release/bindings/universal-setup/package_fixture.py verify --bundle NEW_DIRECTORY/package --inventory INVENTORY.json --build-info BUILD_INFO.json
python release/bindings/universal-setup/package_fixture.py extract-fixture --workspace NEW_DIRECTORY --bundle NEW_DIRECTORY/package --inventory INVENTORY.json --build-info BUILD_INFO.json --output extracted
python -m unittest discover -s tests/setup -v
```

`BUILD_INFO.json` is the exact `result` from the qualified executable's
`--json build inspect`. The first profile is clean `0.1.0-dev.N`,
`windows.nt10.x64.win32`, `windows.native.image.prototype`. The fixture does
not itself prove that a supplied identity belongs to a binary; retain its
actual launch, source-bound build receipt and exact executable hash separately.
Verify and extraction require those separately selected independent inputs;
they never trust an inventory or build identity derived only from the bundle
being checked. Their own input integrity and actual review remain the caller's
responsibility; a maliciously replaced inventory is not an authentication root.

An existing root always refuses, even if empty. No overwrite, cleanup or retry
path exists. Write failure leaves partial output for inspection. Case, journal,
recovery and user configuration are externally owned and absent from payload
ownership. Tests use generated stand-ins, never customer files. Quiescent local
fixture inputs are required; these Python path checks are not an atomic
filesystem snapshot or isolation against hostile concurrent mutation.

The upstream recipe describes requirements and remains fixture-qualified. Its
`verify` selection is not the callable USK `package.verify` request. Schema
minimum reader is an authored requirement; `maximum_tested_reader` is explicitly
`not_run`, which the pinned schema permits. This does not establish a real
consumer's semantic acceptance or measured installed-state compatibility.
Live Setup SDK/ABI use, all lifecycle modes, embedded H/D/S, installation,
signatures, release licensing and other platforms need their own evidence.
No supplied upstream script is executed.
