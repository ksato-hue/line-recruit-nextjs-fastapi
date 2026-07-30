# Reminder Policy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 外部サービスへ接続せず、応募未完了sessionに対するリマインド予定時刻、送信可否、二重送信防止、決定的な一括選択を純粋なPythonポリシーとして固定する。

**Architecture:** `backend/reminder_policy.py`を副作用のない境界とし、標準ライブラリのimmutable dataclass・string Enum・timezone-aware datetimeだけを使う。単件評価は全拒否理由を構造化して返し、一括評価は全定義の結果を保持しつつ、期限超過候補から最古の未送信1件だけを返す。企業状態の判定規則は`backend/authz_policy.py`の`CompanyState`、`CompanyCapability.LINE_ACCEPT`、`evaluate_company_capability`を再利用する。

**Tech Stack:** Python 3.12.10標準ライブラリ、既存`backend/authz_policy.py`、`unittest`

## Global Constraints

- Supabase、DB、HTTP、LINE API、環境変数、ファイルI/O、FastAPIを参照しない。
- migration、application session schema、既存API、frontend、CI、依存packageを変更しない。
- datetimeはtimezone-aware値だけを受け付け、UTC以外のaware値はUTCへ正規化し、naive値は構造化された拒否結果にする。
- session statusは実schemaの`active`、`completed`、`cancelled`を完全一致で扱い、`active`だけを送信候補にする。
- 単位は既存validationと同じ`minutes`、`hours`、`days`だけとし、上限は順に525600、8760、365とする。
- reminderは最大20件、本文はtrim後に空でなく5000文字以下、`reminder_id`は空でなく一括内で一意とする。
- 同一sessionで複数件が期限超過していても、一度に返す送信対象は`due_at`が最古の未送信1件だけとする。
- テストは`backend`を作業ディレクトリとして`python -m unittest discover -s tests -p "test_*.py" -v`で実行する。

---

### Task 1: 既存契約をテストへ固定する

**Files:**
- Create: `backend/tests/test_reminder_policy.py`

**Interfaces:**
- Consumes: `authz_policy.CompanyState`
- Produces: 後続実装に要求する`ReminderDefinition`、`ReminderReasonCode`、`calculate_due_at`、`evaluate_reminder`、`evaluate_reminders`

- [ ] **Step 1: 時刻・設定・session・企業状態・送信履歴・一括評価の失敗テストを45件以上書く**

```python
def test_due_exactly_at_scheduled_time(self) -> None:
    result = evaluate_reminder(
        self.reminder(interval=1, unit="hours"),
        activity_at=NOW,
        now=NOW + timedelta(hours=1),
        session_status="active",
        sent_reminder_ids=frozenset(),
        application_reception_enabled=True,
        company_state=CompanyState.ACTIVE,
    )
    self.assertTrue(result.should_send)
    self.assertEqual(ReminderReasonCode.DUE, result.reason_code)
```

テストは、予定時刻の1秒前・ちょうど・1秒後、UTC/非UTC aware/naive、対応3単位、session 3状態と不明値、受付ON/OFF、企業5状態と不明値、ID・間隔・単位・本文・件数上限、送信済み集合、重複ID、入力順変更、同時刻、複数期限超過、不正設定混在を個別の`test_*` methodとして記録する。

- [ ] **Step 2: 対象テストを実行してREDを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_reminder_policy -v
```

Expected: `ModuleNotFoundError: No module named 'reminder_policy'`。テストの構文やfixtureではなく、production moduleが未実装であるため失敗する。

- [ ] **Step 3: テストmethod数を機械的に確認する**

Run:

```powershell
rg -n "^\s+def test_" backend/tests/test_reminder_policy.py
```

Expected: 45件以上。

### Task 2: immutableな型と予定時刻計算を実装する

**Files:**
- Create: `backend/reminder_policy.py`
- Test: `backend/tests/test_reminder_policy.py`

**Interfaces:**
- Produces:
  - `ReminderUnit(str, Enum)`
  - `ReminderReasonCode(str, Enum)`
  - `ReminderDefinition`
  - `ReminderSchedule`
  - `ReminderDecision`
  - `ReminderBatchDecision`
  - `calculate_due_at(reminder, *, activity_at) -> ReminderSchedule`

- [ ] **Step 1: 型、定数、datetime正規化、設定validation、予定時刻計算を最小実装する**

```python
@dataclass(frozen=True)
class ReminderDefinition:
    reminder_id: str
    enabled: bool
    interval: int
    unit: ReminderUnit | str
    message: str
    order: int = 0


def calculate_due_at(
    reminder: ReminderDefinition,
    *,
    activity_at: Optional[datetime],
) -> ReminderSchedule:
    validation_reason = _validate_reminder(reminder)
    if validation_reason is not None:
        return ReminderSchedule(False, validation_reason, reminder.reminder_id, None)
    normalized_activity = _normalize_aware_datetime(activity_at)
    if normalized_activity is None:
        reason = (
            ReminderReasonCode.MISSING_ACTIVITY_TIME
            if activity_at is None
            else ReminderReasonCode.INVALID_DATETIME
        )
        return ReminderSchedule(False, reason, reminder.reminder_id, None)
    unit = ReminderUnit(reminder.unit)
    if unit is ReminderUnit.MINUTES:
        delay = timedelta(minutes=reminder.interval)
    elif unit is ReminderUnit.HOURS:
        delay = timedelta(hours=reminder.interval)
    else:
        delay = timedelta(days=reminder.interval)
    due_at = normalized_activity + delay
    return ReminderSchedule(True, None, reminder.reminder_id, due_at)
