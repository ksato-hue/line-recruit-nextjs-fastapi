# Codebase Audit

## 1. Audit metadata

- Audit date: 2026-07-21 (Asia/Tokyo)
- Scope: repository-tracked application code, dependency manifests, Supabase migrations, documentation, and repository-level automation/configuration
- Excluded or unverified: deployed Supabase schema and policies, Supabase dashboard settings, deployed environment variables, Render configuration, LINE console settings, runtime logs, production data, and network dependency vulnerability status
- Change constraint: no backend/frontend source, dependency, migration, environment, deployment, or Git-history changes

This document separates **Fact**, **Inference**, **Proposal**, and **Unverified**. A repository search proves what is present in this checkout; it does not prove deployed runtime state.

## 2. Verification commands

Representative commands executed from the repository root:

```powershell
git status --short
rg --files --hidden -g '!.git/**' -g '!frontend/node_modules/**' -g '!frontend/.next/**'
python -c "from pathlib import Path; print(len(Path('backend/main.py').read_text(encoding='utf-8').splitlines()))"
rg -n 'supabase\.(table|rpc)|\.eq\("company_id"|COMPANY_ID' backend/main.py
rg -n -i 'row level security|enable rls|disable rls|create policy|grant |revoke ' supabase/migrations docs README.md
rg -n 'webhookEventId|last_event_id|requests\.post|async def webhook' backend/main.py
npm exec tsc -- --noEmit --incremental false
python -c "import ast,pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8'))"
git diff --check
git diff -- AGENTS.md docs/CODEBASE_AUDIT.md .agents/skills/evidence-based-codebase-audit
git status --short
```

Test and CI discovery excluded generated/dependency directories and matched conventional test locations/names and common CI providers. This establishes that no project-owned test or CI file is present under the searched conventions; unconventional or externally configured CI remains **Unverified**.

## 3. Current structure

### Confirmed facts

- `backend/main.py` has 2,617 logical lines. It contains FastAPI setup, LINE Webhook handling, conversation state, Supabase access, LINE HTTP calls, legacy HTML views, schemas, and admin APIs.
- `frontend/app/page.tsx` has 1,626 logical lines. It contains the dashboard and the applicant, inquiry, analytics, FAQ, question-tree, reminder, and general-settings views.
- Browser API calls go to the same-origin Next.js proxy (`frontend/lib/api.ts:5-7`). The proxy attaches `X-Admin-Key` server-side (`frontend/app/api/admin/[...path]/route.ts:36-45`).
- Four checked-in Supabase migrations add settings, company columns/indexes, application sessions, and applicant tags.

### Inference

- The two large files concentrate multiple responsibilities and will make isolated testing and review harder. File size alone does not prove defects or require an immediate split.

## 4. Confirmed findings

### P0: Tenant isolation is not comprehensively enforced by this checkout

**Fact:** `COMPANY_ID` is a process-wide environment value with a `default` fallback (`backend/main.py:39`). Company-scoped settings and application-session queries use it, for example `backend/main.py:226-229`, `253-256`, and `964-980`.

**Fact:** Several business-table paths omit a company predicate and sometimes omit `company_id` on insert:

- FAQ category and FAQ reads: `backend/main.py:458-466`, `477-484`, `493-500`
- Interview lookup/update: `backend/main.py:762-770`, `815-836`
- Line-log insert/read: `backend/main.py:1503-1512`, `backend/main.py:2541-2556`
- Legacy applicant/inquiry views: `backend/main.py:1514-1542`, `backend/main.py:1684-1696`, `backend/main.py:1777-1785`
- Interview-slot operations: `backend/main.py:2094-2169`
- Applicant status rename/use operations: `backend/main.py:2203-2215`
- FAQ writes: `backend/main.py:2244-2336`

**Fact:** Migrations add `company_id` to major legacy tables (`supabase/migrations/202607190001_mvp_security_foundation.sql:68-75`) and assign legacy rows/defaults to `default` (`supabase/migrations/202607190001_mvp_security_foundation.sql:77-96`), but the migrations contain no `ENABLE ROW LEVEL SECURITY` or `CREATE POLICY`. The project decision explicitly says RLS is not enabled (`docs/security-decisions.md:14-23`).

