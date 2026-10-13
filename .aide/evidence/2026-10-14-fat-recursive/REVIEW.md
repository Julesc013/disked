# Partial DE-W056 agent review

This review covers the new supplied-reader content cursor, its held-file
integration, focused tests and the expected contract for the remaining recursive
backend. It does not accept DE-W056 or qualify a release.

The cursor owns its copied selection and callback ports. Region bounds use
checked offsets; borrowed bytes are copied before further reads. One allocation
bitmap persists across pages, so a cycle cannot reappear as fresh work. File data
excludes cluster slack. Tests independently check chunk source offsets, byte
contents, page hashes, partition equivalence and terminal callback silence.

The native adapter admits a file key only from its own latest applicable tree
page and keeps content on the same held file and ancestry. It cannot advance the
tree while content is active. Per-page read/applicability receipts reset, and
cancellation callbacks are cleared even on an exception. Fault-target dependency
checks pass without linking the normal file adapter into the fault executable.

The source map and naming rules remain coherent: shared continuation lives in
`runtime/capture/`; ordinary-file identity and reads live in `providers/image/`.
No new public command, SDK surface or storage mutation permission is introduced.

The content adapter is currently a synchronous private prerequisite. It has not
yet been connected to an owned recursive writer/worker. Destination creation,
effects/grants, original metadata evidence, native restoration policy and the
complete clean-source native campaign remain unfinished. Keep the work unit
active and retain this checkpoint on `dev`; owner acceptance remains separate.
