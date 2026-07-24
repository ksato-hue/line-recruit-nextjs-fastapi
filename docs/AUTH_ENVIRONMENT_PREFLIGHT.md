# Auth Environment Preflight

## 2026-07-24 schema-reconciliation correction

This section supersedes the 2026-07-23 `execute_sql` cancellation-related
`UNVERIFIED` items below. Full evidence and the non-applicable sanitized snapshot
are in `docs/SUPABASE_SCHEMA_RECONCILIATION.md` and
`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`.

- **FACT:** project-scoped/read-only MCP catalog SELECTs succeeded. `public` has
  12 base tables, 2 functions, 7 non-internal triggers, and 42 indexes; no view,
  materialized view, sequence, or foreign table was found.
- **FACT:** all 12 tables have RLS and FORCE RLS disabled. No `public` or
  `storage` policy exists.
- **FACT:** every public table grants all table privileges to `anon`,
  `authenticated`, and `service_role`. Both public functions are executable by
  `PUBLIC`, `anon`, `authenticated`, and `service_role`. Public default
  privileges also grant client roles broad privileges for new tables,
  sequences, and functions.
- **FACT:** the 11 `company_id` columns are `text` and have no company FK.
  Six legacy tables are nullable with a constant default (value not recorded);
  five settings/session tables are non-null without a default. `contacts` still
  has no `company_id`.
- **FACT:** aggregate-only inspection found no NULL `company_id` in any of the
  11 tables. Non-empty tables each reported one distinct identifier; empty
  tables reported zero. No identifier value was read or recorded.
- **FACT:** Storage bucket count and Storage policy count are both zero.
- **FACT:** installed extensions are `pgcrypto`, `supabase_vault`,
  `pg_stat_statements`, `uuid-ossp`, and `plpgsql`. The earlier statement that
  `pg_graphql` was installed is corrected: it had no installed version.
- **FACT:** `supabase_migrations.schema_migrations` does not exist, and the
  dedicated migration list is empty. The four checked-in files have matching
  live DDL artifacts but cannot be treated as CLI-recorded migrations.
- **INFERENCE (high confidence):** `README.md:21-26` instructs operators to run
  the four files through Supabase SQL Editor. That route explains matching
  artifacts without migration-history rows, but execution logs were not
  available to prove the historical route.
- **BLOCKER:** Auth migration creation remains NO-GO until a clean migration
  chain is replayed in staging and schema equivalence is demonstrated. The
  recommended reconciliation route is documented in
  `docs/superpowers/plans/2026-07-24-supabase-schema-reconciliation.md`.

調査日時: 2026-07-23 (Asia/Tokyo; exact live-call timeは記録されていない)
対象ブランチ: `agent/auth-foundation-preflight`
基準: `origin/main` (`61e0a12`) + 認証実装計画コミット `120ebc9`
正式設計: 添付 `2026-07-23-supabase-auth-rbac-mfa-design.md`
実装計画: `docs/superpowers/plans/2026-07-23-supabase-auth-rbac-mfa-implementation.md`

## 1. 判定

**総合判定: NO-GO**

- **NO-GO:** このrunでのPhase-B migration作成、SQLテスト作成、または認証基盤schema実装記録の作成。
- **NO-GO:** production、staging、共有Supabase projectを含む外部環境へのmigration適用。
- **停止理由:** liveのproject migration listが空である一方、4本のmigrationがchecked-inである。さらにgrant、default privilege、function/RPC、trigger、policy、FORCE RLS、`company_id`集計を確認できず、preflight時点の設計・計画にはRLS順序、`legacy_company_key`、table別timestamp/FK action、owner invariantの境界に競合があった。本書と実装計画はRLS順序を修正し未承認項目をdeferしたが、evidence、table別decision、checked-in base DDLは未解決であり、空のlocal databaseをresetできると仮定できない。

この判定はadditive auth schemaを否定するものではない。mandatory catalog evidenceと設計判断が揃うまで、migration作成ゲートで安全に停止する。

### 1.1 2026-07-23 live Supabase MCP preflight

- **FACT:** 設定されたproject-scoped MCP URLはproject ref `dcexrqivikbchxawjzsn`、`read_only=true`、feature `database,docs,storage` を含み、`list_tables`を含むlist operationは成功した。
- **UNVERIFIED:** server-sideでwriteが拒否されること。write試験は安全上実施していない。
- **UNVERIFIED:** project URL hostとproject refの独立照合。connectorはproject URL取得operationを公開しなかった。
- **FACT:** read-only catalog `execute_sql` はMCP endpointによりcancelされ、下記のcatalog・aggregate項目は取得できなかった。
- **FACT:** secret、credential、実company ID、個人データ、LINE ID/本文、Storage object名、OAuth/MCP session detailは取得・記録していない。

### 1.2 live public schema

