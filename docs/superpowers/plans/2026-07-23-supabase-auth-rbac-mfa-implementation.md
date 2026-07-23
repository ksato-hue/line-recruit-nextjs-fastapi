# Supabase Auth / RBAC / MFA 段階実装計画

> 正式設計: 添付 `2026-07-23-supabase-auth-rbac-mfa-design.md`
>
> この計画は正式設計の仕様を変更せず、実装順序、検証単位、ロールバック境界を定義する。各フェーズは `superpowers:executing-plans` と `superpowers:test-driven-development` に従い、失敗テストを先に追加して個別にレビュー・停止・ロールバックできる単位で実施する。

**作成日:** 2026-07-23

**基準コミット:** `61e0a12` (`main`, `origin/main`)

**開始時検証:** Backend `unittest` 62件すべて成功、作業ツリーはクリーン

**目的:** 現在の固定企業・共有キー方式を直ちに撤去せず、正式設計どおりの招待制Supabase Auth、企業所属RBAC、30日セッション、TOTP MFA、Google連携、企業状態、RLS、運営管理、監査・CSV出力へ段階移行する。

## 1. 計画上の不変条件

- 正式設計と競合する独自仕様を追加しない。不明事項はフェーズ開始条件として止め、推測で実装しない。
- 各フェーズで既存Backend 62件を維持し、新しい認証・RLSテストを追加する。既存の企業境界テストは削除しない。
- `Basic` 認証、`ADMIN_API_KEY`、固定 `COMPANY_ID` は代替経路の本番検証が完了するまで残す。
- 通常の利用者APIは最終的に利用者JWTで作成したSupabaseクライアントを使用し、RLSを適用する。
- Webhook、バッチ、運営操作などsecret keyが必要な経路は明示的な許可リストに限定し、SQLクエリ自体の `company_id` 条件も残す。
- secret key、SMTPパスワード、Google client secret、`ADMIN_API_KEY` はブラウザへ渡さない。`NEXT_PUBLIC_` を付けるのはSupabase URL、publishable key、公開サイトURLだけとする。
- Supabaseへの実接続、migration適用、環境変数変更、デプロイは各フェーズの明示承認後にのみ行う。
- 本番データの既存 `company_id` は文字列である。企業UUIDとの対応が承認されるまで破壊的な型変換や上書きを行わない。
- 企業状態、所属、ロール、AAL2、30日絶対期限のいずれかが不正ならfail closedとする。DB障害を「対象なし」として扱わない。

## 2. 現在の実装と正式設計との差分

### 2.1 現在確認できた事実

| 領域 | 現在の実装 | 根拠 |
|---|---|---|
| ブラウザ入口 | 全画面をBasic認証で保護 | `frontend/middleware.ts:1-52` |
| Next.js → FastAPI | Next.js Route Handlerがサーバー側の `X-Admin-Key` を付与 | `frontend/app/api/admin/[...path]/route.ts:5-68` |
| FastAPI管理API | `require_admin` が共有キーだけを検証 | `backend/main.py:40`, `backend/main.py:70-75` |
| 企業選択 | `COMPANY_ID` という単一のサーバー環境変数 | `backend/main.py:39` |
| Supabaseクライアント | `SUPABASE_KEY` で起動時にグローバルクライアントを1個生成 | `backend/main.py:2`, `backend/main.py:16-24` |
| Supabaseキー種別 | 変数名と文書からはpublishable/anon/secret/service-roleを判別不能 | `backend/.env.example:1-2`, `README.md:45-55` |
| 企業境界 | 11テーブルのアプリケーションクエリに固定 `COMPANY_ID` 条件を追加済み | `docs/SUPABASE_COMPANY_SCOPE.md` |
| RLS | checked-in migrationに `ENABLE ROW LEVEL SECURITY` / `CREATE POLICY` なし | `supabase/migrations/*.sql` |
| Auth依存 | Python/Next.jsともSupabase Auth/JWT/SSR依存なし | `backend/requirements.txt`, `frontend/package.json` |
| Auth画面 | login、callback、invite、MFA、企業選択の画面・Route Handlerなし | `frontend/app/` |
| 企業マスター | `companies` 相当テーブルなし。既存企業識別子は文字列だけ | `supabase/migrations/*.sql` |
| 既存企業列 | 11テーブルで `company_id text` | 下記「既存テーブル」 |
| デプロイ定義 | `render.yaml`、Dockerfile、Procfileはリポジトリに存在しない | リポジトリファイル一覧 |
| 回帰基準 | Backend 62件成功。外部接続はテスト用fakeで遮断 | `backend/tests/support.py:16-20`, `backend/tests/test_*.py` |

既存の `company_id` 対象テーブル:

1. `applicants`
2. `inquiries`
3. `interview_slots`
4. `line_message_logs`
5. `faq_categories`
6. `faqs`
7. `faq_settings`
8. `app_settings`
9. `question_tree_settings`
10. `applicant_status_settings`
11. `application_sessions`

既存migration:

1. `supabase/migrations/202607190001_mvp_security_foundation.sql`
2. `supabase/migrations/202607190002_admin_configuration.sql`
3. `supabase/migrations/202607200001_application_sessions.sql`
4. `supabase/migrations/202607210001_applicant_tags.sql`

### 2.2 正式設計に対して未実装のもの

- `companies`、`profiles`、`company_members`、`company_invitations`、`platform_admins`、`app_sessions`、`audit_logs`、`data_exports`
- 招待制登録、7日失効、招待先メール完全一致、最初のowner招待
- Supabase SSR / PKCE、メール＋パスワード、callback、パスワード再設定
- JWTの署名・issuer・audience・expiry・`sub`・`aal`・session ID検証
- 30日絶対期限を持つアプリケーションセッション
- owner/admin/member/platform adminの権限判定
- 複数企業所属、企業選択、企業切替
- 全利用者へのTOTP必須化とMFAリセット
- Google identity linking
- 企業状態によるread/write/LINE制御
- 利用者JWTでの通常Supabaseアクセスと、全業務テーブルのRLS
- `/admin` 運営管理画面
- 監査ログ、CSV出力、保持期限処理
- Auth導入後のBasic、共有管理APIキー、固定企業IDの撤去

### 2.3 設計実装前に確認が必要な事項

以下はリポジトリだけでは確認できない。該当フェーズを開始する前に、管理画面またはread-only調査で確定する。

- 本番 `SUPABASE_KEY` がlegacy anon、publishable、legacy service_role、secret keyのどれか
- 本番Supabaseの実スキーマ、列型、制約、既存RLS、grants、関数、トリガー、Storage bucket
- 本番に存在する文字列 `company_id` の全種類と、正式な企業名・新UUIDとの対応
- Supabase JWT signing keyが非対称鍵かlegacy shared secretか
- Supabase Authの現在の設定、Site URL、redirect allowlist、SMTP、MFA、rate limit
- LINE Channelと企業の信頼できる対応方法。現Webhookは固定 `COMPANY_ID` しか持たないため、固定値を外す前に別途決定が必要
- Renderの実サービス構成、ランタイム、環境変数、Preview/Stagingの有無、ログ・ヘルスチェック
- SMTP事業者、送信ドメイン、Fromアドレス、バウンス処理
- Google Cloudの組織、OAuth consent screenの公開範囲、利用ドメイン
- CSV保存先、最大件数、出力期限、削除ジョブの実行基盤
- Supabaseの現在の契約プランと、必要機能・上限

