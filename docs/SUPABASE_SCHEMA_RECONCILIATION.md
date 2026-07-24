# Supabase Schema Reconciliation

調査日: 2026-07-24 (Asia/Tokyo)

対象ブランチ: `agent/supabase-schema-reconciliation`

基準commit: `8c09a66` (`origin/main`)

対象project: project-scoped / read-only Supabase MCPで指定された1 project

sanitized snapshot: `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`

## 1. 結論

**判定: production migrationはNO-GO、stagingでの再構築準備はCONDITIONAL GO。**

- live `public`には12 base table、2 function、7 non-internal trigger、42 indexがある。view、materialized view、sequence、foreign tableはない。
- `supabase_migrations.schema_migrations`はliveに存在せず、dedicated migration listも空だった。一方、repositoryには4 migration fileがある。
- 4 fileが作る・変更するDDL artifactはliveに広く一致するが、履歴行がないため「Supabase CLI migrationとして適用済み」とは扱えない。
- `README.md:21-26` は4 fileをSupabase SQL Editorで番号順に実行する手順を示す。この手順ならmigration historyが作られないため、4 fileのartifactが存在し履歴が空である現在状態と整合する。ただし実際にその経路で実行されたこと自体は監査ログ未確認のため**高確度の推測**である。
- 7つのlegacy base tableにはchecked-in `CREATE TABLE`がない。特に`contacts`はchecked-in DDLに一切ない。
- 12 tableすべてでRLSとFORCE RLSが無効、policyは0件である。さらに各tableは`anon`、`authenticated`、`service_role`へ全table privilegeを持つ。実際のHTTP到達性はPostgREST exposed-schema設定を未確認だが、認証・RLS migration前に解決すべき重大な権限状態である。
- 推奨は**案C: 新しいstaging projectでclean migration chainを再構築・検証し、productionのhistory整合はschema equivalenceの証明後に別作業で行う**。

今回、SupabaseへのDDL/DML、migration history変更、Storage/Auth/Render設定変更は行っていない。

## 2. 取得方法と安全条件

### 2.1 ローカル環境

| 項目 | 結果 |
|---|---|
| Supabase CLI | 利用不可 |
| Docker CLI / Docker Engine service | 利用不可 |
| `psql` | 利用不可 |
| `pg_dump` | 利用不可 |
| linked project設定 (`supabase/config.toml`, `.supabase`, `supabase/.temp/project-ref`) | なし |
| process環境のDB/Supabase変数名 | 0件 |
| repositoryのenv file | example fileのみ |
| OS credential targetのSupabase/Postgres候補 | 検出なし |

不足ツールはインストールしていない。CLIとDockerがないため`supabase db dump`と`supabase db pull`は実行せず、project-scoped・read-only MCPのcatalog SELECTへ切り替えた。

### 2.2 live取得

次のread-only operationだけを使用した。

- `list_tables(public, verbose=true)`
- `list_migrations`
- `list_extensions`
- `list_storage_buckets`
- `get_storage_config`
- `execute_sql`によるcatalog metadataとaggregate count

catalog queryはobject inventory、column、constraint、index、function、trigger、policy、ACL、company aggregateへ分割した。業務行、company identifier実値、個人情報、LINE ID、メッセージ本文、Auth user行は取得していない。

schema-only raw dumpは作成していないため、削除対象のraw fileもない。

## 3. live `public` schema

### 3.1 object inventory

Base tableは次の12件。

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

functionは次の2件。

- `public.set_updated_at()` returns `trigger`
- `public.complete_application_session(uuid, text, text, text, text, text, text, text, text)` returns `jsonb`

non-internal triggerは次の7件。

- `set_app_settings_updated_at`
- `set_applicant_status_settings_updated_at`
- `set_application_sessions_updated_at`
- `trg_faq_categories_updated_at`
- `set_faq_settings_updated_at`
- `trg_faqs_updated_at`
- `set_question_tree_settings_updated_at`

`complete_application_session`のlive bodyはchecked-in `supabase/migrations/202607200001_application_sessions.sql:111-178`と同じ処理形状だった。sessionの最初の取得はcompany/userを含むが、最後のsession更新は`id`だけを条件とする。このRPCの権限・RLS再設計はAuth/RLS phaseの必須対象である。

### 3.2 constraintsと未定義relation

