# Supabase Company Scope Inventory

Audit date: 2026-07-23
Source: `backend/main.py` after the legacy JSON/HTML route tenant-scope changes in this worktree

## Interpretation

- **Scoped predicate**: the query explicitly filters `company_id = COMPANY_ID`.
- **Scoped value**: an insert/upsert/RPC explicitly writes or receives `COMPANY_ID`.
- **Unscoped**: the operation has no application-enforced company boundary at the call site.
- This inventory describes checked-out application code. Live base-table/column/constraint metadata and disabled RLS state are recorded below; FORCE RLS, grants, policies, service-role use, catalog definitions, and migration provenance remain **unverified**.
- A redacted constant `company_id` fallback/default is not tenant authorization and is classified as unscoped unless the call site supplies or checks company ownership. Its concrete literal is not recorded here.

## 2026-07-23 live Supabase scope preflight

- **FACT:** live `public`には12 base tableが報告された。下記call-site inventoryの11 tableに加えて`contacts`が存在する。
- **FACT:** `contacts`には`company_id`がなく、checked-in Backend sourceとmigrationにDDL/referenceが見つからない。用途とtenant semanticsは**UNVERIFIED**。
- **FACT:** nullable text `company_id`とconstant defaultを持つのは`applicants`, `inquiries`, `interview_slots`, `faq_categories`, `faqs`, `line_message_logs`。non-null text `company_id`でdefaultなしは`faq_settings`, `app_settings`, `question_tree_settings`, `applicant_status_settings`, `application_sessions`。
- **FACT:** live metadataで`company_id` FKは報告されなかった。distinct count、NULL count、index definitionはcatalog/aggregate call cancellationにより**UNVERIFIED**で、actual identifier valuesは取得していない。
- **FACT:** 12 live tableはすべてRLS disabled。FORCE RLS、policy、grant/default privilege、function/RPC、trigger、PostgREST exposureは**UNVERIFIED**。
- **INFERENCE:** application call siteの固定company predicateはcheckout内の防御であり、live DB tenant isolationまたはproduction-ready multi-tenancyを証明しない。
- **FACT:** dedicated migration listはempty、repositoryには4 migration fileがあり、live provenanceは**UNVERIFIED**。このmaterial mismatchと未確認catalog evidenceによりPhase-B migration作成は**NO-GO**。

### LINE binding boundary