**Inference:** Repository code and migrations do not guarantee cross-company isolation. This is stronger than saying every query is wrong: some settings/session paths are scoped correctly.

**Unverified:** The live Supabase project may have out-of-band RLS or policies. That cannot be inferred from this checkout and requires database inspection.

### P0: No project-owned automated tests or checked-in CI were found at initial audit

**Initial fact:** Conventional test files/directories were not found outside dependency/generated directories. No `.github/workflows`, GitLab CI, CircleCI, Azure Pipelines, Bitbucket Pipelines, or Jenkins configuration was found.

**Follow-up:** The current worktree contains 19 offline `unittest` cases under `backend/tests` for LINE signatures, the admin API key, applicant tenant scope, dashboard tenant scope, and inquiry tenant scope. Checked-in CI remains absent under the searched conventions.

**Fact:** Python AST parsing and TypeScript type checking passed during this audit. These checks do not exercise runtime behavior, Supabase calls, LINE calls, or migrations.

**Unverified:** CI configured outside the repository and tests stored under unconventional names or external systems.

### P0: Webhook idempotency is partial, not absent

**Fact:** The raw request body is verified with HMAC-SHA256 and constant-time comparison before JSON parsing (`backend/main.py:78-87`, `352-360`). Missing configuration, missing signature, and invalid signature fail closed.

**Fact:** `webhookEventId` is passed to message handling (`backend/main.py:362-373`). Application sessions store `last_event_id`, and duplicate lookup is scoped by company, user, and event (`backend/main.py:960-970`, `1018-1038`). Application completion uses a database RPC and a unique application-session link (`backend/main.py:1234-1250`; `supabase/migrations/202607200001_application_sessions.sql:100-178`).

**Fact:** The deduplication lookup only checks `application_sessions.last_event_id` (`backend/main.py:1168-1170`). Inquiry creation, interview changes, inbound/outbound log writes, FAQ interactions, and LINE reply execution do not use a global unique event record (`backend/main.py:1180-1204`, `1301-1318`, `1354-1445`).

**Inference:** Application-flow replay has limited protection, including idempotent completion, but the entire webhook is not comprehensively idempotent. Concurrent events can also overwrite a single `last_event_id`; this concurrency behavior requires dedicated testing.

**Unverified:** Actual LINE retry patterns and duplicate effects in deployed runtime.

### P1: Synchronous I/O runs on the async webhook path

**Fact:** `webhook` is async (`backend/main.py:352-354`) but directly calls synchronous message handling and log helpers (`backend/main.py:370-380`). Those paths execute synchronous Supabase client calls and `requests.post`, including LINE reply calls with a 10-second timeout (`backend/main.py:1370-1391`, `backend/main.py:1394-1445`).

**Inference:** Slow database or LINE calls can occupy the event-loop worker. The practical impact depends on server worker configuration and traffic and is therefore **Unverified**.

**Correction:** The previous analysis said there was insufficient timeout design. LINE HTTP calls do have explicit 10-second timeouts. No retry/backoff mechanism was found.

### P1: Conversation state is mixed between memory and persistence

**Fact:** `user_states`, `applicants`, `interview_confirmations`, `faq_sessions`, and `application_tree_sessions` are module-level dictionaries (`backend/main.py:90-94`). Application sessions are also persisted and restored from `application_sessions` (`backend/main.py:960-1088`). Interview confirmation first consults memory and can reconstruct part of its state from `interview_slots` (`backend/main.py:778-800`).

**Inference:** It is inaccurate to call all conversation state memory-only. Process restart and multiple workers can still lose or disagree on transient state, while the application flow has partial persistence.

### P1: Authentication uses two distinct boundaries

**Fact:** Next.js middleware requires environment-backed Basic credentials and matches all paths except static/image/favicon paths (`frontend/middleware.ts:22-52`). Therefore it covers both the admin HTML and same-origin `/api/admin/*` routes.

**Fact:** The proxy accepts only configured path prefixes and GET/POST/PATCH, then adds `X-Admin-Key` (`frontend/app/api/admin/[...path]/route.ts:5-45`). FastAPI management endpoints use `Depends(require_admin)`, whose shared-key check fails closed (`backend/main.py:70-75`; for example `backend/main.py:1946`, `backend/main.py:2020`).

