# Authorization Policy Foundation

作成日: 2026-07-24

実装:

- `backend/authz_policy.py`
- `backend/tests/test_authz_policy.py`

参照:

- 正式設計 `2026-07-23-supabase-auth-rbac-mfa-design.md`
- `docs/superpowers/plans/2026-07-23-supabase-auth-rbac-mfa-implementation.md`
- `docs/AUTH_ENVIRONMENT_PREFLIGHT.md`
- `docs/SUPABASE_SCHEMA_RECONCILIATION.md`
- `docs/STAGING_SUPABASE_BOOTSTRAP.md`

## 1. 適用範囲

このモジュールは、外部I/Oを行わない認証・認可ポリシーである。

実装済み:

- tenant roleと企業向け操作
- platform admin専用操作
- 企業状態とread/write/LINE/CSV capability
- membership状態
- MFA保証レベル
- 30日app sessionの有効性
- 7日招待の受諾可否
- owner変更制約
- HTTP層へ変換可能な構造化判定結果

意図的に未接続:

- Supabase Auth、MCP、DB、RLS、migration
- FastAPI dependency、endpoint、HTTP status変換
- Next.js、Basic認証、`ADMIN_API_KEY`、`COMPANY_ID`
- 実際のsession失効、招待accept transaction、owner変更transaction
- audit log、CSV生成、企業データ削除job

したがって、この実装は認証・認可のルールを固定する安全網であり、本番認証や本番マルチテナントの実装完了を意味しない。

## 2. 構造化判定

全ポリシーは`PolicyDecision`を返す。

| Field | Meaning |
|---|---|
| `allowed` | 操作を許可するか |
| `reason_code` | 拒否理由。許可時は`None` |

理由へメール、user ID、session ID、token、企業ID等を含めない。

実装済みreason code:

| Code | 用途 |
|---|---|
| `MFA_REQUIRED` | `aal2`未到達 |
| `SESSION_EXPIRED` | 絶対期限以上 |
| `SESSION_REVOKED` | app session失効済み |
| `SESSION_INVALID` | session IDまたはuser ID不一致 |
| `MEMBERSHIP_NOT_ACTIVE` | membershipが`active`以外 |
| `COMPANY_READ_ONLY` | 閲覧専用企業へのwriteまたはLINE受付 |
| `COMPANY_SUSPENDED` | 停止企業、または保持期限を過ぎたclosed企業 |
| `INSUFFICIENT_ROLE` | roleに操作権限がない |
| `INVITATION_EXPIRED` | 招待期限切れまたはexpired状態 |
| `INVITATION_INVALID` | acceptedまたはrevoked状態 |
| `EMAIL_MISMATCH` | 正規化メールの完全一致に失敗 |
| `OWNER_CHANGE_FORBIDDEN` | owner変更経路または人数制約違反 |

`EMAIL_MISMATCH`は内部判定用である。外部HTTPメッセージは既存利用者や招待先の存在を漏らさない汎用表現へ変換する。

## 3. Roleと操作

企業向けrole:

- `owner`
- `admin`
- `member`

`platform_admin`は企業membership roleとして使わず、運営専用ポリシーのactor種別として扱う。

### 3.1 企業向け操作

| Operation | owner | admin | member | platform_admin |
|---|:---:|:---:|:---:|:---:|
| `applicant_read` | allow | allow | allow | deny |
| `applicant_update` | allow | allow | allow | deny |
| `message_send` | allow | allow | allow | deny |
| `interview_manage` | allow | allow | allow | deny |
| `settings_read` | allow | allow | allow | deny |
| `settings_update` | allow | allow | deny | deny |
| `member_read` | allow | deny | deny | deny |
| `member_invite` | allow | deny | deny | deny |
| `member_suspend` | allow | deny | deny | deny |
| `member_role_update` | allow | deny | deny | deny |
| `csv_export` | allow | deny | deny | deny |

`member`の`settings_read`は、正式設計にある日常対応に必要な最小範囲を想定する。具体的なfield filteringはAPI接続フェーズで別途実装する。

### 3.2 Platform専用操作

`platform_admin`かつ`aal2`の場合だけ、次を許可する。

- `company_metadata_read`
- `initial_owner_invite`
- `mfa_reset`
- `owner_change`
- `company_status_update`
- `audit_log_read`

tenant roleはこれらを実行できず、platform adminは企業業務データ操作を実行できない。

## 4. 企業状態

