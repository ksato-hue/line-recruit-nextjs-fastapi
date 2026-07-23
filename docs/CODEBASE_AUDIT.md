# Codebase Audit

## 1. Audit metadata

- Audit date: 2026-07-21; implementation follow-up updated 2026-07-23 (Asia/Tokyo)
- Scope: repository-tracked application code, dependency manifests, Supabase migrations, documentation, and repository-level automation/configuration
- Excluded or unverified: deployed Supabase schema and policies, Supabase dashboard settings, deployed environment variables, Render configuration, LINE console settings, runtime logs, production data, and network dependency vulnerability status
- Current follow-up constraint: only tenant-scope production code, offline tests, and audit/plan documents may change; no dependency, migration, environment, deployment, commit, or push action

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
Push-Location backend; python -m unittest discover -s tests -v; Pop-Location
python -c "import ast,pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8'))"
git diff --check
git diff -- AGENTS.md docs/CODEBASE_AUDIT.md .agents/skills/evidence-based-codebase-audit
git status --short
```

The initial test and CI discovery excluded generated/dependency directories and matched conventional test locations/names and common CI providers. No project-owned test or CI file was present then. Project-owned tests have since been added under `backend/tests`; checked-in CI is still not found under those conventions, while externally configured CI remains **Unverified**.

## 3. Current structure

### Confirmed facts

- `backend/main.py` has 2,755 logical lines after the 2026-07-23 FAQ/status/session tenant-scope follow-up. It contains FastAPI setup, LINE Webhook handling, conversation state, Supabase access, LINE HTTP calls, legacy HTML views, schemas, and admin APIs.
- `frontend/app/page.tsx` has 1,626 logical lines. It contains the dashboard and the applicant, inquiry, analytics, FAQ, question-tree, reminder, and general-settings views.
- Browser API calls go to the same-origin Next.js proxy (`frontend/lib/api.ts:5-7`). The proxy attaches `X-Admin-Key` server-side (`frontend/app/api/admin/[...path]/route.ts:36-45`).
- Four checked-in Supabase migrations add settings, company columns/indexes, application sessions, and applicant tags.

### Inference

- The two large files concentrate multiple responsibilities and will make isolated testing and review harder. File size alone does not prove defects or require an immediate split.

## 4. Confirmed findings

### P0: Tenant isolation is not comprehensively enforced by this checkout

**Fact:** `COMPANY_ID` is a process-wide environment value with a `default` fallback (`backend/main.py:39`). Company-scoped settings and application-session queries use it, for example `backend/main.py:226-229`, `253-256`, and `1022-1047`.

**Fact:** The current management API paths for applicants, dashboard/inquiries, interviews/messages, FAQ, status settings, and application sessions now have application-level company predicates or explicit company insert values. The remaining known unscoped business-table paths are legacy JSON/HTML views:

- Legacy applicant/inquiry aggregate views: `backend/main.py:1584-1610`
- Legacy applicant detail HTML: `backend/main.py:1759-1765`
- Legacy inquiry HTML: `backend/main.py:1851-1855`

**Fact:** The current interview-slot paths use company predicates for Webhook lookup, confirmation, cancellation, reset, management list, private lookup, applicant update, and PATCH (`backend/main.py:802-985`, `1986-2023`, `2177-2262`). Slot inserts contain `COMPANY_ID` (`backend/main.py:2200-2209`).

**Fact:** LINE message-log inserts contain `COMPANY_ID`, and history queries combine `company_id` with the optional `line_user_id` filter (`backend/main.py:1572-1580`, `2678-2694`).

**Fact:** FAQ category/FAQ reads, ownership lookups, inserts, PATCH, and DELETE are now company-scoped (`backend/main.py:458-556`, `2345-2479`). Applicant status-name usage checks and bulk updates are scoped (`backend/main.py:2296-2321`), and application-session cancellation scopes both its lookup and update (`backend/main.py:1037-1048`, `1133-1152`). These paths are covered by offline two-company tests (`backend/tests/test_faq_status_session_tenant_scope.py:242-478`).

**Fact:** Migrations add `company_id` to major legacy tables (`supabase/migrations/202607190001_mvp_security_foundation.sql:68-75`) and assign legacy rows/defaults to `default` (`supabase/migrations/202607190001_mvp_security_foundation.sql:77-96`), but the migrations contain no `ENABLE ROW LEVEL SECURITY` or `CREATE POLICY`. The project decision explicitly says RLS is not enabled (`docs/security-decisions.md:14-23`).

**Inference:** Repository code and migrations still do not guarantee production multi-tenant isolation because the tenant is process-wide, legacy paths remain, and RLS is absent. This is not a claim that the checked management paths are unscoped; those now have focused application-level boundary tests.

**Unverified:** The live Supabase project may have out-of-band RLS or policies. That cannot be inferred from this checkout and requires database inspection.

### P0: No project-owned automated tests or checked-in CI were found at initial audit

**Initial fact:** Conventional test files/directories were not found outside dependency/generated directories. No `.github/workflows`, GitLab CI, CircleCI, Azure Pipelines, Bitbucket Pipelines, or Jenkins configuration was found.

**Follow-up:** The current worktree contains 56 offline `unittest` cases under `backend/tests`: the previous 36 boundary tests plus 20 FAQ, applicant-status, and application-session tenant tests. Checked-in CI remains absent under the searched conventions.

**Fact:** Python AST parsing and TypeScript type checking passed during this audit. These checks do not exercise runtime behavior, Supabase calls, LINE calls, or migrations.

**Unverified:** CI configured outside the repository and tests stored under unconventional names or external systems.

### P0: Webhook idempotency is partial, not absent

**Fact:** The raw request body is verified with HMAC-SHA256 and constant-time comparison before JSON parsing (`backend/main.py:78-87`, `352-360`). Missing configuration, missing signature, and invalid signature fail closed.

**Fact:** `webhookEventId` is passed to message handling (`backend/main.py:362-373`). Application sessions store `last_event_id`, and duplicate lookup is scoped by company, user, and event (`backend/main.py:1022-1034`, `1080-1103`). Application completion uses a database RPC and a unique application-session link (`backend/main.py:1303-1318`; `supabase/migrations/202607200001_application_sessions.sql:100-178`).

**Fact:** The deduplication lookup only checks `application_sessions.last_event_id` (`backend/main.py:1237-1239`). Inquiry creation, interview changes, inbound/outbound log writes, FAQ interactions, and LINE reply execution do not use a global unique event record (`backend/main.py:1249-1273`, `1370-1387`, `1423-1514`, `1572-1580`). Company scoping does not make these event side effects idempotent.

**Inference:** Application-flow replay has limited protection, including idempotent completion, but the entire webhook is not comprehensively idempotent. Concurrent events can also overwrite a single `last_event_id`; this concurrency behavior requires dedicated testing.

**Unverified:** Actual LINE retry patterns and duplicate effects in deployed runtime.

### P1: Synchronous I/O runs on the async webhook path

**Fact:** `webhook` is async (`backend/main.py:352-354`) but directly calls synchronous message handling and log helpers (`backend/main.py:370-380`). Those paths execute synchronous Supabase client calls and `requests.post`, including LINE reply/push calls with a 10-second timeout (`backend/main.py:1440-1460`, `1464-1514`, `1534-1555`).

**Inference:** Slow database or LINE calls can occupy the event-loop worker. The practical impact depends on server worker configuration and traffic and is therefore **Unverified**.

**Correction:** The previous analysis said there was insufficient timeout design. LINE HTTP calls do have explicit 10-second timeouts. No retry/backoff mechanism was found.

### P1: Conversation state is mixed between memory and persistence

**Fact:** `user_states`, `applicants`, `interview_confirmations`, `faq_sessions`, and `application_tree_sessions` are module-level dictionaries (`backend/main.py:90-94`). Application sessions are also persisted and restored from `application_sessions` (`backend/main.py:1022-1154`). Interview confirmation first consults company-tagged memory and can reconstruct part of its state from a company-scoped `interview_slots` query (`backend/main.py:819-843`).

**Inference:** It is inaccurate to call all conversation state memory-only. Process restart and multiple workers can still lose or disagree on transient state, while the application flow has partial persistence.

### P1: Authentication uses two distinct boundaries

**Fact:** Next.js middleware requires environment-backed Basic credentials and matches all paths except static/image/favicon paths (`frontend/middleware.ts:22-52`). Therefore it covers both the admin HTML and same-origin `/api/admin/*` routes.

**Fact:** The proxy accepts only configured path prefixes and GET/POST/PATCH, then adds `X-Admin-Key` (`frontend/app/api/admin/[...path]/route.ts:5-45`). FastAPI management endpoints use `Depends(require_admin)`, whose shared-key check fails closed (`backend/main.py:70-75`; for example `backend/main.py:2031`, `backend/main.py:2125`). The newly added Backend FAQ DELETE routes are therefore not exposed through the current frontend proxy.

**Inference:** Basic authentication is the browser/user-facing gate; `ADMIN_API_KEY` is server-to-server authentication, not user identity or role authorization. Direct backend exposure is still protected by the shared key but has no per-user authorization.

**Unverified:** TLS termination, credential rotation, brute-force protection, and deployed network reachability.

### P1: Reminder automation is not connected

**Fact:** Reminder values are loaded, normalized, validated, and saved (`backend/main.py:168-188`, `248-284`, `2545-2601`). The frontend provides editing UI and explicitly warns that automatic delivery is not connected (`frontend/app/page.tsx:1320-1405`, especially `frontend/app/page.tsx:1384`). Migration columns record three legacy sent timestamps (`supabase/migrations/202607200001_application_sessions.sql:19-22`, `supabase/migrations/202607200001_application_sessions.sql:42-45`).

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

1. Decide whether to scope and test legacy JSON/HTML routes or remove them through a separately approved change.
2. Write webhook replay tests for application, inquiry, interview, FAQ, reply, and logging paths; document which duplicates must produce no side effect.
3. Decide and document the deploy model and live RLS inspection procedure before writing policies.
4. If FAQ deletion becomes a management-screen requirement, separately approve and test the Next.js DELETE forwarding, API client functions, confirmation UI, and deletion semantics. If that requirement is withdrawn, remove the currently unreachable Backend DELETE routes rather than retaining unused surface indefinitely.

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

The broader tenant-isolation finding remains open because legacy JSON/HTML paths are unscoped, tenant identity is still process-wide, and checked-in RLS is absent. The tested management API paths are now explicitly company-scoped.

### 2026-07-22 dashboard and inquiry follow-up

- Added seven offline tests for tenant-scoped dashboard counts/recent rows and inquiry list/detail/update/create behavior.
- Added company predicates to dashboard applicant/inquiry aggregates and recent queries.
- Added company predicates to inquiry list, detail, and update; another company's ID returns 404 and is not modified.
- Inquiry creation now writes `company_id` explicitly instead of relying on the database default.
- The dashboard response and UI now include company-scoped recent inquiries.

### 2026-07-23 interview-slot and message-log follow-up

- Added 17 offline tests for interview list/internal lookup, other-company PATCH/update/confirm/cancel with no mutation, direct PATCH query scoping, explicit slot/log insert ownership, applicant ownership, Webhook selection/confirmation/reset, and message history isolation.
- Added `company_id = COMPANY_ID` to every current interview-slot select/update path, including Webhook confirmation and sibling cancellation; derived applicant IDs are validated through `_get_applicant_or_404`.
- Added `_get_interview_slot_or_404` for the existing PATCH path without adding a public detail endpoint. Both the preflight select and actual update are company-scoped.
- Interview-slot and line-message-log inserts now write `company_id` explicitly. Line history is scoped before the optional `line_user_id` predicate, so another tenant's user returns an empty array.
- The checked-in migration already adds `company_id` to both tables (`supabase/migrations/202607190001_mvp_security_foundation.sql:72-73`); no migration was created or executed.
- Supabase Auth and RLS remain unimplemented in this checkout, and the deployed database state remains **Unverified**.

### 2026-07-23 FAQ, status-name, and application-session follow-up

- Added 18 offline tests covering FAQ/category list isolation, exact-question collisions, Webhook FAQ settings, explicit insert ownership, category ownership, other-company PATCH/DELETE 404 behavior without mutation, applicant status-name bulk updates, and application-session cancellation.
- The pre-change RED run produced 11 assertion failures and five errors: cross-company reads/writes, missing ownership checks, missing company insert values, unscoped status/session updates, and absent delete route functions. The two pre-existing protections—company-scoped `faq_settings` Webhook answers and another-company-only session no-op—already passed.
- Added company predicates to legacy FAQ category/FAQ list and exact-question search helpers, plus scoped ownership helpers. FAQ/category inserts now write `company_id`; actual PATCH/DELETE queries include company predicates.
- FAQ creation and category-changing FAQ updates validate that the category belongs to the current company before writing. Another company's resource ID produces 404 and leaves the original row unchanged.
- Added the company predicate to both the applicant status-use lookup and the actual name-based bulk update. Added the same predicate to the actual application-session cancellation update while preserving safe no-op behavior.
- The active LINE Webhook FAQ implementation already used company-scoped `faq_settings`; the older `faq_categories`/`faqs` search helpers are not called by that flow. No keyword-search or batch reorder implementation was found.
- Checked-in migrations already add `company_id` to `faq_categories`, `faqs`, applicants/status settings, and application sessions; no migration was created or executed. Live migration state remains **Unverified**.

### 2026-07-23 FAQ DELETE reachability follow-up

- Added two normal-path regression tests: deleting an owned FAQ and deleting an owned FAQ category. Each asserts that the executed query contains both resource ID and `company_id`, and that unrelated local and other-company rows remain unchanged (`backend/tests/test_faq_status_session_tenant_scope.py:277-306`, `389-422`). Existing other-company 404/no-mutation tests remain in place (`backend/tests/test_faq_status_session_tenant_scope.py:269-275`, `381-387`).
- The current FAQ management screen loads and updates only `faq_settings`; it has no FAQ/category deletion control (`frontend/app/page.tsx:1134-1206`, `1224-1306`).
- The API client declares FAQ GET/POST/PATCH helpers but no DELETE helper (`frontend/lib/api.ts:80-109`). The Next.js proxy allows and exports only GET/POST/PATCH (`frontend/app/api/admin/[...path]/route.ts:22-68`). A repository search found no production caller of `api_delete_faq_category` or `api_delete_faq`; only their definitions and Backend tests exist.
- **Decision:** Keep the Backend DELETE routes in this change because deletion isolation was an explicit acceptance criterion, but do not expose an unused browser capability. Wiring the routes through the proxy/UI, or removing them if the product requirement is withdrawn, is a separately reviewed future change.
