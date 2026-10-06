# DE-W014 development review

Base: `f183b0d162fc21538455a0cd0c8abee0306af518`.
Authority: the explicit local 0.1.0 programme grant in
`.aide/programmes/disked-0.1.0.json`. This is agent review, not owner acceptance
or independent accessibility, platform or storage qualification.

The same executable now offers native-console screen and linear presentations.
Both use one bounded model and the existing frontend service. Selection binds a
graph identity and revision; forms derive their fields from command descriptors.
The explorer distinguishes available, unavailable and transport-only commands.
The stdio server cannot be nested inside an interactive form.

Reviewed boundaries:

- Channel roles and minimum screen geometry are checked before fake-provider
  initialization. Essential help and malformed invocations remain static.
- A form is inert until a fresh F9 reviews it and another fresh F9 submits it.
  Enter, pasted newlines and held activation keys do not submit forms. Stale
  review revisions produce service refusals rather than automatic rebasing.
- Model tests compare graph outcomes with actual CLI and stdio responses. They
  exercise removal, stable missing selection, bounds, escaped labels, paging and
  every command's explorer availability. Native console tests exercise real key
  records and actual product command forms, including build and mode inspection.
- Screen rendering owns a noninheritable console buffer. Restoration captures
  the actual active buffer through `CONOUT$`; a standard output handle may name
  an inactive buffer. A dedicated fixture verifies that distinction.
- Input restoration merges only the bits changed by this process. An unrelated
  bit changed while the child runs survives. No title, code page, font, standard
  handle or caller buffer-size changes are requested.
- Normal exit, key-based Ctrl+C, delivered Ctrl+C and a caught injected failure
  restore owned state. The injected fault exists only in a separate test binary.
- Text is ASCII escaped before terminal presentation. Exact underlying names
  remain in the shared data model. Forms, captures, outcomes and frames have
  finite bounds; future larger providers still require payload qualification.

The initial console run found a real cancellation defect: a launcher can pass
its ignore-Ctrl+C attribute to a child. The interactive child now enables its own
handler explicitly; both delivered signals and input key events pass. The initial
observations are retained in `initial-console-observations.json`.

That run also exposed an overstrict fixture: linear output legitimately advances
the cursor and viewport through scrollback. The corrected check preserves viewport
dimensions and caller settings; screen-only cases additionally require unchanged
caller content, cursor and viewport position. No input or restoration check was
removed. A subsequent review found that `mode explain` omitted an explicitly
selected linear preference. Its startup capability report now includes that
preference, with a real-console regression test.

The working tree passed 13 native CTest groups and 163 specification tests, with
two symlink skips. Post-review checks and the exact clean source reproduction are
recorded separately. The terminal producer's native-console and redirected-pipe
observations are validated against the strict capability schema.

Limitations: this is a Windows 10 x64 native-console implementation. Screen-reader,
ConPTY, VT, remote, legacy-host, clean-VM and forced-termination qualification have
not run. Linear presentation is an accessible design path, not a certification.
Capability observations describe startup channels and API support, not a live
screen-state protocol. GUI, asynchronous execution, real providers and storage
operations remain subsequent work. Nothing here admits a storage effect.

Next local work: DE-W015, a native Win32 GUI using the same fake service and
descriptor semantics. Owner acceptance remains a separate recorded decision.
