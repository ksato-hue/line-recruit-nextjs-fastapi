# Inquiry Response Workflow Design

Date: 2026-08-06

Base: `main@cbc249c`

Implementation branch: `agent/inquiry-response-workflow`

Status: Approved-design candidate; no runtime implementation is included in this document branch.

## 1. Outcome

An operator can move from dashboard or inquiry list to a tenant-scoped inquiry detail, assign a human-readable owner, review a reply snapshot, send exactly once through LINE, inspect the reply history, and mark the inquiry complete only after LINE acceptance and an atomic database finalization.

The durable domain record is an append-only `inquiry_replies` history plus a current workflow projection on `inquiries`. A generic manual LINE endpoint is not used for this flow.

## 2. Current-system evidence

| Area | Confirmed fact | Evidence |
|---|---|---|
| Backend API | List/detail/status PATCH exist and are scoped by fixed `COMPANY_ID`; PATCH accepts any nonempty status. | `backend/main.py:2436-2476` |
| Frontend | Inquiry screen is a read-only table. | `frontend/app/page.tsx:1142-1177` |
| API client | `getInquiry` exists but no update or reply client exists. | `frontend/lib/api.ts:40-46` |
| Dashboard | Recent inquiry text is rendered in a non-interactive row without clamping. | `frontend/app/page.tsx:460-477` |
| Schema | `inquiries` has no assignee, reply, replied time, or update time. | `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:122-131` |
| Message log | Log rows have no inquiry/reply correlation. | `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:151-161` |
| Existing send | LINE success followed by best-effort log insert can report success even when log insert fails. | `backend/main.py:1608-1618`, `backend/main.py:2479-2492` |
| Authorization policy | Pure policy defines `message_send`, but user JWT/role enforcement is not connected to inquiry endpoints. | `backend/authz_policy.py:16-27`, `backend/authz_policy.py:116-145` |
| Auth/RLS | Current app uses the server admin-key/fixed-company boundary. Auth-backed membership and complete RLS are not connected. | `docs/AUTHORIZATION_POLICY.md`, `docs/AUTH_ENVIRONMENT_PREFLIGHT.md` |

The live database was not queried for this design. Current distinct inquiry statuses, grants, and schema drift are **未確認**. The implementation gate is a read-only staging catalog check and aggregate-only status count.

### Confirmed problems

- There is no end-to-end route from a list row to owned, auditable reply completion.
- Arbitrary status text and absent assignee/history make responsibility and completion ambiguous.
- Calling generic LINE send and inquiry PATCH separately creates irreversible partial success.
- Dashboard text has no action and can dominate narrow layouts.
- Fixed company predicates reduce risk but do not provide user identity, role authorization, or RLS.

## 3. User experience

### 3.1 Dashboard

- The unanswered count links to `/inquiries?status=未対応` within the current single-page navigation model.
- Each recent item shows two clamped lines, received time, and status. The whole semantic button opens the detail.
- Long unbroken content uses `overflow-wrap:anywhere`; it must not become a one-character vertical column.
- Empty copy: `未対応のお問い合わせはありません`.
- No reply editor exists on the dashboard.

### 3.2 Desktop and mobile

Desktop uses a list/detail split: the list remains visible while a 520–640px detail panel opens. Mobile uses a full-screen detail with a labelled back button. In both layouts the same detail state and API are used.

List fields:

- two-line message excerpt;
- received time;
- `未対応 / 対応中 / 対応済み`;
- assignee;
- last reply time;
- related-applicant indicator;
- elapsed time while not complete.

Detail sections:

1. Inquiry body and received time.
2. Current status and assignee.
3. Related applicant links, if the same tenant and LINE subject match.
4. Reply editor.
5. Reply history.
6. Optional conversation log, lazy-loaded and visually separated from inquiry replies.

### 3.3 Reply interaction

The editor validates non-whitespace text and 5,000 UTF-16 code units, preserving all leading/trailing whitespace and newlines in the payload. It uses the existing `ConfirmationDialog` and the same snapshot pattern as manual LINE sending.

The dialog shows inquiry text, assignee, reply text, a masked destination, the resulting status, and an irreversible-send warning. Its confirm label is `この内容でLINE返信`.

State union:

