# Staging Supabase Current-State Baseline Design

設計日: 2026-08-10 (Asia/Tokyo)

対象環境:

- production: `dcexrqivikbchxawjzsn`（schema参照元、変更禁止）
- staging: `eygotkbexkjzzvcxqfea`（現在は空、設計段階では変更禁止）

この文書はmigration chainの設計仕様である。migration SQL、DB変更、migration history変更は含まない。

## 1. Background

Productionの`public` schemaには、12 tables、19 constraints、43 indexes、7 non-internal triggers、2 functionsが存在する。一方、productionのremote migration historyは0件であり、repositoryのactive migration 8本だけでは空DBから現在schemaを再現できない。

既存の非active候補`supabase/baselines/2026-07-24-public-schema-baseline.sql`は現在構造の大部分を記録しているが、次が意図的に未解決である。

- legacy 6 tablesの固定`company_id` default
- `complete_application_session()`の実body
- RLS、policy、table/routine/schema grants、default privileges
- applicationが必要とするextensionとSupabase管理extensionの境界

本設計は、productionのbusiness dataをコピーせず、productionの現在のデータ構造をcurrent-state baselineとして再現する。Productionの危険なACL/RLS状態は正規仕様にせず、baseline直後の独立security migrationでfail-closedにする。

## 2. Current production state

### 2.1 Structural inventory

Production read-only監査で確認済みの構造をbaseline equivalenceの基準とする。

- tables: 12
- constraints: 19（12 PK、3 UNIQUE、3 CHECK、1 FK）
- indexes: 43（15 constraint-backed、28 explicit）
- non-internal triggers: 7
- functions: 2
- sequences: 0
- identity/generated columns: 0

対象tableは次の12個である。

1. `app_settings`
2. `applicant_status_settings`
3. `applicants`
4. `application_sessions`
5. `contacts`
6. `faq_categories`
7. `faq_settings`
8. `faqs`
9. `inquiries`
10. `interview_slots`
11. `line_message_logs`
12. `question_tree_settings`

Functionsは`public.set_updated_at()`と`public.complete_application_session(...)`である。Triggersはsettings系、application session、FAQ category/FAQの`updated_at`を更新する7個である。

### 2.2 Security state

Productionの現状は再現対象ではなく、修正対象として扱う。

- 12 tablesすべてRLS disabled
- RLS policies 0
- `anon` / `authenticated`に広範なtable privileges
- 2 functionsにPUBLICおよびclient rolesからの広範な`EXECUTE`
- functionsに固定`search_path`なし
- public schemaのdefault privilegesが将来objectにもclient権限を与え得る

Productionをschema equivalenceの参照元にする場合も、これらを安全な仕様として承認したことにはならない。

### 2.3 Migration evidence

Production remote migration historyは0件である。次の2026年7月migration 4本に相当するartifactはproductionに存在するが、migrationとして適用された事実は証明できない。

- `202607190001_mvp_security_foundation.sql`
- `202607190002_admin_configuration.sql`
- `202607200001_application_sessions.sql`
- `202607210001_applicant_tags.sql`

基礎7 tables（`applicants`、`inquiries`、`contacts`、`interview_slots`、`faq_categories`、`faqs`、`line_message_logs`）を作成するchecked-in migrationは存在しない。

## 3. Current staging state

Staging project `eygotkbexkjzzvcxqfea`は、直前のread-only preflightで次の状態を確認済みである。

- public tables: 0
- public functions: 0
- remote migration history: 0
- business data: 0

Stagingはproduction data、LINE credentials、production secretsを受け取らない。Migration適用後の動作確認にはsynthetic dataだけを使用する。

## 4. Goals

1. 空DBから現在のapplicationが必要とするproduction相当のデータ構造を再現する。
2. Baseline、security hardening、問い合わせworkflowの責務を分離する。
3. `supabase db reset --local`で何度でも同じschemaへ到達できるactive migration chainを作る。
4. Productionの危険なACL/RLS状態をstagingへ正式仕様として複製しない。
5. 既存問い合わせmigration 4本を内容とversionを維持したまま後続適用できる順序にする。
6. Productionはread-only参照元のままとし、将来のhistory repairを独立した承認作業にする。

## 5. Non-goals

- productionまたはstagingへのmigration適用
- migration SQLの作成
- production migration history repair
- production dataのcopy、seed、匿名化dump
- Supabase Auth、role-based multi-tenant RLS policyの実装
- `companies` tableやUUID company modelの導入
- `contacts`への`company_id`追加
- legacy nullable `company_id`のNOT NULL化またはFK追加
- application schemaの機能拡張
- production ACL/RLSの変更