- 19 constraintを確認した。PK、FAQのFK、FAQ/statusのUNIQUE、session/tagのCHECKはsanitized snapshotへ記録した。
- `faqs.category_id -> faq_categories.id ON DELETE CASCADE`だけが業務table間FKとして確認された。
- `interview_slots.applicant_id`、`applicants.application_session_id`にはFKがない。
- 11本の`company_id`はいずれもcompanies相当tableへのFKを持たない。
- `faq_categories.name`は全企業でglobal unique、`faqs(category_id, question)`もcategory単位uniqueである。将来の企業UUID bridge前に意図を再確認する。

### 3.3 RLS、policy、grant、API公開可能性

| 項目 | live事実 |
|---|---|
| RLS | 12 tableすべてdisabled |
| FORCE RLS | 12 tableすべてdisabled |
| `public` policy | 0件 |
| `storage` policy | 0件 |
| schema grant | `PUBLIC`, `anon`, `authenticated`, `service_role`が`USAGE` |
| table ACL | 12 tableすべてで`anon`, `authenticated`, `service_role`が全table privilege |
| function ACL | 2 functionとも`PUBLIC`, `anon`, `authenticated`, `service_role`が`EXECUTE` |
| default privilege | `postgres`と`supabase_admin`が作るpublic table/sequence/functionへclient role権限を付与 |

PostgRESTの実exposed-schema設定はDashboard/Management API未確認である。ただしpublic schemaが公開対象なら、現在のACLとRLS無効の組合せはclient roleによる行アクセスを妨げない。Auth/RLS実装ではpolicyだけでなく既存grant、function `EXECUTE`、default privilegeを明示的に設計する必要がある。

### 3.4 Storageとextension

- Storage bucketは0件。public/private bucket設定対象は現時点でない。
- Storage policyも0件。
- installed extensionは`pgcrypto`, `supabase_vault`, `pg_stat_statements`, `uuid-ossp`, `plpgsql`。
- `pg_graphql`はavailable entryとしては存在したが`installed_version`がなく、installedとは判定しない。

## 4. `company_id`集計

値は取得・記録していない。`distinct`件数とNULL件数だけを集計した。

| Table | 型 | Nullable | Default | company index | FK | distinct数 | NULL数 |
|---|---|---:|---|---|---|---:|---:|
| `applicants` | `text` | yes | constant / REDACTED | yes | none | 1 | 0 |
| `inquiries` | `text` | yes | constant / REDACTED | yes | none | 0 | 0 |
| `interview_slots` | `text` | yes | constant / REDACTED | yes | none | 1 | 0 |
| `faq_categories` | `text` | yes | constant / REDACTED | yes | none | 1 | 0 |
| `faqs` | `text` | yes | constant / REDACTED | yes | none | 1 | 0 |
| `line_message_logs` | `text` | yes | constant / REDACTED | yes | none | 1 | 0 |
| `faq_settings` | `text` | no | none | yes | none | 0 | 0 |
| `app_settings` | `text` | no | none | yes | none | 1 | 0 |
| `question_tree_settings` | `text` | no | none | yes | none | 0 | 0 |
| `applicant_status_settings` | `text` | no | none | yes | none | 1 | 0 |
| `application_sessions` | `text` | no | none | yes | none | 0 | 0 |
| `contacts` | 列なし | n/a | n/a | no | none | n/a | n/a |

distinct 0かつNULL 0はempty tableを意味する。非empty tableで確認されたdistinct数はいずれも1だが、これだけではそのidentifierが正式な1社を表すこと、または全rowが正しい企業へ割り当て済みであることを証明しない。

## 5. checked-in migrationとの照合

判定では、live DDL artifactの一致と「migration history上の適用済み」を分ける。実company default literalと業務rowは比較対象外であり、DML実行履歴は証明できないため、4本とも最終分類は**部分一致**とする。

