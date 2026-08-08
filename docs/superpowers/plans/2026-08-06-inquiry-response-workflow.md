# Inquiry Response Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理画面で、企業スコープ済みの問い合わせを開き、担当者と返信内容を確認し、LINEへの重複送信とDB部分成功を制御しながら返信履歴と対応済み状態を確定できるようにする。

**Architecture:** `inquiries`を現在状態、append-onlyな`inquiry_replies`を送信意図と監査履歴、`line_message_logs`を会話タイムラインとして分離する。Browserは`company_id`とLINE送信先を送らず、FastAPIが`COMPANY_ID`で取得した問い合わせから送信先を解決する。返信意図をLINE送信前に保存し、初回から`X-Line-Retry-Key`を付与し、LINE受理後だけ`finalize_inquiry_reply`で返信・会話ログ・問い合わせ状態を原子的に最終化する。Frontendは問い合わせ機能を`frontend/features/inquiries/`へ切り出し、既存`ConfirmationDialog`とimmutable snapshotを使う。

**Tech Stack:** Python 3.12.10、FastAPI、Pydantic 2、Supabase Python client、PostgreSQL/Supabase migration、Next.js 14.2.35、React 18.3.1、TypeScript 5.9.3、Node.js 24.18.0、Python標準`unittest`、Node標準test runner。

## Global Constraints