```ts
type InquiryReplyState =
  | { kind: "idle" | "editing" }
  | { kind: "confirming"; snapshot: InquiryReplySnapshot }
  | { kind: "submitting"; snapshot: InquiryReplySnapshot }
  | { kind: "failed" | "delivery_unknown"; snapshot: InquiryReplySnapshot; safeMessage: string }
  | { kind: "sent"; replyId: string };
```

Cancel discards only the snapshot and keeps the draft. Failure keeps draft and snapshot. Success refreshes detail/list/dashboard and then clears the draft. A submission snapshot owns one idempotency UUID and reuses it for retries.

## 4. Assignee name

The Backend owns a pure `default_assignee_name(recruiter_name: str) -> str` helper. It trims outer half/full-width whitespace, splits on one-or-more U+0020 or U+3000 spaces, and returns the first nonempty token. With no separator it returns the complete trimmed value; an empty setting returns empty.

Examples:

| Setting | Default |
|---|---|
| `佐藤 太郎` | `佐藤` |
| `佐藤　太郎` | `佐藤` |
| `佐藤   太郎` | `佐藤` |
| `佐藤太郎` | `佐藤太郎` |
| whitespace only | empty; user input required before reply |

The detail API returns the default. The browser does not reimplement name splitting. The final manually edited assignee is trimmed, required, limited to 80 characters, and stored unchanged as a send-time snapshot. It is not an identity or authorization key. After Auth, `actor_user_id` becomes the identity and the string remains historical display data.

## 5. Domain model

### 5.1 `inquiries` projection

Add `assignee_name`, `last_replied_at`, `updated_at`, and a CHECK-constrained non-null status. Status is one of:

- `未対応`: no operator has taken ownership;
- `対応中`: ownership/editing/retry is active;
- `対応済み`: a reply was accepted by LINE and DB finalization completed.

Unknown current live values are not auto-mapped. The staging migration aborts until an explicit reviewed mapping exists.

Allowed transitions:

| From | Event | To |
|---|---|---|
| 未対応 | save assignee/start handling | 対応中 |
| 対応中 | LINE accepted + finalization | 対応済み |
| 対応済み | explicit reopen | 対応中 |

Failure and delivery-unknown never imply completion.

### 5.2 `inquiry_replies`

Required columns:

```text
id uuid PK
company_id text NOT NULL
inquiry_id uuid NOT NULL FK inquiries(id) ON DELETE RESTRICT
assignee_name text NOT NULL
message text NOT NULL
delivery_status text NOT NULL CHECK (...)
idempotency_key uuid NOT NULL
line_retry_key uuid NOT NULL
safe_error_code text NULL
actor_user_id uuid NULL
created_at timestamptz NOT NULL
updated_at timestamptz NOT NULL
sent_at timestamptz NULL
```

First verify that `inquiries.company_id` has no NULL rows. If any exist, stop rather than infer a tenant. Then make it non-null and add UNIQUE `(company_id, id)`. `inquiry_replies` uses composite FK `(company_id, inquiry_id) → inquiries(company_id, id)`, UNIQUE `(company_id, id)`, and UNIQUE `(company_id, inquiry_id, idempotency_key)`. Index history by `(company_id, inquiry_id, created_at desc)` and operational recovery by `(company_id, delivery_status, created_at)`.

`line_message_logs.inquiry_reply_id` is nullable for existing rows and points to the reply for new inquiry sends. New reply logs include non-null company ID and use composite FK `(company_id, inquiry_reply_id) → inquiry_replies(company_id, id)` so they cannot correlate across tenants. Message logs remain the communication timeline, not workflow state.

## 6. API contract

### 6.1 List and detail

`GET /api/inquiries?status=&sort=&limit=&cursor=` returns a paginated summary. `sort=oldest` is used by the unanswered dashboard action. All filters are server-side and company-scoped.

`GET /api/inquiries/{id}` returns:

```json
{
  "inquiry": {},
  "default_assignee_name": "佐藤",
  "masked_destination": "Uabcd…1234",
  "related_applicants": [],
  "replies": []
}
```

No raw LINE user ID is newly returned to the browser. Related applicants are selected by both company and the inquiry's server-side LINE subject. Multiple matches are returned rather than silently choosing one.

### 6.2 Workflow update

`PATCH /api/inquiries/{id}` accepts only status, assignee, and `expected_updated_at`. It rejects illegal transitions with 409, invalid values with 422, other tenants/missing rows with 404. The update query includes both id and company.

