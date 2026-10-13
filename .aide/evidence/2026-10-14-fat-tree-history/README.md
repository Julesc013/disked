# DE-W056 supplied-byte history inspection

At base 547c3995 with retained working changes, 78 cases/13 methods pass.
Sixteen direct and three owned-worker actual histories cover recorded complete,
partial and unresolved effects. FAT12/16/32, original metadata/result consistency,
deep directories, the 33,000-cluster file, source-free inspection after source
withdrawal, six input partitions, incomplete tails, finite budgets and rehashed
contradictions have independent expected results. Tooling runs 238 tests:
236 pass and two skip. The new selected standalone header and generated closure
checks pass; the source map covers 248 current files once.

The inspector consumes supplied bytes and opens no recorded path. Matching
hashes establish declaration consistency, not authenticity, current destination
bytes/metadata, worker exit, power-loss persistence or replay authority. The
content-page digest is retained rather than recomputed because data is omitted
from that page. Directory create intents are identified as intents. No source
writes, physical/elevated/customer/installation effects or release admission.

Failed runs remain retained. Run 1 caught the missing traversal hash domain and
incorrect new test fault-selector names. Run 2 caught Windows text-mode stdin
normalizing CRLF; the probe now reads exact binary bytes. Run 3 passes before
the final original-metadata checks and owned-history coverage; the final run
passes the retained implementation. Rehashed negative cases require their
specific expected diagnostics rather than accepting unrelated early errors.

The development build directory predates this checkpoint. Its older generated
product identity is not a clean-source qualification of these new probes.
Exact retained working-input hashes and artifact copies bind this focused run.
The final new probe import/dependent observations are retained; KERNEL32 is its
only reported DLL dependency. Full exact-source native qualification remains
before unit review/main integration. DE-W056 and the full original 0.1.0 scope
stay active; no owner or release acceptance is recorded.

Build:
cmake --preset windows-bootstrap -B .aide-local/fat-recursive-development-build
  -D Python3_EXECUTABLE=D:/Projects/DiskEd/disked/.aide-local/venv/Scripts/python.exe
cmake --build .aide-local/fat-recursive-development-build --config Release
  --target fat_tree_history_probe disked_fat_tree_history_headers
  fat_tree_extraction_probe fat_tree_extraction_worker_probe
  fat_tree_extraction_worker_fault --parallel 2
ctest --test-dir .aide-local/fat-recursive-development-build -C Release
  -R '^evidence.fat_tree_history$' --output-on-failure