**Inference:** Basic authentication is the browser/user-facing gate; `ADMIN_API_KEY` is server-to-server authentication, not user identity or role authorization. Direct backend exposure is still protected by the shared key but has no per-user authorization.

**Unverified:** TLS termination, credential rotation, brute-force protection, and deployed network reachability.

### P1: Reminder automation is not connected

**Fact:** Reminder values are loaded, normalized, validated, and saved (`backend/main.py:168-188`, `backend/main.py:248-284`, `backend/main.py:2388-2436`). The frontend provides editing UI and explicitly warns that automatic delivery is not connected (`frontend/app/page.tsx:1320-1405`, especially `frontend/app/page.tsx:1384`). Migration columns record three legacy sent timestamps (`supabase/migrations/202607200001_application_sessions.sql:19-22`, `supabase/migrations/202607200001_application_sessions.sql:42-45`).

**Fact:** No scheduler, queue worker, cron endpoint, or reminder-dispatch function was found in the repository. README also calls the periodic job unconnected (`README.md:105`).

**Inference:** Configuration persistence exists; automatic execution does not exist in this checkout.

### P2: Dependency and quality-tool configuration is minimal

**Fact:** All five Python requirements are unpinned (`backend/requirements.txt:1-5`).

**Fact:** `frontend/package.json:6-11` defines `dev`, `build`, `start`, and `lint`. It has no `test` or explicit `typecheck` script. TypeScript is a dependency and `npm exec tsc -- --noEmit --incremental false` succeeds.

**Fact:** No ESLint configuration or direct ESLint dependency was found. A `next lint` script exists, but lint success was not verified because running it without configuration may be interactive or generate configuration. Therefore “ESLint is available and working” is **Unverified**.

**Fact:** No pytest configuration or pytest dependency was found. A Next.js build command exists but a fresh build was not executed during this documentation-only audit because it writes generated `.next` output. Build success is **Unverified**.

## 5. Corrections to the prior analysis

- Replace “Webhook idempotency is unimplemented” with “application-session replay and completion have partial idempotency; webhook-wide idempotency is absent.”
- Replace “all conversation state is in memory” with “five transient dictionaries remain, while application sessions and part of interview confirmation are recoverable from the database.”
- Qualify “no CI” and “no tests” as no project-owned files found under documented search conventions; external/unconventional systems remain unverified.
- Qualify RLS conclusions as checked-in migration state, not live Supabase state.
- State that LINE HTTP calls have 10-second timeouts; retries/backoff were not found.
- Avoid treating large file size as a defect by itself; it is a maintainability signal supported by responsibility concentration.

## 6. Risk order and proposed implementation sequence

The following is a **Proposal**, not current implementation status.

1. Define the supported deployment boundary: explicitly record single-company restricted MVP versus shared multi-tenant production.
2. Add a minimal test harness and characterization tests before splitting files.
3. Protect management and tenant boundaries with negative tests, then add company predicates to one business-table slice at a time.
4. Add webhook replay tests and a durable event-receipt design before changing webhook processing.
5. Move remaining transient state to durable storage only after state-transition tests exist.
6. Split backend/frontend by responsibility in small, test-protected changes.

### Small next-work units

1. Add a backend test dependency/configuration and one isolated test proving valid/invalid LINE signatures; do not connect Supabase.
2. Add tests for `require_admin`: missing server key → 503, missing/wrong request key → 401, correct key → success.
3. Inventory every business-table operation in a table with columns: operation, table, read/write, current company predicate/value, expected tenant rule.
4. Write failing cross-company tests for applicant list/detail/update before modifying their queries.
5. Write webhook replay tests for application, inquiry, interview, and logging paths; document which duplicates must produce no side effect.
6. Decide and document the deploy model and live RLS inspection procedure before writing policies.

## 7. Self-assessment

### Before re-verification: 73/100