## 6. Proposed architecture

採用するB案は、active chainを次の4層へ分ける。

1. **Current-state structural baseline**
   Productionの現在構造をbusiness dataなしで再現する。
2. **Fail-closed security and privilege migration**
   Client rolesを遮断し、将来objectのdefault privilegesも安全側にする。
3. **Inquiry workflow migrations**
   既存4本をversionと内容を維持して順番に適用する。
4. **Future forward migrations**
   Auth/RLS、company model、contacts tenant scope等を別設計で追加する。

Baselineとsecurity migrationは別ファイルにするが、一組としてreview・local replayする。Remote stagingへbaselineだけを単独適用する運用は禁止する。途中失敗したstagingはapplicationへ接続せず、空projectから再作成する。

Supabase CLIは`supabase/migrations/`のlocal migrationと`supabase_migrations.schema_migrations`のremote versionを比較し、timestamp順に未適用migrationを実行する。`migration list`はversionだけで差分を識別するため、active directoryとlegacy archiveの境界は曖昧にしない。[Supabase Database Migrations](https://supabase.com/docs/guides/deployment/database-migrations) [Supabase CLI Reference](https://supabase.com/docs/reference/cli/supabase-orgs-list)

## 7. Baseline scope

### 7.1 Included

正式baselineは次を含む設計とする。

- 12 public tables
- productionと同じcolumn name、type、nullability、non-tenant default
- 19 constraints
- 43 indexes
- 7 triggers
- `set_updated_at()`
- security review後の`complete_application_session()`
- application DDLが必要とするextension

`pgcrypto`はapplication migrationが明示的に依存するため、存在確認または冪等な有効化をbaselineの責務にする。`pg_stat_statements`、`supabase_vault`、Supabase管理schema/ownershipはapplication baselineに取り込まない。`uuid-ossp`はcurrent application DDLから利用が確認できない限り必須extensionにしない。

### 7.2 Excluded

- business rows
- productionのstatus/settings row
- productionの固定tenant identifier
- production secrets、URLs、LINE identifiers
- Auth/Storage/Supabase管理schema
- broad grants、default ACL、RLS disabledを再現するstatement
- inquiry workflowで追加されるcolumns/table/function

Statusやsettingsが動作確認に必要な場合は、migrationではなくstaging専用synthetic seedとして管理する。Seedはproduction値をコピーしない。

### 7.3 Structural equivalence rule

Baseline equivalenceはtable/column/constraint/index/trigger/function signatureを比較する。次は承認済みの意図的差分として別管理する。

- legacy company defaultを除くこと
- function security/search_pathを強化すること
- grants/RLSをfail-closedにすること

意図的差分を除くschema fingerprintが一致しなければstaging適用へ進まない。

## 8. Security / fail-closed strategy

Baseline直後のsecurity migrationは、本格的なtenant policyを作らず、直接client accessを拒否する。

### 8.1 Required end state

- baselineの12 tablesでRLS enabled、FORCE RLSはdisabled
- client向けRLS policyは0件
- PUBLIC、`anon`、`authenticated`からbusiness table privilegesをrevoke
- public schemaのCREATEをPUBLIC/client rolesへ付与しない
- application backendが使用するserver roleだけに必要なschema/table privilegesを付与
- PUBLIC、`anon`、`authenticated`からapplication functionsの`EXECUTE`をrevoke
- application backend roleだけに必要なfunction `EXECUTE`を付与
- object作成主体のdefault privilegesを安全側へ変更し、後続table/function/sequenceへclient権限が自動付与されないようにする

RLS policyが0件であることは一時的なfail-closed状態であり、multi-tenant RLSが完成したことを意味しない。Supabase Auth/RLS導入時に、必要なrole/policyをforward migrationで明示的に追加する。

### 8.2 Backend credential gate

Security migration適用前に、staging Backend credentialが`service_role`または承認されたserver-only roleであることを、値を表示せず分類する。分類できない場合はstaging applyを停止する。BrowserやNext.js client bundleへserver credentialを渡さない。

### 8.3 Failure containment

Supabase migrationはfile単位で履歴化されるため、baseline成功後にsecurity migrationが失敗する可能性がある。Stagingは空かつdisposableであることを前提に、次を強制する。

- baselineとsecurity migrationを同じreview/push単位にする
- staging rolloutではbaselineの直後にsecurity migrationを中断なく連続適用する
- baselineとsecurity migrationの両方についてmigration history、RLS、ACL、function権限の成功確認が完了するまで、Backend/Frontendをstagingへ接続・deployせず、Render/LINE webhookからも参照させない
- security migration後のACL/RLS検査が成功するまでsynthetic dataを入れない
- security migration失敗時は部分状態を修復せず、staging projectを再作成して空DBからreplayする

## 9. Function security strategy

### 9.1 `set_updated_at()`

採用仕様:

- `SECURITY INVOKER`
- fixed `search_path = pg_catalog`
- built-in functionは`pg_catalog`で明示
- trigger以外のpublic APIとして扱わない
- PUBLIC、`anon`、`authenticated`から`EXECUTE`をrevoke
- migration ownerと必要なserver roleだけが利用可能

Triggersからの利用を、insert/update APIの回帰試験で確認する。Functionをbrowser-callable RPCとして公開しない。

`set_updated_at()`はbusiness tableを直接参照せず、triggerから渡される`NEW` rowだけを更新する。したがって`search_path = pg_catalog`と整合し、利用するbuilt-in functionは`pg_catalog`で明示する。Trigger定義側の対象tableは`public.app_settings`のようにschema-qualifiedで指定する。

### 9.2 `complete_application_session()`

Production bodyをそのまま複製せず、返却契約を維持しながら次を強化する。

- `SECURITY INVOKER`を維持する。`SECURITY DEFINER`へ変更しない。
- fixed `search_path = pg_catalog`
- `public.application_sessions`と`public.applicants`を常にschema-qualifiedで参照
- session取得は`id + company_id + line_user_id`で行い、`FOR UPDATE`を維持
- applicant重複確認は`application_session_id + company_id + line_user_id`で行う
- applicant INSERTでは`company_id`を明示する
- session UPDATEにも`id + company_id + line_user_id`を付け、更新件数を検証する
- completed sessionは既存契約どおり冪等な結果を返す
- cancelled/non-active sessionはfail-closedで拒否する
- PUBLIC、`anon`、`authenticated`から`EXECUTE`をrevokeし、server roleだけへgrantする

Row lock、applicant INSERT、session UPDATEは1回のfunction call内の同一transactionで行う。Function本体のapplicant/session data flow、return JSON shape、重複event挙動は既存Backend characterization testsで固定してからbaseline SQLを作る。

## 10. `company_id` compatibility strategy

### 10.1 Legacy six tables

次の6 tablesはproductionで`company_id text nullable + fixed default`である。

- `applicants`
- `inquiries`
- `interview_slots`
- `line_message_logs`
- `faq_categories`
- `faqs`

Staging baselineでは、productionのnullabilityを維持しつつ**fixed defaultを設定しない**。これにより現在schemaとの互換性を最小限に保ち、暗黙の単一tenant割当を新しい正式仕様にしない。

Current Backendが6 tablesへのINSERTで`company_id`を明示することをcharacterization testで固定する。暗黙defaultへ依存する経路が見つかった場合はbaselineへdefaultを戻さず、application側の明示設定を別修正として先に完了する。

`inquiries.company_id`は後続`202608070001_inquiry_workflow_columns.sql`でNOT NULLになる。空stagingではbackfill不要である。他の5 tablesのNOT NULL/FK化はcompanies modelとtenant migrationへ回す。

### 10.2 Existing NOT NULL tables

Settings tablesと`application_sessions.company_id`はproductionどおりNOT NULLかつ暗黙tenant defaultなしを維持する。

### 10.3 `contacts`

`contacts`はproductionと同じくbaselineでは`company_id`を追加しない。これはproduction同値構造を維持し、baselineへ未設計のmulti-tenant変更を混ぜないためである。

ただし、複数企業が同じLINE userを扱う前に、`contacts`をcompany-scoped keyへ移行する独立migrationが必須である。それまでは`contacts`をmulti-tenant safeと扱わない。

## 11. Legacy migration handling

### 11.1 Archive location

2026年7月の4 filesは、将来のchain-cutover commitでbyte-for-byte維持して次へ移す。

`supabase/legacy_migrations/2026-07-pre-baseline/`

同directoryへmanifestを置き、各fileについて次を記録する。

- original filename
- SHA-256
- original Git commit
- production artifactとの対応
- remote historyでappliedと証明できないこと
- canonical active chainでは再実行しない理由

`supabase/baselines/2026-07-24-public-schema-baseline.sql`は監査artifactとして残し、active migrationにはしない。

### 11.2 Active chain separation

`supabase/migrations/`にはcanonical chainだけを置く。Supabase CLIはこのdirectoryをlocal historyとして扱うため、legacy fileをactive directoryへ残したままbaselineを追加しない。

既存問い合わせ4 filesはactive directoryに残し、内容・version・filenameを維持する。

### 11.3 Version selection rule

Baselineとsecurity migrationの数値versionはこの設計では確定しない。理由は、`supabase migration new`が生成する現在時刻versionは既存`202608070001`より後になり、必要な適用順と一致しないためである。

実装時は次の決定手順を必須とする。

1. localとstagingの`migration list`を再確認し、remote historyが0件であることを確認する。
2. `202608070001`より前、かつrepository historyで未使用の2つのversionを候補化する。
3. baseline versionがsecurity versionより前であることを確認する。
4. version衝突、桁数、lexical/timestamp順を使用するSupabase CLI versionで検証する。
5. Pull request reviewで2 versionを明示承認する。

File suffixは次で固定する。

- `public_schema_current_state_baseline.sql`
- `fail_closed_security_privileges.sql`

この手順により、安易なbackdateや問い合わせmigrationのrenameを避ける。

### 11.4 Future production history repair

Production history repairは別承認作業とする。原則は次のとおりである。

- legacy 7月versionをproductionへappliedとして記録しない
- baseline post-stateとproduction構造の同値性を証明できた場合だけ、baseline versionをapplied候補にする
- security migrationのpost-stateは現在productionに存在しないため、未実行のままapplied扱いにしない
- security migrationと問い合わせ4本は、production rolloutが承認された場合に通常のforward migrationとして適用する
- `migration repair`はhistoryだけを変更しSQLを実行しないが、それ自体がproduction変更なので独立承認、backup、dry-run、監査記録を必須にする

## 12. Proposed migration chain

Active chainの論理順は次とする。

```text
empty database
  -> current-state structural baseline
  -> fail-closed security / privilege migration
  -> 202608070001_inquiry_workflow_columns.sql
  -> 202608070002_inquiry_replies.sql
  -> 202608070003_line_message_log_inquiry_reply.sql
  -> 202608070004_finalize_inquiry_reply.sql
  -> future forward migrations
```

問い合わせmigrationの前提は次のように満たされる。

- Migration 1: baselineが`inquiries`と`set_updated_at()`を提供
- Migration 2: baselineがUUID生成依存を提供し、Migration 1がcomposite UNIQUEを提供
- Migration 3: baselineが`line_message_logs`、Migration 2が`inquiry_replies`を提供
- Migration 4: Migration 1〜3が全table/column/constraintを提供

## 13. Verification strategy

将来実装は次の順序以外でremoteへ進めない。

1. **Static review**
   - migration file順、transaction境界、DML不在、secret/PII不在を確認
   - function bodyだけに業務DMLが存在し、migration適用時にfunctionを呼ばないことを確認
2. **Empty local DB replay**
   - `supabase db reset --local`でactive chainを最初から適用
   - 2回再作成してschema fingerprintが一致
3. **Structural equivalence**
   - tables/columns/type/nullability/default
   - 19 base constraints、43 base indexes、7 base triggers
   - function signaturesとnormalized definitions
   - inquiry migration後に増えるobjectsは別expected inventoryとして確認
4. **Security assertions**
   - baseline 12 tablesでRLS enabled、policy 0
   - inquiry migration後の`inquiry_replies`もRLS enabled
   - PUBLIC/anon/authenticatedにbusiness table/function権限なし
   - approved server roleだけが必要操作を実行可能
   - default ACLが新規test objectへclient grantを付与しない
5. **Function tests**
   - cross-company session/applicantを取得・更新しない
   - concurrent completionでapplicantを重複作成しない
   - completedは冪等、cancelledは拒否
   - `set_updated_at()` triggerが対象tableだけを更新
6. **Application regression**
   - Python compile
   - Backend全unittest
   - TypeScript typecheck
   - Next.js production build
7. **Staging preflight**
   - project refが`eygotkbexkjzzvcxqfea`
   - migration history 0
   - application未接続、business data 0
8. **Staging apply**
   - full chainを一度だけ適用
   - schema/security fingerprintを再確認
9. **Synthetic-only workflow**
   - synthetic company、session、applicant、inquiryだけでAPI/RPCを検証
   - LINE本番送信は行わない

Productionは全工程でread-only comparison sourceとする。

## 14. Rollback strategy

### Local

Migrationに問題があればfileを修正し、local DBを破棄して空DB replayをやり直す。未公開chainにdown migrationは作らない。

### Staging

Stagingはbusiness dataを持たないdisposable environmentとして扱う。Baseline/security migrationの途中失敗、fingerprint不一致、権限検査失敗時は、部分修復やhistory repairをせずstaging projectを削除・再作成し、history 0からreplayする。Project削除は費用・承認を伴う外部操作なので、実行前にユーザー承認を得る。

### Production

本設計ではrollback対象の変更を行わない。将来のproduction rolloutでは、managed backupとrestore rehearsalを先に確認し、schema変更失敗はreview済みforward fixまたはbackup restoreで扱う。Productionへ`db reset --linked`を使用しない。

## 15. Production safety rules

Production remote migration historyが0件であるため、production history repairの手順が別途承認され、schema equivalence、backup、dry-run、対象versionの検証が完了するまで、productionに対する次の操作を全面的に禁止する。

- `supabase db push`
- migration apply
- `supabase migration repair`
- その他のproduction schemaまたはmigration history変更

- Production MCPはproject-scopedかつ`read_only=true`でなければ接続しない。
- ProductionへDDL/DML/function invocation/migration applyを行わない。
- ProductionをCLIのdefault linked projectにしない。
- Apply command前にproject refを二者確認する。
- Production schema comparisonはcatalog metadataと非PII集計だけを使う。
- Production secrets、business rows、Auth users、Storage objectsをstagingへcopyしない。
- `db pull`、`migration repair`、`db push`をproductionへ実行する作業は別承認にする。
- Production remote historyをschemaそのものの証拠として扱わない。

## 16. Open risks

| Risk | Resolution gate |
|---|---|
| Baseline/securityの数値versionが未選定 | 実装PRでlocal/remote historyとCLI orderingを確認し、問い合わせmigrationより前の未使用2 versionを明示承認する |
| Backend credential種別が未確認 | staging apply前に値を表示せずserver-only credentialとして分類する。分類不能なら停止する |
| Production RPCのreturn契約をsecurity強化で壊す可能性 | 現行bodyのcharacterization testsを先に追加し、同じresponse shapeと冪等挙動を固定する |
| Legacy company columnsがnullable | fixed defaultは追加せず、全INSERTのcompany明示テストをgateにする。NOT NULL/FKはcompany model migrationへ分離する |
| `contacts`がtenant scopeを持たない | baselineでは現状維持し、複数企業LINE導入前の独立migrationを必須にする |
| Security migration失敗後の短時間の部分状態 | stagingをapplicationへ接続せず、失敗時はproject再作成で回復する |
| Supabase managed default ACLの作成主体差 | staging catalogでobject owner/default ACLを確認し、対象roleごとのpost-state assertionで判定する |
| Baselineとproductionの意図的security差分 | structural fingerprintとsecurity fingerprintを別々に記録し、差分を混同しない |
| Production remote history 0 | staging equivalence後も自動repairせず、別承認のproduction cutover計画で扱う |

## 17. Acceptance criteria

この設計に基づく将来のmigration implementationは、次をすべて満たした場合だけstaging適用候補になる。

- Active chainから2026年7月legacy 4 filesが分離され、manifest/hash付きで保存されている
- Existing inquiry migration 4 filesの内容・version・filenameが維持されている
- Baseline/securityの承認済みversionが問い合わせmigrationより前に並ぶ
- Empty local DBから全chainを連続replayできる
- Base inventoryが12 tables、19 constraints、43 indexes、7 triggers、2 functionsと一致する
- Business data、production tenant default、secret、PIIを含まない
- `complete_application_session()`のcompany境界、locking、冪等性、更新条件がtestで固定されている
- `set_updated_at()`と`complete_application_session()`がfixed search pathを持つ
- PUBLIC/anon/authenticatedからbusiness table/function accessがfail-closedである
- Future objectのdefault ACLがclient accessを自動付与しない
- Legacy 6 tablesの`company_id`にfixed defaultがない
- `contacts`の非tenant構造が既知の制約として明示されている
- Backend全tests、TypeScript typecheck、Next.js buildが成功する
- Staging検証はsynthetic dataだけを使う
- ProductionへのDB変更、history repair、migration applyが行われていない

このacceptance criteriaを満たしてもproduction applyは自動承認されない。Production rolloutはbackup、staging equivalence、security reviewを含む別設計と承認を必要とする。
