---
name: evidence-based-codebase-audit
description: Use when reviewing a repository, validating an earlier codebase analysis, self-scoring audit quality, or recording findings that must distinguish evidence from inference and deployed-state uncertainty.
---

# Evidence-Based Codebase Audit

## Overview

Produce a reproducible repository audit whose claims can be traced to current files and commands. Never promote checkout evidence into a claim about deployed state.

## Workflow

1. Read repository instructions and existing architecture/security/audit documents.
2. Record initial `git status`; do not overwrite user changes.
3. Define scope and exclusions before searching. Exclude dependencies and generated output when claiming project-owned tests or CI.
4. Recompute facts with commands; do not copy stale counts or prior conclusions.
5. Trace critical paths end to end, including authentication, tenant scope, persistence, retries/idempotency, scheduled work, and error handling.
6. Classify every material statement:
   - **Fact:** directly supported by checkout evidence.
   - **Inference:** reasoned consequence of facts.
   - **Proposal:** recommended future action.
   - **Unverified:** requires runtime, external system, or additional access.
7. Attach `path:line` evidence to security and correctness claims. Use multiple references when a boundary spans components.
8. Search for counter-evidence before finalizing words such as “none,” “all,” “disabled,” or “unimplemented.” Prefer “not found under these conventions” and “partial” when accurate.
9. Score the original analysis against the requested rubric before correction, then score the corrected audit separately.
10. Persist only durable working rules in `AGENTS.md`; put dated findings, commands, counts, and risks in an audit document.
11. Break recommendations into the smallest independently testable or decision-complete units.
12. Re-run permitted verification, inspect `git diff --check`, `git diff`, and `git status`, and confirm only authorized files changed.

## Evidence contract

| Claim type | Minimum support |
|---|---|
| File size or absence | Reproducible command plus scope/exclusions |
| Security boundary | Every component in the request path plus relevant configuration |
| Tenant isolation | Application queries, database policies, and explicit live-state caveat |
| Feature implemented | Entry point through side effect; configuration/UI alone is insufficient |
| Verification passed | Fresh command, exit code, and relevant output |

## Common mistakes

- Treating documentation as proof of implementation rather than corroboration.
- Treating no checked-in policy as proof of live database state.
- Calling partial persistence or idempotency wholly absent.
- Calling a script usable without checking its dependency/configuration.
- Recommending a large refactor before characterization tests.
- Writing volatile counts or dated defects into permanent agent instructions.

## Output order

Report: original score, corrections, corrected summary, corrected score, files changed, durable rules, top next tasks, and final Git status.
