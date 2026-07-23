# Interview and Message Tenant Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent interview-slot and LINE message-log operations from reading, creating, or updating another company's data while preserving the existing fixed `COMPANY_ID` deployment model.

**Architecture:** Keep the current FastAPI routes and Supabase client structure. Add `company_id = COMPANY_ID` directly to every affected select and update query, add `company_id` to inserted rows, and reuse `_get_applicant_or_404` whenever an interview operation accepts or derives an `applicant_id`. A private slot lookup helper protects the existing PATCH path without adding a new public detail endpoint.

**Tech Stack:** Python 3.12 unittest, FastAPI, Pydantic, existing Supabase query API

## Global Constraints

- Do not add Supabase Auth or RLS, execute migrations, connect to Supabase, change environment variables, deploy, commit, or push.
- Do not modify FAQ, FAQ categories, legacy HTML routes, or add a public interview-slot detail API.
- Use the server-fixed `COMPANY_ID` and put the predicate on each Supabase query itself; Python-only post-filtering is not sufficient.
- Confirm the new boundary tests fail for missing tenant predicates or insert values before production changes.
- Preserve the existing LINE history contract: list responses remain arrays and another company's user ID returns `[]`.
- Keep production changes local to the affected call sites and helpers; do not perform a broad query-layer refactor.

---

### Task 1: Interview-slot tenant boundary tests

**Files:**
- Create: `backend/tests/test_interview_message_tenant_scope.py`

**Interfaces:**
- Consumes: `_find_active_interview_slot`, `_get_pending_interview_confirmation`, `_get_interview_slot_or_404`, `_finish_interview_confirmation`, `_reset_interview_confirmation`, `handle_interview_slot_selection`, `api_get_interview_slots`, `api_create_interview_slots`, and `api_update_interview_slot`
- Produces: an offline mixed-tenant Supabase fake supporting `select`, `insert`, `update`, `eq`, `neq`, `order`, and `limit`

- [x] **Step 1: Build the mixed-tenant fake**

  Model two companies with overlapping `applicant_id` associations and the same `line_user_id`/slot time. Keep inserts and mutations in memory so tests can assert both returned data and untouched other-company rows.

- [x] **Step 2: Add failing read-boundary tests**

  Add tests proving:

  ```python
  api_get_interview_slots("own-applicant")
  _find_active_interview_slot("shared-line", "2026-08-01 10:00")
  _get_pending_interview_confirmation("shared-line")
  _get_interview_slot_or_404("other-slot")
  ```

  only expose `tenant-a` rows, and the private helper raises `HTTPException(404)` for another company's slot.

- [x] **Step 3: Add failing write-boundary tests**

  Exercise PATCH with ordinary update, `status="選択済み"`, and `status="キャンセル"`. Assert each other-company request raises 404 and leaves the original row unchanged.

- [x] **Step 4: Add failing create and Webhook tests**

  Assert slot creation writes `company_id="tenant-a"`, another company's applicant receives 404 before any insert/push, selection updates only the scoped row, confirmation updates/cancels only scoped slots and applicant, and reset only changes/returns scoped slots.

- [x] **Step 5: Verify RED**

  Run:

  ```powershell
  Push-Location backend
  python -m unittest tests.test_interview_message_tenant_scope -v
  Pop-Location
  ```

  Expected: failures caused by missing `company_id` filters/insert values and the missing private slot helper, while the already-scoped applicant rejection test may pass as characterization.

### Task 2: LINE message-log tenant boundary tests

**Files:**
- Modify: `backend/tests/test_interview_message_tenant_scope.py`

**Interfaces:**
- Consumes: `api_line_messages` and `try_insert_line_message_log`
- Produces: list/history and insert boundary coverage without network or live Supabase access

- [x] **Step 1: Add failing history tests**

  Assert the unfiltered list excludes other-company rows, a shared `line_user_id` returns only `tenant-a` rows, and an ID present only in `tenant-b` returns `[]`.

- [x] **Step 2: Add failing insert test**

  Call `try_insert_line_message_log` and assert the inserted row explicitly contains `company_id="tenant-a"`.

- [x] **Step 3: Re-run the focused file and record RED reasons**

  Use the Task 1 command and confirm failures are boundary failures, not import, fake-query, or assertion setup errors.

### Task 3: Minimal production query changes

**Files:**
- Modify: `backend/main.py:762-953`
- Modify: `backend/main.py:1525-1534`
- Modify: `backend/main.py:1939-1976`
- Modify: `backend/main.py:2130-2215`
- Modify: `backend/main.py:2587-2603`

**Interfaces:**
- Produces: direct tenant predicates on all affected Supabase reads/updates and explicit tenant values on inserts

- [x] **Step 1: Scope Webhook interview reads**

  Add `.eq("company_id", COMPANY_ID)` to active-slot and pending-confirmation selects. Store/check `company_id` in the in-memory confirmation record so stale state is not trusted across tenant context.

- [x] **Step 2: Scope Webhook interview writes**

  Route every derived `applicant_id` through `_get_applicant_or_404`. Add company predicates to selection, confirmation, sibling cancellation, applicant update, reset update, and reset list queries. Stop the confirmation flow if the selected scoped update returns no row so later writes cannot run after a tenant mismatch.

- [x] **Step 3: Scope management interview APIs**

  Add `_get_interview_slot_or_404(slot_id)` with `id` and company predicates, use it before PATCH, keep the same predicates on the actual PATCH update, add company to applicant-slot list queries, inserted slot rows, and the applicant status update performed during creation.

- [x] **Step 4: Scope message-log writes and reads**

  Add `"company_id": COMPANY_ID` to `try_insert_line_message_log` and begin `api_line_messages` with `.eq("company_id", COMPANY_ID)` before applying the optional user filter.

- [x] **Step 5: Verify GREEN**

  Run the focused test file, then all backend tests from `backend/`. Fix production code rather than weakening boundary assertions.

### Task 4: Inventory, audit, and final verification

**Files:**
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Modify: `docs/CODEBASE_AUDIT.md`

**Interfaces:**
- Produces: line-numbered current evidence, remaining unscoped operations, and reproducible validation results

- [x] **Step 1: Update the Supabase operation inventory**

  Change every affected interview-slot and line-message-log entry from unscoped to scoped, include insert values and Webhook helpers, and leave FAQ/status/legacy HTML findings unchanged.

- [x] **Step 2: Update the audit follow-up**

  Record the date, new tests, exact production paths, fixed-company limitation, no-live-Supabase caveat, and remaining unscoped operations without claiming RLS coverage.

- [x] **Step 3: Reconcile inventory against code**

  Search every `interview_slots` and `line_message_logs` operation in `backend/main.py` and verify each affected read/update contains a company predicate and each insert payload contains a company value.

- [x] **Step 4: Run final verification**

  Run all backend tests, Python AST parsing for production and tests, `git diff --check`, inspect `git diff`, and inspect `git status -sb`. TypeScript checking is not required unless a frontend file changes.