- **FACT:** `public`には次の12 base tableが報告された: `applicants`, `inquiries`, `contacts`, `interview_slots`, `faq_categories`, `faqs`, `line_message_logs`, `faq_settings`, `app_settings`, `question_tree_settings`, `applicant_status_settings`, `application_sessions`。
- **FACT:** proposed Auth foundationの8 table、`companies`, `profiles`, `company_members`, `company_invitations`, `platform_admins`, `app_sessions`, `audit_logs`, `data_exports` はreported `public`に存在しない。
- **FACT:** 12 tableすべてでRLS disabledが報告された。
- **UNVERIFIED:** FORCE RLS、policy詳細、grant/default privilege、function/RPC metadataとEXECUTE grant、trigger、view/materialized view/sequence、partitioned table、index定義、PostgREST exposed-schema設定。catalog `execute_sql`がcancelされたためである。
- **INFERENCE:** list operationのcritical advisoryは12 tableをSupabase client roleへ露出し得る対象として示したが、実際の到達可能性とread/write権限はgrantおよびPostgREST設定が未確認のため断定しない。

live column、constraint、indexに関する報告は次のとおり。`NN`はNOT NULL、`NULL`はnullableを表す。company identifier defaultのliteralは記録しない。

| Table | Columns | Reported constraints / index evidence |
|---|---|---|
| `applicants` | `id uuid NN default gen_random_uuid()`; `line_user_id text NN`; `name text NULL`; `phone text NULL`; `job text NULL`; `motivation text NULL`; `status text NULL default`; `created_at timestamptz NULL default now()`; `interview_status text NULL default`; `interview_date text NULL`; `memo text NULL`; `company_id text NULL` constant default; `application_session_id uuid NULL`; `tags jsonb NN default []` | PK (`id`); CHECK `jsonb_typeof(tags) = 'array'`; `application_session_id` FKは報告なし。PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `inquiries` | `id uuid NN default gen_random_uuid()`; `line_user_id text NN`; `message text NN`; `status text NULL default`; `created_at timestamptz NULL default now()`; `company_id text NULL` constant default | PK (`id`); PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `contacts` | `line_user_id text NN`; `display_name text NULL`; `status text NULL default`; `created_at timestamptz NULL default now()` | PK (`line_user_id`); `company_id`なし。PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `interview_slots` | `id uuid NN default gen_random_uuid()`; `applicant_id uuid NN`; `interview_round text NULL`; `candidate_1/2/3 text NULL`; `selected_date text NULL`; `status text NULL default`; `created_at timestamptz NULL default now()`; `line_user_id text NULL`; `slot_datetime timestamptz NULL`; `selected_at timestamptz NULL`; `company_id text NULL` constant default | PK (`id`); `applicant_id` FKは報告なし。PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `faq_categories` | `id uuid NN default gen_random_uuid()`; `name text NN`; `sort_order integer NULL default 0`; `is_active boolean NULL default true`; `created_at/updated_at timestamptz NULL default now()`; `company_id text NULL` constant default | PK (`id`); UNIQUE (`name`); `faqs.category_id`から参照。PK/UNIQUE backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `faqs` | `id uuid NN default gen_random_uuid()`; `category_id uuid NN`; `question text NN`; `answer text NN default ''`; `is_visible boolean NN default false`; `sort_order integer NULL default 0`; `created_at/updated_at timestamptz NULL default now()`; `company_id text NULL` constant default | PK (`id`); FK `category_id -> public.faq_categories(id)`。PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `line_message_logs` | `id uuid NN default gen_random_uuid()`; `created_at timestamptz NN default now()`; `line_user_id text NN`; `message text NULL`; `direction text NULL`; `message_type text NULL`; `company_id text NULL` constant default | PK (`id`); PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |
| `faq_settings` | `company_id text NN`; `faq_key text NN`; `answer text NN default ''`; `is_visible boolean NN default false`; `created_at/updated_at timestamptz NN default now()` | composite PK (`company_id`,`faq_key`); backing indexに`company_id`を含むことは**INFERENCE**、定義は**UNVERIFIED** |
| `app_settings` | `company_id text NN`; `key text NN`; `value jsonb NN`; `created_at/updated_at timestamptz NN default now()` | composite PK (`company_id`,`key`); backing indexに`company_id`を含むことは**INFERENCE**、定義は**UNVERIFIED** |
| `question_tree_settings` | `company_id text NN`; `tree jsonb NN default {}`; `created_at/updated_at timestamptz NN default now()` | PK (`company_id`); backing indexに`company_id`を含むことは**INFERENCE**、定義は**UNVERIFIED** |
| `applicant_status_settings` | `company_id text NN`; `status_key text NN`; `name text NN`; `sort_order integer NN default 0`; `is_active boolean NN default true`; `created_at/updated_at timestamptz NN default now()` | composite PK (`company_id`,`status_key`); backing indexに`company_id`を含むことは**INFERENCE**、定義は**UNVERIFIED** |
| `application_sessions` | `id uuid NN default gen_random_uuid()`; `company_id text NN`; `line_user_id text NN`; `status text NN default active`; `current_question_key text NULL`; `answers jsonb NN default []`; `started_at/last_activity_at timestamptz NN default now()`; completion/cancellation/reminder timestamps nullable; `last_event_id text NULL`; `created_at/updated_at timestamptz NN default now()` | PK (`id`); CHECK status in `active/completed/cancelled`; CHECK answers is JSON array。PK backing indexは**INFERENCE**、定義は**UNVERIFIED** |

