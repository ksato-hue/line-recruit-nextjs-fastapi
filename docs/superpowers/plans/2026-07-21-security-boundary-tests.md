# Security Boundary Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add offline characterization tests for LINE signatures and admin-key authentication, document Supabase tenant scope, and enforce tenant isolation on applicant APIs.

**Architecture:** Use Python standard-library `unittest` and a fake fluent Supabase client so tests never contact external services. Keep existing module structure and change only applicant query predicates required by failing tenant-isolation tests.

**Tech Stack:** Python 3.12, unittest, unittest.mock, FastAPI HTTPException, existing Supabase client API

## Global Constraints

- Do not connect to Supabase, mutate data, apply migrations, change environment configuration, deploy, commit, or push.
- Write and run characterization tests before production behavior changes.
- Keep production changes minimal and limited to tenant predicates proven by failing tests.

---

### Task 1: Offline test harness and security characterization

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/support.py`
- Create: `backend/tests/test_security_boundaries.py`

**Interfaces:**
- Consumes: `_verify_line_signature(raw_body, signature)` and `require_admin(x_admin_key)` from `backend/main.py`
- Produces: import isolation from Supabase and executable unittest cases

- [ ] Create a fake Supabase client and import helper that replaces `supabase.create_client` before importing `main`.
- [ ] Add tests for valid signature, missing signature, invalid signature, and missing secret.
- [ ] Add tests for configured matching key, missing key, mismatched key, and missing server key.
- [ ] Run `python -m unittest discover -s tests -v` from `backend`; expect all characterization tests to pass without network access.

### Task 2: Supabase company-scope inventory

**Files:**
- Create: `docs/SUPABASE_COMPANY_SCOPE.md`

**Interfaces:**
- Consumes: every `supabase.table` and `supabase.rpc` call in `backend/main.py`
- Produces: operation-level inventory of current scope and required follow-up

- [ ] List each call site by table, operation, line, current company enforcement, and risk.
- [ ] Separate correctly scoped settings/sessions from unscoped business-table operations.
- [ ] Mark live RLS state as unverified.

### Task 3: Applicant tenant-isolation tests and minimal fix

**Files:**
- Create: `backend/tests/test_applicant_tenant_scope.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `api_applicants`, `api_applicant_detail`, `api_update_applicant`, and `_get_applicant_or_404`
- Produces: applicant queries constrained by `COMPANY_ID`

- [ ] Add fake-query tests proving list, detail, update, and helper operations include `company_id = COMPANY_ID`.
- [ ] Run the focused tests and confirm they fail because the predicates are absent.
- [ ] Add `.eq("company_id", COMPANY_ID)` to those four query paths only.
- [ ] Re-run focused tests and all backend tests; expect success.

### Task 4: Final verification

**Files:**
- Verify all changed files without adding generated output.

**Interfaces:**
- Consumes: completed Tasks 1-3
- Produces: fresh evidence for completion

- [ ] Run Python AST parsing.
- [ ] Run all backend unittest tests.
- [ ] Run `npm exec tsc -- --noEmit --incremental false` in `frontend`.
- [ ] Run `git diff --check`, inspect `git diff`, and inspect `git status --short`.
