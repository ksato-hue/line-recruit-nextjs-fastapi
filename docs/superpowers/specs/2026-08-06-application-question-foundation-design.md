# Application Question Foundation Design

Date: 2026-08-06

Base: `main@cbc249c`

Implementation branch: `agent/application-question-foundation`

Status: Approved-design candidate; no runtime implementation is included in this document branch.

## 1. Outcome

Administrators can enable, disable, require, reorder, and relabel four stable basic questions, and can create or retire custom questions without changing fixed applicant destinations or historical answer meaning. Applicants see a clearer start message, correct progress, and a confirmation before cancellation. Existing v2 trees, applicants, and active sessions have an explicit compatibility path.

## 2. Current-system evidence and problems

| Area | Confirmed fact | Consequence | Evidence |
|---|---|---|---|
| Defaults | v2 has `name`, `phone`, `job`, `motivation`. | `job` is the compatible desired-job key. | `backend/main.py:200-212` |
| Validation | 1–30 questions; four input types; no enabled/basic concept. | All-off and undeletable basics are impossible. | `backend/main.py:2347-2387` |
| Editor | Any item except the last can be deleted; type can change; IDs use current time. | Fixed destinations and durable identity can be lost. | `frontend/app/page.tsx:1211-1242`, `frontend/app/page.tsx:1293-1308` |
| Sessions | Answers are only question ID + string and resume against the current tree. | Label/options and in-flight meaning can change. | `backend/main.py:1035-1044`, `backend/main.py:1076-1097` |
| Completion | Extra answers are concatenated into `motivation`. | No structured detail/search/snapshot. | `backend/main.py:1182-1202` |
| Prompt | `【応募情報入力中】` has no ordinal/total. | Progress is unclear. | `backend/main.py:1226-1247` |
| Cancel | Immediate cancel clears answers without confirmation. | Accidental data loss. | `backend/main.py:1158-1179`, `backend/main.py:1303-1309` |
| Applicant schema | No current-status or structured-answer column. | Basic four and historical custom answers cannot be represented. | `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:30-48` |
| Session schema | No tree snapshot or cancel-confirm state. | Settings changes affect active sessions. | `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:50-72` |
| RPC | Fixed four text inputs; clears session answers after completion. | All-off and durable answer snapshots need a new version. | `supabase/migrations/202607200001_application_sessions.sql:111-170` |
| FAQ templates | `shared/faq_templates.json` is a static FAQ catalog, not the application tree. | It must not be reused or changed by this feature. | `shared/faq_templates.json:1-366` |

The live database and business rows were not inspected. Current tree-version counts, active-session counts, and production schema drift are **未確認**. The implementation preflight is an aggregate/catalog-only read of staging; no answer text, LINE ID, name, or phone is retrieved.

### Confirmed problems

- Basic fields can be deleted or retyped without an immutable destination contract.
- No question/option snapshot survives later configuration changes.
- Active sessions hydrate the latest tree and can change meaning mid-application.
- Motivation concatenation cannot safely support question-level detail, search, export, or analysis.
- One-question minimum plus the completion guard blocks the approved all-off flow.
- Immediate cancel makes accidental answer destruction unrecoverable.

## 3. Question tree v3

```ts
type BasicSystemField = "name" | "phone" | "current_status" | "job";
type QuestionKind = "basic" | "custom";
type QuestionType = "text" | "tel" | "textarea" | "select";

type QuestionOption = {
  id: string;          // immutable UUID
  label: string;
};

type QuestionV3 = {
  id: string;          // immutable
  kind: QuestionKind;
  system_field: BasicSystemField | "motivation" | null;
  label: string;
  type: QuestionType;
  enabled: boolean;
  required: boolean;
  options?: QuestionOption[];
  allow_other?: boolean;
  show_when?: { question_id: string; option_id?: string; equals_text?: string };
};

type QuestionTreeV3 = { version: 3; questions: QuestionV3[] };
```

Array order controls presentation only. IDs, not indexes, control answers and destinations. Disabled required questions retain their required preference but are ignored during validation until re-enabled.

### 3.1 Basic questions