### 1.3 `company_id` evidence

- **FACT:** `contacts`には`company_id`がなく、checked-in codeおよびmigrationのliteral searchにも存在しない。live tableの用途・owner・provenanceは**UNVERIFIED**。
- **FACT:** `applicants`, `inquiries`, `interview_slots`, `faq_categories`, `faqs`, `line_message_logs` の6 tableはnullable `text company_id`とconstant defaultを持つ。default literalは安全上記録しない。
- **FACT:** `faq_settings`, `app_settings`, `question_tree_settings`, `applicant_status_settings`, `application_sessions` の5 tableはnon-null `text company_id`でdefaultなし。
- **FACT:** 11の`company_id`列にFKは報告されなかった。
- **UNVERIFIED:** distinct count、NULL count、catalog index定義。aggregate `execute_sql`がcancelされたためであり、実際のidentifier valueは読んでいない。

### 1.4 checked-in / live migration classification

- **FACT:** checked-in migrationが作成する5 table、`faq_settings`, `app_settings`, `question_tree_settings`, `applicant_status_settings`, `application_sessions` はliveにも存在する。
- **FACT:** checked-in migrationがalterするがcreateしない6 business table、`applicants`, `inquiries`, `interview_slots`, `faq_categories`, `faqs`, `line_message_logs` はliveに存在する。
- **FACT:** `contacts`はliveに存在するが、checked-in DDL/referenceは見つからない。
- **FACT:** dedicated project migration-list operationは0 rowsを返した一方、repositoryには4 migration fileがある。これはmaterial mismatchである。
- **UNVERIFIED:** live objectの正確なprovenance、4 versionがmigration historyに報告されない理由、catalog上のchecked-in定義との差分。SQL Editor、別repository、履歴欠損等を推測で断定しない。
- **FACT:** checked-in chainは6 legacy base tableを作成せず、後続migrationが`applicants`を無条件にalter/referenceするため、空local databaseのreset可能性を前提にできない。

### 1.5 extensions, Auth, Storage

- **FACT:** installed extensionとして `pgcrypto`, `supabase_vault`, `pg_stat_statements`, `uuid-ossp`, `pg_graphql`, `plpgsql` が報告された。
- **FACT:** aggregate-only Auth countは `auth.users = 0`, MFA factors `= 0`, `auth.refresh_tokens`, `auth.sessions`, `auth.mfa_challenges`, `auth.mfa_amr_claims`, `auth.flow_state`, `auth.one_time_tokens`, `auth.saml_relay_states`, `auth.oauth_authorizations`, `auth.oauth_consents`, `auth.oauth_client_states` は各`0`, `auth.schema_migrations = 77`。
- **UNVERIFIED:** Auth migration version/name、JWT signing、JWKS、provider、MFA setting、redirect、SMTP。
- **FACT:** dedicated bucket listはbucketを報告せず、private CSV/data-export bucket candidateはない。Storage system table aggregateも0と報告された。
- **FACT:** Storage object listは実行していない。
- **UNVERIFIED:** Storage policy。

### 1.6 LINE company resolution

- **FACT:** 現在はprocess-wide fixed `COMPANY_ID`、単一 `/webhook` path、単一channel secret、単一access tokenで動作する。署名検証後の処理もfixed companyを使い、body-level `destination`は読まない。
- **PROPOSAL:** 将来はopaque webhook pathまたはchannel-specific gatewayをtrusted bindingとし、そのbindingでverification secretを選択して署名検証する。検証成功後に`destination`とbindingの一致を確認し、companyおよび対応access tokenを解決する。未検証の`destination`でverification secretを選ばない。
- **PROPOSAL:** この設計、state keyのcompany/channel複合化、secret rotation、移行手順が別途承認されるまでfixed `COMPANY_ID`を変更しない。

## 2. 調査範囲と制約

今回実施したのは読み取り専用調査だけである。

- SQLのINSERT、UPDATE、DELETE、DDLは実行していない。
- migrationは適用していない。
- Supabase、Render、Google Cloudの設定は変更していない。
- Auth userの作成・招待は行っていない。
- 環境変数の追加・更新・削除は行っていない。
- API key、JWT、token、password、メールアドレス、応募者情報、LINE user ID、会話本文は出力・記録していない。
- production codeは変更していない。