```

`activity_at`がない場合は`MISSING_ACTIVITY_TIME`、naiveなら`INVALID_DATETIME`、設定不正なら`INVALID_REMINDER`を返す。aware値は`astimezone(timezone.utc)`で正規化し、`timedelta`で曖昧さなく加算する。

- [ ] **Step 2: 時刻・設定テストを実行してGREENを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_reminder_policy.ReminderScheduleTests tests.test_reminder_policy.ReminderValidationTests -v
```

Expected: 対象テストがすべて成功する。

### Task 3: 単件送信判定を実装する

**Files:**
- Modify: `backend/reminder_policy.py`
- Test: `backend/tests/test_reminder_policy.py`

**Interfaces:**
- Consumes: `calculate_due_at`、`authz_policy.evaluate_company_capability`
- Produces:

```python
def evaluate_reminder(
    reminder: ReminderDefinition,
    *,
    activity_at: Optional[datetime],
    now: datetime,
    session_status: str,
    sent_reminder_ids: Collection[str],
    application_reception_enabled: bool,
    company_state: CompanyState | str,
) -> ReminderDecision:
    normalized_now = _normalize_aware_datetime(now)
    schedule = calculate_due_at(reminder, activity_at=activity_at)
    if normalized_now is None:
        return _decision(reminder, ReminderReasonCode.INVALID_DATETIME)
    if not schedule.valid:
        return _decision(reminder, schedule.reason_code, evaluated_at=normalized_now)
    if not reminder.enabled:
        return _decision_from_schedule(
            reminder, schedule, ReminderReasonCode.REMINDER_DISABLED, normalized_now
        )
    if session_status == "completed":
        reason = ReminderReasonCode.SESSION_COMPLETED
    elif session_status != "active":
        reason = ReminderReasonCode.SESSION_NOT_ACTIVE
    elif application_reception_enabled is not True:
        reason = ReminderReasonCode.APPLICATION_RECEPTION_DISABLED
    elif not _company_accepts_line(company_state):
        reason = ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE
    elif reminder.reminder_id in sent_reminder_ids:
        reason = ReminderReasonCode.ALREADY_SENT
    elif normalized_now < schedule.due_at:
        reason = ReminderReasonCode.NOT_DUE
    else:
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.DUE,
            normalized_now,
            should_send=True,
        )
    return _decision_from_schedule(reminder, schedule, reason, normalized_now)
```

- [ ] **Step 1: fail-closedな優先順位で最小実装する**

判定順は、`now`妥当性、reminder/activity妥当性、enabled、session状態、応募受付、企業LINE受付、送信済み、予定時刻とする。`completed`は`SESSION_COMPLETED`、それ以外の非`active`値は`SESSION_NOT_ACTIVE`、企業状態の変換失敗またはLINE拒否は`COMPANY_NOT_ACCEPTING_LINE`とする。理由には本文、LINE ID、個人情報を含めない。

- [ ] **Step 2: 単件判定テストを実行してGREENを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_reminder_policy.ReminderEvaluationTests -v
```

Expected: 境界時刻、session、受付、企業状態、送信済み判定がすべて成功する。

### Task 4: 決定的な一括評価を実装する

**Files:**
- Modify: `backend/reminder_policy.py`
- Test: `backend/tests/test_reminder_policy.py`

**Interfaces:**
- Consumes: `evaluate_reminder`
- Produces:

```python
def evaluate_reminders(
    reminders: Collection[ReminderDefinition],
    *,
    activity_at: Optional[datetime],
    now: datetime,
    session_status: str,
    sent_reminder_ids: Collection[str],
    application_reception_enabled: bool,
    company_state: CompanyState | str,
) -> ReminderBatchDecision:
    definitions = tuple(reminders)
    if len(definitions) > MAX_REMINDERS:
        decisions = tuple(
            _decision(item, ReminderReasonCode.INVALID_REMINDER)
            for item in definitions
        )
        return ReminderBatchDecision(
            decisions=decisions,
            due=(),
            reason_code=ReminderReasonCode.INVALID_REMINDER,
        )
    id_counts = Counter(
        item.reminder_id
        for item in definitions
        if isinstance(item.reminder_id, str) and item.reminder_id.strip()
    )
    decisions = []
    for item in definitions:
        if (
            isinstance(item.reminder_id, str)
            and item.reminder_id.strip()
            and id_counts[item.reminder_id] > 1
        ):
            decisions.append(
                _decision(item, ReminderReasonCode.DUPLICATE_REMINDER_ID)
            )
        else:
            decisions.append(
                evaluate_reminder(
                    item,
                    activity_at=activity_at,
                    now=now,
                    session_status=session_status,
                    sent_reminder_ids=sent_reminder_ids,
                    application_reception_enabled=application_reception_enabled,
                    company_state=company_state,
                )
            )
    ordered = tuple(sorted(decisions, key=_decision_sort_key))
    due = sorted(
        (item for item in ordered if item.should_send),
        key=_decision_sort_key,
    )
    return ReminderBatchDecision(
        decisions=ordered,
        due=tuple(due[:1]),
        reason_code=None,
    )