## 3. 推奨アーキテクチャと移行方式

### 3.1 採用する方式

**additive schema → hybrid authentication → UUID橋渡し → RLS段階有効化 → legacy撤去** の順にする。

既存 `company_id text` を一度にUUIDへ変更せず、移行中だけ `company_uuid uuid` を追加する。`companies.legacy_company_key` と承認済み対応表でbackfillし、アプリとRLSをUUIDへ切り替えた後、最終フェーズで `company_uuid` を正式な `company_id` にする。これにより、移行途中は現行固定企業経路へ戻せる。

### 3.2 採用しない方式

- **RLS先行:** 利用者JWT、所属、AAL2、企業選択がないため正しいpolicyを評価できない。
- **big-bang置換:** Auth、DB型、RLS、画面、権限、Webhookを同時に変えると、障害原因とロールバック境界を分離できない。
- **secret key常用:** RLSを迂回するため正式設計に反する。
- **JWT payloadのデコードだけ:** 署名、issuer、audience、expiry、session stateを検証できない。

### 3.3 フェーズ依存関係

```text
Phase 0: 実環境read-only事前確認
  └─ Phase 1A: 新規認証テーブル（既存業務テーブル非変更）
      └─ Phase 1B: UUID橋渡し列・private helper
          ├─ Phase 2: Next.js/FastAPI認証基盤
          │   └─ Phase 3: 招待制
          │       └─ Phase 4: RBAC
          │           └─ Phase 5: 複数企業・企業切替
          │               ├─ Phase 6: TOTP MFA
          │               │   └─ Phase 9: 業務テーブルRLS
          │               └─ Phase 7: Google連携
          └─ Phase 8: 企業状態

Phase 4 + Phase 6 + Phase 8 + Phase 9
  └─ Phase 10: /admin
      └─ Phase 11: 監査・CSV
          └─ Phase 12: Basic / ADMIN_API_KEY / 固定COMPANY_ID撤去
```

Google連携はメール＋パスワード、招待、企業選択、MFAが安定した後に追加する。RLSはAAL2、所属、ロール、企業状態の関数が揃ってから業務テーブル群ごとに有効化する。

## 4. migration一覧

予定ファイル名は実装開始時の最新migration番号と衝突しないことを再確認する。

| 順番 | 新規ファイル | 目的 | 主なロールバック |
|---|---|---|---|
| 1 | `supabase/migrations/202607230001_auth_core.sql` | companies、profiles、company_members、platform_admins | 未使用なら新規テーブルを依存順にdrop |
| 2 | `supabase/migrations/202607230002_auth_invites_sessions_audit_exports.sql` | invitations、app_sessions、audit_logs、data_exports | 未使用なら新規テーブルを依存順にdrop |
| 3 | `supabase/migrations/202607230003_auth_private_functions.sql` | AAL、所属、role、企業状態、招待受諾、owner移譲のprivate関数 | EXECUTE revoke後に関数drop |
| 4 | `supabase/migrations/202607230004_auth_tables_rls.sql` | 新規認証テーブルのRLSとgrants | policy drop。テーブルは維持 |
| 5 | `supabase/migrations/202607230005_business_company_uuid_bridge.sql` | 11業務テーブルへnullable `company_uuid`、FK、indexを追加 | アプリ未切替なら列/index/FKをdrop |
| 6 | `supabase/migrations/202607230006_daily_business_rls.sql` | applicants、inquiries、interview_slots、line_message_logs、application_sessionsのRLS | policy単位でdrop。緊急時のみ承認済み手順でRLS無効化 |
| 7 | `supabase/migrations/202607230007_settings_business_rls.sql` | FAQ・設定・status系6テーブルのRLS | policy単位でdrop |
| 8 | `supabase/migrations/202607230008_rpc_and_storage_security.sql` | `complete_application_session`、Storage、関数grantの安全化 | 旧関数をversioned名で保持し呼出先を戻す |
| 9 | `supabase/migrations/202607230009_company_lifecycle_retention.sql` | 企業状態、監査・export保持期限のDB関数 | schedulerを先に停止し関数drop |
| 10 | `supabase/migrations/202607230010_company_id_cutover.sql` | 十分な併存後、text列を廃止しUUID列を正式 `company_id` 化 | 本番バックアップと逆変換表がある場合のみ。通常はforward fix |

### 4.1 主要SQL制約

実装前に実スキーマを取得し、名前・型・参照先を正式設計と照合する。少なくとも次をSQLで保証する。

- 主キーは正式設計どおりUUIDとする。アプリが新規採番するIDは `gen_random_uuid()`、`profiles.user_id` / `platform_admins.user_id` は `auth.users(id)`、`app_sessions.session_id` は検証済みJWTのsession IDを正本とする。
- `companies` は正式設計の `name`、`status`、`is_monitor`、`monitor_started_at`、`monitor_ends_at`、`closed_at`、`data_delete_at`、作成・更新日時を持つ。`closed` の削除予定は原則 `closed_at + 1 year` とする。
- `profiles.user_id` は `auth.users.id` と1対1で、`display_name`、`last_company_id`、`last_login_at`、作成・更新日時を持つ。メールの正本はAuthとし、profileへ権限情報を複製しない。
- `company_members(company_id, user_id)` は一意。
- `company_members.role` は `owner | admin | member` のCHECKまたはenum。
- `company_members.status` は `pending | active | suspended`。所属権限はDBのactive membershipを正本にし、`user_metadata` を使わない。
- 企業ごとのactive ownerは部分一意indexで1名だけにする。owner移譲は単一transactionのSECURITY DEFINER関数だけに許可する。
- `company_invitations` はtoken平文を保存せずSHA-256 hashを一意保存し、`expires_at = created_at + 7 days`、使用済み・取消済み状態を持つ。
- `company_invitations.status` は `pending | accepted | revoked | expired` とし、`invited_by_user_id`、`accepted_by_user_id`、`accepted_at` を正式設計どおり保持する。
- 同一企業・同一正規化メールの未使用招待は一意。
- 招待受諾は認証済みのverified email完全一致、未使用、有効期限内を1 transactionで確認する。
- `app_sessions` はSupabase session ID、user ID、作成、最終利用、絶対期限、失効日時を持ち、`absolute_expires_at <= created_at + interval '30 days'`。
- `companies.status` は `monitor_active | monitor_expired | active | suspended | closed`。
- `profiles.last_company_id` は所属確認後だけ更新する。
- `platform_admins.user_id` は一意。業務データへのFKや閲覧権限を持たせない。
- `audit_logs` はactor、action、target type/id、company metadata、timestamp、IP/user-agent等の最小情報だけとし、応募者PII・LINE本文・secretを禁止する。
- `data_exports` は要求者、企業、状態、保存object path、有効期限を持ち、LINE本文を含めない。
- 全tenant FKは可能なら `(company_id, id)` の複合FKで企業間参照をDBでも拒否する。
- 既存text企業IDは `companies.legacy_company_key` の一意値として移行期間だけ保持する。
- public schemaへviewを追加する場合は `security_invoker` を明示するか、公開しない。権限判定を `user_metadata` に依存させない。