| Migration | 目的 | live artifact | 判定 | 基礎DDL依存 / 空DB | 再実行安全性 | 将来方針 |
|---|---|---|---|---|---|---|
| `202607190001_mvp_security_foundation.sql` | settings 3 table、company列/default/index、timestamp function/trigger | 対象table、列、index、3 trigger、functionを確認 | 部分一致（DDL shapeは一致。default実値と過去DMLは非比較） | 単独でも3 settings tableは作るがlegacy 6 tableは作らない | current compatible schemaでは概ねidempotent。ただし既存rowを書き換える処理を含む | stagingでbaselineへ統合候補 |
| `202607190002_admin_configuration.sql` | status settings table/index/trigger/seed | table、constraint、冗長unique index、sort index、triggerを確認。現在row数は7でseed後変更の可能性 | 部分一致 | `set_updated_at`へ依存し単独不可 | conflict-safe seedだが、partial tableのNOT NULL/constraint修復は保証しない | baseline統合候補。seedは別管理を検討 |
| `202607200001_application_sessions.sql` | persistent session、applicant link、RPC | table全列、CHECK、index、trigger、applicant列/index、RPCを確認 | 部分一致（DDL/function shapeは一致。backfill履歴は非比較） | `applicants`と`set_updated_at`へ依存。checked-in chainだけの空DBでは失敗 | compatible schemaでは概ね再実行可能だが、index作成前の重複や既存不正rowで失敗し得る | baselineへ現状態を回収し、RPC securityは後続migration |
| `202607210001_applicant_tags.sql` | applicants tags列/CHECK/backfill | 列、default、NOT NULL、CHECKを確認 | 部分一致（DDLは一致。backfill履歴は非比較） | `applicants`へ依存し単独・checked-in chainだけでは不可 | compatible schemaではidempotent。row normalizationを含む | baseline統合候補 |

### 5.1 migrationにはないlive artifact

checked-in chainは次の7 base tableを作成しない。

- `applicants`
- `inquiries`
- `contacts`
- `interview_slots`
- `faq_categories`
- `faqs`
- `line_message_logs`

さらに次の代表的なbase artifactもchecked-in migrationにない。

- base PK、FAQ FK、global UNIQUE、legacy default/nullability
- `idx_faq_categories_active`, `idx_faq_categories_sort_order`
- `idx_faqs_category_id`, `idx_faqs_sort_order`, `idx_faqs_visible`
- `idx_interview_slots_applicant_id`, `idx_interview_slots_line_user_id`, `idx_interview_slots_status`
- `idx_line_message_logs_created_at`, `idx_line_message_logs_line_user_id`
- `trg_faq_categories_updated_at`, `trg_faqs_updated_at`

## 6. migration history不整合の原因仮説

### 高確度

4本はSupabase SQL Editorから手動実行された可能性が高い。

根拠:

1. `README.md:21-26`がSQL Editorで番号順に実行するよう明示する。
2. 4本のDDL artifactがliveに広く一致する。
3. `supabase_migrations.schema_migrations`自体がliveに存在しない。
4. Supabase CLI公式仕様では最初の`db push`がhistory tableを作り、適用versionを記録する。

これは経路を直接証明する監査ログではないため、事実ではなく高確度の推測として扱う。

### 中確度

legacy 7 tableは4本より前にDashboard Table Editor、SQL Editor、別script、または別repositoryから作られた。checked-in migrationがそれらを`ALTER`前提にすることは事前存在を示すが、どの経路かは判断不能。

### 低確度 / 根拠なし

- migration history tableが後から削除された
- 別migration toolがversionを別schemaへ保存した
- live schemaが別branchの未保存SQLから作られた

これらを支持するrepository/catalog evidenceはない。

## 7. 再構築案の比較

| 比較 | 案A: liveを1 baselineへ統合 | 案B: pre-4本基礎DDLを逆算 | 案C: 新stagingでclean chain構築 |
|---|---|---|---|
| 本番リスク | 中。baselineを誤って実行する危険 | 中〜高。過去状態の逆算誤り | 低。productionへ触れず検証 |
| 再現性 | 高。ただし歴史は失う | 成功すれば高い | 最も高い。空DB replayを証明可能 |
| 作業量 | 中 | 高 | 高 |
| ロールバック性 | baseline適用前なら容易 | 複数段階で複雑 | staging破棄で容易 |
| 既存データ影響 | history repair判断を誤ると危険 | backfill再実行リスク | staging検証中はなし |
| history整合 | 新baseline versionの扱いが必要 | 既存4 versionを維持しやすい | 証明後にproduction historyを別途repair |
| Auth/RLSへの進みやすさ | schema固定後は進みやすい | 過去DDLの補修に時間 | 安全なrehearsal後に最も進みやすい |
| 費用 | 追加なし得る | 追加なし得る | staging projectのplan/usage費用可能性 |

### 推奨: 案C

新しいstaging projectで、sanitized snapshotを直接適用せず、review済みの実行可能baselineを別途作る。空DBへreplayし、liveとのschema equivalenceと62件のapplication回帰を確認する。production migration historyはその証明とbackupの後に独立した承認作業として整合させる。

staging用canonical chainの形は、最初はcurrent live schemaを表す1 baselineを候補とする。ただしcompany default、nullable、ACL、RLS無効をそのまま安全な将来仕様として固定しない。live同値を再現するbaselineと、その直後に権限を安全化するforward migrationを分離してレビューする。

