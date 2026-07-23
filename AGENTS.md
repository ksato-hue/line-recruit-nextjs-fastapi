# Repository working rules

- Add characterization tests before large splits or refactors so current behavior is protected.
- Treat the LINE Webhook, application state transitions, and company scope as critical paths.
- Do not assume production-ready multi-tenancy. Verify every relevant query and database policy before making a tenant-isolation claim.
- Support security claims with exact code, migration, or configuration evidence. Mark runtime state that was not inspected as unverified.
- Do not describe configured, partially implemented, or documented features as operational without tracing their execution path.
- Distinguish an empty result from a database or integration failure; do not silently treat both as the same outcome.
- Preserve the boundary between browser Basic authentication and the server-to-server admin API key unless an approved design changes it.
- After source changes, run a Python syntax check and a TypeScript type check. Run focused tests for every changed critical path once tests exist.
- Before completion, inspect `git diff` and `git status`, and report skipped or unavailable verification explicitly.

