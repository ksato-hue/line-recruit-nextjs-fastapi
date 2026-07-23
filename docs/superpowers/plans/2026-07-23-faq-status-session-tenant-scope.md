# FAQ, Status, and Session Tenant Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent FAQ category, FAQ, applicant-status rename, and application-session cancellation operations from reading or changing another company's data while preserving the fixed server-side `COMPANY_ID` model.

**Architecture:** Keep the current FastAPI and Supabase query structure. Add `company_id = COMPANY_ID` to each affected select/update/delete query, write `company_id` explicitly on inserts, and use small private lookup helpers to validate FAQ/category ownership. Preserve the current application-session cancellation contract: another company's session is indistinguishable from no active session and therefore produces a safe no-op.

**Tech Stack:** Python 3.12 unittest, FastAPI, Pydantic, existing Supabase query API

## Global Constraints

- Do not add Supabase Auth or RLS, execute migrations, connect to Supabase, change environment variables, deploy, commit, or push.
- Do not change legacy HTML routes or perform a broad query-layer refactor.
- Put the tenant predicate on the Supabase query itself; Python-only filtering is insufficient.
- Confirm boundary tests fail for the intended missing predicate, ownership check, route, or insert value before changing production code.
- The checked-in migrations declare `company_id` for `faq_categories`, `faqs`, `applicant_status_settings`, `applicants`, and `application_sessions`; deployed schema state remains unverified.
- Do not add dedicated FAQ detail GET or bulk reorder APIs. The explicit delete requirements are implemented as the smallest resource DELETE routes; frontend UI work is out of scope.

---

### Task 1: Mixed-tenant test harness and FAQ boundary tests

**Files:**
- Create: `backend/tests/test_faq_status_session_tenant_scope.py`

**Interfaces:**
- Consumes: FAQ category/FAQ query helpers and API route functions
- Produces: an offline mixed-tenant Supabase fake supporting select, insert, update, delete, upsert, equality filters, ordering, and limits

- [x] **Step 1: Build a mixed-tenant fake**

  Model two companies with active categories, identical FAQ questions, separate answers, and mutation logs. No test may construct a live Supabase client.

- [x] **Step 2: Add category read/write RED tests**

  Cover scoped lists, category-specific retrieval, explicit insert ownership, another-company PATCH/DELETE returning 404, no mutation after failure, and query-level company predicates.

- [x] **Step 3: Add FAQ read/search/Webhook RED and characterization tests**

  Cover grouped lists, identical questions across tenants, old-table search, the already-scoped `faq_settings` Webhook answer path, explicit insert ownership, category ownership checks, another-company PATCH/DELETE, and query-level predicates.

- [x] **Step 4: Verify RED**

  Run `python -m unittest tests.test_faq_status_session_tenant_scope -v` from `backend/`. Expected failures must be caused by the missing tenant boundary, missing ownership validation, missing DELETE route, or absent insert value. The existing `faq_settings` Webhook characterization may already pass.

### Task 2: Status rename and application-session cancellation tests

**Files:**
- Modify: `backend/tests/test_faq_status_session_tenant_scope.py`

- [x] **Step 1: Add applicant-status tests**

  Rename an identical status used by applicants in both companies and assert only the current company's rows change. Assert the actual update query contains `company_id`. Also verify another company's usage does not block removal of an unused local status.

- [x] **Step 2: Add cancellation tests**

  Cover an identical LINE user in two companies, another-company-only sessions, no mutation after safe no-op, and a company predicate on the actual cancellation update.

- [x] **Step 3: Re-run focused RED**

  Confirm failures arise from the unscoped applicant update/use check and cancellation update, not from fake-query or import errors.

### Task 3: Minimal production changes

**Files:**
- Modify: `backend/main.py`

- [x] **Step 1: Scope FAQ reads and ownership helpers**

  Add company predicates to category and FAQ list/search helpers. Add private `_get_faq_category_or_404` and `_get_faq_or_404` lookups scoped by ID and company.

- [x] **Step 2: Scope FAQ writes**

  Add company to category/FAQ inserts. Validate FAQ category ownership during create and category-changing update. Scope actual PATCH/DELETE queries and return 404 when no scoped row is affected.

- [x] **Step 3: Scope status rename/use queries**

  Add company predicates to applicant use checks and the actual name-based bulk update.

- [x] **Step 4: Scope session cancellation update**

  Retain the already-scoped active-session lookup and add company to the actual update predicate while preserving safe no-op behavior when no local session exists.

- [x] **Step 5: Verify focused and full GREEN**

  Run the focused file, then all Backend tests. Fix production code rather than weakening boundary assertions.

### Task 4: Documentation and final verification

**Files:**
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `docs/superpowers/plans/2026-07-23-faq-status-session-tenant-scope.md`

- [x] **Step 1: Reconcile the Supabase operation inventory**

  Search every affected table call and record the exact select/insert/update/delete enforcement. Keep legacy HTML and other unrelated findings unchanged.

- [x] **Step 2: Update the audit follow-up**

  Record the new tests, production paths, pre-existing protections, fixed-company limitation, absent bulk reorder implementation, no-live-Supabase caveat, and remaining unscoped operations.

- [x] **Step 3: Verify paths and line numbers**

  Re-run searches after edits and update documentation references to the final file positions.

- [x] **Step 4: Run final verification**

  Run all Backend tests, Python AST parsing for production and tests, TypeScript type checking required by `AGENTS.md`, `git diff --check`, inspect `git diff`, and inspect `git status -sb`.