- **FACT:** company resolutionはprocess-wide `COMPANY_ID`で、Webhookはone path、one channel secret、one access tokenを使用し、body-level `destination`を読まない。
- **PROPOSAL:** opaque pathまたはchannel-specific gatewayをtrusted bindingとして、bindingに対応するsecretで署名検証する。検証後に`destination`の一致を確認し、company/access tokenを解決する。
- **PROPOSAL:** 未検証の`destination`に基づいてsecretを選択しない。設計・migration・state-key変更は別承認とし、今回は実装しない。

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
| `backend/main.py:1587-1590` | legacy applicant JSON | applicants / select | `company_id` predicate | Scoped predicate—fixed and tested |
| `backend/main.py:1599-1602,1620-1623` | legacy applicant dashboard HTML | applicants, inquiries / select | independent `company_id` predicates before counts/rendering | Scoped predicates—fixed and tested |
| `backend/main.py:1774-1778` | legacy applicant detail HTML | applicants / select | applicant ID plus `company_id` | Scoped predicate—fixed and tested; another tenant receives existing not-found HTML |
| `backend/main.py:1867-1871` | legacy inquiry HTML | inquiries / select | `company_id` predicate before ordering | Scoped predicate—fixed and tested |
| `backend/main.py:2005` | `_get_applicant_or_404` | applicants / select | applicant ID plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2018` | `_get_interview_slot_or_404` | interview_slots / select | slot ID plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2031,2040` | `_insert_interview_slots` | interview_slots / insert/retry | supplied rows contain `COMPANY_ID`; fallback only removes `interview_type` | Scoped value—tested |
| `backend/main.py:2051,2063` | dashboard applicant aggregate/recent | applicants / select | `company_id` predicate | Scoped predicate—tested |
| `backend/main.py:2057,2071` | dashboard inquiry aggregate/recent | inquiries / select | `company_id` predicate | Scoped predicate—tested |
| `backend/main.py:2079` | dashboard sessions | application_sessions / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2145,2157,2183` | applicant list/detail/update APIs | applicants / select/update | ID where applicable plus `company_id` | Scoped predicate—tested |
| `backend/main.py:2198` | applicant interview-slot API | interview_slots / select | applicant ID plus `company_id`; applicant was prevalidated | Scoped predicate—tested |
| `backend/main.py:2232,2271` | interview creation/PATCH | applicants, interview_slots / update | entity ID plus `company_id`; inserted slots contain company value | Scoped predicate/value—tested |
| `backend/main.py:2297` | status settings update | applicant_status_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2316` | removed-status usage check | applicants / select | status name plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:2333` | status rename | applicants / bulk update | old status name plus `company_id` | Scoped predicate—fixed and tested |
| `backend/main.py:2348` | status settings save | applicant_status_settings / upsert | every row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2353` | removed status settings | applicant_status_settings / delete | status key plus `company_id` | Scoped predicate |
| `backend/main.py:2373` | FAQ category create | faq_categories / insert | row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:2394,2408` | FAQ category PATCH/DELETE | faq_categories / update/delete | category ID plus `company_id` | Scoped predicate—fixed and tested; another tenant receives 404 |
| `backend/main.py:2439` | FAQ create | faqs / insert | category ownership checked; row contains `COMPANY_ID` | Scoped value—fixed and tested |
| `backend/main.py:2471,2485` | FAQ PATCH/DELETE | faqs / update/delete | FAQ ID plus `company_id`; PATCH preloads scoped FAQ and validates changed category | Scoped predicate—fixed and tested |
| `backend/main.py:2507,2527` | FAQ template settings | faq_settings / select | `company_id` predicate | Scoped predicate |
| `backend/main.py:2552` | FAQ template settings | faq_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2615` | general/reminder settings | app_settings / upsert | rows contain `COMPANY_ID` | Scoped value |
| `backend/main.py:2681` | question tree settings | question_tree_settings / upsert | row contains `COMPANY_ID` | Scoped value |
| `backend/main.py:2699` | LINE message history | line_message_logs / select | `company_id` plus optional user ID | Scoped predicate—tested; another tenant's user yields `[]` |
| `backend/main.py:2717,2729,2746` | inquiry list/detail/update | inquiries / select/update | ID where applicable plus `company_id` | Scoped predicate—tested |

## Completed in this change

- Kept all four documented compatibility routes and added company predicates directly to their five Supabase selects. No Python-side-only filtering is used.
- Added six offline regression tests covering JSON and HTML isolation, company-scoped counts, duplicate applicant IDs across companies, another-company not-found behavior, query predicates, no row mutation, and the current GET-only route surface (`backend/tests/test_legacy_routes_tenant_scope.py:139-226`).
- No legacy mutation or inquiry-detail route is registered, so this change did not invent applicant/inquiry update routes or frontend proxy paths.
- The Backend suite now contains 62 tests.

## Earlier completed scope work

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

- No unscoped Supabase business-table operation remains in the current `backend/main.py` inventory. This is a statement about checked-out call sites, not database-enforced isolation.
- Supabase Auth and RLS are not implemented in checked-in migrations. Application predicates do not replace database policies.
- Tenant identity remains the process-wide `COMPANY_ID`; this is not end-user identity or authorization.
- Live base-table constraints reported by the list operation and disabled RLS state are documented above. FORCE RLS, policy/grant details, service-role access, company aggregates, and the reason the project migration list is empty remain **unverified** because catalog SQL was canceled.

## Recommended next slices

1. Define the supported deployment model and inspect the live schema before designing Supabase Auth/RLS.
2. Add durable Webhook-wide idempotency for inquiry, interview, FAQ, reply, and log side effects.
3. Decide the long-term compatibility-route deprecation policy after live request logs and external consumers can be checked.

Each slice should begin with cross-company or replay failure tests and should remain independently reviewable.