### 4.2 RLS方針

- 全public業務テーブルでRLSを有効化し、ownerによるtable bypassを前提にしない。
- `SELECT`: verified user、`aal2`、有効app session、active membership、選択企業一致、企業状態がread可能。
- `INSERT`: 上記に加え、JWT/選択企業と挿入 `company_id` が一致。書込可能状態とroleを確認。
- `UPDATE`: `USING` と `WITH CHECK` の両方で同じ企業、role、状態を確認。
- `DELETE`: `USING` で同じ企業と管理権限を確認。対象ごとにowner/admin限定を定義する。
- `monitor_expired` と `closed` はread-only、`suspended` は利用者アクセス不可、`monitor_active` と `active` は正式設計の範囲でread/write可。
- 全policyは `auth.uid()`、AAL、所属、企業状態をprivate schemaの小さなhelperで評価する。
- SECURITY DEFINER関数は固定 `search_path`、所有者固定、public EXECUTE revoke、必要ロールだけgrantする。
- platform adminを通常業務policyへ含めない。運営APIは企業メタデータと集計だけを専用関数で扱う。
- secret key経路はRLSを迂回し得るため、Webhook/ジョブ/運営操作の関数・モジュールを許可リスト化し、明示的 `company_id` 条件を維持する。

## 5. フェーズ別実装タスク

### Phase 0: 実環境と移行前提のread-only確認

**依存:** なし

**変更ファイル:**

- Create: `docs/superpowers/specs/2026-07-23-supabase-auth-rbac-mfa-design.md`（正式添付の同一内容をリポジトリへ定着。内容変更禁止）
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Create: `docs/runbooks/auth-migration-preflight.md`

**先に書く失敗検査:**

- migration一覧に存在しない本番object、未把握のRLS、null/未知の企業IDがあればpreflightを失敗させるread-only検査を作る。
- secret/service-role相当キーがフロントエンドやbuild artifactに存在すれば失敗するsecret scanを追加する。

**タスク:**

1. 正式添付を上記specパスへbyte-equivalentに保存し、今後のPRで設計変更と実装変更を分離する。
2. Supabase CLIを開発依存として導入するか、固定versionの実行手順を決める。
3. local Supabaseへ現在のmigrationを適用し、SQL lintとschema diffを取得する。
4. 承認を得て本番をread-only調査し、全table/column/type/FK/index/policy/grant/function/trigger/storageを保存する。データ値は必要最小限とし、PIIを文書へ残さない。
5. `select distinct company_id` の件数と値を管理者確認用に出し、新UUID・正式企業名との対応表をGit外の安全な場所で承認する。
6. `SUPABASE_KEY` の種別、JWT signing方式、Render runtime、現在の外部URLを確認する。
7. LINE channel → companyの信頼できる対応を決定するまで、Webhookの固定 `COMPANY_ID` 撤去をブロックする。

**ロールバック:** read-only調査と文書追加のみ。文書PRをrevertできる。

**完了条件:** 不明な本番schema差分がなく、company mappingとキー種別が承認されている。

### Phase 1A: DB認証基盤（新規テーブルのみ）

**依存:** Phase 0

**変更・作成ファイル:**

- Create: `supabase/config.toml`
- Create: `supabase/migrations/202607230001_auth_core.sql`
- Create: `supabase/migrations/202607230002_auth_invites_sessions_audit_exports.sql`
- Create: `supabase/tests/000_auth_schema.test.sql`
- Create: `supabase/tests/001_auth_constraints.test.sql`
- Modify: `README.md`
- Modify: `docs/CODEBASE_AUDIT.md`

**先に書く失敗テスト:**

- 必須table、PK、FK、unique、CHECK、部分一意owner indexがないため失敗するpgTAP。
- 二人目のactive owner、重複membership、8日先の招待期限、不正role、不正company status、31日app sessionをINSERTして拒否されないため失敗するテスト。

**タスク:**

1. 8テーブルを追加するが、既存業務テーブルとAPIは変更しない。
2. `companies.legacy_company_key` は移行専用nullable unique列として追加する。
3. timestampは`timezone`付き、更新対象には一貫した`updated_at` triggerを適用する。
4. local DBへresetしてpgTAPをGREENにする。
5. 既存Backend 62件が無変更でGREENであることを確認する。

**ロールバック:** 利用開始前なら新規テーブルを依存順にdropするdown手順をrunbookへ記録する。本番適用後はmigration fileを編集せず新しいforward migrationを使う。

**最小実装フェーズ:** 最初に実装するのはこのPhase 1Aとする。既存認証・業務経路に触れず、正式設計のデータ制約をlocal DBで検証できる最小単位だからである。

### Phase 1B: private helperと企業UUID橋渡し

**依存:** Phase 1A、承認済みcompany mapping

**変更・作成ファイル:**

- Create: `supabase/migrations/202607230003_auth_private_functions.sql`
- Create: `supabase/migrations/202607230004_auth_tables_rls.sql`
- Create: `supabase/migrations/202607230005_business_company_uuid_bridge.sql`
- Create: `supabase/tests/002_auth_helpers.test.sql`
- Create: `supabase/tests/003_auth_tables_rls.test.sql`
- Create: `supabase/tests/004_company_uuid_bridge.test.sql`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`

**先に書く失敗テスト:**

- aal1、非member、期限切れapp session、別企業、suspended企業でhelperがtrueになる失敗。
- public/anonがhelperを直接実行できる失敗。
- 未対応text企業ID、null、FK不一致、企業間複合参照を許す失敗。

**タスク:**

1. helperはprivate schemaへ作成し、固定`search_path`と最小grantを設定する。
2. 新規認証テーブルへRLSを設定する。profilesは本人最小情報、membershipは本人所属、招待は権限経路に限定する。
3. 11業務テーブルへnullable `company_uuid`、FK、indexを追加する。
4. 承認済み対応表からbackfillし、未知値が1件でもあれば中止する。
5. `company_uuid is null` 件数が0であることを確認しても、正式切替までtext列は残す。

**ロールバック:** アプリがUUIDを参照する前ならbridge列とindex/FKをdropできる。RLSは新規認証テーブルのpolicyだけをdropし、業務RLSはまだ有効化しない。

### Phase 2: Next.js・FastAPI認証基盤

**依存:** Phase 1A。所属判定の本番利用はPhase 1B

**変更・作成ファイル:**

- Modify: `backend/requirements.txt`
- Create: `backend/auth_config.py`
- Create: `backend/auth_models.py`
- Create: `backend/jwt_verifier.py`
- Create: `backend/supabase_clients.py`
- Create: `backend/auth_dependencies.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_jwt_verifier.py`
- Create: `backend/tests/test_auth_dependencies.py`
- Create: `backend/tests/test_supabase_clients.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/lib/supabase/client.ts`
- Create: `frontend/lib/supabase/server.ts`
- Create: `frontend/lib/supabase/middleware.ts`
- Modify: `frontend/middleware.ts`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/forgot-password/page.tsx`
- Create: `frontend/app/reset-password/page.tsx`
- Create: `frontend/app/auth/callback/route.ts`
- Create: `frontend/app/account-blocked/page.tsx`
- Modify: `frontend/app/api/admin/[...path]/route.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/auth-proxy.test.ts`
- Modify: `backend/.env.example`
- Modify: `frontend/.env.local.example`
- Modify: `README.md`

