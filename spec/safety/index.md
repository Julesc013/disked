# Safety

[Bundle index](../index.md)

- [DE-040 — Threat model and trust boundaries](threat-model.md): Adversarial media, local privilege boundaries and recovery failures are first-class inputs.
- [DE-041 — Broker identity and bounded authorization](broker-and-authorization.md): Authenticate the request, exact executable, operator intent and live target.
- [DE-042 — Planner, action graph and simulation](planning.md): Compile intents into explicit dependencies, resources and recovery obligations.
- [DE-043 — Journal, recovery and durability](journal-and-recovery.md): Explicit recovery classes without false transactional or rollback claims.
- [DE-044 — Independent verification and efficient execution](verification-and-performance.md): Optimize verified work, never cache away fresh safety checks.
- [DE-045 — Bounded responsiveness and failure containment](degraded-operation.md): Bound waiting and resources without treating timeout as proof that effects stopped.
