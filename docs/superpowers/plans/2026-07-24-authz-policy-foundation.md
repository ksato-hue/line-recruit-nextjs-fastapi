# Authorization Policy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supabase、FastAPI、Next.jsへ接続せず、認証・認可の合意済みルールを純粋なPython関数と単体テストで固定する。

**Architecture:** `backend/authz_policy.py`へ文字列Enum、不変な構造化判定結果、純粋なポリシー関数だけを置く。企業向け操作はMFA、membership、企業状態、roleの順で合成し、30日セッション、7日招待、owner変更は独立して評価できるようにする。

**Tech Stack:** Python標準ライブラリ（`dataclasses`、`datetime`、`enum`、`typing`）、`unittest`

## Global Constraints

- Supabase、migration、RLS、FastAPI endpoint、Next.js、既存APIへ接続しない。
- 依存パッケージを追加しない。
- 日時判定はUTCのtimezone-aware `datetime`だけを受け入れる。
- 判定理由へ秘密情報、メールアドレス、user ID、session IDを含めない。
- `backend/main.py`、Basic認証、`ADMIN_API_KEY`、`COMPANY_ID`を変更しない。
- 既存Backend 62件を変更・削除しない。
- 最終検証成功後に指定の1コミットだけを作成し、指定ブランチへpushする。

---

### Task 1: 公開インターフェースと境界テスト

**Files:**
- Create: `backend/tests/test_authz_policy.py`
- Create: `backend/authz_policy.py`

**Interfaces:**
- Consumes: 正式設計のrole、企業状態、membership、AAL、session、invitation、owner制約
- Produces:
  - `PolicyDecision(allowed: bool, reason_code: Optional[ReasonCode])`
  - `authorize_tenant_action(role, operation, company_state, membership_status, assurance_level)`
  - `authorize_platform_action(role, operation, assurance_level)`
  - `evaluate_company_capability(company_state, capability)`
  - `evaluate_membership(status)`
  - `evaluate_assurance_level(level)`
  - `evaluate_session(session, token_session_id, token_user_id, now)`
  - `normalize_email(email)`
  - `evaluate_invitation(invitation, authenticated_email, now)`
  - `authorize_owner_change(actor_role, current_owner_count, resulting_owner_count)`

- [x] **Step 1: roleと操作の失敗テストを書く**

`backend/tests/test_authz_policy.py`で次を個別の`test_*`として固定する。

```python
decision = authorize_tenant_action(
    Role.ADMIN,
    TenantOperation.MEMBER_INVITE,
    CompanyState.ACTIVE,
    MembershipStatus.ACTIVE,
    AssuranceLevel.AAL2,
)
self.assertFalse(decision.allowed)
self.assertEqual(ReasonCode.INSUFFICIENT_ROLE, decision.reason_code)
```

ownerは企業向け全操作、adminは日常業務と設定read/write、memberは日常業務と設定readだけを許可する。platform adminは企業業務操作を拒否し、`PlatformOperation`だけを別関数で許可する。

- [x] **Step 2: 企業状態、membership、MFAの失敗テストを書く**

```python
decision = evaluate_company_capability(
    CompanyState.MONITOR_EXPIRED,
    CompanyCapability.DASHBOARD_WRITE,
)
self.assertEqual(
    PolicyDecision(False, ReasonCode.COMPANY_READ_ONLY),
    decision,
)
```

`monitor_active`と`active`は全capability、`monitor_expired`はread/CSVのみ、`closed`は削除予定日時より前のread/CSVのみ、`suspended`はすべて拒否する。membershipは`active`だけを許可し、AALは`aal2`だけを許可する。

- [x] **Step 3: session、invitation、ownerの失敗テストを書く**

```python
expires_at = datetime(2026, 8, 23, tzinfo=timezone.utc)
decision = evaluate_session(
    SessionRecord("session-1", "user-1", expires_at),
    token_session_id="session-1",
    token_user_id="user-1",
    now=expires_at,
)
self.assertEqual(ReasonCode.SESSION_EXPIRED, decision.reason_code)
```

期限の1秒前、ちょうど、1秒後、revoke、session ID不一致、user ID不一致を分離する。招待はpendingかつ期限内かつ正規化メール完全一致だけを許可する。owner変更はplatform adminかつ変更後owner数が1人の場合だけ許可する。