### 2.1 利用可能性を確認した接続方法

> **2026-07-23 live-audit update:** Supabase MCP行はlive audit結果へ更新した。Render、CLI、local Supabase等はrepository-only調査時点から更新していない。

| 手段 | 結果 | 判定根拠 |
|---|---|---|
| Supabase MCP | list operation利用可 | project-scoped `read_only=true`; catalog `execute_sql`はendpointでcancel |
| Render MCP | 利用不可 | 利用可能・遅延ツールを検索したがRender専用toolなし |
| Supabase CLI | 利用不可 | `supabase` commandなし |
| Render CLI | 利用不可 | `render` / `render-cli` commandなし |
| `psql` | 利用不可 | commandなし |
| Docker / local Supabase | 利用不可 | `docker` commandなし、`supabase/config.toml`なし |
| process環境変数 | 接続情報なし | Supabase、Render、DB関連の変数名なし。値は確認していない |
| local `.env` | 実値ファイルなし | `backend/.env.example` と `frontend/.env.local.example` だけ存在 |
| CLI認証設定 | 見つからない | sandboxから確認可能なSupabase/Render CLI設定directoryなし |
| リポジトリ内設定 | 部分的に利用可能 | example env、migration、README、source codeのみ |
| ログイン済み管理画面 | 利用不可 | 利用可能なbrowser sessionが0件 |
| checked-in Render Blueprint | なし | `render.yaml`、Dockerfile、Procfileなし |

Supabaseは§1.1-1.5のtable/column/constraint/RLS/aggregate-only evidenceまで確認済みである。catalog SQLを要する権限・policy・function等とDashboard/Auth設定、Renderの管理面・runtimeは**UNVERIFIED**のままである。

## 3. 確認できた事実

以下はcheckoutから直接確認した事実であり、実環境状態の証明ではない。

### 3.1 現在のSupabase接続

- `backend/main.py:16-17` は `SUPABASE_URL` と単一の `SUPABASE_KEY` を読む。
- `backend/main.py:21-24` はprocess起動時にグローバルSupabase clientを1個作る。
- publishable/anon clientとsecret/service-role clientの分離はない。
- `backend/.env.example:2` の値はplaceholderであり、キー種別を判定できない。
- process環境にも実値を持つ `SUPABASE_KEY` はなかった。
- `backend/requirements.txt:3` はversion未固定の `supabase` だけを指定し、JWT検証libraryを明示していない。

**SUPABASE_KEY分類:** **不明**

production keyを値なしで分類できる証拠はない。publishable、anon、secret、service_roleのいずれとも断定しない。

### 3.2 現在の認証と企業境界

- `frontend/middleware.ts:23-46` がBasic認証を行う。
- `frontend/app/api/admin/[...path]/route.ts:5-6,39-42` がNext.js serverからFastAPIへ `X-Admin-Key` を付ける。
- `backend/main.py:40,70-75` の `require_admin` は共有 `ADMIN_API_KEY` だけを検証する。
- `backend/main.py:39` の `COMPANY_ID` はprocess全体で1値であり、未設定時のfallback literalが存在する。具体値は本書へ記録しない。
- checked-out `backend/main.py` の11業務テーブルに対する現在のcall siteは `docs/SUPABASE_COMPANY_SCOPE.md:14-62` の棚卸しどおり、明示的なcompany predicateまたはvalueを持つ。
- この境界はアプリケーションの固定値によるもので、user identity、membership、role、RLSではない。

### 3.3 checked-in migrationが作成するobject

checked-in migrationは4本である。

1. `supabase/migrations/202607190001_mvp_security_foundation.sql`
2. `supabase/migrations/202607190002_admin_configuration.sql`
3. `supabase/migrations/202607200001_application_sessions.sql`
4. `supabase/migrations/202607210001_applicant_tags.sql`

明示的に作成するtable:

- `public.faq_settings`
- `public.app_settings`
- `public.question_tree_settings`
- `public.applicant_status_settings`
- `public.application_sessions`

既存を前提に変更するtable:

- `public.applicants`
- `public.inquiries`
- `public.interview_slots`
- `public.line_message_logs`
- `public.faq_categories`
- `public.faqs`

明示的に作成するfunction:

- `public.set_updated_at()`
  根拠: `supabase/migrations/202607190001_mvp_security_foundation.sql:6-13`
- `public.complete_application_session(...)`
  根拠: `supabase/migrations/202607200001_application_sessions.sql:111-178`

checked-in migrationで見つからなかったobject:

- view
- materialized view
- RLS policy
- `ENABLE ROW LEVEL SECURITY`
- `GRANT`
- `REVOKE`
- Storage bucket / `storage.objects` policy
- `auth.users` へのFK
- `companies` 相当table
- Supabase Auth用table

