# Agent review of partial owned writer integration

The bridge reuses the existing one-child/128MiB and four-process/512MiB host.
A compiled capability flag affects only the new writer profile; it grants no
effects and old reader claims remain unchanged. The provider constructor now
accepts preparation cancellation/progress callbacks without output creation.

Separate bounded publication/grant slots retain one prepared backend instance
and held source. Parent validation checks native process/code/request owner,
exact source/parents/policy/budgets/footprints and the independently derived
preparation capture. Opaque preparation artifacts cannot be constructed from
imported JSON. The child binds the grant to both that owner and the exact
prepared publication/definition. Outcome conservation and authority claims
are validated; failed publication withdraws future grant eligibility.

Publication and process exit remain separate. Parent dependencies persist;
an unresolved destructor transfers its preallocated owner into a passive
retained list without dropping quota/handles. Reaping uses actual exit only.
No scheduler, restart, automatic cleanup or new physical authority appears.
Source bytes stay unchanged and foreign/incomplete outputs are retained.

The quota failure was a harness-stage error: preparation allocates an owner,
while the existing job's limit applies at process launch. The corrected case
proves four children running before a refused fifth launch and observes their
retirement. Focused hang/cancellation/late/startup/poison cases and unchanged
reader/frontend regressions pass. Independent history inspection and a complete
frozen-source native campaign remain; no full-unit/owner/release acceptance.