**依存version方針:**

- 実装日に公式最新版とNode互換性を再確認し、caretではなく再現可能なversionへ固定する。
- 2026-07-23時点の候補は `supabase==2.31.0`、`PyJWT==2.13.0`、`@supabase/ssr@0.12.3`、`@supabase/supabase-js@2.110.7`。
- `@supabase/supabase-js` 最新版のNode要件を満たすためRenderとローカルをNode 22へ固定してから導入する。満たせない場合は互換versionを公式release noteから選び、理由を記録する。

**先に書く失敗テスト:**

- 署名なし、改ざんJWT、誤issuer、誤audience、期限切れ、未来の`nbf`、未知kid、`sub`なし、`role != authenticated`、`aal1`、session IDなし、app sessionなし/失効/30日超過を拒否できないテスト。
- JWKS取得失敗を認証成功や404へ変換しないテスト。
- 通常利用者クライアントがsecret keyを使用する、利用者JWTを付けないテスト。
- Next.js proxyがcookie/sessionなしでも転送する、Bearerや選択企業を転送しない、secretをレスポンスへ出すテスト。
- callbackの`next`が外部URLへopen redirectできるテスト。

**タスク:**

1. JWTは公式JWKSで署名を検証し、issuer、`aud='authenticated'`、expiry、存在時の`nbf`、`sub`、`role='authenticated'`、`aal`、session IDを検証する。legacy shared secretの場合は勝手にブラウザ検証へ使わず、公式Auth `/user` 検証またはsigning key移行を先に行う。
2. JWKSはTTL付きcacheとkey rotation時の再取得を実装する。障害時はfail closedにする。
3. `AuthContext` にuser ID、verified email、AAL、app session、選択企業、membership、role、company statusだけを格納する。
4. 通常API用Supabase clientはpublishable key＋利用者Bearer tokenでrequest単位に生成する。secret clientは別factory・別型・許可モジュールに限定する。
5. Next.jsはSSR/PKCEのbrowser/server clientを分け、本番cookieへSecure、HttpOnly、適切なSameSiteを設定する。Route HandlerのmutationにはOrigin/CSRF検証を追加する。
6. `frontend/middleware.ts` に `AUTH_MODE=legacy|hybrid|supabase` を導入する。hybrid中は既存Basic経路を残し、Supabase利用者経路は別判定とする。
7. Route Handlerは検証済みaccess tokenを `Authorization: Bearer` で転送し、選択企業を署名済みサーバーセッションから `X-Company-ID` として転送する。ブラウザ入力だけを信用しない。
8. hybrid中のみ `X-Admin-Key` を併送できるが、FastAPIはSupabase経路とlegacy経路を明確に区別する。
9. login、callback、forgot/resetの最小画面を追加する。公開ルートallowlistを狭く保つ。
10. このフェーズでは全業務routeを一括置換せず、read-only health/auth確認routeから導入する。
11. 正式設計のHTTP契約を共通error modelで固定する: 無効JWTは401、MFA未完了は403 `MFA_REQUIRED`、30日超過は401 `SESSION_EXPIRED`、停止membershipは403 `MEMBERSHIP_SUSPENDED`、read-only企業へのwriteは403 `COMPANY_READ_ONLY`、停止企業は403 `COMPANY_SUSPENDED`、role不足は403 `INSUFFICIENT_ROLE`、期限切れ招待は410 `INVITATION_EXPIRED`。業務データIDの他社所属は404を優先し、存在を漏らさない。

**ロールバック:** `AUTH_MODE=legacy` で既存Basic＋共有キーへ戻せる。新しいAuthコードは残し、cookieを無効化する。DB新規tableは破壊しない。

### Phase 3: 招待制

**依存:** Phase 2、Auth email/password設定

**変更・作成ファイル:**

- Create: `backend/invitations.py`
- Create: `backend/mailer.py`
- Create: `backend/routes/invitations.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_invitations.py`
- Create: `frontend/app/invite/[token]/page.tsx`
- Create: `frontend/lib/invitations.ts`
- Create: `frontend/tests/invite-flow.test.ts`
- Create: `supabase/tests/005_invitation_flow.test.sql`
- Modify: `backend/.env.example`
- Modify: `README.md`

**先に書く失敗テスト:**

- 未招待登録、期限切れ、使用済み、取消済み、token hash不一致、認証メールの大文字小文字正規化後不一致、別企業招待を拒否できないテスト。
- owner以外のメンバー招待、二重受諾、同時受諾、owner二重作成を許すテスト。
- 招待tokenやSMTP secretがログ・監査へ残るテスト。

**タスク:**

1. public signupを無効にし、招待tokenは十分なentropyのrandom値を一度だけ表示、DBにはSHA-256 hashだけ保存する。
2. 7日失効、メール完全一致、pending membership作成、最初のowner一意を保証する。招待はTOTP完了前にacceptedへせず、Phase 6のaal2到達後に同一transactionでmembershipをactive、招待をaccepted、`app_sessions`を作成する。
3. platform adminが最初のowner招待、ownerだけが同企業のmember/admin招待を行えるAPIを作る。
4. 招待URLは `/invite/[token]`。認証後のverified emailと一致しない場合は内容を漏らさず拒否する。
5. SMTP送信失敗と招待作成成功を区別し、安全な再送・取消を実装する。
6. Phase 3単独では招待経路をstaging/feature flag内に留め、Phase 6のTOTP必須化と原子的な受諾処理がGREENになるまで本番利用者へ公開しない。

**ロールバック:** 新規招待の発行を停止し、未使用招待をrevokeする。作成済みmembershipは監査付きで個別に戻す。公開signupは有効化しない。

### Phase 4: RBAC

**依存:** Phase 3

**変更・作成ファイル:**