| UI label | immutable ID | system field | locked type | initial state |
|---|---|---|---|---|
| お名前 | `name` | `name` | text | enabled, required |
| 電話番号 | `phone` | `phone` | tel | enabled, required |
| 現在の状況 | `current_status` | `current_status` | select | enabled, required |
| 希望職種 | `job` | `job` | select | enabled, required |

`job` is deliberately retained. Renaming it to `desired_job` would break v2 tree IDs, `system_field`, session keys, RPC inputs, and `applicants.job`.

Basic labels may be edited because the immutable key and answer snapshot preserve storage meaning. Basic input types may not be edited because the fixed-column contract would become ambiguous. Basic rows show `基本項目・削除できません` and have no delete control.

### 3.2 Current-status options

Defaults:

- 高校卒業予定
- 大学・短大・専門学校を卒業予定
- 既卒・第二新卒
- 社会人
- その他

`その他` uses one structured answer containing the selected option snapshot and `other_text`; it does not create a second progress item. This keeps selection and explanation atomic. The fixed display column stores the selected label or `その他: <text>`.

Option labels are 1–20 UTF-16 code units because current select answers render as LINE quick replies, whose action labels have a 20-character maximum. Each select has 1–12 options so the cancel/other controls stay within LINE's maximum 13 quick reply buttons. Primary reference: [LINE Messaging API label specifications](https://developers.line.biz/en/reference/messaging-api/).

### 3.3 Custom questions and IDs

New custom IDs and new option IDs are Backend-issued UUIDv4 values on creation. Existing v2 question IDs, including `motivation` and enterprise-created opaque IDs, are preserved as immutable compatibility IDs rather than rewritten. IDs are never editable or reused. A deleted question disappears from future trees but remains inside historical applicant/session snapshots.

Custom fields support enabled, required, reorder, label, current four input types, options, and delete. Existing `motivation` becomes a removable custom question during v3 conversion while retaining ID/system field for compatibility.

The initial PR does not add a condition editor. Existing `show_when` is retained and evaluated for read/active-session compatibility.

### 3.4 Validation

- Exactly four basic IDs must be present once each, even when all are disabled.
- At most 30 total questions.
- IDs are unique and immutable after first save.
- Basic kind/system field/type combinations match the table above.
- Enabled or disabled labels remain nonempty; display text is not silently trimmed on send, while outer whitespace is rejected at config save.
- Select questions have 1–12 unique option IDs and nonempty LINE-compatible labels.
- `allow_other` is valid only for select questions.
- `show_when` may reference only an earlier immutable question/option ID; cycles and dangling references are rejected.
- All-off is valid and produces a warning, not a validation error.

## 4. Answer storage

### 4.1 Selected model

Add `applicants.answers JSONB` and keep fixed columns. JSONB is selected over motivation concatenation and a child-row table because it preserves snapshots with one applicant read while avoiding an extra tenant/RLS model at current scale.

```ts
type ApplicantAnswerSnapshot = {
  question_id: string;
  system_field: string | null;
  question_label: string;
  question_type: QuestionType;
  answer:
    | { kind: "text"; text: string }
    | { kind: "option"; option_id: string; label_snapshot: string; other_text?: string };
  answered_at: string; // UTC
};
```

The snapshot preserves the exact question and option labels at answer time. Editing/deleting config never rewrites it.

### 4.2 Fixed fields and compatibility

The completion transaction dual-writes:

```text
name            -> applicants.name
phone           -> applicants.phone
current_status  -> applicants.current_status
job             -> applicants.job
all answers     -> applicants.answers
```

For a transition period, new custom-answer content also produces the existing readable `motivation` summary. Structured display and future exports use `answers`. Existing applicants with no structured answers show `motivation` under `従来の応募内容`; no heuristic backfill is permitted.

A normalized `applicant_answers` table is deferred until measured cross-applicant analytics/search needs justify its added joins and RLS surface. If introduced later, JSON snapshots remain the historical source during migration.

## 5. Session and settings consistency

Add `application_sessions.question_tree_snapshot`. A new session stores the validated v3 tree once. All question routing, answer validation, progress, resume, and confirmation use that snapshot rather than current settings.

