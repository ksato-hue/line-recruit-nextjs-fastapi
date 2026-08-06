# Applicant Outbound Send Confirmation Dialogs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 手動LINEメッセージと面接候補日を、応募者名・送信内容を確認して明示確定した場合にだけ既存APIへ送る。

**Architecture:** `ConfirmationDialog`がdialog semantics、focus trap、Escape、focus復帰、body scroll lockを一元管理する。`ApplicantDrawer`は送信操作ごとに型付きpayload snapshotと`editing / confirmation_open / submitting / success / failure`状態を持ち、確認表示とAPI引数の両方を同じsnapshotから生成する。

**Tech Stack:** Next.js 14.2.35、React 18.3.1、TypeScript 5.9.3、既存CSS、Node.js 24.18.0。新規UI・test packageは追加しない。

## Global Constraints

- Backend API、BFF、Supabase、DB、LINE送信仕様、Auth、RLSを変更しない。
- `frontend/package.json`と`frontend/package-lock.json`を変更しない。
- 生のLINE user ID、内部error、secretを新しい表示・logへ追加しない。
- 正常時だけdraftを初期化し、失敗・キャンセル時はdraftを保持する。
- 確認表示と実送信payloadは同じimmutable snapshotを参照する。
- 送信中は確定、キャンセル、close、Escape、backdrop closeを無効化する。
- Frontend test runnerは未導入のため、純粋helperはNode標準の一時テスト、UIはstrict typecheck・production build・静的検査で検証する。

---

### Task 1: 共通dialogとsnapshot helper

**Files:**
- Create: `frontend/components/ui/ConfirmationDialog.tsx`
- Create: `frontend/lib/send-confirmation.ts`
- Modify: `frontend/lib/datetime.ts`
- Modify: `frontend/app/globals.css`
- Create then remove after RED/GREEN: `frontend/tests/send-confirmation.temp.test.ts`
- Create: `docs/SEND_CONFIRMATION_UX.md`

**Interfaces:**
- Produces: `ConfirmationDialog(props: ConfirmationDialogProps)`。
- Produces: `utf16CodeUnitLength(value: string): number`、`maskLineUserId(value?: string): string`、`isValidInterviewSlot(value: string): boolean`。
- Produces: `createLineSendSnapshot(input): LineSendSnapshot`、`createInterviewSendSnapshot(input): InterviewSendSnapshot`。
- Produces: `formatJstDateTimeWithWeekday(value?: string | null): string`。

- [ ] **Step 1: 純粋helperの失敗テストを書く**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import {
  createInterviewSendSnapshot,
  createLineSendSnapshot,
  isValidInterviewSlot,
  utf16CodeUnitLength
} from "../lib/send-confirmation.ts";

test("UTF-16文字数は絵文字を2符号単位として数える", () => {
  assert.equal(utf16CodeUnitLength("採用🙂"), 4);
});

test("LINE snapshotは前後空白と送信先を保持する", () => {
  const result = createLineSendSnapshot({
    applicantId: "applicant-1",
    applicantName: "応募者A",
    lineUserId: `U${"a".repeat(32)}`,
    message: " 連絡です\n "
  });
  assert.equal(result.payload.message, " 連絡です\n ");
  assert.equal(result.maskedLineUserId, "Uaaa••••aaaa");
});

test("面接snapshotは現在のtrim/filter順を維持し配列を複製する", () => {
  const slots = [" 2026-08-10T10:00 ", "2026-08-11T11:30", ""];
  const result = createInterviewSendSnapshot({
    applicantId: "applicant-1",
    applicantName: "応募者A",
    lineUserId: `U${"a".repeat(32)}`,
    interviewType: "1次面接",
    slots
  });
  slots[0] = "changed";
  assert.deepEqual(result.payload.slots, ["2026-08-10T10:00", "2026-08-11T11:30"]);
});

test("実在しない日付は確認対象にしない", () => {
  assert.equal(isValidInterviewSlot("2026-02-30T10:00"), false);
});
```

- [ ] **Step 2: REDを確認する**

Run: `node --test tests/send-confirmation.temp.test.ts` from `frontend`

Expected: `frontend/lib/send-confirmation.ts`が未作成のためFAILする。

- [ ] **Step 3: 最小helperを実装する**

```ts
export function utf16CodeUnitLength(value: string) {
  return value.length;
}

export function maskLineUserId(value?: string) {
  if (!value) return "未設定";
  if (value.length <= 8) return `${value.slice(0, 2)}••••`;
  return `${value.slice(0, 4)}••••${value.slice(-4)}`;
}
```

`createLineSendSnapshot`はmessageを変更せず新しいpayloadへ複製する。`createInterviewSendSnapshot`は既存処理と同じ`trim`・空値除外を一度だけ実行し、新しいslots配列をpayloadへ格納する。`isValidInterviewSlot`は`YYYY-MM-DDTHH:mm`完全一致と暦上の実在日時を検証する。

- [ ] **Step 4: GREENを確認して一時テストを削除する**

Run: `node --test tests/send-confirmation.temp.test.ts` from `frontend`

Expected: 4 tests PASS。一時テストは`apply_patch`で削除し、package scriptやCIへ追加しない。

- [ ] **Step 5: 共通dialogを実装する**

`ConfirmationDialog`は`open=false`で`null`を返し、title/descriptionへ`useId`で`aria-labelledby`/`aria-describedby`を設定する。open effectは起点element、bodyの既存overflow値、keydown listenerを管理し、cleanupでlistener・scroll lockを解除して起点へfocusを戻す。キャンセルボタンを初期focusとし、Tab/Shift+Tabをdialog内の有効なfocusable elementへ循環させる。

- [ ] **Step 6: 共通styleと共通文書を追加する**

dialogは`max-height: calc(100dvh - 32px)`、header/content/footer分割、contentのみoverflow、44px以上の操作領域、`:focus-visible`を持つ。animationは追加せずreduced-motion利用者へ動きを発生させない。`docs/SEND_CONFIRMATION_UX.md`へ共通focus、scroll、snapshot、二重操作防止を記録する。

- [ ] **Step 7: 第1コミット前の検証を行う**

Run:

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run build
git diff --check
```