## 8. 将来のmigration history修復計画

今回は以下を一切実行していない。

1. **tooling準備:** 承認済み端末へSupabase CLI、Docker Engine、PostgreSQL clientを導入し、versionを固定する。
2. **接続確認:** `supabase link`後、`supabase migration list --linked`でlocal/remote versionを比較する。現在はremote history tableなしを想定するが、実行時に再確認する。
3. **backup:** productionのSupabase managed backup状態を確認し、schema-only dumpと暗号化したdata backupをrepository外へ取得する。restore rehearsalをstagingで行う。
4. **baseline作成:** このsanitized snapshotではなく、秘密値方針、function body、grant、owner差分をレビューした実行可能migrationを新規作成する。versionはCLIが作成した実timestampを使用し、今は推測しない。
5. **staging replay:** clean stagingへmigration chainを最初から適用する。`db reset --linked`はproductionでは絶対に使わない。
6. **schema equivalence:** live/staging双方で、table/column/type/default/nullability、constraint、index、function definition hash、trigger、RLS/FORCE RLS、policy、ACL、extensionを正規化して比較する。owner、generated name等の許容差分は事前に列挙する。
7. **application検証:** Backend 62件、Python構文、TypeScript型検査に加え、staging接続専用のread/write smoke testをテストデータだけで行う。
8. **repair条件:** production schemaと選んだmigration versionのpost-stateが同値であり、migration本体をproductionへ再実行してはいけない場合だけhistory repairを検討する。DDLが部分一致のまま、またはDML効果が必要なversionは`applied`扱いにしない。
9. **applied version:** 既存4 versionを維持する場合の候補はfile名のversion部分だけである。ただし4本をbaselineへ統合する場合はそのversionを使用しない。どちらを記録するかはstaging chain確定後に承認し、今は決定しない。
10. **repair実行:** 承認されたversionだけを`supabase migration repair <version> --status applied --linked`で記録する。これはschema変更ではなくhistory変更だが、production changeとして別承認を必須にする。
11. **repair後確認:** `supabase migration list --linked`、catalog fingerprint、application smoke test、Supabase advisorを再実行する。
12. **dry-run:** `supabase db push --dry-run --linked`でpending migrationが意図どおりか確認する。0件を期待する場合は0件以外なら停止する。
13. **rollback:** repairだけを戻す必要がある場合、同じversionを`--status reverted`でhistoryから戻し、schemaは触らない。schema変更後のrollbackはbackup restoreまたはreview済みforward fixを使用し、remote resetは使用しない。

Supabase CLIでは`migration list`がlocal/remote timestampを比較し、`migration repair`はhistoryだけをapplied/revertedへ変更し、`db push --dry-run`は予定migrationを表示する。現行仕様は[Supabase CLI reference](https://supabase.com/docs/reference/cli/supabase-db-dump)で再確認した。

## 9. Auth migration前のブロッカー

1. canonical baselineとmigration version方針が未確定。
2. liveの全tableでRLS無効、client roleへ全table privilegeがある。
3. company master/FKがなく、company identifierは`text`。
4. 6 tableはcompany列nullableかつconstant default、`contacts`には列がない。
5. company identifierと将来の`companies.id uuid`の人手承認済み対応表がない。
6. `complete_application_session`の最終更新queryがcompany条件を含まず、functionはPUBLIC execute可能。
7. `faq_categories.name`のglobal unique等、multi-tenant制約の意図が未確定。
8. clean empty DBから現行schemaを再現できるmigration chainがない。

## 10. 実行した検証

### 開始時

```text
git switch main
git fetch origin main
git merge --ff-only origin/main
git switch -c agent/supabase-schema-reconciliation
python -m unittest discover -s tests -v
```

開始時Backend test: 62件成功。開始時working tree: clean。

### 完了時

```text
python -m unittest discover -s tests -v
python -c "import ast, pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8'))"
C:\Program Files\nodejs\npm.cmd exec tsc -- --noEmit --incremental false
git diff --check
git status
```

- Backend test: 62件成功
- Python AST parse: 成功
- TypeScript type check: 成功
- `git diff --check`: 成功
- PowerShellは`npm`をexecution-policyで拒否される`npm.ps1`へ解決したため、同じNode.js installationの`npm.cmd`を直接使用した。repositoryと環境設定は変更していない。

sanitized SQLは、行データstatement、実company default、API key、URL、メールアドレス、LINE identifierを含まないことを機械検索した。