### 3.4 checked-in `company_id` 定義

| Table group | checked-in type | checked-in default | checked-in nullability | 注意 |
|---|---|---|---|---|
| `faq_settings`, `app_settings`, `question_tree_settings` | `text` | なし | 新規作成時はNOT NULL | tableが既存だった場合の `ADD COLUMN` 後にbackfill / NOT NULL化がない |
| `applicant_status_settings` | `text` | なし | 新規作成時はNOT NULL | tableが既存だった場合の `ADD COLUMN` 後にbackfill / NOT NULL化がない |
| `application_sessions` | `text` | なし | backfill後にNOT NULLを明示 | `supabase/migrations/202607200001_application_sessions.sql:50-74` |
| `applicants`, `inquiries`, `interview_slots`, `line_message_logs`, `faq_categories`, `faqs` | `text` | constant literal（redacted） | NOT NULL化なし | `supabase/migrations/202607190001_mvp_security_foundation.sql:70-95` |

上表はmigrationを空DBまたは既存DBへ適用した場合の記述であり、productionの実列定義ではない。特に `CREATE TABLE IF NOT EXISTS` と `ADD COLUMN IF NOT EXISTS` の組み合わせにより、既存tableの制約は同じ状態になるとは限らない。

### 3.5 `company_id` defaultへの依存

**現在のBackend call site:**

- application session insertは `COMPANY_ID` を明示する (`backend/main.py:1115-1123`)。
- 応募完了RPCは `p_company_id` を明示し、applicant insertにも渡す (`backend/main.py:1309-1318`; migration `:130-170`)。
- inquiry、LINE log、interview slot、status setting、FAQ category、FAQ、FAQ setting、app setting、question treeのinsert/upsertも `COMPANY_ID` を明示する (`backend/main.py:1383-1384`, `1574-1579`, `2031-2040`, `2340-2348`, `2374-2383`, `2440-2453`, `2544-2552`, `2611-2615`, `2681-2687`)。

したがって、checked-out Backendの既知write pathにDB defaultだけへ依存するものは見つからなかった。

**migrationと外部writer:**

- 6つのlegacy tableはmigrationがnull rowをredacted constant literalへbackfillし、その後のDB defaultにも同じliteralを使う。具体値は記録しない。
- productionに別のwriter、SQL、trigger、古いserviceがあればDB defaultを利用する可能性があるが、未確認。
- UUID橋渡し前に、そのredacted fallback literalが実在企業1社だけを意味することを実データから確認する必要がある。

### 3.6 RPCの事前確認事項

`public.complete_application_session` は:

- `p_company_id` とsession/userを照合する (`supabase/migrations/202607200001_application_sessions.sql:130-145`)。
- applicant insertへ `p_company_id` を明示する (`:154-160`)。
- session updateは最終的に `id` だけを条件にする (`:163-170`)。
- `SECURITY DEFINER`、固定 `search_path`、明示的 `GRANT` / `REVOKE` を持たない。

実際のEXECUTE grantは未確認である。public schemaに作られたfunctionはData APIのRPC候補になり得るため、Auth/RLS migrationより前に実grantとAPI公開状態を確認し、必要なroleだけへ制限する必要がある。

### 3.7 既存Backendテスト

- 現在のsuiteは62件。
- `backend/tests/support.py:16-20` が `supabase.create_client` をpatchするため、Supabaseへ実接続しない。
- 企業境界テストは `main.COMPANY_ID` とfake queryを利用する。
- LINE署名と管理API key境界は `backend/tests/test_security_boundaries.py` で保護されている。

62件の成功はchecked-out application behaviorの回帰証拠であり、production RLS、grant、schema、key種別の証拠ではない。

## 4. 実環境で残る未確認事項

project-scoped MCPのlist operationで確認できた範囲は§1.1-1.5へ記録した。以下はcatalog `execute_sql` cancellationまたはDashboard/Render access不在により残る未確認dimensionである。

### 4.1 Supabase Database / API

- view、materialized view、partitioned table、sequence、RPC、function、triggerのinventory/definition
- 各業務tableのcatalog index definition
- distinct `company_id` の件数
- distinct IDごとの行数。値自体は監査文書へ記録しない
- FORCE RLS状態（RLS enabledは12 tableすべてdisabledを確認済み）
- policy一覧
- table、sequence、function、schemaのgrant
- public / graphql_public等、Data APIで公開されるschema
- PostgRESTのexposed schema設定
- project migration historyのempty resultとchecked-in 4 fileが一致しない理由、およびchecksum
- `complete_application_session` の実定義とEXECUTE権限

### 4.2 Supabase Storage

- bucket listが0である理由と将来bucketのpublic/private設定
- `storage.objects` policy
- object ownership、retention、signed URL設定