- Modify: `backend/auth_dependencies.py`
- Create: `backend/authorization.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_rbac.py`
- Create: `backend/tests/test_route_authorization_matrix.py`
- Create: `frontend/lib/authorization.ts`
- Modify: `frontend/app/page.tsx`
- Create: `supabase/tests/006_role_constraints.test.sql`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`

**先に書く失敗テスト:**

- memberが設定、招待、export、企業管理を変更できるテスト。
- adminがowner移譲、owner削除、platform操作を実行できるテスト。
- UI非表示だけでBackend APIを直接呼べるテスト。
- platform adminが応募者・問い合わせ・LINE本文を読めるテスト。

**タスク:**

1. 正式設計のrole matrixをBackend dependency、RLS、UIで同じ定数・文書から実装する。
2. 日常業務、設定、メンバー管理、owner専用、platform専用にrouteを分類する。
3. owner移譲はplatform admin専用transactionに限定する。
4. UI制御は利便性のみとし、BackendとRLSを権限の正本にする。

**ロールバック:** route単位feature flagで新Auth経路を止める。roleを広げる緊急変更は行わず、legacy経路へ限定的に戻す。

### Phase 5: 複数企業所属・企業切り替え

**依存:** Phase 4

**変更・作成ファイル:**

- Create: `backend/routes/account.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_company_selection.py`
- Create: `frontend/app/select-company/page.tsx`
- Create: `frontend/components/company-switcher.tsx`
- Create: `frontend/lib/company-session.ts`
- Modify: `frontend/app/api/admin/[...path]/route.ts`
- Modify: `frontend/app/page.tsx`
- Create: `frontend/tests/company-switch.test.ts`

**先に書く失敗テスト:**

- 非所属企業を選択できる、削除済みmembershipを継続利用できる、別tabの旧企業データが残るテスト。
- ブラウザが任意の `X-Company-ID` を指定して越境できるテスト。
- 同じ利用者が複数企業に所属する場合に前回企業を誤って選ぶテスト。

**タスク:**

1. `/api/auth/companies` と `/api/auth/select-company` を追加し、選択対象membershipをサーバーで再確認する。
2. 選択企業をHttpOnly sessionへ保存し、`profiles.last_company_id` は有効所属の場合だけ更新する。
3. 複数所属時は `/select-company`、1社時は自動選択する。
4. 企業切替は正式設計どおりfull reloadし、全query cacheと画面stateを破棄する。
5. 各FastAPI requestでmembershipを再評価し、header単独を信用しない。

**ロールバック:** company switcherを無効化し、既存1社だけをサーバー選択する。固定 `COMPANY_ID` はlegacy利用者のみに残す。

### Phase 6: TOTP MFA必須化

**依存:** Phase 5

**変更・作成ファイル:**

- Modify: `backend/auth_dependencies.py`
- Create: `backend/routes/mfa_admin.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_mfa_enforcement.py`
- Create: `frontend/app/mfa/setup/page.tsx`
- Create: `frontend/app/mfa/verify/page.tsx`
- Create: `frontend/lib/mfa.ts`
- Modify: `frontend/middleware.ts`
- Create: `frontend/tests/mfa-routing.test.ts`
- Create: `supabase/tests/007_aal2_policies.test.sql`

**先に書く失敗テスト:**

- aal1で管理画面/API/RLSへ到達できる、TOTP未登録者が通常画面へ進める、MFAリセット後も旧aal2 sessionを使えるテスト。
- platform adminだけに限定すべきMFA resetをowner/adminが実行できるテスト。

**タスク:**

1. 初回login後、未登録者を `/mfa/setup` へ強制する。
2. TOTP enroll → challenge → verify後に新しいaal2 claimを取得する。
3. middleware、FastAPI、RLSの三層でaal2を必須にする。
4. MFA resetは本人確認済みのplatform admin操作として監査し、既存sessionをすべて失効させる。
5. recovery codeやsupport手順は正式設計に記載がないため独自追加せず、必要なら設計変更PRを先に行う。

**ロールバック:** rollout対象者feature flagを段階的に戻せるが、本番でaal2を解除する場合はsecurity incidentとして記録する。RLS policy変更はversioned migrationで行う。

### Phase 7: Googleアカウント連携

**依存:** Phase 3、Phase 5、Phase 6

**変更・作成ファイル:**

- Create: `frontend/app/account/page.tsx`
- Create: `frontend/components/google-identity-link.tsx`
- Modify: `frontend/app/auth/callback/route.ts`
- Create: `frontend/tests/google-linking.test.ts`
- Create: `backend/tests/test_google_identity_claims.py`
- Modify: `docs/runbooks/auth-migration-preflight.md`

**先に書く失敗テスト:**

- 招待メールと異なるGoogle email、未verified email、別userへ既存identityをlink、state/PKCE不一致、外部redirectを許すテスト。
- Google provider token/client secretをcookie、ログ、Backend、ブラウザbundleへ残すテスト。

**タスク:**

1. メール＋パスワードで作成済みの同一利用者へGoogle identityを明示的にlinkする。
2. Supabaseのmanual linking機能が実装時点で利用可能か、beta条件と安全性を公式文書で再確認してから有効化する。
3. callbackはPKCEとallowlisted相対redirectだけを許可する。
4. Google access/refresh tokenは業務要件に不要なので保存・Backend転送しない。
5. Google login後もTOTP aal2を必須にする。

**ロールバック:** Google providerとlink UIを無効化する。メール＋パスワード＋TOTP経路を維持し、既存identityを無断でunlinkしない。

### Phase 8: 企業状態

**依存:** Phase 4。RLS完全適用はPhase 6後

**変更・作成ファイル:**

- Create: `backend/company_access.py`
- Modify: `backend/auth_dependencies.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_company_states.py`
- Create: `backend/tests/test_webhook_company_state.py`
- Create: `frontend/components/company-state-banner.tsx`
- Modify: `frontend/app/page.tsx`
- Create: `supabase/tests/008_company_state_access.test.sql`

**先に書く失敗テスト:**

- `monitor_expired`/`closed`がwriteできる、`suspended`がreadできる、停止企業へLINE送信・Webhook進行できるテスト。
- 別企業の状態で自社アクセスが決まるテスト。
- DB障害をinactive/対象なしへ変換するテスト。

**タスク:**

1. 正式設計の状態行列を単一の定義にし、Backend、RLS、UIへ反映する。
2. read-only状態のmutationは明示的403とし、存在の有無を漏らさない。
3. LINE送信、Webhookの状態遷移、定期処理にも企業状態を適用する。
4. Webhookの企業決定は承認済みchannel-company mappingを使う。決まるまでは固定 `COMPANY_ID` を維持し、この経路だけ未完了とする。

**ロールバック:** 状態変更を監査付きで前状態へ戻せる。コードを戻してもDBのstatus履歴は保持する。

### Phase 9: 業務テーブルRLSと通常APIの利用者JWT化

**依存:** Phase 1B、Phase 4、Phase 6、Phase 8

**変更・作成ファイル:**

- Create: `supabase/migrations/202607230006_daily_business_rls.sql`
- Create: `supabase/migrations/202607230007_settings_business_rls.sql`
- Create: `supabase/migrations/202607230008_rpc_and_storage_security.sql`
- Create: `supabase/tests/009_daily_business_rls.test.sql`
- Create: `supabase/tests/010_settings_business_rls.test.sql`
- Create: `supabase/tests/011_rpc_security.test.sql`
- Modify: `backend/supabase_clients.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_rls_client_routing.py`
- Create: `backend/tests/test_service_client_allowlist.py`
- Modify: `backend/tests/support.py`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`

