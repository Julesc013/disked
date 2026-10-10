# Source ownership and shared text input

Clean product source `3f648127b7716a34e7c5fdf6c391165fa44764d1` built `disked.exe` dev.40 and passed all
77 selected native product test groups on ordinary non-elevated Windows 10
Enterprise 19045 x64. Corrected private source `67f3cfb0703418f16c08071b51238fde5348193d` passes the
separately compiled cached-frontend campaign:
15 controllers, 26 actual owned readers and 1300 assertions on each x64/x86
binary (82 processes and 2600 assertions combined). Tooling: 215 run,
213 passed, 2 skipped; 1055 structural checks and
source-map/index/context/manifest checks pass. All 457
selected source inputs match exact Git/checkout bytes. All
404 product inputs remain byte-identical across those two
revisions. The second run reuses the verified product and its 77-group result;
it does not rebuild or repeat the full product suite. x86 binaries ran on the
tested x64 host; this is not
historical Windows, x86-host, live-device or complete product qualification.

TUI and shell share the private host-neutral `TextKey`/`TextInput` contract in
`runtime/presentation/text_input.h`. Shell no longer imports `tui_model.h` or
exposes the TUI include directory in its CMake target. Native input decoding
stays in the Windows terminal host. Key ordering, payloads, reducer behavior,
command identities, protocol schemas and the selected ordinary product
composition stay unchanged. Existing independent behavioral expectations were
retained; only probe C++ type names changed.

The contributor map explains all 172 current source files, frontend/terminal
placement and the currently specified future ownership families. Exact future
filenames and zero refactoring are not promises. A public compatibility claim
does not arise from a private filename, C++ type or helper.

An initial structural check rejected the new registry item's invented `source`
kind. It was corrected to the existing `build` kind before clean qualification;
the validator and its allowed kinds were unchanged. The initial x64 private
probe build at `3f648127b7716a34e7c5fdf6c391165fa44764d1` then exposed its reliance on the shell header
to include the unrelated TUI model. The probe now includes `tui_model.h`
explicitly. The failed compiler log, source inputs and successful product
build/tests are retained under `product-prior/`. No behavioral expectation changed.

Final dependency metadata adds explicit terminal/shell ownership and a direct
build-input-list dependency for the shared header. The final metadata has its
own retained structural/tooling/index/context/manifest validation; exact native
source/build identities remain at the source revision above.

Commands, logs, configurations, source/build identities, actual requests/results,
PE imports/dependencies and artifact hashes are retained. Three executables
remain local under ignored `.aide-local/artifacts/`; their identities enter Git.
Large raw observations use lossless gzip with decoded size/hash bindings.
Implementing-agent review is in [REVIEW.md](REVIEW.md). No owner/independent
acceptance, full DE-W030 completion or all-platform/storage 0.1.0 completion is
claimed. New /2 interface/raw-comparison qualification remains separate.

```text
python .aide/evidence/2026-10-10-source-layout/reproduce.py --source-revision 67f3cfb0703418f16c08071b51238fde5348193d --output .aide-local/NEW_SHORT_ROOT
python .aide/evidence/2026-10-10-source-layout/audit_retention.py
```
