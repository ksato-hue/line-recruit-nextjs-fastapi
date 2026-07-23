# Supabase Company Scope Inventory

Audit date: 2026-07-23
Source: `backend/main.py` after the applicant, dashboard, inquiry, interview-slot, and LINE message-log scope fixes in this worktree

## Interpretation

- **Scoped predicate**: the query explicitly filters `company_id = COMPANY_ID`.
- **Scoped value**: an insert/upsert/RPC explicitly writes or receives `COMPANY_ID`.
- **Unscoped**: the operation has no application-enforced company boundary at the call site.
- This inventory describes checked-in application code. Live Supabase RLS, grants, policies, and service-role use are **unverified**.
- Database defaults such as `company_id = 'default'` are not tenant authorization and are classified as unscoped.

## Inventory

| Call site | Function or route | Table / operation | Current enforcement | Assessment |
|---|---|---|---|---|
| `backend/main.py:226` | `get_applicant_status_settings` | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:253` | `get_app_settings` | app_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:298` | `get_question_tree_for_bot` | question_tree_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:462` | `get_active_faq_categories` | faq_categories / select | none | Unscoped—cross-company read risk |
| `backend/main.py:479` | `get_faqs` | faqs / select | none | Unscoped—cross-company read risk |
| `backend/main.py:499` | `get_faq_categories_with_faqs` | faq_categories / select | none | Unscoped—cross-company read risk |
| `backend/main.py:542` | `get_visible_faq_settings` | faq_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:765,785` | interview selection/restore | interview_slots / select | user/date/status plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:820,830` | `_finish_interview_confirmation` | interview_slots / update chosen/siblings | slot/applicant IDs plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:838` | `_finish_interview_confirmation` | applicants / update | applicant ID and `company_id`; applicant prevalidated by `_get_applicant_or_404` | Scoped predicate—fixed and tested |
| `backend/main.py:878,889` | `_reset_interview_confirmation` | interview_slots / update/select | slot/applicant IDs plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:937` | `handle_interview_slot_selection` | interview_slots / update | slot/applicant IDs plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:986,999,1055` | application-session lookup/update | application_sessions / select/update | `company_id` predicate | Scoped predicate |
| `backend/main.py:1083` | `_start_or_resume_application_session` | application_sessions / insert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:1105` | `_cancel_application_session` | application_sessions / update | session ID/status; row was previously selected with company scope | Indirectly scoped; add predicate for defense in depth |
| `backend/main.py:1262` | application completion | `complete_application_session` RPC | passes `p_company_id`; SQL checks company/user/session | Scoped value and database check |
| `backend/main.py:1336` | inquiry submission | inquiries / insert | row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:1527` | `try_insert_line_message_log` | line_message_logs / insert | row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:1539,1546` | legacy applicant JSON/HTML views | applicants / select | none | Unscoped read |
| `backend/main.py:1562` | legacy applicant view | inquiries / select | none | Unscoped read |
| `backend/main.py:1712` | legacy applicant detail HTML | applicants / select | applicant ID only | Unscoped read |
| `backend/main.py:1804` | legacy inquiry HTML | inquiries / select | none | Unscoped read |
| `backend/main.py:1941` | `_get_applicant_or_404` | applicants / select | applicant ID and `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:1954` | `_get_interview_slot_or_404` | interview_slots / select | slot ID and `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:1967,1976` | `_insert_interview_slots` | interview_slots / insert/retry | supplied rows contain `COMPANY_ID`; fallback removes only `interview_type` | Scoped value—fixed and tested |
| `backend/main.py:1987,1999` | dashboard | applicants / aggregate/recent select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:1993,2007` | dashboard | inquiries / aggregate/recent select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:2015` | dashboard | application_sessions / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2081` | `GET /api/applicants` | applicants / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:2093` | `GET /api/applicants/{id}` | applicants / select | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2119` | `PATCH /api/applicants/{id}` | applicants / update | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2134` | applicant interview-slot API | interview_slots / select | applicant ID and `company_id`; applicant prevalidated | Scoped predicate—fixed and tested |
| `backend/main.py:2153,2168` | interview-slot creation flow | interview_slots / insert; applicants / update | inserted rows contain `COMPANY_ID`; applicant update has `company_id` | Scoped value and predicate—fixed and tested |
| `backend/main.py:2207` | `PATCH /api/interview-slots/{id}` | interview_slots / update | slot ID and `company_id`; slot prevalidated by scoped helper | Scoped predicate—fixed and tested |
| `backend/main.py:2233` | status settings update | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2251,2261` | status use/rename | applicants / select/update | status text only | Unscoped read and bulk update |
| `backend/main.py:2271` | status settings update | applicant_status_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2276` | status settings delete | applicant_status_settings / delete | `company_id` predicate | Scoped predicate |
| `backend/main.py:2296` | FAQ category create | faq_categories / insert | no `company_id` value | Unscoped write |
| `backend/main.py:2316` | FAQ category update | faq_categories / update | category ID only | Unscoped update |
| `backend/main.py:2344` | FAQ create | faqs / insert | no `company_id` value | Unscoped write |
| `backend/main.py:2365,2378` | FAQ update | faqs / select/update | FAQ ID only | Unscoped read/update |
| `backend/main.py:2399,2419` | FAQ template settings | faq_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2444` | FAQ template settings | faq_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2507` | general/reminder settings | app_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2573` | question tree settings | question_tree_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2591` | line message history | line_message_logs / select | `company_id` plus optional user ID | Scoped predicate—fixed and tested; another tenant's user yields `[]` |
| `backend/main.py:2609` | inquiry list | inquiries / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:2621` | inquiry detail | inquiries / select | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2638` | inquiry status update | inquiries / update | ID and `company_id` predicates | Scoped predicate—fixed and tested |

## Completed in this change

- Added company predicates to applicant API list, detail, update, and the shared applicant lookup helper.
- Added offline tests proving another company's applicant is excluded or returned as 404 and is not updated.
- Added tenant-scoped dashboard counts and recent applicant/inquiry queries.
- Added scoped inquiry list/detail/update, explicit `company_id` on inquiry creation, and seven offline boundary tests.
- Added company predicates to all current interview-slot reads and writes, including Webhook selection, confirmation, sibling cancellation, and reset paths.
- Added a scoped private interview-slot lookup, explicit `company_id` on slot creation, and applicant ownership validation through `_get_applicant_or_404`.
- Added scoped LINE message history and explicit `company_id` on every message-log insert call path through `try_insert_line_message_log`.
- Added 17 offline interview/message boundary tests; the Backend suite now contains 36 tests.
- No applicant-ID-specific message-history route was found; the applicant drawer uses the existing `line_user_id` history filter (`frontend/lib/api.ts:73-77`, `frontend/app/page.tsx:599`).

## Recommended next slices

1. FAQ category/FAQ operations, including ownership validation between category and FAQ.
2. Status rename/use queries that currently operate across applicant rows by status text.
3. Legacy HTML routes: either scope and test them or remove them through a separately approved change.
4. Add a direct company predicate to application-session cancellation for defense in depth.

Each slice should begin with a cross-company failing test. RLS design should follow the chosen authentication/deployment model and be tested independently; it is not replaced by these application predicates.
