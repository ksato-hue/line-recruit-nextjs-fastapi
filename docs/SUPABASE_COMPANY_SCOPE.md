# Supabase Company Scope Inventory

Audit date: 2026-07-23
Source: `backend/main.py` after the FAQ, applicant-status rename, and application-session cancellation scope changes in this worktree

## Interpretation

- **Scoped predicate**: the query explicitly filters `company_id = COMPANY_ID`.
- **Scoped value**: an insert/upsert/RPC explicitly writes or receives `COMPANY_ID`.
- **Unscoped**: the operation has no application-enforced company boundary at the call site.
- This inventory describes checked-out application code. Live Supabase schema, RLS, grants, policies, service-role use, and migration application state are **unverified**.
- Database defaults such as `company_id = 'default'` are not tenant authorization and are classified as unscoped unless the call site supplies or checks company ownership.

## Inventory

| Call site | Function or route | Table / operation | Current enforcement | Assessment |
|---|---|---|---|---|
| `backend/main.py:226` | `get_applicant_status_settings` | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:253` | `get_app_settings` | app_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:298` | `get_question_tree_for_bot` | question_tree_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:462,506` | FAQ category list helpers | faq_categories / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:481` | `get_faqs` and exact-question search | faqs / select | `company_id` predicate before visibility/category filters | Scoped predicate—fixed and tested |
| `backend/main.py:533,547` | FAQ/category ownership helpers | faq_categories, faqs / select | ID plus `company_id` predicates | Scoped predicate—fixed and tested |
| `backend/main.py:582` | active Webhook FAQ settings | faq_settings / select | `company_id` and visibility predicates | Scoped predicate—pre-existing and tested |
| `backend/main.py:805,825` | interview selection/restore | interview_slots / select | user/date/status plus `company_id` | Scoped predicate—tested |
| `backend/main.py:860,870` | interview confirmation | interview_slots / update selected/siblings | slot/applicant IDs plus `company_id` | Scoped predicate—tested |
| `backend/main.py:878` | interview confirmation | applicants / update | applicant ID plus `company_id`; applicant was prevalidated | Scoped predicate—tested |
| `backend/main.py:918,929` | interview reset | interview_slots / update/select | slot/applicant IDs plus `company_id` | Scoped predicate—tested |
| `backend/main.py:977` | Webhook slot selection | interview_slots / update | slot/applicant IDs plus `company_id` | Scoped predicate—tested |
| `backend/main.py:1026,1039,1095` | application-session event/active/persist helpers | application_sessions / select/update | `company_id` predicate | Scoped predicate |
| `backend/main.py:1123` | application-session start | application_sessions / insert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:1146` | `_cancel_application_session` | application_sessions / update | session ID, status, and `company_id` | Scoped predicate—fixed and tested; no local session remains a no-op |
| `backend/main.py:1309` | application completion | complete_application_session / RPC | passes `p_company_id`; SQL validates company/user/session | Scoped value and database check |
| `backend/main.py:1383` | inquiry submission | inquiries / insert | row contains `COMPANY_ID` | Scoped value—tested |
| `backend/main.py:1574` | `try_insert_line_message_log` | line_message_logs / insert | row contains `COMPANY_ID` | Scoped value—tested |
| `backend/main.py:1586,1593` | legacy applicant JSON/HTML views | applicants / select | none | Unscoped read—out of current scope |
| `backend/main.py:1609` | legacy applicant view | inquiries / select | none | Unscoped read—out of current scope |
| `backend/main.py:1759` | legacy applicant detail HTML | applicants / select | applicant ID only | Unscoped read—out of current scope |
| `backend/main.py:1851` | legacy inquiry HTML | inquiries / select | none | Unscoped read—out of current scope |
| `backend/main.py:1988` | `_get_applicant_or_404` | applicants / select | applicant ID plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2001` | `_get_interview_slot_or_404` | interview_slots / select | slot ID plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2014,2023` | `_insert_interview_slots` | interview_slots / insert/retry | supplied rows contain `COMPANY_ID`; fallback only removes `interview_type` | Scoped value—tested |
| `backend/main.py:2034,2046` | dashboard applicant aggregate/recent | applicants / select | `company_id` predicate | Scoped predicate—tested |
| `backend/main.py:2040,2054` | dashboard inquiry aggregate/recent | inquiries / select | `company_id` predicate | Scoped predicate—tested |
| `backend/main.py:2062` | dashboard sessions | application_sessions / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2128,2140,2166` | applicant list/detail/update APIs | applicants / select/update | ID where applicable plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2181` | applicant interview-slot API | interview_slots / select | applicant ID plus `company_id`; applicant was prevalidated | Scoped predicate—tested |
| `backend/main.py:2215,2254` | interview creation/PATCH | applicants, interview_slots / update | entity ID plus `company_id`; inserted slots contain company value | Scoped predicate/value—tested |
| `backend/main.py:2280` | status settings update | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2299` | removed-status usage check | applicants / select | status name plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:2316` | status rename | applicants / bulk update | old status name plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:2331` | status settings save | applicant_status_settings / upsert | every row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2336` | removed status settings | applicant_status_settings / delete | status key plus `company_id` | Scoped predicate |
| `backend/main.py:2356` | FAQ category create | faq_categories / insert | row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:2377,2391` | FAQ category PATCH/DELETE | faq_categories / update/delete | category ID plus `company_id` | Scoped predicate—fixed and tested; another tenant receives 404 |
| `backend/main.py:2422` | FAQ create | faqs / insert | category ownership checked; row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:2454,2468` | FAQ PATCH/DELETE | faqs / update/delete | FAQ ID plus `company_id`; PATCH preloads scoped FAQ and validates changed category | Scoped predicate—fixed and tested |
| `backend/main.py:2490,2510` | FAQ template settings | faq_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2535` | FAQ template settings | faq_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2598` | general/reminder settings | app_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2664` | question tree settings | question_tree_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2682` | LINE message history | line_message_logs / select | `company_id` plus optional user ID | Scoped predicate—tested; another tenant's user yields `[]` |
| `backend/main.py:2700,2712,2729` | inquiry list/detail/update | inquiries / select/update | ID where applicable plus `company_id` | Scoped predicate—tested |

## Completed in this change

- Added company predicates to every checked old-table FAQ category/FAQ read, search, update, and delete query.
- Added `_get_faq_category_or_404` and `_get_faq_or_404`; FAQ create and category-changing PATCH now reject another company's category before writing.
- Added explicit `company_id` values to FAQ category and FAQ inserts.
- Added minimal Backend DELETE routes for FAQ categories and FAQs because deletion isolation was an explicit acceptance criterion. Owned-resource success tests verify both ID and company predicates and preserve every non-target row; other-company tests continue to verify 404/no mutation (`backend/tests/test_faq_status_session_tenant_scope.py:269-306`, `381-422`).
- The FAQ management screen uses only `faq_settings` and has no deletion control (`frontend/app/page.tsx:1134-1306`). The API client has no FAQ/category DELETE helper (`frontend/lib/api.ts:80-109`), and the Next.js proxy permits only GET/POST/PATCH (`frontend/app/api/admin/[...path]/route.ts:22-68`). No current production caller reaches the Backend DELETE routes.
- The Backend DELETE routes remain because they satisfy an explicit API boundary requirement; browser exposure is not added without an existing caller. Future work must either approve and test proxy/client/UI wiring or remove the routes if deletion is no longer a product requirement.
- Scoped both applicant status-name usage checks and the actual name-based bulk update.
- Added a direct company predicate to the application-session cancellation update while preserving the existing safe no-op when only another company's session exists.
- Added 20 offline boundary tests (`backend/tests/test_faq_status_session_tenant_scope.py:242-478`); the Backend suite now contains 56 tests.

## Existing protections confirmed

- The active LINE Webhook FAQ flow reads `faq_settings`, not the legacy `faq_categories`/`faqs` rows (`backend/main.py:597-619`, `674-780`). Its query already contained a company predicate and is now covered by an overlapping-key two-company test.
- FAQ visibility and sort-order changes use the same scoped PATCH routes. No batch reorder endpoint or keyword-search implementation was found.
- Application-session lookup was already scoped by company and LINE user (`backend/main.py:1037-1047`); another-company-only cancellation was already a no-op. This change adds the missing company predicate to the actual update.

## Remaining unscoped operations

- The legacy JSON/HTML applicant and inquiry routes at `backend/main.py:1586-1858` remain unscoped by explicit request. They should be scoped and tested or removed in a separately approved change.
- Supabase Auth and RLS are not implemented in checked-in migrations. Application predicates do not replace database policies.
- Live database constraints, applied migrations, RLS state, grants, and service-role access remain **unverified** because no Supabase connection was made.

## Recommended next slices

1. Decide whether to scope/test or remove the legacy JSON/HTML routes.
2. Define the supported deployment model and inspect the live schema before designing Supabase Auth/RLS.
3. Add durable Webhook-wide idempotency for inquiry, interview, FAQ, reply, and log side effects.

Each slice should begin with cross-company or replay failure tests and should remain independently reviewable.