### 4.3 Supabase Auth

- Auth provider設定
- public signup可否
- email/password設定
- MFA/TOTP設定
- JWT signing方式
- JWKS endpointに非対称公開鍵が存在するか
- Site URLとredirect allowlist
- custom SMTP設定
- rate limit、password policy、email template

### 4.4 Render

- Backend / Frontendの実service有無とURL
- runtimeとversion
- Build command
- Start command
- root directory
- branchとauto deploy
- deploy hook
- migration実行方法
- environment variable名と設定有無
- secret/public変数の分離
- Environment Group
- staging / production / preview環境
- Cron Job、background worker、one-off job

READMEの起動例と `frontend/package.json` のscriptはrepository上の候補であり、Renderの実設定ではない。

## 5. checked-in状態と実環境の差分

live list operationとchecked-in migrationを照合できた範囲を以下に記録する。catalog定義差分とobject provenanceは未確認である。

### 5.1 migrationにはあるが実DBにないもの

**FACT:** checked-in migrationがcreateする5 tableはliveにも存在する。checked-in function、trigger、indexの正確なlive定義、および4 migration versionの適用履歴は**UNVERIFIED**である。

### 5.2 実DBにはあるがmigrationにないもの

**FACT:** 6つの主要tableはliveに存在するが、checked-in migrationにはbase `CREATE TABLE`がなく、`ALTER TABLE IF EXISTS`の対象だけである。

**FACT:** `contacts`はliveに存在するが、checked-in DDL/referenceがない。

**UNVERIFIED:** これらのobjectを作成した経路。SQL Editor、別repository、履歴欠損等を推測で断定しない。

### 5.3 文書との照合

- `docs/SUPABASE_COMPANY_SCOPE.md` はlive table/RLS/company-column factsと、残るpolicy/grant/key uncertaintyを区別している。
- `docs/CODEBASE_AUDIT.md` はlive table/RLS/migration-list factsと、残るcatalog/runtime uncertaintyを区別している。
- `docs/requirements.md:309` の「COMPANY_IDは設定系の一部にしか適用されない」は以前の状態であり、現在のcall-site inventoryとは一致しない。現在は既知の11業務table call siteが明示的にscopeされている。
- ただし、call-site scopeが本番マルチテナントやRLSを意味しないという監査結論は有効。

## 6. UUID橋渡し前に解決すべき不整合

1. productionのdistinct `company_id` 件数と、各IDの正式企業を確認する。
2. redacted fallback literalが1社だけを指すか、複数企業データが混在していないかを確認する。
3. 11tableすべての実型、default、null、index、FKを取得する。
4. null `company_id` と、想定外IDの件数を取得する。値や業務データは文書へ記録しない。
5. legacy text ID → `companies.id uuid` の対応表を人手承認する。
6. base tableの正規DDLをmigrationへ回収する方針を決める。
7. UUID bridge中のdual-write、read source、cutover、rollbackをtable単位で決める。
8. `complete_application_session` の引数と内部queryをUUID bridgeへ対応させる。
9. 外部writer、trigger、RPC、scheduled jobが文字列defaultへ依存していないことを確認する。
10. actual RLS/grant/API公開範囲を取得する。

## 7. Authテーブル追加前のセキュリティブロッカー

### Blocker 1: live migration historyがchecked-in filesと不一致

dedicated project migration listはemptyだが4 filesがchecked-inである。reported table/column/constraint形状は取得できたものの、catalog-level差分とprovenanceを確定できず、production migration適用は不可。

### Blocker 2: `SUPABASE_KEY` 種別が不明

現在の単一clientがRLSを迂回するsecret/service-role相当か判断できない。通常利用者clientとservice clientの分離設計を実環境に合わせられない。

### Blocker 3: grant / policy / FORCE RLS / exposed schemaが未確認

liveの12 tableはRLS disabledと確認済みである。checked-in SQLにもRLS、grant、revokeがない。actual policy、grant、FORCE RLS、Data API exposureは未確認である。
参考: <https://supabase.com/docs/guides/database/postgres/row-level-security>

### Blocker 4: 新規Auth tableのcreation-time RLSを実装時に保持する

旧計画はAuth table作成とRLS enablementを別migrationへ分けていたが、dated plan correctionで修正した。将来の各table-creation migrationは同一transaction内でRLSをenableし、承認済みallow policy追加までdeny-by-defaultを維持しなければならない。

### Blocker 5: 企業対応表がない

redacted fallback literalを推測で新UUIDへbackfillできない。対応表の人手承認が必要。

### Blocker 6: LINE eventの企業識別がない

後述のとおり、現在のWebhookは固定 `COMPANY_ID` だけを利用する。複数企業対応後に同一processで安全にsecret、access token、state、DB scopeを選択できない。

### Blocker 7: JWT / Auth設定が未確認