Expected: 全てexit 0。`package.json`と`package-lock.json`のdiffは0。

- [ ] **Step 8: 第1コミットを作成する**

```powershell
git add -- frontend/components/ui/ConfirmationDialog.tsx frontend/lib/send-confirmation.ts frontend/lib/datetime.ts frontend/app/globals.css docs/SEND_CONFIRMATION_UX.md
git commit -m "feat: add accessible confirmation dialog"
```

### Task 2: 応募者drawerへ2つの確認フローを統合

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `docs/SEND_CONFIRMATION_UX.md`
- Modify as facts require: `docs/ADMIN_UX_AUDIT.md`
- Modify as facts require: `docs/requirements.md`
- Modify as facts require: `docs/CODEBASE_AUDIT.md`
- Include: `docs/superpowers/plans/2026-08-03-send-confirmation-dialogs.md`

**Interfaces:**
- Consumes: Task 1の`ConfirmationDialog`、snapshot helper、JST曜日付きformatter。
- Produces: 手動LINEと面接候補日の`OutboundSubmissionState<T>`。`confirmation_open`、`submitting`、`failure`だけがsnapshotを保持する。

- [ ] **Step 1: 現行直接送信経路をRED基準として記録する**

Run:

```powershell
rg -n "await sendLineMessage|await createInterviewSlots" frontend/app/page.tsx
```

Expected: どちらも現在の送信ボタンhandler内から直接呼ばれ、confirm handlerが存在しない。

- [ ] **Step 2: 手動LINEの確認開始handlerを実装する**

`handleLineSubmit`をAPI非呼出の`openLineConfirmation`へ置き換える。送信先なし、空白のみ、5,000 UTF-16符号単位超過をdialog前に拒否し、正常時は`createLineSendSnapshot`の結果を`confirmation_open`へ保存する。

- [ ] **Step 3: 手動LINEの確定handlerを実装する**

`confirmLineSend`は`confirmation_open`または`failure`のsnapshotだけを`submitting`へ移し、そのsnapshotで`sendLineMessage`を1回呼ぶ。成功時だけmessageを空にして`success`へ移し、同じline userの履歴を再取得する。送信成功後の履歴取得失敗は送信失敗へ戻さず、履歴再読込失敗を短いnoticeで示す。失敗時はgeneric messageと同じsnapshotを`failure`へ残す。

- [ ] **Step 4: 面接候補日の確認開始・確定handlerを実装する**

`openInterviewConfirmation`は送信先、2〜5件、全日時の妥当性を確認しsnapshotを保存する。`confirmInterviewSend`はsnapshotのapplicant idとpayloadだけで`createInterviewSlots`を1回呼び、成功時だけslotsを3つの空欄、typeを既定値へ戻し、応募者・Dashboard状態を既存callbackで更新する。失敗時はsnapshotと編集stateを保持する。

- [ ] **Step 5: 2つの確認画面をrenderする**

LINE dialogは応募者名、マスク済みID、本文、UTF-16符号単位数、5,000上限、取消不能、履歴記録を表示する。面接dialogは応募者名、候補数、JST・曜日付き一覧、入力順、面接種別、面接調整中への更新、LINE送信、取消不能を表示する。本文はReact text nodeと`white-space: pre-wrap`を使い、`dangerouslySetInnerHTML`を使わない。

- [ ] **Step 6: 静的なGREEN検査を行う**

Run:

```powershell
rg -n "await sendLineMessage|await createInterviewSlots" frontend/app/page.tsx
rg -n "ConfirmationDialog|role=\"alert\"|aria-busy|utf16CodeUnitLength" frontend/app/page.tsx frontend/components/ui/ConfirmationDialog.tsx
rg -n "dangerouslySetInnerHTML" frontend
```

Expected: API callは2つの確定handlerに各1箇所だけ、`dangerouslySetInnerHTML`は0件。

- [ ] **Step 7: 文書を実装結果へ更新する**

`docs/SEND_CONFIRMATION_UX.md`へ両flowのvalidation、cancel/success/failure、未対応retry/idempotencyを追記する。監査・要件・コード監査は「確認dialog実装済み」「Backend契約不変」「Frontend自動component test未導入」という確認済み事実だけ更新する。

- [ ] **Step 8: 全検証を実行する**

Run:

```powershell
python -m pip check
python -m compileall backend
cd backend
python -m unittest discover -s tests -p "test_*.py" -v
cd ../frontend
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
git status --short
```

Expected: Backend 288件以上PASS、typecheck/build exit 0、許可したFrontendと文書だけが変更される。

- [ ] **Step 9: 第2コミットを作成する**

```powershell
git add -- frontend/app/page.tsx docs/SEND_CONFIRMATION_UX.md docs/ADMIN_UX_AUDIT.md docs/requirements.md docs/CODEBASE_AUDIT.md docs/superpowers/plans/2026-08-03-send-confirmation-dialogs.md
git commit -m "feat: confirm applicant outbound messages"
```

- [ ] **Step 10: pushと同期確認を行う**

```powershell
git push -u origin agent/send-confirmation-dialogs
git status -sb
git rev-list --left-right --count origin/main...HEAD
git rev-list --left-right --count origin/agent/send-confirmation-dialogs...HEAD
```

Expected: feature remoteとの差は`0 0`、origin/mainに対してbehind 0でahead 2。
