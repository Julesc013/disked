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
Installed Setup SDK/CoreShared use, all lifecycle modes, embedded H/D/S, installation,
signatures, release licensing and other platforms need their own evidence.
No supplied upstream script is executed.

The separate [native source probe](../../../tests/setup/native/CMakeLists.txt)
compiles original CoreStatic bytes selected by
[`native-source-lock.json`](../../../external/universal-setup/native-source-lock.json)
under a DiskEd-owned build. It is private fixture tooling, not linked into
`disked.exe` or an installed-SDK qualification. Export from an explicitly
selected local repository into a **new** directory:

```text
python release/bindings/universal-setup/export_native.py --repository UPSTREAM_REPOSITORY --output NEW_SOURCE_DIRECTORY
cmake -S tests/setup/native -B NEW_BUILD_DIRECTORY -G "Visual Studio 17 2022" -A x64,version=10.0.19041.0 -T v143,version=14.44.35207,host=x64 -DUSK_SOURCE_DIR=ABSOLUTE_SOURCE_DIRECTORY -DCMAKE_SYSTEM_VERSION=10.0.19041.0
cmake --build NEW_BUILD_DIRECTORY --config Release
python tests/setup/run_source_consumer.py --probe NEW_BUILD_DIRECTORY/Release/setup_source_probe.exe --package REVIEWED_PACKAGE --inventory ORIGINAL_INDEPENDENT_INVENTORY.json --output NEW_CAMPAIGN_DIRECTORY
```

The probe whitelists six read-only commands, uses null lifecycle authority and
copies supplier response bytes before invalidation. Its zero exit means an
observation was captured; check the retained supplier return, response status
and refusal separately. Both generic package commands refuse because this pin
requires FacMan metadata. The archive inspector checks structure/source hash;
it does not replace decoded-byte completeness verification. The unconfigured
plan refusal is a gate observation, not a successful lifecycle plan.