非対称signing keyならJWKSを利用できるが、JWKS endpointは非対称鍵を使わないprojectでは鍵を返さない。actual signing方式を確認する必要がある。
参考: <https://supabase.com/docs/guides/auth/jwts>

## 8. 最初のmigrationへ必要な修正

`202607230001_auth_core.sql` を作成する前に、実装計画へ次を反映する。

1. `companies`、`profiles`、`company_members`、`platform_admins` のcolumn名・型・constraintを正式設計と完全一致させる。
2. `profiles` のPK/FKは `user_id uuid references auth.users(id)` とする。
3. `platform_admins.user_id` も `auth.users(id)` を参照し、画面から自己登録できる経路を作らない。
4. 企業ごとのactive owner最大1名をpartial unique indexで保証する。
5. `company_members(company_id, user_id)`、role、statusのconstraintと必要indexを同じmigrationへ含める。
6. 正式設計にない`legacy_company_key`はPhase 1Aへ追加しない。UUID bridge方式は別途正式承認後のphaseへdeferする。
7. public schemaへ作る全新規tableで、作成と同時にRLSを有効化する。
8. 正式policyが後続なら、最初はpolicyなしのdeny-by-defaultとし、anon/authenticatedへ過剰grantしない。
9. default privilegeを含むactual grantを取得してから、必要な明示GRANT/REVOKEを決める。
10. `gen_random_uuid()` のextension可用性をlocalと実環境で確認する。
11. migrationはtransaction内で完結させ、部分適用を防ぐ。
12. 既存11業務table、既存text `company_id`、既存データ、既存RPCは最初のmigrationで変更しない。
13. table・index・constraint・RLS状態を確認するpgTAPを先に書く。
14. productionへ適用する前にschema-only stagingでrehearsalする。

Supabaseの公式指針ではraw SQLでexposed schemaへtableを作る場合、RLSを自分で有効化し、roleへ必要最小限の権限だけを与える必要がある。

## 9. LINE企業識別

### 9.1 現状

- LINE設定はprocess全体で1組の `LINE_ACCESS_TOKEN` と `LINE_CHANNEL_SECRET` (`backend/main.py:18-19`)。
- `/webhook` は単一path (`backend/main.py:352`)。
- HMAC検証は単一 `LINE_CHANNEL_SECRET` を使う (`backend/main.py:77-91`)。
- event処理は `event.source.userId`、message、replyToken、webhookEventIdを読む (`backend/main.py:362-380`)。
- Webhook bodyのtop-level `destination` は読まない。
- Channel IDまたはchannel-company mappingを保持する設定・table・codeは見つからない。
- DB read/write、RPC、LINE logは固定 `COMPANY_ID` を使う。
- LINE返信・pushは単一 `LINE_ACCESS_TOKEN` を使う (`backend/main.py:1439-1514`, `1534-1558`)。
- in-memory stateも主にLINE user IDだけをkeyにするため、同一processで複数channelを扱う前にcompany/channelを複合keyへ含める必要がある。

**現在の企業判定:** request、Channel ID、`destination` ではなく、process-wide固定 `COMPANY_ID`。

### 9.2 複数企業化の案

| 案 | 概要 | 長所 | 短所 | 評価 |
|---|---|---|---|---|
| A. 企業ごとのopaque webhook path + channel mapping | `/webhook/line/{opaque_binding_id}` から信頼済みbindingを引き、対応secretで署名検証し、検証後に`destination`も照合する。company、channel secret参照、access token参照を1レコードに結ぶ | 1serviceで複数企業、署名前に使用secretを決定可能、rotation可能 | secret保管、mapping管理、path漏えい対策、全stateの複合key化が必要 | **推奨** |
| B. Channel別gateway / edge ingress | channelごとの入口が署名検証し、内部署名付きcompany contextだけを共通Backendへ転送 | 共通Backendへ未検証companyを渡さない。channel分離が明確 | gateway運用、内部署名、監視、費用が増える | 大規模化時の候補 |
| C. 企業ごとにBackend serviceを分離 | 現在の固定 `COMPANY_ID` とLINE secret/tokenを企業ごとのRender serviceへ配置 | 最小code変更、process分離 | service数・費用・deploy・監視が企業数に比例。共通Auth/RBACとの整合が弱い | 短期限定 |

案Aを推奨する。ただし正式設計に `company_line_channels` 相当のdata modelはまだないため、実装前に設計変更として承認する。最低限、company ID、LINE destination/channel識別子、secret/tokenの安全な参照、status、rotation metadataを持ち、秘密値そのものを通常business tableやbrowserへ公開しない。

`destination` だけでcompanyを選択してから署名を信用してはならない。対応するsecretを安全に選んで署名検証した後、検証済みbodyのdestinationとbindingを照合する。

## 10. 外部管理画面で人手確認・設定が必要な項目

### Supabase