| State | 管理画面read | 管理画面write | LINE受付 | CSV |
|---|:---:|:---:|:---:|:---:|
| `monitor_active` | allow | allow | allow | allow |
| `monitor_expired` | allow | deny | deny | allow |
| `active` | allow | allow | allow | allow |
| `suspended` | deny | deny | deny | deny |
| `closed` | 保持期限前のみallow | deny | deny | 保持期限前のみallow |

`closed`は`now < data_delete_at`だけを保持期間内とする。期限ちょうどの`now == data_delete_at`から拒否する。`now`または`data_delete_at`が渡されない場合はfail closedで拒否する。

日時はUTCのtimezone-aware `datetime`だけを受け入れる。naive datetimeまたはUTC以外のoffsetは`ValueError`として呼び出し側の不正を明示する。

## 5. 合成判定の順序

企業向け操作は次の順で判定する。

```text
aal2
→ active membership
→ company capability
→ tenant role
```

この順序により、複数条件が同時に不正でも上位層が安定したreason codeを取得できる。

例:

- `aal1`かつ停止membershipなら`MFA_REQUIRED`
- `aal2`かつpending membershipなら`MEMBERSHIP_NOT_ACTIVE`
- active membershipでも停止企業なら`COMPANY_SUSPENDED`
- 企業状態が許可してもrole不足なら`INSUFFICIENT_ROLE`

## 6. MembershipとMFA

Membership:

| Status | 業務操作 |
|---|:---:|
| `pending` | deny |
| `active` | allow |
| `suspended` | deny |

MFA:

| AAL | 企業業務・運営管理 |
|---|:---:|
| `aal1` | deny (`MFA_REQUIRED`) |
| `aal2` | allow |

ここでのallowは後続のmembership、企業状態、role、session判定も通過することを前提とする。

## 7. 30日session

`SessionRecord`は次を保持する。

- `session_id`
- `user_id`
- `absolute_expires_at`
- `revoked_at`

許可条件:

```text
revoked_at is None
AND token_session_id == session.session_id
AND token_user_id == session.user_id
AND now < absolute_expires_at
```

境界:

- 期限の1秒前: allow
- 期限ちょうど: `SESSION_EXPIRED`
- 期限の1秒後: `SESSION_EXPIRED`
- `revoked_at`あり: `SESSION_REVOKED`
- session IDまたはuser ID不一致: `SESSION_INVALID`

日時はUTCのtimezone-aware値に限定する。

## 8. 7日招待

招待受諾を許可する条件:

```text
status == pending
AND now < expires_at
AND normalize(authenticated_email) == normalize(invitation.email_normalized)
```

正規化は前後空白除去と小文字化だけを行い、部分一致は許可しない。

状態と結果:

| Condition | Result |
|---|---|
| pendingかつ期限内かつメール一致 | allow |
| 期限ちょうど以降 | `INVITATION_EXPIRED` |
| statusがexpired | `INVITATION_EXPIRED` |
| acceptedまたはrevoked | `INVITATION_INVALID` |
| 正規化メール不一致 | `EMAIL_MISMATCH` |

実際の7日間`expires_at`生成、token hash、利用者の有無を漏らさないHTTP表現、受諾transactionは未接続である。

## 9. Owner制約

`authorize_owner_change`は次を固定する。

- owner変更actorは`platform_admin`だけ
- 変更後owner数は必ず1
- 最初のowner作成は`0 → 1`としてplatform adminだけ許可
- owner移譲は`1 → 1`としてplatform adminだけ許可
- `1 → 0`と`1 → 2`を拒否
- owner、admin、memberによるowner変更を拒否
- 負のowner数は呼び出し不正として`ValueError`

これはDB制約やtransactionの代替ではない。将来、部分一意index、ownerを0人にしない専用transaction、grant、RLS、監査ログで同じ不変条件を二重に保護する。

## 10. テスト

`backend/tests/test_authz_policy.py`は84件を持つ。

対象:

- role許可・拒否
- platform adminとtenant操作の分離
- 企業5状態と4 capability
- closed保持期限の前・ちょうど・後
- membership 3状態
- AAL 2状態
- 合成判定の優先順位
- session有効、失効、ID不一致、UTC境界
- invitation状態、期限、メール正規化
- owner actorと人数制約

テストはPython標準`unittest`だけを使用し、Supabase、ネットワーク、環境変数、既存FastAPIアプリを読み込まない。
