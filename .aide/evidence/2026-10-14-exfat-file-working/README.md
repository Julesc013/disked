# Working held ordinary-file exFAT adapter

60 native generated-file cases in seven methods and 20 selected regression
groups pass. Header and normal/fault PE/import checks pass. Ordered actual reads,
pure replay, source byte preservation, held access denial, malformed inputs,
limits, early/late cancellation, callback exceptions and binding failures are
verified. Separate fixture callbacks are absent from the normal environment/API.
Actual leaf/ancestor junction and hardlink refusals pass; the file-symlink fixture
is explicitly unverified because its creation required an unavailable privilege.
There was no elevation. Original compiler failure and repair are retained.

This is working-tree evidence. Exact source/context/tooling/local review remain.
The private synchronous adapter is not frontend/worker, tree/content/extraction,
other-host, physical writer or full original 0.1.0 admission.