**先に書く失敗テスト:**

- 11テーブルそれぞれのSELECT/INSERT/UPDATE/DELETEで、別企業、aal1、無所属、不正role、read-only/suspended状態を許すpgTAP。
- 同一ID・同一line_user_id・同一質問文が別企業にあるケースで越境するテスト。
- secret clientが通常管理APIで使われる、利用者JWT clientがWebhookで誤使用されるテスト。
- `complete_application_session` がcompany/role/aal2を迂回するテスト。

**タスク:**

1. 日常業務5テーブルと設定6テーブルを別migrationで有効化する。
2. 通常APIをrequest-scoped利用者JWT clientへroute群単位で切り替える。アプリ側の明示company条件は防御層として残す。
3. Webhook/ジョブはsecret client allowlistに残し、全query/RPCへcompany条件を保持する。
4. RPCの引数だけを信用せず、実行者とcompanyをDB内で検証する。
5. local pgTAP、Backend fake、stagingの実JWT E2Eを順にGREENにしてから次のtable群へ進む。
6. 全policy適用後も既存62件を残し、テストfakeのpatch境界を一度に壊さない。

**ロールバック:** table群単位で新API routeをlegacy clientへ戻す。RLS無効化は最終手段で、承認済み緊急migrationのみ許可する。旧policy/migrationを編集しない。

### Phase 10: 運営管理画面 `/admin`

**依存:** Phase 4、Phase 6、Phase 8、Phase 9

**変更・作成ファイル:**

- Create: `backend/routes/platform_admin.py`
- Create: `backend/platform_admin_service.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_platform_admin.py`
- Create: `backend/tests/test_platform_admin_privacy.py`
- Create: `frontend/app/admin/layout.tsx`
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/app/admin/companies/page.tsx`
- Create: `frontend/app/admin/companies/[companyId]/page.tsx`
- Create: `frontend/app/admin/audit/page.tsx`
- Create: `frontend/lib/platform-admin-api.ts`
- Create: `frontend/tests/platform-admin-boundary.test.ts`

**先に書く失敗テスト:**

- 通常ownerが `/admin` を使える、platform adminが応募者・問い合わせ・LINE本文を取得できるテスト。
- platform admin権限を自己付与できる、owner移譲が非transaction、MFA reset後にsessionが残るテスト。

**タスク:**

1. `/admin` は通常企業UIとroute/API moduleを分離する。
2. 企業metadata、状態、owner招待/移譲、MFA reset、件数集計、監査だけを提供する。
3. 応募者PII、問い合わせ本文、LINE本文、FAQ本文などの業務内容を返すendpointを作らない。
4. `platform_admins` 登録は手動の承認済みDB操作だけとし、画面から自己昇格させない。
5. 初期の利用状況表示は正式設計どおり有効なadmin/member数を対象とし、決済情報や請求処理は追加しない。

**ロールバック:** `/admin` feature flagとrouteを停止する。platform admin tableと監査は保持する。

### Phase 11: 監査ログ・CSV出力・保持期限

**依存:** Phase 10

**変更・作成ファイル:**

- Create: `supabase/migrations/202607230009_company_lifecycle_retention.sql`
- Create: `supabase/tests/012_audit_export_retention.test.sql`
- Create: `backend/audit_service.py`
- Create: `backend/export_service.py`
- Create: `backend/routes/exports.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_audit_service.py`
- Create: `backend/tests/test_exports.py`
- Create: `backend/tests/test_retention_jobs.py`
- Create: `frontend/app/exports/page.tsx`
- Create: `frontend/lib/exports.ts`
- Create: `docs/runbooks/audit-export-retention.md`

**先に書く失敗テスト:**

- role/状態/他社境界を越えたexport、LINE本文を含むexport、CSV formula injection、public bucket、期限超過downloadを許すテスト。
- 監査へPII/token/secretが入る、重要操作の監査が欠ける、1年超過auditが削除候補にならないテスト。

**タスク:**

1. Auth、招待、role、企業状態、MFA reset、export、owner移譲を監査する。
2. audit payload allowlistを作り、自由形式request bodyを保存しない。
3. CSVは企業・role・状態を再検証し、LINE本文を除外し、formula injectionをneutralizeする。
4. private Storage bucketへ保存し、短時間signed URLだけを発行する。
5. audit 1年、exportの短期保持を削除する関数を作る。
6. schedulerはRender CronまたはSupabaseの利用可能機能を費用・運用とともに比較し、承認後にどちらか一方だけ設定する。
7. `data_delete_at` 到達前にplatform admin画面とownerへ通知し、削除jobは企業IDと対象件数を監査する。他企業membershipがあるAuth userは削除しない。

**ロールバック:** 新規export受付とschedulerを停止する。既存監査は削除しない。Storage objectは保持期限runbookに従う。

### Phase 12: legacy認証と固定企業の段階的撤去

**依存:** Phase 2-11の本番安定、全利用者移行、rollback window経過

**変更・作成ファイル:**

- Create: `supabase/migrations/202607230010_company_id_cutover.sql`
- Modify: `backend/main.py`
- Modify: `backend/auth_config.py`
- Modify: `backend/supabase_clients.py`
- Modify: `backend/.env.example`
- Modify: `frontend/middleware.ts`
- Modify: `frontend/app/api/admin/[...path]/route.ts`
- Modify: `frontend/.env.local.example`
- Modify: `README.md`
- Modify: `docs/security-decisions.md`
- Modify: `docs/SUPABASE_COMPANY_SCOPE.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `backend/tests/test_security_boundaries.py`
- Create: `backend/tests/test_legacy_auth_removed.py`
- Create: `frontend/tests/legacy-auth-removed.test.ts`
- Create: `docs/runbooks/auth-cutover.md`

**先に書く失敗テスト:**

- Basicだけ、`X-Admin-Key`だけ、固定 `COMPANY_ID`だけで通常APIへ到達できるテスト。
- secret keyが通常API clientで使われるテスト。
- text企業ID列やtransition envへ依存するrouteを静的棚卸しで検出するテスト。
- Webhookの企業mapping未確定でも固定値を削除できてしまうcutover checklist。

**タスク:**

1. 2週間以上の安定期間、全利用者MFA、legacy trafficゼロ、全RLS/E2E GREENをcutover gateとする。
2. まずNext.jsのBasicを無効化し、Supabase loginだけにする。
3. 次に通常APIの `X-Admin-Key` fallbackを無効化する。Webhook/ジョブの専用認証は別物として維持する。
4. 通常APIから固定 `COMPANY_ID` を除き、選択企業＋membershipへ統一する。
5. Webhookは承認済みchannel-company mappingが動作してから固定値を撤去する。
6. 全行UUID backfill、FK、RLS、コード参照を再確認後、bridgeを正式 `company_id` へcutoverする。
7. Renderのlegacy secretをローテーション後に削除する。
8. 既存セキュリティテストは「削除」ではなく、新仕様で旧認証を拒否する回帰テストへ置換する。

