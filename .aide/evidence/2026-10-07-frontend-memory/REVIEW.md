# DE-W017 partial local agent review

Reviewed `07fd5dc67670a75dc0eeb6a7031953289ee268c1` against `271706b0213e5b15b96e8794f82ce2ede2019a13` and the DE-015/045 admission contract.
This is implementing-agent review under the continuation grant, not owner
acceptance or independent security review. The acceptance ledger stays empty.

- OS identity, name and ACL setup are fixed/bounded and RAII-managed. Advapi32 is
  loaded from System32. A same-user/session initialization mutex serializes job
  creation, limit verification and assignment; timeout is distinct from API
  failure. An abandoned mutex still requires inspecting the existing job.
- The process memory flag is the sole added job restriction. Existing limits
  must match; they are never rewritten. Incompatible hierarchy errors do not
  add breakaway, remove limits, launch a provider or retry through another job.
- CLI, stdio, GUI, TUI and shell admission precedes their handlers. Invalid
  syntax retains its original result without admission. Fixed parsing and the
  Windows loader are explicitly outside post-start job assignment coverage.
- A common ancestor avoids unrelated per-frontend job chains around the shared
  worker job. Actual concurrent-worker tests retain stricter worker quotas and
  independent lifetime, including after closing every frontend.
- Fault allocation and the separate named-object namespace compile only into
  disked_memory_test. The product's environment has no allocation or budget
  override. The denial probe measures real OS commitment rejection, not arbitrary
  production heap-failure recovery; no such broader claim is made.
- Tests assign inherited jobs atomically during owned process creation, query
  actual job membership/limits and sample owned process memory. GUI/console tests
  use isolated test desktops/consoles. No user window or physical storage is used.
- The initial failure cleanup revealed a suspended fixture worker after client
  termination during creation. Its exact identity and cleanup are retained;
  the underlying suspension cause remains unestablished. Cleanup now allows
  finite admission to return. No timeout or cleanup is called storage recovery.
- The clean source reproduces all 27 native groups and exact response/operation
  producer checks. Generated source/input identities include the new files and
  tests; spec/work contexts bind them. Documentation retains the open programme.

Continue local DE-W017 work. Combined provider failures and public event-stream
scope still need evidence; neither DE-W017 nor the full 0.1.0 goal is complete.
