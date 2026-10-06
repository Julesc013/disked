# DE-W015 development review

Base: `dec51212be3f310aca4c819ae14a4cc9af01825f`.
Authority: the explicit local programme grant. This is agent review, not owner
acceptance, an independent reviewer or platform/accessibility certification.

The native Win32 adapter shares the existing service and descriptor contracts.
It has a target navigator, command explorer, structured inspector and separate
review/submit controls. The current/proposed summary honestly reports no plan.
All storage effects remain unavailable. The GUI model retains exact identity and
review revision; selection removal and stale requests use the service's results.

Reviewed implementation boundaries:

- Complete argument validation and explicit help precede GUI initialization.
  Required user32/gdi32 APIs load from System32 only on the explicit GUI path.
  A dedicated unavailable-dependency/provider-trap binary proves that headless
  commands and malformed GUI requests avoid that boundary. Direct PE imports
  remain independently checked by the native protocol tests.
- Interactive window-station visibility and API availability are checked before
  constructing the fake service. No console attach/detach/hide, global theme,
  clipboard, system display or high-contrast setting is changed.
- Native controls provide roles, font, colors, focus and scrollable complete
  text. Original editable values remain separate from escaped review/results.
  A rejected edit cannot leave an older value authorized. Review is consumed by
  editing, submission, staging or a selection-clearing result.
- Request submission consumes review before dispatch. Repeated button activation
  cannot resubmit. Refresh preserves the staged revision so a later service
  capture produces a refusal. No UI eligibility calculation grants storage access.
- Dynamic optional thread DPI support and actual high-contrast observations are
  recorded without converting them into untested compatibility claims.
- Native callbacks contain exceptions; owned window, font, class and thread DPI
  state have bounded lifetimes. There are no persistent preferences, history,
  custom icon assets, production providers or asynchronous operations.

Actual keyboard testing found that the read-only multiline edit consumed Tab.
The message loop now explicitly traverses native tab stops, including that edit.
The regression visits all enabled main controls. A separate check visits Submit,
returns to an edit, and confirms Enter still cannot submit the reviewed request.
Review also found that a rejected edit was replaced by a question-mark sentinel;
bounded rejected text is now retained for correction and separately marked invalid.

The first capture attempt returned a blank image for a hidden window. It was not
used as rendered-UI evidence. The fixture now creates an inactive private desktop,
places only its own process there, waits for the actual window to become visible
on that desktop and captures only that window. It never switches the user's
desktop. Python's subprocess startup wrapper omits `lpDesktop`, so this path uses
an explicit CreateProcessW structure. Keyboard inspection uses the fixture
thread's temporary desktop association, restored before closing the desktop.

The initial native-window suite exposed two fixture defects: module enumeration
can return ERROR_BAD_LENGTH while modules load, and the capability assertion
addressed the envelope rather than its assessment member. The fixture now uses
a finite retry for the [documented snapshot race](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot) and reads the existing schema's
assessment path. No runtime refusal or assertion was bypassed. Initial observations
are retained separately from final results.

The host injects Windhawk and several associated modules into both headless and
GUI processes. Consequently a loaded user32 module on this host does not prove
DiskEd initialized its GUI, and the module observation is not a clean-loader
qualification. Source/import checks and the dedicated initialization trap establish
the application boundary; a clean VM is still required for the broader claim.

Working verification passed 15 native CTest groups and 163 specification tests
with two symlink skips. Six native GUI-model tests compare GUI/CLI/TUI outcomes;
seven actual-window tests cover keyboard traversal, form admission, bounded
input, native control roles, resizing, host observations and dependency refusal.
Post-review and clean-source evidence are recorded separately with exact inputs.

Limitations: only this Windows 10 x64 host was exercised. High-contrast-on,
screen-reader behavior, per-monitor DPI, old Windows, remote/Explorer launch,
clean-VM and missing real system-DLL environments remain unqualified. System
colors were observed with high contrast off; the user's settings were not changed.
Model publication tests do not simulate an admitted real provider or writer.
Stock host icons are used in memory; no supplied extracted artwork is redistributed.

The next local unit is DE-W016: bounded same-file process roles and fake execution.
Owner acceptance, real storage authority and public release remain separate gates.