**ロールバック:** UI/APIはcutover window内なら `AUTH_MODE=hybrid` へ戻す。UUID schema cutoverは原則forward fixとし、本番backup・対応表・rehearsalなしには実行しない。

## 6. Basic認証との併存期間

| 段階 | Browser入口 | Next.js → FastAPI | 企業決定 | Supabase |
|---|---|---|---|---|
| 現在 | Basic | `X-Admin-Key` | 固定 `COMPANY_ID` | 単一server key |
| Phase 2 hybrid | BasicまたはSupabase session | legacy keyまたはBearer＋selected company | legacyは固定、Authはmembership | legacy global client＋新request client |
| Phase 5-9 | Supabaseを標準、Basicは緊急rollback対象 | Bearerを標準、key fallbackは監視 | membershipを標準 | 通常JWT、secret allowlist |
| Phase 12 | Supabaseのみ | Bearerのみ | membership＋Webhook mapping | 通常JWT、限定secret |

併存中も同じrequestでどちらを採用したかを明確にし、Basic利用者をSupabase利用者として偽装しない。legacy trafficをPIIなしの監査metricで観測し、ゼロになってから撤去する。

## 7. 外部サービス設定

### 7.1 Supabase Dashboard

実装・staging・productionを分離し、Dashboard変更は二者確認で記録する。

- Auth URL Configuration:
  - production Site URL
  - `/auth/callback`、password reset、inviteに必要な正確なredirect URL
  - wildcardではなく環境別allowlist
- Email/Password:
  - public signupを無効化し招待制にする
  - minimum password length 12以上と文字要件
  - leaked password protectionは契約プランと費用を確認して有効化
  - rate limit、CAPTCHA要否を確認
- MFA:
  - TOTP enrollment/verificationを有効化
  - aal2のJWT claimをstagingで確認
- SMTP:
  - custom SMTP、From、sender name
  - SPF、DKIM、DMARC
  - invite、signup confirmation、password reset、email changeのtemplate
- Google provider:
  - Google client ID/secret
  - Supabaseが表示するcallback URLをGoogleへ正確に登録
  - manual identity linkingの提供状態とbeta条件を確認
- JWT:
  - asymmetric signing keyを推奨
  - JWKS URL、issuer、audience、rotation手順
  - legacy shared secretなら先にsigning key移行計画を実施
- API keys:
  - frontend用publishable key
  - Backend secret key
  - 旧keyはcutover後にrotation/revoke
- Storage:
  - private `data-exports` bucket
  - signed URL期限、object size、保持期限
- Database:
  - migration history、RLS、grants、Security Advisor
  - platform admin初期登録は手動承認

### 7.2 Google Cloud Console

- 管理対象projectとownerを確定する。
- OAuth consent screenのbranding、support email、authorized domain、audienceを設定する。
- scopeは `openid email profile` の最小限とする。
- Web application OAuth clientを作成する。
- authorized JavaScript originsにstaging/productionの正確なHTTPS originを登録する。
- authorized redirect URIにSupabase Dashboardが示すcallback URIを完全一致で登録する。
- client secretはSupabase Dashboardだけに登録し、Render/Next.js browser/リポジトリへ置かない。
- consent screen公開・verification要否とリードタイムを本番日程前に確認する。

### 7.3 Render環境変数

**Frontend server-only:**

- `BACKEND_API_BASE_URL`
- `AUTH_MODE`（移行中のみ）
- `ADMIN_API_KEY`（併存中のみ）
- `ADMIN_BASIC_USERNAME`（併存中のみ）
- `ADMIN_BASIC_PASSWORD`（併存中のみ）

**Frontend public:**

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_SITE_URL`

**Backend server-only:**

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_JWT_ISSUER`
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_JWKS_URL`
- `AUTH_MODE`（移行中のみ）
- `TENANT_MODE`（移行中のみ）
- `ADMIN_API_KEY`（併存中のみ）
- `COMPANY_ID`（legacy/Webhook mapping完了まで）
- 既存LINE secret/token
- SMTPをアプリから直接使う場合のみ `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM_EMAIL`、`SMTP_FROM_NAME`

**Render設定:**

- Node 22を明示する。
- production/stagingのEnvironment Groupを分離する。
- secretをPreviewへ自動複製しない。
- health checkとdeploy前migration jobを分け、Web service起動時にmigrationを自動実行しない。
- 変更後に環境変数名だけを確認し、値をログへ出さない。

### 7.4 メール送信設定

- Supabase Authメールはcustom SMTPを使用し、既定SMTPを本番配信に使わない。
- 独自招待URLをアプリ側で送る場合も同じ送信ドメイン・認証済みFromを使う。
- sandbox/staging宛先制限、送信rate limit、bounce/complaintの運用窓口を決める。
- token、パスワード、利用者存在有無をログ・エラーメッセージへ出さない。
- 招待、期限切れ、再送、取消、password reset、MFA resetのテンプレートを日本語でレビューする。

### 7.5 費用が発生し得る設定

- Supabase有料プラン、DB/Storage/egress超過、バックアップ、leaked password protection等のプラン限定機能
- custom SMTP事業者、専用IP、送信ドメイン運用
- Render staging service、Cron Job/background worker、追加帯域
- CSV Storage容量とdownload帯域
- Google OAuth自体の基本login以外に必要となる組織審査・外部支援。通常の設定に直接費用がない場合も、審査リードタイムは見込む

TOTPはSupabase公式上すべてのprojectで利用できるが、実装時点の料金・上限を再確認する。外部サービスの契約や有料機能の有効化は別承認とする。

## 8. テスト戦略

### 8.1 既存62件への影響

- `backend/tests/support.py` はimport時の `supabase.create_client` をpatchし、`main.supabase` を差し替える。クライアント分離を先に行うと全企業境界テストのfake境界が壊れる。
- Phase 2ではlegacy用 `main.supabase` を残し、新Auth client factoryを別moduleで追加する。
- Phase 9でroute群単位に新factoryへ切り替え、そのrouteの既存企業境界テストと新RLS client routing testを同時にGREENにする。
- `test_security_boundaries.py` のBasic/API key期待はPhase 12まで維持する。撤去時は旧方式を拒否するテストへ置換し、カバレッジを減らさない。
- テストはSupabase実接続なしのunit/fake、local SupabaseのpgTAP、staging E2Eを層別にする。

### 8.2 共通検証コマンド

各タスクでfocused RED → focused GREEN → 全体GREENの順に実行する。

```powershell
# Backend focused
Push-Location backend
python -m unittest tests.test_<target> -v
Pop-Location

# Backend全件
Push-Location backend
python -m unittest discover -s tests -v
Pop-Location

