# Implementer review: shared FAT image commands

Reviewed mode-specific schema/bounds/UTF-16 conversion, generated command/forms,
reader port wiring, native source/process lifetime and worker composition. Old
map/table/GPT schemas and command identities keep their established behavior.
FAT view requires explicit selection/window; help and invalid inputs cannot open
sources. No source-derived name becomes a path or terminal instruction.

Coverage/change are independently derived from actual captures, including changed
reads in an incomplete tree. Projection omissions bind original details without
rewriting complete analysis or queries. Request wait expiry does not release a
running callback or establish child exit. The actual owned worker is retired;
essential commands remain available and frontends preserve caller state.

At 57cfd113: 62 focused command cases, 97 native groups, 17 headers and 221 tooling
passes/two skips. This is implementing-agent review, not independent-person or
owner acceptance. Original names/process/epoch/hash facts remain scoped; no
filesystem health, mounted consumer, further host, extraction, writer/recovery,
installation, release or full 0.1.0 qualification is inferred.