For an existing active session without a snapshot, Backend performs a one-time transactional capture of the then-current compatible tree before processing the next event. It maps answers by immutable ID and retains unmatched legacy answers in confirmation; it never drops them to fit a new tree.

Configuration changes affect new sessions only. This guarantees:

- reorder does not move an active user's current question;
- OFF/delete does not skip a question already in the session snapshot;
- relabel/options do not reinterpret saved answers;
- restart resumes using the same route.

## 6. All questions disabled

All four basic and every custom question may have `enabled=false`.

On `応募`:

1. Backend creates or obtains the active session with a tree snapshot.
2. It sees zero enabled questions.
3. It calls the v2 completion RPC immediately in the same request/event.
4. The applicant stores tenant, LINE subject, application session, status, and created time; basic columns are NULL and answers is `[]`.
5. It returns the configured completion message without start, question, or confirmation prompts.

This requires changing the current Python nonempty-data guard; the present RPC parameters/columns accept NULL but do not store current-status/answers. The new RPC provides the complete contract.

Settings show: `現在、応募時に質問する項目がありません。新しい応募者の基本情報は空欄になります。` Save remains enabled.

## 7. Start message and progress

The new default, used only when no company value has been stored, is:

```text
ご応募ありがとうございます！
これから応募に必要な情報を、
1項目ずつお伺いします。
画面に表示される質問に沿って、
順番に入力してください。
```

Stored customized messages are never overwritten by migration or default changes.

Prompt format:

```text
応募情報の入力（1/5）
まず、お名前を入力してください。
```

The route calculator starts from the session snapshot, keeps enabled questions, evaluates known `show_when` conditions, and includes optional questions. Numerator is the one-based index of the actual question shown. Denominator is the actual currently resolved route. For legacy conditional trees the denominator may increase after a parent answer makes a branch eligible; hidden branches never remain in the final total. New v3 editing does not introduce branches, so ordinary totals remain stable.

On resume, current immutable question ID determines the position. Reorder after session start has no effect because the snapshot owns order.

## 8. Cancellation conversation

### 8.1 Interaction

Replace the immediate text command with quick-reply/postback intent:

```text
応募を中止しますか？
ここまで入力した内容は破棄されます。

[入力を続ける] [応募を中止する]
```

Labels fit the LINE quick-reply 20-character limit. Postback data, not answer text, identifies:

- `application_cancel_request`
- `application_cancel_continue`
- `application_cancel_confirm`

The legacy text `キャンセル` remains a compatibility alias for the request step, never immediate deletion.

### 8.2 Durable state

Add nullable `application_sessions.pending_action`, CHECK-limited to `cancel_application`. It does not overwrite `current_question_key`.

| Current | Event | Result |
|---|---|---|
| active/collecting | request | same session, pending cancel, answer retained |
| pending cancel | continue | clear pending action, re-render current question |
| pending cancel | confirm | status cancelled, answer array cleared, timestamps/event persisted |
| any | duplicate event ID | return idempotent prior result/no second transition |

Cancellation physically clears raw answer PII to honor “破棄”, but retains the session row, terminal status, timestamps, and event ID for audit/idempotency. No applicant is created.

Global menu/application/FAQ/inquiry commands are evaluated before conversational state, consistent with the interview-routing incident fix. Opening the menu does not cancel the active application; sending `応募` resumes it. Interview or FAQ postbacks cannot be interpreted as cancel confirmation.

## 9. Applicant list and detail

Fixed list columns are always:

1. 名前
2. 電話番号
3. 現在の状況
4. 希望職種
5. 選考ステータス
6. 面接状況
7. 面接日時
8. 登録日時
9. 操作

Question OFF never removes a column or erases prior values. Empty is visually `—` with accessible text `未入力`. Custom questions appear in detail grouped by answer-time label; they do not dynamically create list columns.

A future configurable list may expose at most two custom fields to protect table usability. It requires a separate design for data type, pagination, export, and indexing and is excluded from PR 2.

## 10. API contracts