### 6.3 Send reply

`POST /api/inquiries/{id}/replies`

```json
{
  "assignee_name": "佐藤",
  "message": "お問い合わせありがとうございます。",
  "idempotency_key": "5e1a...",
  "expected_updated_at": "2026-08-06T00:00:00Z"
}
```

The request never accepts `line_user_id`, `company_id`, delivery status, reply ID, or actor ID from the browser. Backend derives them from authenticated server context and scoped rows.

Responses:

| Result | HTTP | Body behavior |
|---|---:|---|
| sent or already sent with same key | 200 | same reply ID/status |
| delivery result unknown but durable | 202 | `delivery_unknown`, safe retry instruction |
| stale detail/operation in progress | 409 | safe conflict code |
| invalid fields | 422 | field-level safe validation |
| missing/other tenant | 404 | identical not-found result |
| explicit upstream rejection | 502 | persisted `failed`, no provider body |
| service/database unavailable before send | 503 | no LINE call |

## 7. Consistency and idempotency

### 7.1 Selected MVP

Use a synchronous dedicated Backend endpoint with a durable intent, LINE retry key, and atomic DB finalization. A Frontend sequence of generic LINE send plus inquiry PATCH is forbidden.

```text
Frontend snapshot
   │ POST idempotency key
   ▼
insert/select reply intent ──fail──> no LINE call
   │ pending/sending
   ▼
LINE Push with same X-Line-Retry-Key
   │
   ├─ explicit reject ──> reply failed; inquiry not complete
   ├─ timeout/5xx ──────> delivery_unknown; retry same key only
   └─ 2xx or accepted-key 409
             ▼
finalize_inquiry_reply transaction/RPC
  reply sent + message log + inquiry complete
```

The finalizer locks/selects both reply and inquiry using company ID and is idempotent. It inserts the message log, marks reply sent, and updates inquiry in one transaction. Retrying it after a DB disconnect produces the same result.

`X-Line-Retry-Key` must be present on the first push. LINE documents that it prevents duplicated API execution for the same key, does not itself guarantee delivery, and is managed for 24 hours. A retry receiving the accepted-key 409 is treated as accepted for finalization. After 24 hours, the system does not automatically reuse or replace an unknown key; it asks an operator to inspect the timeline.