- Projectとenvironmentの対応確認
- Database schema、RLS、policy、grant、exposed schema、migration履歴のread-only export
- API key種別の分類とrotation計画。値は監査文書へ記録しない
- JWT signing keyとJWKSの確認
- Auth provider、public signup、email/password、password policy
- TOTP MFA
- Site URLとredirect allowlist
- custom SMTP、From domain、template、rate limit
- Storage bucketのpublic/privateとpolicy

参考:

- Auth設定: <https://supabase.com/docs/guides/auth/general-configuration>
- TOTP MFA: <https://supabase.com/docs/guides/auth/auth-mfa/totp>
- Redirect URL: <https://supabase.com/docs/guides/auth/redirect-urls>
- Custom SMTP: <https://supabase.com/docs/guides/auth/auth-smtp>
- Storage access: <https://supabase.com/docs/guides/storage/security/access-control>

### Render

- Backend/Frontend service、runtime、root directory、build/start command
- production branch、auto deploy、deploy hook、preview
- environment variable**名と設定有無**。値は取得・記録しない
- secret/public変数とEnvironment Group
- staging / production分離
- migration job、Cron、one-off job
- Node/Python version固定

Renderでは環境変数変更がdeployを起動し得るため、今回のread-only調査では変更していない。
参考: <https://render.com/docs/configure-environment-variables>

### Google Cloud

- OAuth project owner
- consent screen、authorized domain、support email
- Web client ID
- exact originとSupabase callback URL
- client secretの保管先

今回はGoogle Cloudへアクセスしておらず、設定変更も行っていない。

## 11. 費用が発生し得る設定

- Supabaseの利用者数、DB、Storage、egress、backup、プラン限定Auth機能
- custom SMTP provider、専用IP、送信量
- Render staging service、企業別service案、Cron Job、background worker
- CSV用private Storageとdownload帯域
- Google OAuthの審査・運用工数

Supabase TOTP APIは公式文書上すべてのprojectで利用可能とされるが、全体のAuth/MAU課金と契約プランは実装時に再確認する。Render Cronは実行時間に応じた課金と最低月額があるため、保持期限jobの選択時に承認が必要である。
参考:

- <https://supabase.com/docs/guides/auth/auth-mfa/totp>
- <https://render.com/docs/cronjobs>

## 12. 次のread-only確認に必要なもの

次のいずれかを、値を文書へ記録しない方法で用意する。

1. Supabase Dashboardのread-only access
2. Supabase Management APIのread-only相当access
3. DB catalogだけを読めるPostgres role
4. 管理者が実行したsanitized schema/RLS/grant/migration report
5. Render Dashboardのread-only accessまたはsanitized service configuration export

Supabaseで取得すべき結果は件数、型、boolean状態、object名、policy/grantだけに限定する。応募者、問い合わせ、LINE、メールアドレス等の行データは取得しない。distinct company IDは「件数」をまず取得し、値の対応付けは管理者がGit外で行う。

## 13. 実行した確認コマンド

秘密値を表示しない形で次を実行した。

```text
git fetch origin main
git rev-list --left-right --count origin/main...main
git status --short
Get-Command supabase/render/render-cli/psql/docker/node/npm/python
process環境変数の「名前」だけをフィルタ
local .envファイルの「パスと変数名」だけを列挙
Supabase/Render CLI設定directoryの存在確認
rg / git grepによるmigration、RLS、grant、Storage、Auth、company scope棚卸し
backend/main.pyのSupabase table/RPC/insert/update/deleteとWebhook経路の検索
browser接続可能性の確認
```

このrepository-only command記録の後、project-scoped read-only Supabase MCPのlist operationを実行した。catalog `execute_sql`はendpointでcancelされ、外部write、Render API、設定変更は実行していない。

## 14. 次回更新時の確認項目

- [x] public base table一覧
- [ ] view/function/RPC/trigger/sequenceのcatalog一覧
- [x] 11tableのcompany列型/default/null/FK metadata
- [ ] 11tableのcompany index definition
- [ ] distinct company ID件数とnull/unknown件数
- [ ] FORCE RLS/policy/grant/exposed schema（RLS enabled stateは確認済み）
- [ ] Storage public/policy（bucket list 0は確認済み）
- [ ] Auth provider/MFA/redirect/SMTP（user/factor aggregate countは確認済み）
- [ ] JWT signing/JWKS
- [ ] applied migration履歴とchecked-in 4本の対応
- [ ] `SUPABASE_KEY` 種別
- [ ] Render service/runtime/build/start/env名/deploy/migration
- [ ] LINE channel数、destination、secret/tokenの管理単位
- [ ] 最初のAuth migrationをRLS deny-by-defaultへ修正
- [ ] local Supabase / pgTAPの実行基盤

上記を確認するまで、production migration適用の判定はNO-GOのままとする。
