# Dashboard and Inquiry Tenant Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent dashboard and inquiry operations from reading, counting, creating, or updating another company's data.

**Architecture:** Extend the offline unittest fake to model applicants, inquiries, and application sessions. Add explicit `company_id` predicates or values only at the affected FastAPI/Supabase call sites, plus the minimal dashboard response/type/UI needed for recent inquiries.

**Tech Stack:** Python 3.12 unittest, FastAPI, existing Supabase query API, Next.js/TypeScript

## Global Constraints

- Do not connect to Supabase, modify migrations, add RLS/Auth, change environment variables, deploy, commit, or push.
- Confirm new tests fail for missing tenant boundaries before production changes.
- Keep prior applicant API changes and all existing 12 tests intact.

---

### Task 1: Dashboard tenant tests

**Files:**
- Create: `backend/tests/test_dashboard_inquiry_tenant_scope.py`

**Interfaces:**
- Consumes: `api_dashboard()`
- Produces: assertions for tenant-scoped counts, sessions, dropout/interviews, and recent applicants/inquiries

- [ ] Add mixed-tenant fake rows and dashboard assertions.
- [ ] Run only the new test file and confirm failures are caused by unscoped dashboard queries or missing recent inquiries.

### Task 2: Inquiry tenant tests

**Files:**
- Modify: `backend/tests/test_dashboard_inquiry_tenant_scope.py`

**Interfaces:**
- Consumes: inquiry list/detail/update APIs and inquiry creation in `handle_message`
- Produces: cross-company 404/no-mutation checks and explicit insert-company assertion

- [ ] Add list, own detail, other detail, other update/no-mutation, and insert tests.
- [ ] Confirm they fail for the current missing predicates/value/detail route.

### Task 3: Minimal implementation

**Files:**
- Modify: `backend/main.py`
- Modify: `frontend/types/index.ts`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Produces: scoped dashboard/inquiry queries, explicit inquiry `company_id`, inquiry detail route, scoped recent inquiries

- [ ] Add only the predicates, insert value, detail endpoint, and recent-inquiry response/UI required by failing tests.
- [ ] Run the new tests, then all backend tests.

### Task 4: Verification and documentation

**Files:**
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Modify: `docs/CODEBASE_AUDIT.md`

**Interfaces:**
- Produces: current scope inventory and fresh verification evidence

- [ ] Update affected inventory entries without claiming RLS coverage.
- [ ] Run Python syntax checks, all backend tests, TypeScript type checking, `git diff --check`, `git diff`, and `git status --short`.
