# Legacy Routes Tenant Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the four documented compatibility routes while preventing them from reading or rendering another company's applicant or inquiry data.

**Architecture:** Keep the existing FastAPI route surface and HTML construction. Add `company_id = COMPANY_ID` directly to each legacy Supabase select, use the existing “not found” HTML contract for another company's applicant ID, and add an offline mixed-tenant test file that asserts query predicates and rendered content. Do not add legacy update/detail APIs, redirects, frontend calls, or deployment configuration.

**Tech Stack:** Python 3.12 unittest, FastAPI, existing Supabase query API, server-rendered HTML strings

## Global Constraints

- Keep the server-fixed `COMPANY_ID`; do not add Supabase Auth or RLS.
- Do not connect to Supabase, execute migrations, change environment variables, deploy, commit, push, or modify Webhook idempotency.
- Do not delete a compatibility route while README documents it and deployed traffic/external bookmarks remain unverified.
- Put company predicates on Supabase queries themselves; Python-only post-filtering is insufficient.
- Do not create legacy mutation routes, inquiry-detail routes, frontend pages, or proxy paths.
- Preserve `require_admin` on every compatibility route.

---

### Task 1: Route and caller inventory

**Files:**
- Inspect: `backend/main.py:1584-1908`
- Inspect: `README.md:73-80`
- Inspect: `frontend/lib/api.ts:32-52`
- Inspect: `frontend/app/api/admin/[...path]/route.ts:8-45`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`

**Interfaces:**
- Consumes: registered FastAPI routes, repository URL references, Next.js API client/proxy configuration
- Produces: evidence-backed keep/remove/scope decision for every legacy route

- [x] **Step 1: Enumerate registered compatibility routes**

  Confirm the registered methods, paths, endpoints, response types, and `require_admin` dependencies:

  ```text
  GET /applicants
  GET /applicants-view
  GET /applicant/{applicant_id}
  GET /inquiries-view
  ```

- [x] **Step 2: Search checked-in callers and alternatives**

  Search README, docs, frontend, Backend tests, HTML links, forms, and scripts. Confirm the Next.js screen uses `/api/admin/*` to reach `/api/applicants*` and `/api/inquiries*`, while only the compatibility HTML links call other compatibility routes.

- [x] **Step 3: Record deployment uncertainty**

  Confirm there is no checked-in Render/Docker/Procfile deployment configuration. Classify live route reachability, request logs, bookmarks, and external callers as unverified.

- [x] **Step 4: Select the minimal approach**

  Keep and scope all four routes because README explicitly retains them for compatibility and external/runtime usage cannot be disproved. Record that no legacy applicant update, inquiry detail, or inquiry update route exists.

### Task 2: Legacy-route boundary tests

**Files:**
- Create: `backend/tests/test_legacy_routes_tenant_scope.py`

**Interfaces:**
- Consumes: `get_applicants()`, `applicants_view()`, `applicant_detail(applicant_id)`, `inquiries_view()`, and `main.app.routes`
- Produces: an offline fake supporting `select`, `eq`, and `order`, with executed-query evidence

- [x] **Step 1: Build mixed-tenant fixtures**

  Include local and other-company applicants/inquiries, duplicate applicant IDs across companies, and duplicate LINE user IDs. Preserve deep copies so every read test can assert no row was mutated.

- [x] **Step 2: Add failing JSON and HTML list tests**

  Assert:

  ```python
  self.assertEqual(["own-applicant", "shared-id"], [row["id"] for row in main.get_applicants()])
  self.assertIn("Own Applicant", main.applicants_view())
  self.assertNotIn("Other Applicant", main.applicants_view())
  self.assertIn(("company_id", "tenant-a"), applicant_select["eq"])
  self.assertIn(("company_id", "tenant-a"), inquiry_select["eq"])
  ```

- [x] **Step 3: Add failing applicant-detail tests**

  Assert a duplicate ID resolves to the current company's row, an ID present only in another company returns the existing “応募者が見つかりません” HTML without revealing content, and the select contains ID plus company predicates.

- [x] **Step 4: Add failing inquiry HTML test**

  Assert local inquiry content is rendered, another company's inquiry content is absent, the query contains the company predicate, and all fake rows remain unchanged.

- [x] **Step 5: Add route-surface characterization**

  Assert all four routes remain GET-only with `require_admin`, and no legacy applicant mutation, inquiry detail, or inquiry mutation endpoint is registered. This characterization may pass before production changes.

- [x] **Step 6: Verify RED**

  Run:

  ```powershell
  Push-Location backend
  python -m unittest tests.test_legacy_routes_tenant_scope -v
  Pop-Location
  ```

  Expected: list/detail/HTML assertions fail because the existing selects lack company predicates. Route-surface characterization may pass.

### Task 3: Minimal production query changes

**Files:**
- Modify: `backend/main.py:1584-1908`
- Test: `backend/tests/test_legacy_routes_tenant_scope.py`

**Interfaces:**
- Produces: tenant-scoped compatibility reads without changing routes, HTML structure, status codes, or authentication

- [x] **Step 1: Scope legacy applicant JSON**

  Change the query to:

  ```python
  supabase.table("applicants").select("*").eq("company_id", COMPANY_ID).execute()
  ```

- [x] **Step 2: Scope compatibility dashboard HTML**

  Add the company predicate independently to both applicant and inquiry selects before calculating counts or rendering rows.

- [x] **Step 3: Scope applicant detail HTML**

  Add `company_id = COMPANY_ID` after the applicant ID predicate. Preserve the existing not-found HTML for an absent or another-company ID.

- [x] **Step 4: Scope inquiry list HTML**

  Add the company predicate before ordering by `created_at`.

- [x] **Step 5: Verify focused and full GREEN**

  Run the focused test file, then `python -m unittest discover -s tests -v` from `backend/`.

### Task 4: Documentation and final verification

**Files:**
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `docs/superpowers/plans/2026-07-23-legacy-routes-tenant-scope.md`

**Interfaces:**
- Produces: current route inventory, caller evidence, keep/remove rationale, line-numbered query evidence, and residual-risk list

- [x] **Step 1: Update the operation inventory**

  Mark all four compatibility route queries scoped. Retain the fixed-company/RLS caveat and distinguish repository evidence from live Render state.

- [x] **Step 2: Add a route decision table to the audit**

  For each route record method, behavior, tables, previous/current scope, callers, necessity judgment, recommendation, deletion impact, and unverified runtime facts. Explicitly record absent legacy mutation and inquiry-detail routes.

- [x] **Step 3: Reconcile paths and line numbers**

  Re-run route and Supabase searches after edits. Update every affected `backend/main.py` reference and the Backend test count.

- [x] **Step 4: Run final verification**

  Run the focused tests, Backend full suite, Python AST parsing, `git diff --check`, inspect `git diff`, and inspect `git status -sb`. Run TypeScript only if a frontend file changed.