- [x] **Step 4: 対象テストを実行しREDを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_authz_policy -v
```

Expected: 未実装の型・関数または拒否stubにより失敗し、テスト自体のtypoや既存環境接続では失敗しない。

### Task 2: 純粋ポリシーの最小実装

**Files:**
- Create: `backend/authz_policy.py`
- Test: `backend/tests/test_authz_policy.py`

**Interfaces:**
- Consumes: Task 1のテスト契約
- Produces: 外部I/Oを持たない再利用可能な認証・認可判定

- [x] **Step 1: Enumと構造化結果を実装する**

```python
class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    PLATFORM_ADMIN = "platform_admin"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: Optional[ReasonCode] = None
```

許可結果は`PolicyDecision(True, None)`、拒否結果は秘密値を含まない`ReasonCode`だけを持つ。

- [x] **Step 2: role・企業状態・membership・MFAを実装する**

roleの許可集合を不変な`frozenset`として定義する。企業向け合成判定は次の順序を固定する。

```text
aal2
→ active membership
→ company capability
→ tenant role
```

この順序により上位層は`MFA_REQUIRED`、`MEMBERSHIP_NOT_ACTIVE`、`COMPANY_READ_ONLY` / `COMPANY_SUSPENDED`、`INSUFFICIENT_ROLE`を安定してHTTPエラーへ変換できる。

- [x] **Step 3: session・invitation・owner制約を実装する**

sessionとinvitationの全日時引数へ、UTCかつtimezone-awareであることを検証する。期限判定は`now >= expires_at`を失効とする。メール正規化は`email.strip().lower()`だけとし、部分一致やdomain推測を行わない。

- [x] **Step 4: 対象テストを実行しGREENを確認する**

Run:

```powershell
cd backend
python -m unittest tests.test_authz_policy -v
```

Expected: 追加した30件以上がすべて成功する。

### Task 3: ポリシー決定の文書化

**Files:**
- Create: `docs/AUTHORIZATION_POLICY.md`
- Modify: `docs/superpowers/plans/2026-07-24-authz-policy-foundation.md`

**Interfaces:**
- Consumes: `backend/authz_policy.py`の公開Enum、関数、判定順序
- Produces: API/RLS接続フェーズが参照できる実装済み／未接続の境界

- [x] **Step 1: 実装したマトリクスと理由コードを書く**

事実として実装済みの純粋関数、設計上の決定、意図的に未接続のSupabase/FastAPI/RLSを分ける。`closed`のread/CSV許可は、UTCの削除予定日時より前に限定し、削除job自体は未実装と明記する。

- [x] **Step 2: 計画チェックボックスを実績に合わせて更新する**

RED/GREENを確認した項目だけを`[x]`へ更新し、未実施を成功扱いにしない。

### Task 4: 全検証と公開

**Files:**
- Verify: `backend/authz_policy.py`
- Verify: `backend/tests/test_authz_policy.py`
- Verify: `docs/AUTHORIZATION_POLICY.md`
- Verify: `docs/superpowers/plans/2026-07-24-authz-policy-foundation.md`

**Interfaces:**
- Consumes: Task 1-3の成果物
- Produces: 検証済みcommitとremote branch

- [x] **Step 1: 新規テストとBackend全件を実行する**

```powershell
cd backend
python -m unittest tests.test_authz_policy -v
python -m unittest discover -s tests -v
```

- [x] **Step 2: 構文・型・安全性・差分を検証する**

```powershell
python -m compileall -q backend
cd frontend
npm exec tsc -- --noEmit --incremental false
git diff --check
git status --short
```

加えて、naive/local datetime、秘密値・個人情報らしいliteral、文書内の存在しないrepository pathがないことを検索する。

- [ ] **Step 3: 指定メッセージでコミットする**

```powershell
git add -- backend/authz_policy.py backend/tests/test_authz_policy.py docs/AUTHORIZATION_POLICY.md docs/superpowers/plans/2026-07-24-authz-policy-foundation.md
git commit -m "feat: add authentication policy foundation"
```

- [ ] **Step 4: 指定ブランチへpushして同期を確認する**

```powershell
git push -u origin agent/authz-policy-foundation
git status --short
git rev-list --left-right --count origin/agent/authz-policy-foundation...HEAD
git rev-list --left-right --count origin/main...HEAD
```