Primary references: [LINE retry guide](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/), [Messaging API reference](https://developers.line.biz/en/reference/messaging-api/)

### 7.2 Rejected alternatives

- DB transaction around external HTTP cannot atomically roll back LINE and would hold DB locks.
- A full worker/outbox is more robust at high volume but requires deployment, retry scheduling, monitoring, and dead-letter operations. It becomes the next design if synchronous recovery metrics show a need.
- Reusing best-effort `try_insert_line_message_log` would misreport partial success.

## 8. Failure copy and observability

| Condition | User copy |
|---|---|
| validation | `送信内容を確認してください。` |
| explicit failure | `LINEへ返信できませんでした。内容を保持しています。もう一度お試しください。` |
| unknown | `送信結果を確認しています。新しく送信せず、この返信から再確認してください。` |
| conflict | `別の更新がありました。最新の内容を確認してください。` |
| success | `LINEへ返信し、お問い合わせを対応済みにしました。` |

Logs permit operation/stage, exception type, safe error code, HTTP status, reply ID, and a hashed subject. They prohibit inquiry/reply text, assignee, raw LINE ID, applicant name, keys, tokens, and provider response bodies.

Operational metrics are aggregate counts of pending, unknown, failed, finalization retry, and age buckets by non-PII tenant hash.

## 9. Tenant and Auth/RLS boundary

Every inquiry/reply/applicant/log select, insert, update, finalizer condition, and uniqueness lookup includes company ID. Company ID is explicit on insert and never taken from the request body. A cross-company target returns 404 without leaking existence.

Before Auth/RLS:

- retain Basic browser boundary, server admin key, and fixed `COMPANY_ID`;
- add company-scope query tests and service-role-only access;
- enable RLS with no anon/authenticated policy on the new reply table;
- do not claim user identity or role enforcement.

After Auth/RLS:

- derive company/member/actor from verified JWT and active membership;
- require aal2 and `message_send` permission;
- add tenant/role policies and populate actor user ID;
- support company switching and platform audit views.

## 10. Migration units

No migration is created by this design task. The feature PR must contain separately runnable and staging-verifiable units:

1. Add projection columns/index/trigger to `inquiries`; after status and NULL-company preflight, add status CHECK, company NOT NULL, and tenant-composite uniqueness.
2. Create `inquiry_replies` with constraints, indexes, RLS enabled, and no browser-role grants.
3. Add nullable `line_message_logs.inquiry_reply_id` and its tenant-aware correlation index.
4. Create new `finalize_inquiry_reply` function with explicit company inputs and locked, idempotent behavior.

The implementation-time migration version is assigned from the repository's chronological convention; this design does not invent a remote history version. Production application waits for migration-history reconciliation.

## 11. Implementation files and order

Expected production paths for PR 1:

- `backend/main.py`: endpoints and orchestration only.
- `backend/inquiry_response.py`: pure assignee/status/idempotency policy and safe result types.
- `backend/line_send_validation.py`: reuse validation; do not fork it.
- `backend/tests/test_inquiry_response_workflow.py`: red/green Backend and failure-path tests.
- `frontend/types/index.ts`: summary/detail/reply types.
- `frontend/lib/api.ts`: list filters, detail, update, reply methods.
- `frontend/app/page.tsx`: route state and feature composition only.
- `frontend/features/inquiries/InquiryWorkspace.tsx`: list/detail/editor.
- `frontend/components/ui/ConfirmationDialog.tsx`: reuse unchanged unless an independently tested accessibility defect is found.
- `frontend/app/globals.css`: scoped list/detail/clamp/mobile styles.
- `supabase/migrations/<implementation-version>_inquiry_workflow_columns.sql`.
- `supabase/migrations/<implementation-version>_inquiry_replies.sql`.
- `supabase/migrations/<implementation-version>_inquiry_reply_finalizer.sql`.

Implementation order is migration unit tests → pure policy tests → Backend failure tests → minimal Backend → Frontend states → dashboard link → full verification. The migration files are applied to staging separately before code is exercised.

## 12. Test matrix

Backend minimum:

- list/detail/filter only include own company;
- cross-company detail/update/reply is 404 and does not mutate;
- default assignee cases including half/full-width/repeated spaces and empty;
- status transitions and optimistic conflict;
- insert explicitly includes company ID;
- invalid, blank, 5,001 UTF-16 message never calls LINE;
- same idempotency key sends once;
- LINE reject, timeout, accepted retry key, DB finalizer failure and retry;
- finalizer all-or-nothing and idempotent;
- raw content/identity absent from logs.

Frontend minimum:

- dashboard two-line action and unanswered filter;
- list/detail loading, empty, network, read-only, conflict states;
- snapshot display equals submitted body;
- cancel/failure retains draft; success alone clears it;
- duplicate confirm disabled;
- masked destination only;
- keyboard/focus/mobile behavior inherited from and regression-tested with ConfirmationDialog.

Staging minimum:

- schema constraints and indexes;
- no anon/authenticated access to reply table;
- service backend can complete the transaction;
- failure injection before send, after LINE acceptance, and during finalization without duplicates.

## 13. Rollout, rollback, acceptance

Rollout uses a default-off feature flag, read-only schema preflight, backup, staging migrations, one synthetic LINE test subject, one pilot company, then general enablement. No real inquiry body is copied into test evidence.

Rollback disables the flag and reverts app code. Additive schema and append-only replies remain; no rollback deletes audit history. Unknown deliveries are manually reconciled using the same idempotency/retry key.

Acceptance:

- the operator completes the eight-step flow from inquiry open through history;
- status cannot become complete before accepted send plus atomic finalization;
- duplicate click/network retry cannot create duplicate LINE execution;
- list, details, related applicants, replies, and writes are all tenant scoped;
- desktop split and mobile full-screen detail have complete loading/error/empty states;
- no raw destination or reply/inquiry text appears in logs;
- current Auth/RLS limitations are visible in technical documentation, not represented as complete.

## 14. Explicitly unverified before implementation

- Live distinct status values: verify with aggregate-only read-only staging query.
- Live schema/grants/RLS drift after 2026-07-24: verify catalog only.
- LINE channel response behavior in this project: verify with a synthetic staging account after the dedicated endpoint exists; never with a real applicant.
- Current migration history readiness: require the schema-reconciliation gate before production migration.

These are verification gates with stated methods, not omitted design decisions.
