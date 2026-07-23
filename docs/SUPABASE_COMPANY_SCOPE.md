# Supabase Company Scope Inventory

Audit date: 2026-07-22  
Source: `backend/main.py` after the applicant, dashboard, and inquiry API scope fixes in this worktree

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
| `backend/main.py:765,784` | interview selection/restore | interview_slots / select | user/date/status only | Unscoped—tenant collision risk |
| `backend/main.py:816,822` | `_finish_interview_confirmation` | interview_slots / update | slot/applicant IDs only | Unscoped—cross-company update risk |
| `backend/main.py:829` | `_finish_interview_confirmation` | applicants / update | applicant ID only | Unscoped—cross-company update risk |
| `backend/main.py:867,874` | `_reset_interview_confirmation` | interview_slots / update/select | slot/applicant IDs only | Unscoped |
| `backend/main.py:920` | `handle_interview_slot_selection` | interview_slots / update | slot ID only | Unscoped |
| `backend/main.py:964,977,1033` | application-session lookup/update | application_sessions / select/update | `company_id` predicate | Scoped predicate |
| `backend/main.py:1061` | `_start_or_resume_application_session` | application_sessions / insert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:1083` | `_cancel_application_session` | application_sessions / update | session ID/status; row was previously selected with company scope | Indirectly scoped; add predicate for defense in depth |
| `backend/main.py:1240` | application completion | `complete_application_session` RPC | passes `p_company_id`; SQL checks company/user/session | Scoped value and database check |
| `backend/main.py:1314` | inquiry submission | inquiries / insert | row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:1505` | `try_insert_line_message_log` | line_message_logs / insert | no `company_id` value | Unscoped write |
| `backend/main.py:1516,1523` | legacy applicant JSON/HTML views | applicants / select | none | Unscoped read |
| `backend/main.py:1539` | legacy applicant view | inquiries / select | none | Unscoped read |
| `backend/main.py:1689` | legacy applicant detail HTML | applicants / select | applicant ID only | Unscoped read |
| `backend/main.py:1781` | legacy inquiry HTML | inquiries / select | none | Unscoped read |
| `backend/main.py:1918` | `_get_applicant_or_404` | applicants / select | applicant ID and `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:1931,1940` | `_insert_interview_slots` | interview_slots / insert/retry | supplied rows omit `company_id` | Unscoped write |
| `backend/main.py:1951,1963` | dashboard | applicants / aggregate/recent select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:1957,1971` | dashboard | inquiries / aggregate/recent select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:1979` | dashboard | application_sessions / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2045` | `GET /api/applicants` | applicants / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:2057` | `GET /api/applicants/{id}` | applicants / select | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2083` | `PATCH /api/applicants/{id}` | applicants / update | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2098` | applicant interview-slot API | interview_slots / select | applicant ID only | Unscoped read |
| `backend/main.py:2130` | interview-slot creation flow | applicants / update | applicant ID only | Unscoped update |
| `backend/main.py:2166` | `PATCH /api/interview-slots/{id}` | interview_slots / update | slot ID only | Unscoped update |
| `backend/main.py:2187` | status settings update | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2205,2215` | status use/rename | applicants / select/update | status text only | Unscoped read and bulk update |
| `backend/main.py:2225` | status settings update | applicant_status_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2230` | status settings delete | applicant_status_settings / delete | `company_id` predicate | Scoped predicate |
| `backend/main.py:2250` | FAQ category create | faq_categories / insert | no `company_id` value | Unscoped write |
| `backend/main.py:2270` | FAQ category update | faq_categories / update | category ID only | Unscoped update |
| `backend/main.py:2298` | FAQ create | faqs / insert | no `company_id` value | Unscoped write |
| `backend/main.py:2319,2332` | FAQ update | faqs / select/update | FAQ ID only | Unscoped read/update |
| `backend/main.py:2353,2373` | FAQ template settings | faq_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2398` | FAQ template settings | faq_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2461` | general/reminder settings | app_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2527` | question tree settings | question_tree_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2545` | line message history | line_message_logs / select | optional user ID only | Unscoped read |
| `backend/main.py:2562` | inquiry list | inquiries / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:2574` | inquiry detail | inquiries / select | ID and `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:2591` | inquiry status update | inquiries / update | ID and `company_id` predicates | Scoped predicate—fixed and tested |

## Completed in this change

- Added company predicates to applicant API list, detail, update, and the shared applicant lookup helper.
- Added offline tests proving another company's applicant is excluded or returned as 404 and is not updated.
- Added tenant-scoped dashboard counts and recent applicant/inquiry queries.
- Added scoped inquiry list/detail/update, explicit `company_id` on inquiry creation, and seven offline boundary tests.

## Recommended next slices

1. Interview-slot reads/writes plus explicit `company_id` on inserted rows.
2. Message-log inserts/reads so new records do not depend on a database default.
3. FAQ category/FAQ operations, including ownership validation between category and FAQ.
4. Status rename/use queries that currently operate across applicant rows by status text.
5. Legacy HTML routes: either scope and test them or remove them through a separately approved change.

Each slice should begin with a cross-company failing test. RLS design should follow the chosen authentication/deployment model and be tested independently; it is not replaced by these application predicates.