- Browser request、query string、Frontend stateから`company_id`を受け取らない。企業識別は現在のサーバー固定`COMPANY_ID`を使用し、利用者認証・完全なmulti-tenancyとは表現しない。
- Reply APIはBrowserから`line_user_id`、`line_retry_key`、delivery status、reply ID、actor IDを受け取らない。送信先は`inquiries.id + company_id`で取得した行からBackendだけが解決する。
- 問い合わせ、関連応募者、返信、会話ログのselect/insert/update/RPCに`company_id = COMPANY_ID`または同値の複合制約を含める。他社IDは404とし存在を漏らさない。
- `assignee_name`は返信時表示名のsnapshotでありAuth user IDではない。`actor_user_id`はAuth導入までNULLのままにする。
- raw LINE user IDを新しいAPI response/UIへ追加しない。アプリケーションログへ問い合わせ本文、返信本文、担当者名、生LINE user ID、token、keyを記録しない。
- LINE受理前に問い合わせを`対応済み`へ変更しない。timeout/5xxを自動再送せず`delivery_unknown`として同じ操作の監査可能性を残す。
- Frontendから汎用`POST /api/line/send`と問い合わせPATCHを組み合わせない。唯一の返信導線は`POST /api/inquiries/{inquiry_id}/replies`とする。
- 現行のBasic認証、Next.js BFF、`ADMIN_API_KEY`、固定`COMPANY_ID`境界を維持する。Supabase Auth、利用者role、利用者JWTによるRLS policyは別フェーズである。
- Supabase/LINEを使うテストは、通常のunit suiteではfake client/fake transportを使う。staging migration検証は明示承認されたstagingだけで実施し、production refと一致したら停止する。
- 現在の`SUPABASE_KEY`種別は未確認である。`inquiry_replies`のRLSを有効化した後、Backend credentialがserver-onlyの`secret`または`service_role`として期待どおりアクセスできることを値非表示でstaging証明できなければ、Backend deployとfeature有効化へ進まない。Supabaseはsecret/service-role keyをBackend専用・RLS bypassとして扱うが、現在の環境が該当するとは推測しない。[Supabase API key documentation](https://supabase.com/docs/guides/getting-started/api-keys)
- LINE公式仕様に従い、`X-Line-Retry-Key`は初回Pushから付ける。同じkeyが受理済みの`409`は`x-line-accepted-request-id`存在時だけ受理済みとして扱う。keyの管理期間24時間を超えた`delivery_unknown`は自動・ワンクリック再送しない。[LINE retry documentation](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/)
- 各implementation taskは、記載したREDを確認してから最小実装、対象GREEN、Backend全回帰、Frontend typecheck/build（Frontend変更task）、`git diff --check`、task commitの順で進める。

---

## Verified Baseline and Unverified Runtime State

### Repository facts verified on 2026-08-07

- `backend/main.py:2437-2476`には企業スコープ済み一覧、詳細、PATCHがある。PATCH modelは`status: str`だけで、非空なら任意値を受け付ける。
- `backend/main.py:1570-1630`の`push_line_message`はretry keyを付けず、`try_insert_line_message_log`は失敗をcatchするbest-effortである。これは問い合わせ返信の最終化には再利用しない。
- `backend/line_send_validation.py:7-42`は空白本文、孤立surrogate、5,000 UTF-16符号単位上限を検証している。返信本文でも同じ正規関数を再利用する。
- 調査用snapshotの`public.inquiries`は`id/line_user_id/message/status/created_at/company_id`のみ、`public.line_message_logs`は`inquiry_reply_id`を持たない（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:122-161`）。
- `frontend/app/page.tsx`は現在1,818行で、問い合わせUIは`frontend/app/page.tsx:1142`の一覧だけである。`frontend/lib/api.ts:40-45`は一覧/詳細GETだけを持つ。
- BFF `frontend/app/api/admin/[...path]/route.ts`は`inquiries` prefixとGET/POST/PATCHを既に許可し、`X-Admin-Key`をserver-sideで付ける。返信追加のためのBFF変更は不要である。
- `ConfirmationDialog`と`utf16CodeUnitLength`は既に存在する。Frontend test frameworkはなく、CIはtypecheck/buildだけを実行する。

### Runtime items not yet verified

- 2026-07-24 snapshot以後のlive/staging schema drift、既存`inquiries.status`のdistinct値/NULL、`inquiries.company_id`のNULL件数、実grants/RLS/policies、remote migration historyは未確認である。
- deployed Backendの`SUPABASE_KEY`が`anon`、`secret`、`service_role`のどれかは未確認である。
- 実データの件数・本文・担当者・LINE IDはこの計画作成では取得していない。

これらはTask 14のread-only preflightで確認し、条件不一致ならmigrationを適用せず停止する。推測によるbackfillやcredential変更は行わない。

---

## Dependency Graph and PR Boundary

| Task | Produces | Depends on |
|---|---|---|
| 1 | characterization、status/assignee policy | current main |
| 2 | strict request validation、shared LINE text validator | Task 1 |
| 3 | inquiries metadata migration | Tasks 1-2 |
| 4 | inquiry_replies migration | Task 3 |
| 5 | line_message_logs correlation migration | Task 4 |
| 6 | atomic finalizer migration | Tasks 3-5 |
| 7 | safe list/detail API | Tasks 1-4 |
| 8 | status/assignee PATCH with optimistic concurrency | Tasks 1-3, 7 |
| 9 | retry-aware LINE transport | Task 2 |
| 10 | dedicated reply API and recovery | Tasks 2, 4-9 |
| 11 | Frontend wire types/API/state reducer | Tasks 7-10 |
| 12 | focused inquiry list/detail UI | Task 11 |
| 13 | confirmation and reply state UI | Tasks 11-12 |
| 14 | Dashboard/mobile/state completion and staging validation | Tasks 3-13 |
| 15 | rollout documents, full verification and PR handoff | Task 14 |

This plan is one feature PR on `agent/inquiry-response-workflow`. The four migrations remain four separately reviewable and separately applied files inside that PR. Question-tree/application-start work is excluded and stays in its independent design/PR.

---

### Task 1: Characterize the current boundary and add pure inquiry policy

**Files:**
- Modify: `backend/tests/test_dashboard_inquiry_tenant_scope.py`
- Create: `backend/tests/test_inquiry_response_policy.py`
- Create: `backend/inquiry_response.py`

**Interfaces:**
- Consumes: fixed `COMPANY_ID`, current inquiry rows, `app_settings.recruiter_name`.
- Produces: `InquiryStatus`, `InquiryDeliveryStatus`, `InquiryReasonCode`, `InquiryPolicyDecision`.
- Produces: `extract_default_assignee_name(value: str | None) -> str`.
- Produces: `normalize_assignee_name(value: str) -> str` and `validate_operator_status_transition(current, target) -> InquiryPolicyDecision`.
- Produces: `mask_line_destination(value: str) -> str`; raw value is never returned from list/detail responses.

- [ ] **Step 1: Add passing characterization assertions before changing behavior.**

Extend the existing tenant fixture to assert that current list/detail/update queries include `company_id`, other-tenant detail/PATCH returns 404, and current detail contains only the fields present in the fake row. Run:

```powershell
cd backend
python -m unittest tests.test_dashboard_inquiry_tenant_scope -v
```

Expected: current characterization tests PASS. This is the required behavior lock before the new contract.

- [ ] **Step 2: Write the prospective failing policy tests.**

Test at least:

```python
self.assertEqual("佐藤", extract_default_assignee_name(" 佐藤 太郎 "))
self.assertEqual("佐藤", extract_default_assignee_name("佐藤　太郎"))
self.assertEqual("佐藤", extract_default_assignee_name("佐藤   太郎"))
self.assertEqual("佐藤太郎", extract_default_assignee_name("佐藤太郎"))
self.assertEqual("", extract_default_assignee_name(" \u3000 "))
self.assertEqual("田中 花子", normalize_assignee_name(" 田中 花子 "))
self.assertTrue(validate_operator_status_transition("未対応", "対応中").allowed)
self.assertTrue(validate_operator_status_transition("対応済み", "対応中").allowed)
self.assertFalse(validate_operator_status_transition("対応中", "対応済み").allowed)
```

`対応中 -> 対応済み`はoperator PATCHでは拒否し、Task 6のfinalizerだけが許可する。同一statusはidempotent no-opとして許可し、それ以外は`INVALID_STATUS_TRANSITION`を返す。

- [ ] **Step 3: Run RED.**

Run: `python -m unittest tests.test_inquiry_response_policy -v` from `backend`.

Expected: `ModuleNotFoundError: No module named 'inquiry_response'`でFAILする。

- [ ] **Step 4: Implement only the pure policy.**

`backend/inquiry_response.py`はFastAPI、Supabase、requests、環境変数をimportしない。半角/全角空白の連続を`re.split(r"[ \u3000]+", stripped)`で分割する。担当者確定値は前後の半角/全角空白だけ除去し、1〜80文字、空白のみ拒否とする。statusは`未対応/対応中/対応済み`だけをenum化する。

- [ ] **Step 5: Run GREEN and regression.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_policy tests.test_dashboard_inquiry_tenant_scope -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
```

Expected: focused and all Backend tests PASS; policy module has no external-service imports.

- [ ] **Step 6: Commit.**

```powershell
git add -- backend/inquiry_response.py backend/tests/test_inquiry_response_policy.py backend/tests/test_dashboard_inquiry_tenant_scope.py
git commit -m "test: characterize inquiry response policy"
```

---

### Task 2: Add strict request contracts and reuse the LINE text validator

**Files:**
- Modify: `backend/line_send_validation.py`
- Modify: `backend/inquiry_response.py`
- Modify: `backend/tests/test_line_send_validation.py`
- Modify: `backend/tests/test_inquiry_response_policy.py`

**Interfaces:**
- Produces: `validate_line_message_text(value: object) -> str` in `backend/line_send_validation.py`.
- Produces: `InquiryUpdateRequest(status, assignee_name, expected_updated_at)`; at least one mutable field is required.
- Produces: `InquiryReplyRequest(assignee_name, message, idempotency_key, expected_updated_at)` with `extra="forbid"`.
- `InquiryReplyRequest` never defines `company_id`, `line_user_id`, `line_retry_key`, delivery status, reply ID, or actor ID.

- [ ] **Step 1: Write failing validation tests.**

Cover assignee empty/whitespace/80/81, reply body empty/whitespace, 5,000/5,001 UTF-16 code units, 2,500/2,501 emoji, isolated surrogate, non-string values, invalid status, naive `expected_updated_at`, missing field, unknown field, and forbidden Browser fields. Assert valid message whitespace/newlines are preserved and only assignee outer whitespace is removed.

- [ ] **Step 2: Run RED.**

Run: `python -m unittest tests.test_inquiry_response_policy tests.test_line_send_validation -v` from `backend`.

Expected: missing request types/shared validator cause FAIL; existing `LineSendRequest` tests remain unchanged.

- [ ] **Step 3: Implement the shared validator and strict Pydantic models.**

Move the current body validation into `validate_line_message_text`; call it from both `LineSendRequest` and `InquiryReplyRequest`. Use `StrictStr`, `UUID`, and timezone-aware datetime validation. `InquiryUpdateRequest` accepts optional enum `status`/`assignee_name` plus required `expected_updated_at` and rejects a request with neither mutable field. Whether an enum value is a legal transition depends on the stored current status and is decided only by Task 8, not by the request parser.

- [ ] **Step 4: Run GREEN, all regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_policy tests.test_line_send_validation -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
git add -- backend/line_send_validation.py backend/inquiry_response.py backend/tests/test_line_send_validation.py backend/tests/test_inquiry_response_policy.py
git commit -m "feat: define inquiry response request contracts"
```

Expected: all validation and existing manual LINE request tests PASS; no dependency changes.

---

### Task 3: Migration 1 — formalize inquiry metadata and status

**Files:**
- Create: `backend/tests/test_inquiry_migrations.py`
- Create: `supabase/migrations/202608070001_inquiry_workflow_columns.sql`

**Interfaces:**
- Adds `inquiries.assignee_name text NULL`.
- Adds `inquiries.last_replied_at timestamptz NULL`.
- Adds `inquiries.updated_at timestamptz NOT NULL DEFAULT now()`.
- Makes `inquiries.status` non-null with values exactly `未対応/対応中/対応済み`.
- Makes `inquiries.company_id` non-null only after explicit guards.
- Adds UNIQUE `(company_id, id)` and index `(company_id, status, created_at DESC)`.

- [ ] **Step 1: Write a failing offline migration contract test.**

The test reads the exact migration path and asserts: preflight guards for NULL/invalid status; no guessed company/status backfill; the three columns; assignee length/nonblank CHECK; status CHECK; `company_id NOT NULL`; composite unique; index; and `trg_inquiries_set_updated_at` using `public.set_updated_at()`. The function is defined by `supabase/migrations/202607190001_mvp_security_foundation.sql:6-14` and listed in the sanitized snapshot; Task 14 must stop before applying this migration if the approved staging catalog does not contain that exact dependency.

- [ ] **Step 2: Run RED.**

Run: `python -m unittest tests.test_inquiry_migrations.InquiryWorkflowMigrationTests.test_inquiry_metadata_contract -v` from `backend`.

Expected: missing migration file causes FAIL.

- [ ] **Step 3: Create the guarded additive migration.**

Use `DO` guards that `RAISE EXCEPTION` when `company_id IS NULL`, `status IS NULL`, or status is outside the three values. Do not run `UPDATE`, infer a tenant, or erase old values. Use named constraints so rollback can target only this feature. Drop only the feature-owned trigger name if it exists, then create `trg_inquiries_set_updated_at` against the already-versioned `public.set_updated_at()` dependency.

- [ ] **Step 4: Run GREEN, full offline regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_migrations -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
git diff --check
git add -- backend/tests/test_inquiry_migrations.py supabase/migrations/202608070001_inquiry_workflow_columns.sql
git commit -m "db: add inquiry workflow metadata"
```

Expected: static contract PASS. No migration is applied in this task.

---

### Task 4: Migration 2 — create append-only inquiry replies

**Files:**
- Modify: `backend/tests/test_inquiry_migrations.py`
- Create: `supabase/migrations/202608070002_inquiry_replies.sql`

**Interfaces:**
- Creates `public.inquiry_replies` with `id uuid`, `company_id text`, `inquiry_id uuid`, `assignee_name text`, `message text`, `delivery_status text`, `idempotency_key uuid`, `line_retry_key uuid`, `safe_error_code text NULL`, `actor_user_id uuid NULL`, `created_at`, `updated_at`, `sent_at NULL`.
- CHECK delivery status: `pending/sending/sent/failed/delivery_unknown`.
- Composite FK `(company_id, inquiry_id)` to `inquiries(company_id, id)`.
- UNIQUE `(company_id, id)`, `(company_id, inquiry_id, idempotency_key)` and global `(line_retry_key)`.
- Indexes `(company_id, inquiry_id, created_at DESC)` and `(company_id, delivery_status, created_at)`.
- Adds `trg_inquiry_replies_set_updated_at` using the same versioned `public.set_updated_at()` dependency as Task 3.

- [ ] **Step 1: Add a failing migration contract test.**

Assert exact columns/constraints/indexes, explicit non-null `company_id`, no company default, globally unique retry key, the updated-at trigger, no actor FK before Auth tables exist, RLS enabled, and no `anon`/`authenticated` policy or direct table privilege. Also assert the migration contains no INSERT/UPDATE/DELETE of business data.

- [ ] **Step 2: Run RED.**

Run the new `test_inquiry_replies_contract`; expected missing file FAIL.

- [ ] **Step 3: Create the table migration.**

Set `delivery_status DEFAULT 'pending'`. Use DB checks for non-empty assignee/message and length 1–80 for assignee; the authoritative UTF-16 limit remains Backend validation. Enable RLS immediately. Revoke direct access from `PUBLIC`, `anon` and `authenticated`, and grant only the required table privileges to the PostgreSQL `service_role`. This role grant does not prove which key the deployed Backend uses; Task 14 must classify that credential and prove the staging access path without revealing its value.

- [ ] **Step 4: Run GREEN, all Backend tests and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_migrations -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
git diff --check
git add -- backend/tests/test_inquiry_migrations.py supabase/migrations/202608070002_inquiry_replies.sql
git commit -m "db: add inquiry reply history"
```

---

### Task 5: Migration 3 — correlate outbound message logs

**Files:**
- Modify: `backend/tests/test_inquiry_migrations.py`
- Create: `supabase/migrations/202608070003_line_message_log_inquiry_reply.sql`

**Interfaces:**
- Adds nullable `line_message_logs.inquiry_reply_id uuid`.
- Requires `company_id` whenever `inquiry_reply_id` is non-null.
- Adds composite FK `(company_id, inquiry_reply_id)` to `inquiry_replies(company_id, id)`.
- Adds index `(company_id, inquiry_reply_id)`.
- Preserves all legacy rows with NULL `inquiry_reply_id`.

- [ ] **Step 1: Add a failing contract test and run RED.**

Assert nullable correlation, composite FK, company-presence CHECK, index, no legacy row rewrite, and no change to the existing log PK/message fields. Run the focused test; expected missing file FAIL.

- [ ] **Step 2: Implement the additive migration.**

Do not make the existing `line_message_logs.company_id` globally non-null in this feature. Only new inquiry-reply correlations require both IDs, allowing legacy rows to remain unchanged.

- [ ] **Step 3: Run GREEN, regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_migrations -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
git diff --check
git add -- backend/tests/test_inquiry_migrations.py supabase/migrations/202608070003_line_message_log_inquiry_reply.sql
git commit -m "db: link inquiry replies to message logs"
```

---

### Task 6: Migration 4 — add the idempotent finalizer function

**Files:**
- Modify: `backend/tests/test_inquiry_migrations.py`
- Create: `supabase/migrations/202608070004_finalize_inquiry_reply.sql`

**Interfaces:**
- Produces `public.finalize_inquiry_reply(p_company_id text, p_inquiry_id uuid, p_reply_id uuid) RETURNS jsonb`.
- Locks reply and inquiry by both ID and company.
- Idempotently returns existing sent result when the same reply is already sent.
- In one transaction: mark reply `sent`, clear safe error, set `sent_at`; insert one outbound `line_message_logs` row with `message_type='inquiry_reply'` and `inquiry_reply_id`; update inquiry to `対応済み`, assignee snapshot, `last_replied_at`, `updated_at`.

- [ ] **Step 1: Add failing static/function contract tests.**

Assert exact signature, `SECURITY INVOKER`, fixed safe `search_path`, tenant predicates on every selected/updated/inserted entity, inquiry status must be `対応中`, duplicate finalization creates no second log, and execute is revoked from `PUBLIC/anon/authenticated`. The function must derive message/assignee from the stored reply rather than caller arguments.

- [ ] **Step 2: Run RED.**

Run the focused function migration test; expected missing file FAIL.

- [ ] **Step 3: Implement the minimal PL/pgSQL finalizer.**

Use row locks and raise stable SQLSTATE/application messages for missing tenant-scoped rows or wrong status. Insert the log only when no existing `(company_id, inquiry_reply_id)` correlation exists. Return only IDs, safe delivery state and timestamps; never return LINE ID or message from the function. Revoke execution from `PUBLIC/anon/authenticated` and grant the exact signature only to `service_role`; Task 14 still verifies that the deployed server key maps to an elevated server role.

- [ ] **Step 4: Run GREEN, regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_migrations -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
git diff --check
git add -- backend/tests/test_inquiry_migrations.py supabase/migrations/202608070004_finalize_inquiry_reply.sql
git commit -m "db: finalize inquiry replies atomically"
```

Staging transaction behavior is not claimed by static tests; Task 14 proves it against the approved staging catalog with synthetic rows.

---

### Task 7: Implement safe inquiry list and detail APIs

**Files:**
- Modify: `backend/inquiry_response.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_inquiry_response_api.py`
- Modify: `backend/tests/test_dashboard_inquiry_tenant_scope.py`

**Interfaces:**
- `GET /api/inquiries?status={未対応|対応中|対応済み}&sort={oldest|newest}&limit=1..100&cursor={URL-safe-token}` returns `{items, next_cursor}`.
- List item: `id`, `message_preview`, `created_at`, `status`, `assignee_name`, `last_replied_at`, `updated_at`, `related_applicant_exists`, `unanswered_age_seconds`; never `line_user_id`.
- Cursor: URL-safe base64 JSON containing validated timezone-aware `created_at` and UUID `id`; keyset ordering uses `(created_at, id)`.
- `GET /api/inquiries/{id}` returns `{inquiry, default_assignee_name, masked_destination, related_applicants, replies, reply_enabled}`. `reply_enabled` is derived from server-only `INQUIRY_REPLY_WORKFLOW_ENABLED`, which is introduced here with default false and reused by Task 10.
- Related applicant query uses `company_id + line_user_id`; reply query uses `company_id + inquiry_id`, oldest first.

- [ ] **Step 1: Write failing no-network API tests.**

Extend the fake Supabase query recorder and cover: status filter; oldest/newest; invalid cursor 422; bounded limit; next cursor; no raw LINE ID in list/detail; message preview; empty list; own detail; other tenant 404; related applicants exclude another company sharing the same LINE ID; replies exclude other tenant and sort chronologically; recruiter default surname; feature flag false by default.

- [ ] **Step 2: Run RED.**

Run: `python -m unittest tests.test_inquiry_response_api -v` from `backend`.

Expected: new response envelope/filter/detail fields are missing, causing assertion failures.

- [ ] **Step 3: Implement explicit select lists and response mapping.**

Never return `select("*")` for these routes. Fetch the inquiry's raw LINE ID only inside the detail service, use it for scoped applicant lookup, then expose only `mask_line_destination`. Calculate elapsed seconds from Backend UTC. Cursor decoding rejects extra keys, naive times and non-UUID IDs before building a filter.

- [ ] **Step 4: Narrow the Dashboard recent-inquiry query.**

Replace Dashboard `select("*")` with `id,message,status,created_at,assignee_name,last_replied_at,updated_at`; map to the safe summary type so Dashboard no longer receives raw LINE ID.

- [ ] **Step 5: Run GREEN, all regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_api tests.test_dashboard_inquiry_tenant_scope -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
git add -- backend/inquiry_response.py backend/main.py backend/tests/test_inquiry_response_api.py backend/tests/test_dashboard_inquiry_tenant_scope.py
git commit -m "feat: expose tenant-safe inquiry details"
```

---

### Task 8: Enforce status/assignee transitions and optimistic concurrency

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/inquiry_response.py`
- Modify: `backend/tests/test_inquiry_response_api.py`

**Interfaces:**
- `PATCH /api/inquiries/{id}` accepts `InquiryUpdateRequest` only.
- Actual update predicates: `id`, `company_id`, `expected_updated_at`.
- Allowed operator transitions: same status no-op, `未対応 -> 対応中`, `対応済み -> 対応中`; finalizer alone performs `対応中 -> 対応済み`.
- 404 for other tenant/missing, 409 `INQUIRY_CONFLICT` for stale timestamp, 409 `INVALID_STATUS_TRANSITION` for forbidden transition, 422 for invalid shape.

- [ ] **Step 1: Write failing PATCH tests.**

Cover all allowed/forbidden transitions, empty assignee, assignee manual value preservation, stale timestamp, same timestamp success, other tenant, actual update query company predicate, no mutation on any failure, and a race where pre-read succeeds but update matches zero rows.

- [ ] **Step 2: Run RED.**

Expected: current arbitrary `status: str` PATCH accepts forbidden values and lacks optimistic predicate.

- [ ] **Step 3: Implement scoped conditional update.**

Fetch current row by ID/company, validate transition, and update with ID/company/expected timestamp. If the conditional update returns no row, re-read only by ID/company: return 404 when absent, otherwise 409 without exposing another tenant. The Task 3 trigger is the single source that advances `updated_at`; the API does not manufacture a competing timestamp.

- [ ] **Step 4: Run GREEN, full regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_api -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
git add -- backend/main.py backend/inquiry_response.py backend/tests/test_inquiry_response_api.py
git commit -m "feat: validate inquiry workflow transitions"
```

---

### Task 9: Add a retry-aware LINE push transport without changing generic send

**Files:**
- Modify: `backend/inquiry_response.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_inquiry_response_delivery.py`

**Interfaces:**
- Produces `LinePushDisposition`: `accepted`, `already_accepted`, `rejected`, `unknown`.
- Produces `_push_inquiry_reply(line_user_id: str, message: str, line_retry_key: UUID) -> LinePushResult`.
- Sends `X-Line-Retry-Key` on the first request and every explicit same-operation retry.
- Existing `push_line_message` and `POST /api/line/send` behavior remain unchanged.

- [ ] **Step 1: Write failing transport tests with patched `requests.post`.**

Cover 2xx accepted; 409 plus `x-line-accepted-request-id` accepted; 409 without accepted header rejected; 400/401/403/404/429 rejected; timeout/connection error/5xx unknown; retry header present and identical; payload recipient/body unchanged; timeout is 10 seconds; logs contain only safe event, stage, disposition, status and hashed subject through existing logging helper.

- [ ] **Step 2: Run RED.**

Expected: missing retry-aware function/type causes FAIL.

- [ ] **Step 3: Implement only the transport classifier.**

Do not automatically retry inside the function. Do not parse or log LINE error bodies. Preserve existing generic manual sender so this task cannot regress applicant manual-send behavior.

- [ ] **Step 4: Run GREEN, all regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_delivery tests.test_line_send_validation -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
git add -- backend/inquiry_response.py backend/main.py backend/tests/test_inquiry_response_delivery.py
git commit -m "feat: add retry-safe inquiry LINE transport"
```

---

### Task 10: Add the durable dedicated reply API

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/inquiry_response.py`
- Modify: `backend/tests/test_inquiry_response_api.py`
- Modify: `backend/tests/test_inquiry_response_delivery.py`

**Interfaces:**
- `POST /api/inquiries/{inquiry_id}/replies` accepts only `assignee_name`, `message`, `idempotency_key`, `expected_updated_at`.
- Feature gate: server-only `INQUIRY_REPLY_WORKFLOW_ENABLED`, default false. Detail response exposes only boolean `reply_enabled`; it exposes no env value.
- 200: `{outcome:"sent", reply_id, delivery_status:"sent", inquiry_status:"対応済み", sent_at, idempotent_replay}`.
- 202: `{outcome:"delivery_unknown", reply_id, delivery_status, reason_code:"DELIVERY_RESULT_UNKNOWN"}`.
- 404: missing/other tenant. 409: conflict, reopen required, key/body conflict, or active duplicate. 422: validation. 502: known LINE rejection. 503: feature off or DB failure before external send.

- [ ] **Step 1: Write failing orchestration tests.**

Use fake Supabase and fake LINE transport only. Cover:

- Browser body containing `company_id` or `line_user_id` returns 422 before DB/LINE.
- own inquiry resolves destination server-side; other tenant returns 404 and no insert/send.
- related applicant from another company is neither read nor used.
- reply insert explicitly includes `COMPANY_ID`, generated server `line_retry_key`, `pending`, and NULL actor.
- same idempotency key + same inquiry/assignee/message returns the stored result without a second LINE call.
- same key + different message or assignee returns 409 `IDEMPOTENCY_CONFLICT` and no send.
- concurrent duplicate in `pending/sending` returns 409 `REPLY_IN_PROGRESS` and no second call.
- same key already in known `failed` state returns the stored safe rejection without sending again; an edited/reconfirmed action receives a new idempotency key.
- inquiry must be moved conditionally to`対応中` before LINE; failed conditional update marks the unsent intent with safe conflict and returns 409.
- a `対応済み` inquiry returns 409 `INQUIRY_REOPEN_REQUIRED`; PATCH reopen followed by a new reply succeeds.
- 2xx/accepted 409 calls `finalize_inquiry_reply` once with company/inquiry/reply IDs and returns 200.
- LINE accepted but RPC fails returns 202, preserves durable intent, and never reports completed.
- timeout/5xx records/attempts `delivery_unknown`, returns 202, and performs no automatic retry.
- explicit 4xx records `failed`, returns 502, and does not finalize.
- same unknown key retry within 24h reuses the stored `line_retry_key`; accepted 409 finalizes.
- unknown older than 24h returns 409 `RETRY_WINDOW_EXPIRED` and no LINE call.
- every reply select/insert/update/RPC includes company scope; another company's reply cannot be reused.

- [ ] **Step 2: Run RED.**

Run focused API/delivery suites. Expected: route absent/404 and no durable orchestration.

- [ ] **Step 3: Implement the pre-send durable sequence.**

Sequence:

1. Require feature gate and admin dependency.
2. Get inquiry by `id + company_id`; reject completed until explicit reopen.
3. Validate `expected_updated_at`, assignee and message.
4. Look up existing `(company_id, inquiry_id, idempotency_key)` before insert. Compare stored assignee/message exactly; expected timestamp is not part of payload equivalence.
5. For a new key, insert `pending` reply with explicit company and server-generated retry UUID.
6. Conditionally set inquiry status/assignee to`対応中`using ID/company/expected timestamp. Failure occurs before LINE and leaves an auditable unsent reply marked with safe conflict.
7. Set reply to `sending` by reply ID/company, call Task 9 transport exactly once.
8. Accepted/accepted-409 invokes `finalize_inquiry_reply`. Known rejection stores safe code. timeout/5xx stores unknown when DB is available.

- [ ] **Step 4: Implement recovery semantics.**

If finalizer fails after LINE acceptance, return 202 even when the follow-up status write also fails. The durable row created before LINE is the recovery anchor. A same-key retry reuses the same server retry key; LINE accepted-409 then re-runs the idempotent finalizer. Never generate a replacement retry key for the same idempotency action.

- [ ] **Step 5: Add safe logging assertions.**

Allow event name, handler stage, exception type, safe reason code, HTTP status, hashed subject. Assert captured logs omit inquiry message, reply text, assignee, raw destination, secrets and response body.

- [ ] **Step 6: Run GREEN, full regression and commit.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_api tests.test_inquiry_response_delivery -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
python -m compileall backend
git diff --check
git add -- backend/main.py backend/inquiry_response.py backend/tests/test_inquiry_response_api.py backend/tests/test_inquiry_response_delivery.py
git commit -m "feat: add idempotent inquiry reply API"
```

---

### Task 11: Define Frontend wire contracts, API client and pure reply state

**Files:**
- Modify: `frontend/types/index.ts`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/features/inquiries/types.ts`
- Create: `frontend/features/inquiries/inquiry-response.ts`
- Create: `frontend/tests/inquiry-response.test.ts`

**Interfaces:**
- Wire types: `InquiryStatus`, `InquirySummary`, `InquiryDetailResponse`, `InquiryReply`, `InquiryUpdateRequest`, `InquiryReplyRequest`, `InquiryReplyResponse`.
- UI state: `idle | editing | confirming | submitting | sent | failed | delivery_unknown`.
- Snapshot contains `inquiryId`, `assigneeName`, `message`, `messageCodeUnits`, `idempotencyKey`, `expectedUpdatedAt`, masked destination; no company/raw destination.
- API functions: `getInquiries(params)`, `getInquiry(id)`, `updateInquiry(id, request)`, `sendInquiryReply(id, request)`.

- [ ] **Step 1: Write failing Node pure tests.**

Create the focused feature directory before adding files:

```powershell
New-Item -ItemType Directory -Force frontend/features/inquiries | Out-Null
```

Test default draft, snapshot immutability, injected deterministic UUID generation, cancel retains draft but removes snapshot, submit double-dispatch no-op, 5,000/5,001 UTF-16 units, blank message, success clears draft, failure/unknown retain draft and snapshot, retry uses same idempotency key, and safe UI error mapping. Assert the request serializer contains only the four allowed fields.

- [ ] **Step 2: Run RED.**

From `frontend`, run `node --test tests/inquiry-response.test.ts`.

Expected: missing feature helper module causes FAIL. Node 24.18.0 provides the test runner/type stripping used by this repository; no package is added.

- [ ] **Step 3: Implement pure types/reducer/snapshot and API client.**

Use the existing `utf16CodeUnitLength` from `frontend/lib/send-confirmation.ts`. Generate a UUID when confirmation opens, not on every render/confirm. Add a safe `AdminApiError` shape in `frontend/lib/api.ts` that retains HTTP status/reason code but exposes only approved Japanese copy; never render raw upstream body.

- [ ] **Step 4: Run GREEN, Frontend regression and commit.**

```powershell
cd frontend
node --test tests/inquiry-response.test.ts
npm.cmd run typecheck
npm.cmd run build
cd ../backend
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
git diff --check
git add -- frontend/types/index.ts frontend/lib/api.ts frontend/features/inquiries/types.ts frontend/features/inquiries/inquiry-response.ts frontend/tests/inquiry-response.test.ts
git commit -m "feat: define inquiry response frontend state"
```

Expected: Node tests/typecheck/build PASS; no dependency or lockfile changes.

---

### Task 12: Extract the focused inquiry list and detail workspace

**Files:**
- Create: `frontend/features/inquiries/InquiryWorkspace.tsx`
- Create: `frontend/features/inquiries/InquiriesView.tsx`
- Create: `frontend/features/inquiries/InquiryDetail.tsx`
- Modify: `frontend/features/inquiries/types.ts`
- Modify: `frontend/features/inquiries/inquiry-response.ts`
- Modify: `frontend/tests/inquiry-response.test.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- `InquiryWorkspace({initialInquiryId?, initialStatus?, onDashboardRefresh})` owns list/detail fetch and selection.
- `InquiriesView` renders summaries and emits `onSelect(id)`; it has no LINE sender.
- `InquiryDetail` renders full text, status, assignee, related applicants, masked destination and chronological reply history.
- Desktop uses list + detail; mobile detail uses a full-width view with a semantic Back button.

- [ ] **Step 1: Add failing pure state tests.**

Test query-state initialization, selection preservation after refresh, opening a supplied Dashboard inquiry ID, filter reset, chronological reply sort, and state copies for loading/empty/error/read-only. Run the Node test; expected missing helpers FAIL.

- [ ] **Step 2: Implement the pure workspace helpers and run GREEN.**

Do not import React into `inquiry-response.ts`. This keeps selection/filter/sort behavior executable with Node standard tests.

- [ ] **Step 3: Implement focused components and replace only the inquiry branch in `page.tsx`.**

Remove the old local `InquiriesView` only after `InquiryWorkspace` renders the equivalent list. Do not refactor applicant/dashboard/settings components. Rows/buttons must be semantic, selected state uses `aria-current` or equivalent, loading is announced, errors use `role="alert"`, and empty copy distinguishes no inquiries from no results under a filter.

- [ ] **Step 4: Run tests, typecheck/build, static route check and commit.**

```powershell
cd frontend
node --test tests/inquiry-response.test.ts
npm.cmd run typecheck
npm.cmd run build
cd ../backend
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
rg -n "function InquiriesView" frontend/app/page.tsx
git diff --check
git add -- frontend/features/inquiries/InquiryWorkspace.tsx frontend/features/inquiries/InquiriesView.tsx frontend/features/inquiries/InquiryDetail.tsx frontend/features/inquiries/types.ts frontend/features/inquiries/inquiry-response.ts frontend/tests/inquiry-response.test.ts frontend/app/page.tsx frontend/app/globals.css
git commit -m "feat: add inquiry list and detail workspace"
```

Expected: old `page.tsx` local function is absent; only focused component owns inquiry display; API path remains `/api/admin/inquiries*`.

---

### Task 13: Add assignee editing, confirmation and reply outcome UI

**Files:**
- Modify: `frontend/features/inquiries/InquiryDetail.tsx`
- Modify: `frontend/features/inquiries/InquiryWorkspace.tsx`
- Modify: `frontend/features/inquiries/inquiry-response.ts`
- Modify: `frontend/features/inquiries/types.ts`
- Modify: `frontend/tests/inquiry-response.test.ts`
- Modify: `frontend/app/globals.css`
- Reuse unchanged: `frontend/components/ui/ConfirmationDialog.tsx`

**Interfaces:**
- Editing initializes assignee from stored `assignee_name`, otherwise Backend `default_assignee_name`.
- Confirmation snapshot freezes the exact assignee/message/idempotency/timestamp sent by confirm.
- `ConfirmationDialog` shows inquiry excerpt, assignee, reply text with preserved newlines, masked destination, UTF-16 count, resulting status, and irreversible-send warning.
- Confirm label: `この内容でLINE返信`; cancel makes no API call and preserves draft.

- [ ] **Step 1: Add failing state tests.**

Cover half/full/multiple-space surname value received from Backend, empty recruiter requiring manual assignee, 5,000/5,001 units, snapshot exactness, double click, cancel/Escape reducer event, 409 conflict, 502 rejection, 202 unknown, 200 sent, completed-inquiry reopen requirement, and reply history refresh ordering.

- [ ] **Step 2: Run RED.**

Expected: missing reply actions/reducer transitions cause FAIL.

- [ ] **Step 3: Implement editing and confirmation.**

The edit form never contains raw destination. Backdrop/keyboard/focus behavior comes from the existing dialog. While submitting, controls are disabled and `aria-busy` is true. On cancel, failed, or unknown, retain the original draft/snapshot. On success only, close dialog, clear reply draft/idempotency key, refresh detail/list/dashboard, and display the returned status/assignee/sent time.

- [ ] **Step 4: Implement outcome-specific recovery.**

- Validation: focus first invalid field; no API call.
- 409 stale: retain draft, refresh current detail after explicit user action; require reconfirmation with a new snapshot.
- 409 reopen required: show `再対応を開始`; PATCH to `対応中` only after explicit click.
- 202 unknown: do not say sent/failed, retain same key, show timeline refresh and same-operation retry within 24h.
- 502 known rejection: retain draft; creating a new confirmation creates a new idempotency key only after the user edits/reconfirms.

- [ ] **Step 5: Run GREEN, Frontend regression and commit.**

```powershell
cd frontend
node --test tests/inquiry-response.test.ts
npm.cmd run typecheck
npm.cmd run build
cd ../backend
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
rg -n "sendLineMessage" frontend/features/inquiries frontend/app/page.tsx
rg -n "dangerouslySetInnerHTML" frontend
git diff --check
git add -- frontend/features/inquiries/InquiryDetail.tsx frontend/features/inquiries/InquiryWorkspace.tsx frontend/features/inquiries/inquiry-response.ts frontend/features/inquiries/types.ts frontend/tests/inquiry-response.test.ts frontend/app/globals.css
git commit -m "feat: confirm and track inquiry replies"
```

Expected: inquiry feature has zero generic `sendLineMessage` callers; `dangerouslySetInnerHTML` is not introduced.

---

### Task 14: Complete Dashboard navigation, responsive states and staging proof

Implementation progress (2026-08-08): repository implementation and local/offline proof were completed in `f185c9c`. Steps 5–7 were not executed: staging was not inspected, the four migrations were not applied by Tasks 14–15, and staging/production deployment remains **NO-GO** pending separate approved proof.

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/features/inquiries/InquiryWorkspace.tsx`
- Modify: `frontend/features/inquiries/InquiriesView.tsx`
- Modify: `frontend/features/inquiries/InquiryDetail.tsx`
- Modify: `frontend/features/inquiries/inquiry-response.ts`
- Modify: `frontend/tests/inquiry-response.test.ts`
- Modify: `backend/tests/test_inquiry_response_api.py`
- No repository edit during staging catalog/data verification.

**Interfaces:**
- Dashboard recent card emits exact inquiry ID; unanswered card emits `status=未対応` filter.
- Recent message uses two-line clamp; datetime/status remain visible; zero unanswered copy is `未対応のお問い合わせはありません`.
- Mobile detail is single-column/full-width; touch targets are at least 44px; long inquiry/reply text wraps and scrolls inside bounded regions.

- [x] **Step 1: Add failing navigation/state tests.**

Pure tests cover recent-item ID handoff, unanswered filter handoff, zero state, 2-line preview helper, and deterministic mobile Back transition. Backend test asserts Dashboard recent inquiry response excludes `line_user_id` and includes status/timestamps.

- [x] **Step 2: Run RED.**

Expected: Dashboard handlers/response contract do not yet expose the new navigation state.

- [x] **Step 3: Implement Dashboard and responsive state completion.**

Pass `initialInquiryId/initialStatus` into `InquiryWorkspace` without introducing a new router in this PR. Add explicit `loading`, `empty`, `error`, `sending`, `delivery_unknown`, `sent`, `read-only` rendering. Keep Desktop list+detail and Mobile list/detail transition; do not change global navigation outside inquiries.

- [x] **Step 4: Run local GREEN before any staging access.**

```powershell
cd backend
python -m unittest tests.test_inquiry_response_api tests.test_dashboard_inquiry_tenant_scope -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ../frontend
node --test tests/inquiry-response.test.ts
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
```

- [ ] **Step 5: Execute the staging preflight gate read-only.**

Use the approved staging project only. Before migration application, record without secrets/PII:

1. project identity is staging and not production;
2. migration history is reconciled with checked-in baseline;
3. `inquiries`/`line_message_logs` columns, constraints, indexes, RLS, grants;
4. `inquiries.company_id`/`created_at` NULL counts and status grouped counts only;
5. Backend credential classification and whether the server path can access an RLS-enabled no-browser-policy table.

If any company/created-at NULL or unknown status exists, migration history is inconsistent, project identity is ambiguous, the server key is publishable/anon/unknown, or Backend access after RLS cannot be proven, stop with NO-GO. Do not backfill, repair migration history, weaken RLS, or grant browser roles in this feature.

- [ ] **Step 6: Apply and prove each migration independently in staging.**

After an approved schema-only backup, apply in this exact order and inspect after each:

1. `202608070001_inquiry_workflow_columns.sql`: columns, status CHECK, company NOT NULL, unique/index, existing row counts unchanged.
2. `202608070002_inquiry_replies.sql`: columns/FKs/uniques/indexes, RLS enabled, no anon/authenticated policy/grant, Backend path verified.
3. `202608070003_line_message_log_inquiry_reply.sql`: nullable legacy column, composite FK/index, legacy row counts unchanged.
4. `202608070004_finalize_inquiry_reply.sql`: signature/security/grants, tenant predicates.

Use only synthetic non-PII staging fixtures in a dedicated test company. Prove: other-tenant FK rejected; duplicate idempotency rejected; invalid status/delivery rejected; successful finalizer creates exactly one log and updates all three projections; second finalizer creates no duplicate; forced mid-function error rolls back all changes. Delete synthetic staging fixtures only through the approved test cleanup procedure after results are recorded.

- [ ] **Step 7: Run staging application behavior with LINE transport mocked/disabled.**

Deploy Backend with feature gate false, verify reads/PATCH and RLS access. Enable only in staging with fake LINE transport or a non-delivering contract test; prove 200/202/409/422/502/503 mappings without contacting a real applicant. Browser sends neither company nor raw destination.

- [x] **Step 8: Commit UI/state completion.**

```powershell
git add -- frontend/app/page.tsx frontend/app/globals.css frontend/features/inquiries/InquiryWorkspace.tsx frontend/features/inquiries/InquiriesView.tsx frontend/features/inquiries/InquiryDetail.tsx frontend/features/inquiries/inquiry-response.ts frontend/tests/inquiry-response.test.ts backend/tests/test_inquiry_response_api.py
git commit -m "feat: connect inquiry dashboard workflow"
```

Staging command output containing connection strings, tokens, user IDs or message content must not be committed.

---

### Task 15: Document rollout, execute final verification and prepare the PR

**Files:**
- Modify: `docs/INQUIRY_RESPONSE_WORKFLOW.md`
- Modify: `docs/requirements.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Create: `docs/INQUIRY_RESPONSE_RUNBOOK.md`
- Update implementation progress only: `docs/superpowers/plans/2026-08-06-inquiry-response-workflow.md`

**Interfaces:**
- Runbook states feature flag, migration gates, safe metrics, manual unknown-delivery reconciliation, production activation and rollback.
- Documents distinguish repository implementation, staging proof and production deployment; none is inferred from another.

- [x] **Step 1: Write a failing documentation contract test/check.**

Run a repository search for the required runbook headings before creation:

```powershell
rg -n "Production preflight|Migration order|Feature activation|Delivery unknown|Rollback|PII-safe monitoring" docs/INQUIRY_RESPONSE_RUNBOOK.md
```

Expected: missing file causes FAIL.

- [x] **Step 2: Write exact rollout and rollback instructions.**

Production preflight must require: approved backup; remote migration history reconciliation; schema equivalence to tested staging; zero invalid status/company NULL rows; verified Backend credential; frontend/backend versions containing the same API contract; feature flag false; approved change window; LINE retry behavior reviewed; no real applicant used in smoke tests.

Production order:

1. deploy app code with reply flag false;
2. apply migrations 1→4 one at a time with catalog/row-count checks;
3. smoke-test list/detail/PATCH using an approved non-PII test record;
4. enable the flag for the fixed current company only;
5. monitor counts of safe outcome codes, `pending`, `delivery_unknown`, 409/5xx and finalizer failures without message/assignee/destination;
6. expand only after the observation window has zero unexplained unknown/finalizer mismatch.

Rollback:

- immediately disable the feature flag and revert Frontend/Backend app code;
- do not drop `inquiry_replies`, delete message logs, erase unknown deliveries or reverse completed sends;
- additive columns/tables remain dormant because they preserve audit evidence;
- reconcile every `delivery_unknown` with its existing idempotency/retry key inside 24h; after 24h require operator review and a newly confirmed action;
- schema rollback is allowed only when no reply row/log correlation exists and a separate approved migration has been staging-tested.

- [x] **Step 3: Update factual documents and run placeholder/secret checks.**

Mark Auth/RLS user policies as not implemented, fixed company/admin key as current, and generic LINE endpoint as excluded from inquiry replies. Run:

```powershell
$markers = @(("TB" + "D"), ("TO" + "DO"), ("未" + "定"), ("要" + "検討"), ("適切に" + "実装"))
$paths = @("docs/INQUIRY_RESPONSE_RUNBOOK.md", "docs/INQUIRY_RESPONSE_WORKFLOW.md", "docs/superpowers/plans/2026-08-06-inquiry-response-workflow.md")
if (Select-String -Path $paths -Pattern $markers) { exit 1 }
$secretPattern = @(
  "eyJ[A-Za-z0-9_-]+\.",
  "Bearer [A-Za-z0-9_-]{12,}",
  ("LINE_ACCESS" + "_TOKEN="),
  ("SUPABASE" + "_KEY="),
  ("sb_" + "secret_[A-Za-z0-9_-]+")
) -join "|"
rg -n $secretPattern $paths
rg -n "company_id:|line_user_id:" frontend/features/inquiries frontend/types/index.ts
```

Expected: placeholder and secret-value scans have zero matches. The Frontend field scan has no inquiry reply request field; any pre-existing unrelated type match is inspected and recorded rather than silently accepted. The descriptive word `service_role` appears only as a role/key classification, never followed by a key value.

- [x] **Step 4: Execute final local verification.**

```powershell
python -m pip check
python -m compileall backend
cd backend
python -m unittest discover -s tests -p "test_*.py" -v
cd ../frontend
npm.cmd ci
node --test tests/inquiry-response.test.ts
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
git status --short
```

Expected: dependency check/syntax/all Backend tests/Frontend tests/typecheck/build/diff check PASS. `frontend/package-lock.json` has no unintended version update. Supabase and LINE tests remain fake except the separately approved Task 14 staging verification.

If `next build` rewrites only generated comments in tracked `frontend/next-env.d.ts`, inspect the diff and restore that generated-only change with `apply_patch`; do not include it in this feature PR.

- [ ] **Step 5: Commit documentation.**

```powershell
git add -- docs/INQUIRY_RESPONSE_WORKFLOW.md docs/requirements.md docs/CODEBASE_AUDIT.md docs/INQUIRY_RESPONSE_RUNBOOK.md docs/superpowers/plans/2026-08-06-inquiry-response-workflow.md
git commit -m "docs: document inquiry response rollout"
```

- [ ] **Step 6: Push and report without creating or merging a PR.**

```powershell
git push -u origin agent/inquiry-response-workflow
git status -sb
git rev-list --left-right --count origin/agent/inquiry-response-workflow...HEAD
git rev-list --left-right --count origin/main...HEAD
```

Expected: remote feature branch is `0 0`; worktree clean; origin/main comparison is behind 0 with the task commit count ahead.

---

## Production Completion Criteria

Implementation is complete only when all of the following are evidenced separately:

- Characterization and policy tests prove the previous company boundary and the new status/assignee rules.
- Four migrations replay independently in approved staging and preserve existing row counts/data.
- Another company's inquiry, reply, applicant and message log cannot be selected, changed, correlated or finalized.
- Browser request has no company/raw destination; Backend resolves the destination from a scoped inquiry.
- Empty/whitespace/5,001-unit bodies fail before LINE; 5,000 units pass.
- Same idempotency key cannot create/send twice; same key with changed body is 409.
- Initial and explicit-retry Push use the same `X-Line-Retry-Key`; accepted 409 finalizes without another message.
- Known rejection, timeout, LINE acceptance with DB finalizer failure, and concurrent click have distinct safe outcomes.
- Inquiry becomes `対応済み` only after LINE acceptance and successful atomic finalization.
- Completed inquiry requires explicit reopen before an additional reply.
- Dashboard opens the exact inquiry/filter; detail shows chronological replies and only masked destination.
- Cancel/failure/unknown retain draft; success alone clears it; mobile and keyboard paths are usable.
- Backend suite, Frontend pure tests, typecheck, production build and CI pass without production/Supabase/LINE secrets.
- Production activation remains a human-approved operation after staging evidence; this implementation PR does not connect to or modify production.