# Python構文検査
$env:PYTHONDONTWRITEBYTECODE='1'
python -c "import ast,pathlib; files=list(pathlib.Path('backend').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8')) for p in files]; print(f'Python AST: {len(files)} files OK')"

# Frontend unit/type/build
Push-Location frontend
npm test -- --run
npm exec tsc -- --noEmit --incremental false
npm run build
Pop-Location

# local Supabase（Docker利用、live接続なし）
npx supabase start
npx supabase db reset
npx supabase db lint --local
npx supabase test db

# 差分
git diff --check
git diff --stat
git status --short
```

dependency追加時はlockfile差分と既知脆弱性をレビューする。`npm audit fix --force` や無条件のmajor updateは行わない。

### 8.3 RLSテスト行列

各tableの各operationで最低限以下を組み合わせる。

- same company / other company
- owner / admin / member / non-member / platform admin
- aal1 / aal2
- valid / revoked / 30日超過app session
- monitor_active / monitor_expired / active / suspended / closed
- duplicate record ID、line_user_id、質問文、status名
- direct table access / RPC / FastAPI
- publishable user JWT / secret client

成功結果だけでなく、他社行が変更されていないこと、DB障害がnot-foundへ変換されないこと、実クエリまたはpolicyに企業条件があることを検証する。

## 9. 本番切り替え手順

1. 本番と同等のstagingを用意し、匿名化したschema/data形状で全migrationをrehearsalする。
2. 本番backup、schema dump、company mapping、rollback owner、停止判断基準を承認する。
3. Phase 1A/1Bのadditive migrationを先行適用し、既存サービスに影響がないことを確認する。
4. Auth/SMTP/redirect/MFA設定をstagingでE2E確認する。
5. 内部利用者だけをhybrid Authへ招待し、Basic fallbackを維持する。
6. company選択、RBAC、aal2、30日session、状態行列をstagingと少数本番利用者で確認する。
7. RLSをtable群単位に適用し、各群でerror rate、認証失敗、DB latency、越境テストを確認する。
8. 全利用者を招待・MFA登録し、legacy trafficがゼロになるまで併存する。
9. `/admin`、audit、exportを有効化する。
10. Phase 12 gateを満たした後、Basic →通常API key→固定企業の順に撤去する。
11. secret/keyをrotateし、Renderのlegacy変数を削除する。
12. 24時間、7日、30日の監視点で認証率、MFA、RLS拒否、LINE、export、auditを確認する。

各段階で問題が出たら次へ進まず、feature flagまたは旧経路へ戻す。migrationの履歴改変、force rollback、RLSの無計画な無効化は行わない。

## 10. ブラウザへ秘密鍵を公開しない確認項目

- `NEXT_PUBLIC_` にsecret/service-role、SMTP、Google client secret、API key、LINE secretがない。
- `frontend/` のソース、`.next/static`、source map、HTML、React props、JSON responseにsecret値がない。
- Browser DevToolsのrequest/response/cookie/localStorage/sessionStorageにsecret key、invite token hash、Google provider tokenがない。
- Supabase publishable keyだけがブラウザに存在し、RLSなしでは保護にならないことをテストで確認する。
- Next.js Route HandlerだけがBackend URLと移行中のadmin keyを読む。
- FastAPI error、Render log、audit logにJWT全文、cookie、SMTP secret、LINE token、招待tokenを出さない。
- Git履歴・tracked env exampleへ実値を入れない。secret scanをCIへ追加する。

## 11. CI導入候補

現在checked-in CI設定はない。Phase 1AまたはPhase 2で次を追加する。

**作成ファイル:**

- Create: `.github/workflows/backend-tests.yml`
- Create: `.github/workflows/frontend-checks.yml`
- Create: `.github/workflows/supabase-tests.yml`
- Create: `.github/workflows/secret-scan.yml`

PR必須check:

- Backend全unit testsとPython AST
- Frontend unit、TypeScript、build
- local Supabase reset、lint、pgTAP
- migration filename/order/schema diff
- secret scan
- `git diff --check`

CIへ本番secretを渡さず、Supabase local containerだけを使う。GitHub-hosted runner時間とStorageには費用・上限があり得るため確認する。

## 12. フェーズ完了時の共通チェックリスト

- [ ] 正式設計との対応箇所をPR本文に列挙した
- [ ] 新しい仕様に対する失敗テストを先に確認した
- [ ] focused testsがGREEN
- [ ] 既存Backend 62件以上がGREEN
- [ ] Python構文検査がGREEN
- [ ] Frontend変更時にunit/type/buildがGREEN
- [ ] migration変更時にlocal reset/lint/pgTAPがGREEN
- [ ] secret clientの利用箇所を再棚卸しした
- [ ] 全read/write/RPCのcompany条件とRLSを確認した
- [ ] DB障害と対象なしを区別した
- [ ] ロールバック手順をstagingで確認した
- [ ] 外部管理画面の変更を記録した
- [ ] 文書内のパス・行番号を更新した
- [ ] `git diff --check` と `git status` を確認した

## 13. 参照する公式資料

実装時には最新版を再確認する。

- Supabase SSR client: <https://supabase.com/docs/guides/auth/server-side/creating-a-client>
- Supabase PKCE: <https://supabase.com/docs/guides/auth/sessions/pkce-flow>
- Supabase JWT/JWKS: <https://supabase.com/docs/guides/auth/jwts>
- Supabase signing keys: <https://supabase.com/docs/guides/auth/signing-keys>
- Supabase MFA/TOTP: <https://supabase.com/docs/guides/auth/auth-mfa/totp>
- Supabase identity linking: <https://supabase.com/docs/guides/auth/auth-identity-linking>
- Supabase Google provider: <https://supabase.com/docs/guides/auth/social-login/auth-google>
- Supabase redirect URLs: <https://supabase.com/docs/guides/auth/redirect-urls>
- Supabase SMTP: <https://supabase.com/docs/guides/auth/auth-smtp>
- Supabase password security: <https://supabase.com/docs/guides/auth/password-security>
- Supabase RLS: <https://supabase.com/docs/guides/database/postgres/row-level-security>
- Supabase local testing: <https://supabase.com/docs/guides/local-development/testing/overview>
- Google OAuth web server: <https://developers.google.com/identity/protocols/oauth2/web-server>
- Render environment variables: <https://render.com/docs/configure-environment-variables>

## 14. 実装開始前の停止条件

次のいずれかが未解決なら該当フェーズを開始しない。

- 正式設計のリポジトリ内原本が未確定
- 本番schemaとmigration履歴が一致しない
- 文字列company IDからUUIDへの対応が承認されていない
- Supabase key種別またはJWT signing方式が不明
- 本番redirect URL、SMTP sender、Google管理主体が不明
- LINE channelと企業の対応が不明なままWebhook固定IDを撤去しようとしている
- rollback owner、backup、staging rehearsalがない
- 有料機能・外部契約が未承認

不明事項は「未確認」としてissue化し、推測によるmigration、RLS、環境変数、デプロイを行わない。