```

- [ ] **Step 1: 重複・件数上限と決定的な選択を最小実装する**

20件超はbatch全体を`INVALID_REMINDER`として送信対象0件にする。重複IDは重複した全定義を`DUPLICATE_REMINDER_ID`として除外し、正常な他定義は評価する。全評価結果は`due_at`、`order`、`reminder_id`で決定的に並べ、`due`には最古の未送信1件だけを格納する。

- [ ] **Step 2: 一括評価テストを実行してGREENを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_reminder_policy.ReminderBatchTests -v
```

Expected: 0/1/複数件、同時刻、入力順変更、複数期限超過、重複ID、不正混在、件数上限がすべて成功する。

- [ ] **Step 3: 全リマインドテストを再実行する**

Run:

```powershell
cd backend
python -m unittest tests.test_reminder_policy -v
```

Expected: 新規テストがすべて成功する。

### Task 5: 統合境界を文書化する

**Files:**
- Create: `docs/REMINDER_POLICY.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify if current behavior needs clarification: `docs/requirements.md`

**Interfaces:**
- Consumes: 実装済み公開型・関数と既存DB/settings契約
- Produces: 将来のDB adapter、scheduler、LINE senderが従う接続契約

- [ ] **Step 1: 事実・方針・未接続を分離して記録する**

`activity_at`はadapterが明示的に選ぶUTC時刻で、現行schemaの候補は`application_sessions.last_activity_at`だがpolicy内で列を固定しない。固定IDは`legacy_1h`、`legacy_24h`、`legacy_3d`へ対応し、固定sent列をID集合へ変換する。可変IDは保存後も維持し、並び替え・本文変更で変えず、削除後の履歴は監査・二重送信防止のため保持する。可変ID単位の履歴schema、DB取得・書込、scheduler、LINE送信は未接続と明記する。

- [ ] **Step 2: 文書内のパスと実装名を照合する**

Run:

```powershell
rg -n "reminder_policy|legacy_1h|legacy_24h|legacy_3d|last_activity_at|reminder_1h_sent_at|reminder_24h_sent_at|reminder_3d_sent_at" docs/REMINDER_POLICY.md docs/CODEBASE_AUDIT.md docs/requirements.md
```

Expected: 実在するパス・識別子だけが記載されている。

### Task 6: 全検証と安全確認を行う

**Files:**
- Verify only: repository-wide

- [ ] **Step 1: Backend全検証を実行する**

```powershell
python -m pip check
python -m compileall backend
cd backend
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: 既存149件と新規45件以上がすべて成功する。

- [ ] **Step 2: Frontend回帰検証を実行する**

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

Expected: 型検査とNext.js production buildが成功する。build生成差分はcommitしない。

- [ ] **Step 3: 純粋性と禁止依存を静的確認する**

```powershell
rg -n "supabase|fastapi|requests|os\.environ|open\(|Path\(|http|line" backend/reminder_policy.py
```

Expected: 外部サービス、環境変数、HTTP、ファイルI/Oの参照が0件。`authz_policy`のLINE capability名だけは許可する。

- [ ] **Step 4: diffと作業ツリーを確認する**

```powershell
git diff --check
git diff --stat
git status -sb
```

Expected: 指定したpolicy、tests、docs、planだけが変更され、migration、frontend、CI、dependencyに差分がない。

### Task 7: 1コミットでpushする

**Files:**
- Commit: `backend/reminder_policy.py`
- Commit: `backend/tests/test_reminder_policy.py`
- Commit: `docs/REMINDER_POLICY.md`
- Commit: `docs/CODEBASE_AUDIT.md`
- Commit if changed: `docs/requirements.md`
- Commit: `docs/superpowers/plans/2026-07-30-reminder-policy-foundation.md`

- [ ] **Step 1: 許可対象だけをstageして確認する**

```powershell
git add -- backend/reminder_policy.py backend/tests/test_reminder_policy.py docs/REMINDER_POLICY.md docs/CODEBASE_AUDIT.md docs/requirements.md docs/superpowers/plans/2026-07-30-reminder-policy-foundation.md
git diff --cached --name-status
```

- [ ] **Step 2: commitする**

```powershell
git commit -m "feat: add reminder scheduling policy foundation"
```

- [ ] **Step 3: feature branchだけをpushする**

```powershell
git push -u origin agent/reminder-policy-foundation
```

- [ ] **Step 4: 同期状態を確認する**

```powershell
git status -sb
git rev-list --left-right --count origin/agent/reminder-policy-foundation...HEAD
git rev-list --left-right --count origin/main...HEAD
```

Expected: 作業ツリーclean、local/remoteは`0 0`、`origin/main`に対してbehind 0で1 commit以上ahead。
