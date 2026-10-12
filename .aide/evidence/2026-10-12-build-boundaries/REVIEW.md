# Implementer review: core build boundaries

This is the implementation agent's review, not owner acceptance or a separate
person's independent approval. Native source is7f86f6bfdf45e0b79420f1c451a797ce2f70514a.

The source diff changes private CMake ownership/dependencies and adds bounded
checks/fixtures/standalone core-header compilation. Runtime C/C++ bytes and
source filenames remain unchanged. JSON compiles only the codec; command compiles
parser/protocol/lexer; invocation depends separately on JSON. Actual consumers
declare the required interfaces. Generated flags/projects retain pinned C++14,
MultiThreaded Release CRT and existing warning/security choices. Header checks
compile separately and are not linked into the product. The generated product
build closure excludes private GPT execution/restoration/file-effect adapters.

All84native groups passed, including command semantics, compatible readers,
invocation, GUI/TUI/shell and existing image/recovery fixture groups. All16checker
fixtures and5header compilations passed. The initial checker defects were repaired
with strict wrong-case and -MD rejection fixtures; raw diagnostics remain retained.
No expected product outcome or privilege/recovery guard was weakened.

No wrong-header binding was reproduced in the original tree. These changes add
preventive enforcement and accurate target names. The bounded generated graph is
not direct-link/preprocessor/ABI/full-platform qualification. Module-qualified
includes, broader standalone header coverage and shared GUI/TUI presentation
invariants remain the next scoped work. Full units, owner, production storage/
recovery, other targets, public licensing and release admission remain open.
