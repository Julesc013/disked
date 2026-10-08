# W033 private acquisition pipeline checkpoint

Source `99d9befbddc1be89dc0a717ecf4fb0cb7a9d2302`, work base `e7032bf092070aa227f626139f672e07d9b53b80`. DE-W033 remains active. This checkpoint
implements and verifies its provider-independent native pipeline, not its whole
file acquisition feature or complete DiskEd 0.1.0.

The core under `source/runtime/acquisition/` binds source, destination, map, host,
executable and provider identities/epochs, effect footprints, aliases, access and
verification. Pure definition creates no output; a separate grant binds the exact
immutable definition digest and four effect categories. Actual providers must
establish OS ownership, fresh control, complete aliases and capacity before effects.

Fixed bounded chunks, selected retries and explicit zero substitution retain
successful source coverage separately from substituted/written/verified bytes.
Intention and map flush precede data effects; destination flush/readback precede
checkpoint. Resume validates sequence, exact definition/resources, map prefix and
destination hashes, observes pending effects before replay, and never overwrites
source. Stops are acknowledged at recorded chunk boundaries. Failing-read-mostly
policy does not silently add retries or completed-source rereads. Consistency is
live-uncoordinated; hashes/seals do not establish a snapshot or restore readiness.

Fresh checkout verification at this exact source passed all **41 native CTest
groups**, **207 acquisition-core cases**, and **171 specification tests** (169
pass, two existing Windows symlink privilege skips). Structural validation has
909 checks, 72 concepts, 150 requirements, 36 work units and 43 schemas. Manifest,
freshness and declared context checks pass. The native build binds 196 input
hashes with the pinned MSVC 19.44.35228/toolset 14.44.35207/SDK 10.0.19041.0,
C++14 Release/static /MT configuration. The recorded host is Windows 10.0.19045,
64-bit, non-elevated `BLACKGLASS-WIN1\Jules`.

`reproduction-99d9befb/commands.json` retains actual clone/configure/build/
test/launch/import commands and logs. `clean-results.json` binds exact native
inputs and four artifact hashes: disked.exe, disked_acquisition.lib, disked_hash.lib
and the test-only acquisition_probe.exe. Import/header/dependency observations
are tied to their exact executable subjects. Artifacts are in
`.aide-local/artifacts/DE-W033-pipeline-99d9befb/`. The ordinary product still
has its previous image/fake command set; `image.acquire` remains unavailable.

Reproduce from a clean checkout using the pinned installed toolchain:

```text
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python -m unittest discover -s spec/tools/tests -v
```

The additional producer-schema run uses the coordinator's spec dependencies:
`python tests/images/test_acquisition_pipeline.py --probe build/windows-bootstrap/Release/acquisition_probe.exe --root . --validate-schemas`.

All new acquisition fault tests use separately compiled in-memory ports. They
model pre/post API exceptions and explicit incomplete tails, not real-file or
physical power-loss behavior. The private exact-JSON map is provisional, not
production journal admission. Real persistent files, capacity/sharing races,
process termination, asynchronous frontend lifecycle, other platforms/hosts,
live AIDE and independent qualification remain unverified. Owner acceptance is
not recorded. The earlier source reproduction and the failing provider-error
regression remain historical evidence in FINDINGS; the expectation was retained
while the engine was corrected before this source's reproduction.

Continue DE-W033 with the ordinary Windows generated-file provider: side-effect-free resource preparation, pinned source/parent/output identities, no-clobber creation, separately owned persistent acquisition map, capacity and sharing checks, actual API faults/process interruption and matching-epoch resume. Reuse the private pipeline through inward-facing ports. Keep image.acquire unavailable until file-provider and asynchronous frontend admission/evidence are reviewed; retain the full 0.1.0 scope and all separate owner/storage/release gates.