### 10.1 Tree read/write

`GET /api/question-tree` dual-reads legacy and v3, returning a normalized v3 view without writing on GET.

`PATCH /api/question-tree` validates v3 and upserts with explicit company ID. Existing question IDs are preserved; v2 string options and only questions/options that truly lack IDs receive server-generated IDs during the first explicit v3 save. The response is the canonical stored document.

The request cannot alter immutable basic IDs/system fields/types. Cross-company context is server-derived.

### 10.2 ID creation

The whole-tree PATCH can accept a marker for a newly created custom question/option, but not a caller-selected durable ID. Backend generates UUIDs, validates references, and returns the canonical tree. The UI replaces its temporary local key with the returned durable ID after save.

### 10.3 Completion

Add `complete_application_session_v2`, rather than silently changing the signature of the current RPC. Inputs include session/company/LINE subject, fixed values, validated answer JSON, applicant status, and event ID. It:

- locks by session ID + company + LINE subject;
- returns idempotently if completed;
- inserts one tenant-scoped applicant including current status and answers;
- marks the session completed and clears session raw answers;
- never relies on company defaults.

The old RPC remains for rollback until an observed compatibility window finishes.

## 11. Frontend settings states

The settings editor shows basic and custom rows in one reorderable list.

Basic row:

```text
現在の状況
基本項目・削除できません
質問する [ON]  必須 [ON]
入力形式 選択肢（固定）
[上へ] [下へ]
```

Custom row includes enable, required, editable label/type/options, move, and delete confirmation. There is no basic delete button.

Required page states:

- loading;
- editable/saved;
- unsaved indicator and navigation guard;
- saving with duplicate save blocked;
- validation error with field association;
- all-off warning but enabled save;
- custom delete confirmation;
- LINE preview showing start and next prompt;
- network failure retaining all edits.

## 12. Tenant, privacy, Auth/RLS

Every tree/session/applicant select, insert, update, and completion-function condition includes company ID. Every insert explicitly supplies company ID. Tests include same LINE subject in two tenants and cross-company session/tree/applicant IDs.

Logs never include answer text, question text, name, phone, LINE ID, or settings payload. They may include handler/stage, safe reason, exception type, tenant hash, and subject hash.

Before Auth/RLS, fixed company/admin key boundaries and their tests remain. After Auth/RLS, owner/admin-only settings writes, member reads, aal2, company switching, JWT-derived tenant, and table policies are connected. The PR must not claim current role or RLS enforcement.

The pure policy already defines `settings_update`, but current question-tree endpoints do not receive a verified user JWT/role (`backend/authz_policy.py:16-27`, `backend/authz_policy.py:116-145`).

## 13. Migration units

No SQL is created or applied in this design branch. PR 2 uses independent staging-verifiable units:

1. Add `applicants.current_status` and `applicants.answers` with default empty JSON array and JSON-type CHECK.
2. Add nullable `application_sessions.question_tree_snapshot` and `pending_action`, with JSON-object and allowed-action CHECKs. After one-time capture for existing active rows, add CHECK `status <> 'active' OR question_tree_snapshot IS NOT NULL`; completed/cancelled legacy rows may remain NULL.
3. Add new `complete_application_session_v2` function; do not replace/drop the old function.

Question JSON is converted on explicit application save, not via mass SQL rewrite. Existing applicant motivation and session answers are not heuristically backfilled. Migration versions are assigned only at implementation from the repository sequence; this document does not manufacture a remote version.

## 14. Implementation files and order

Expected production paths for PR 2:

- `backend/main.py`: route/orchestration integration only.
- `backend/application_questions.py`: v2/v3 normalization, route/progress, answer snapshots, basic-field policy.
- `backend/tests/test_application_question_foundation.py`: pure/API/conversation regressions.
- `frontend/types/index.ts`: v3 tree and structured answer types.
- `frontend/lib/api.ts`: canonical tree contracts.
- `frontend/app/page.tsx`: feature composition and fixed list fields.
- `frontend/features/settings/ApplicationQuestions.tsx`: focused settings editor.
- `frontend/features/applicants/ApplicantAnswers.tsx`: structured/legacy detail display.
- `frontend/app/globals.css`: scoped editor/list/mobile styles.
- `supabase/migrations/<implementation-version>_application_question_columns.sql`.
- `supabase/migrations/<implementation-version>_application_session_snapshot.sql`.
- `supabase/migrations/<implementation-version>_complete_application_session_v2.sql`.