| Criterion | Score | Good | Missing | Improvement |
|---|---:|---|---|---|
| Technical accuracy | 20/25 | Correctly identified tenant, test, state, and maintainability risks | Under-described partial idempotency/persistence and omitted existing HTTP timeouts | Trace complete execution paths and distinguish partial from absent |
| Evidence clarity | 13/20 | Named major files and some line references | Most claims lacked exact line-level evidence and search definitions | Attach code/migration references to every high-risk claim |
| Coverage | 10/15 | Covered backend, frontend, migrations, docs, and dependencies | Did not rigorously check CI conventions, every tenant query, reminder dispatch, or deployed-state limits | Use explicit repository-wide searches and an unverified list |
| Priority quality | 13/15 | Put security boundaries and tests first | Mixed deployment-decision work with implementation and did not size early tasks | Separate decision gates from testable slices |
| Uncertainty | 4/10 | Noted production assumptions in places | Several repository observations were phrased as runtime facts | Label Fact, Inference, Proposal, and Unverified |
| Executability | 8/10 | Recommended tests before refactoring and a sensible broad order | Steps remained too broad for immediate execution | Break work into independently reviewable test-first units |
| Clarity | 5/5 | Concise and prioritized | Some compression hid nuance | Preserve concise structure while adding calibrated qualifiers |

### After re-verification: 93/100

| Criterion | Score | Good | Remaining limitation | Further improvement |
|---|---:|---|---|---|
| Technical accuracy | 24/25 | Corrects idempotency, persistence, timeout, and auth-boundary details | No deployed runtime/database inspection | Verify live schema and exercise integrations in a controlled environment |
| Evidence clarity | 19/20 | High-risk findings have file and line references | Not every individual Supabase call is tabulated | Maintain a generated query inventory |
| Coverage | 14/15 | Covers requested code, config, docs, tooling, migrations, and Git state | Dependency vulnerability/network audit excluded | Add a separately authorized dependency/security audit |
| Priority quality | 14/15 | Risks are tied to deployment boundary and tests | Business priority still needs owner confirmation | Confirm MVP deployment model with stakeholders |
| Uncertainty | 9/10 | Explicit fact/inference/proposal/unverified labels | Runtime impact of sync I/O is not benchmarked | Add load and integration evidence later |
| Executability | 9/10 | Next work is split into small reviewable units | Exact test framework choice remains open | Decide framework in the first implementation task |
| Clarity | 4/5 | Durable audit structure and corrections are explicit | Detail level is necessarily high | Keep an executive summary on future updates |

## 8. Next-update checklist

- Recompute both large-file line counts rather than copying them.
- Search project-owned tests and CI with the same exclusions and record any new conventions.
- Re-inventory all Supabase table/RPC calls and compare company scoping.
- Inspect new migrations for RLS enablement, policies, grants, and security-definer functions.
- Trace webhook event identity through every side effect.
- Check whether reminder dispatch, scheduler, or worker code has appeared.
- Re-run Python AST parsing, TypeScript type checking, available focused tests, and a non-interactive lint/build command if configured.
- Reconfirm auth matchers, proxy allowlists, and backend dependencies.
- Separate repository evidence from live-environment evidence.
- Review `git diff` and `git status` before publishing the update.

## 9. Implementation follow-up

On 2026-07-21, the first approved audit actions were implemented:

- Added an offline unittest harness that replaces import-time Supabase client creation.
- Added four LINE signature and four admin-key boundary tests.
- Added four cross-company applicant tests covering list, detail, update, and the shared lookup helper.
- Added `company_id = COMPANY_ID` predicates to those four applicant query paths.
- Added `docs/SUPABASE_COMPANY_SCOPE.md` as the current operation-level scope inventory.

The broader tenant-isolation finding remains open because interview-slot, message-log, FAQ, status rename/use, and legacy HTML operations still include unscoped paths. Dashboard and the current inquiry API/create flow are now explicitly company-scoped; legacy inquiry HTML reads remain unscoped.

### 2026-07-22 dashboard and inquiry follow-up

- Added seven offline tests for tenant-scoped dashboard counts/recent rows and inquiry list/detail/update/create behavior.
- Added company predicates to dashboard applicant/inquiry aggregates and recent queries.
- Added company predicates to inquiry list, detail, and update; another company's ID returns 404 and is not modified.
- Inquiry creation now writes `company_id` explicitly instead of relying on the database default.
- The dashboard response and UI now include company-scoped recent inquiries.