Order: migration tests → pure conversion/route tests → Backend conversation tests → minimal Backend → settings UI → fixed applicant display → staged migration replay → full verification.

## 15. Test matrix

### Policy and API

- v2 normalization preserves `name/phone/job/motivation` IDs and labels;
- all four basics required in document but may all be disabled;
- basic delete/type/system-field change rejected;
- reorder keeps IDs/destinations;
- custom/option UUID assigned once and unchanged on later saves;
- duplicate/dangling/cyclic references rejected;
- all reads/writes tenant scoped, company ID explicit on upsert.

### Conversation

- new default start copy only without saved override;
- ordinal and total include enabled optional questions and exclude disabled ones;
- all-off creates exactly one applicant and sends no question prompt;
- resume after process restart uses snapshot/current immutable ID;
- config edit does not alter active session;
- current status options and same-answer `other_text`;
- legacy conditional progress recalculation;
- same webhook event never duplicates answer/completion.

### Persistence

- fixed columns and answer snapshots written atomically;
- question/option rename/delete does not change historical detail;
- legacy motivation fallback without invented JSON backfill;
- cancelled session clears raw answers but retains terminal row/event;
- v2 RPC remains callable for rollback fixtures.

### Frontend

- basic badge and no delete control;
- type locked, label/enabled/required/order editable;
- all-off warning and successful save;
- unsaved/save/error/delete-confirm/preview states;
- fixed columns remain for null data and announce “未入力”.

The existing Backend suite, Python compile, `npm ci`, typecheck, and production build remain required.

## 16. Rollout and rollback

Rollout:

1. Aggregate/catalog staging preflight and backup.
2. Replay each additive migration unit on empty and staging DB.
3. Run legacy v1/v2 tree, active-session, all-off, other-option, and event-replay fixtures.
4. Deploy Backend in dual-read mode, creating v3 only for new/explicitly saved configs.
5. Enable v3 editor for a pilot tenant; monitor counts of conversion failures and incomplete sessions without PII.
6. Expand after active legacy sessions finish or have been safely captured.

Rollback:

- disable v3 editing and revert app code to dual-read/old-RPC mode;
- leave additive columns, snapshots, and v2 RPC in place;
- never downgrade v3 data destructively or erase applicant answers;
- preserve active sessions and allow resume using stored snapshots.

## 17. PR boundary and acceptance

PR 2 includes question foundations, fixed list display, structured storage, start/progress/cancel conversation, independent migrations, tests, and docs. It excludes inquiry reply workflow, Auth/RLS program, scheduler/reminders, interview routing changes, and dynamic custom list columns.

Before Auth/RLS: schema, fixed tenant scope, conversation, settings, storage, UI, tests.

After Auth/RLS: role-gated settings, actor auditing, JWT tenant derivation, company switch, aal2 and RLS policies.

Acceptance:

- basics cannot be deleted or redirected, but can be enabled/required/reordered/relabeled;
- all-off completes a valid applicant with empty fixed fields;
- IDs and snapshots preserve meaning across every configuration change;
- current-status and other text are stored together and fixed field is populated;
- applicant list columns are stable and past data is untouched;
- progress is based on the session snapshot and resume is correct;
- cancellation requires confirmation, clears answer PII only on confirm, and is event-idempotent;
- all database operations are company scoped and Auth/RLS incompleteness is explicit.

## 18. Explicitly unverified before implementation

- Live tree-version and active-session counts: aggregate-only staging query.
- Live schema/RLS/grant drift since the sanitized snapshot: catalog inspection.
- Existing company-specific start messages: key-existence aggregate only; never read message bodies into reports.
- Migration-history readiness: schema-reconciliation gate before production application.

These checks have defined methods and do not leave behavior unspecified.
