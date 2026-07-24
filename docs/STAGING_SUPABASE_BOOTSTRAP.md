# Staging Supabase Bootstrap

作成日: 2026-07-24

対象: productionと分離した新規Supabase staging project

baseline候補:
`supabase/baselines/2026-07-24-public-schema-baseline.sql`

## 1. 現在の判定

staging projectの作成とschema適用は**まだ実行しない**。

理由:

- 現在の端末にはSupabase CLI、Docker Engine、`psql`、`pg_dump`がない。
- baseline候補には未確定DDLがあり、active migrationではない。
- repositoryの`supabase/migrations/`には、base tableを作成しない既存4 migrationが残っている。
- current production migration historyは空であり、staging作業とproduction history修復を同じ作業にしてはいけない。

### 公開キー露出ゲート

checked-in codeについてはGO。

- frontendにSupabase package/clientはない。
- browser fetchは同一originの`/api/admin/*`だけである。
- tracked frontend envに`NEXT_PUBLIC_SUPABASE_*`はない。
- current local build artifactにもSupabase URL/key参照はない。
- backendの`SUPABASE_KEY`はlocal/process値がなく、分類は**不明**。
- deployed Render env/buildは未確認であり、production key分類も未確認。

このGOはbaseline候補の文書作成だけを許可する。RLS無効かつclient
roleへ広いgrantがあるlive DBの安全性を意味しない。

## 2. 採用するmigration chain

### 採用: 案3「baseline＋今後のmigrationだけを新chainとして開始」

新しいstaging projectへ、承認済みのcurrent-state baselineを最初の履歴付きmigrationとして適用し、その後のAuth、RLS、grant修正を新しいtimestamp migrationとして積み上げる。

既存4 migrationは現在のlive schemaへ至った証拠として保持するが、新chainでは再実行しない。今回は変更・移動・削除しない。将来、実行可能baselineが承認された時点で、別commitによりlegacy archiveへ移すかactive chainから除外する方法を決める。

### 比較

| 案 | 長所 | 短所 | 判定 |
|---|---|---|---|
| 1. 現在の実DB全体を単一baseline化 | current stateへ最短で到達 | unsafeなdefault、ACL、RLS、RPCをそのまま正規仕様として固定しやすい | 不採用 |
| 2. 4 migration適用前の基礎schemaを逆算 | 既存4 fileをactive historyとして残せる | legacy tableの作成経路が不明で、過去DDL/DMLを推測する必要がある | 不採用 |
| 3. baseline＋今後のmigrationだけで新chain | 空DB replayと今後の履歴を明確に分離できる | 既存4 fileのarchive方針とproduction history整合を別途決める必要がある | 採用 |

案3で使うbaselineは、live unsafe stateの無批判な複製ではない。schema equivalenceに必要な構造と、直後に適用するsecurity-forward migrationの境界を明示してレビューする。

## 3. baseline候補の未確定DDL

`supabase/baselines/2026-07-24-public-schema-baseline.sql`は次を含む。

- 12 table
- 2 function signature
- 7 non-internal trigger
- 43 index相当（15 constraint-backed + 28 explicit）
- PK、FK、UNIQUE、CHECK
- `company_id`、applicant `tags`、`application_sessions`
- settings系table

次は意図的に未確定である。

1. 6 legacy tableのconstant `company_id` default
2. `complete_application_session`のrow-changing body
3. RLS、FORCE RLS、policy
4. table/function/schema/default privilege
5. extension ownershipとSupabase-managed schema

候補内の`complete_application_session`はsignatureだけを作り、実行時はfail closedとする。完全なfunction bodyを戻す前にcompany predicate、search path、owner、`EXECUTE` grantをレビューする。

## 4. staging projectの手動作成

Supabase Dashboardで人が次を行う。

1. productionと別のorganization/project名でstaging projectを作成する。
2. region、plan、compute size、backup/log retentionを確認する。
3. productionと識別しやすいproject nameを使用する。
4. staging DB passwordをpassword managerへ保存する。
5. project refを承認記録へ保存する。repositoryや文書へ実値を書かない。
6. production project refとstaging project refを別の担当者が照合する。
7. stagingへ実データ、production secret、LINE credentialをコピーしない。
8. stagingのAPI keyはstaging専用とし、production/Renderへ設定しない。

## 5. CLIとDockerの準備

Supabase local developmentにはCLIとDocker互換container runtimeが必要である。公式CLIはlocal stack起動にDocker API互換runtimeを要求し、全service起動には7 GB以上のRAMを推奨している。

導入前に確認する。

- 会社端末へのsoftware導入権限
- 管理者権限と再起動の必要性
- Docker Desktopまたは代替runtimeの利用規約・license
- 7 GB以上の空きRAM、disk容量、仮想化機能
- approved Supabase CLI versionとversion固定方法
- package downloadに使用するnetwork/proxy
- credential保存先
- CIで使う場合のsecret管理とrunner費用

このrepository調査ではCLI/Dockerをインストールしない。

参考:

- [Supabase Local Development & CLI](https://supabase.com/docs/guides/local-development)
- [Supabase CLI reference](https://supabase.com/docs/reference/cli/supabase-orgs-list)

## 6. local empty-DB replay

baseline候補の未確定項目を解消し、review済みの実行可能SQLへ変換した後に行う。

1. productionへlinkされていない専用worktreeまたはrepository外のrehearsal directoryを作る。
2. `supabase init`を実行する。
3. `supabase migration new public_schema_baseline`で実timestampのmigrationを作る。
4. 承認済みbaseline SQLを生成されたfileへ入れる。
5. 既存4 migrationをこのclean rehearsal chainへコピーしない。
6. `supabase start`でlocal stackを起動する。
7. `supabase db reset --local`で空DBからbaselineを適用する。
8. `supabase migration list --local`でbaseline versionだけが適用済みであることを確認する。
9. `supabase db lint --local`とpgTAP schema testを実行する。
10. local databaseを破棄し、同じ手順をもう一度実行してfingerprintが一致することを確認する。

`supabase/baselines/`の候補を直接`db push`しない。CLIは`supabase/migrations/`だけを履歴付きmigrationとして扱う。

## 7. staging projectへlinkする方法

production refをcommand historyへ混ぜない専用terminalで行う。

```text
supabase login
supabase link --project-ref <APPROVED_STAGING_PROJECT_REF>
supabase migration list --linked
```

DB passwordはpromptまたは安全なcredential storeを使用する。command line、文書、Git、CI logへ値を書かない。

link後に次を確認する。

- `.supabase`または`supabase/.temp/project-ref`がapproved staging refを指す
- Dashboard上のproject name/regionがstaging
- staging migration historyが空
- stagingに業務tableと実データがない
- production projectへ同時にlogin/linkしたterminalがない

一致しなければその場で停止する。

## 8. migrationを履歴付きで適用する

local replayとreviewが成功したclean chainだけで行う。

```text
supabase migration list --linked
supabase db push --dry-run --linked
supabase db push --linked
supabase migration list --linked
```

最初の`db push`はstagingの
`supabase_migrations.schema_migrations`へbaseline versionを記録する。
`--dry-run`にbaseline以外の既存4 versionや予期しないmigrationが表示された場合はpushしない。

`db pull`、`migration repair`、`db reset --linked`は最初のbootstrapでは使用しない。

参考:

- [Database migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [CLI workflows](https://supabase.com/docs/guides/local-development/cli-workflows)

## 9. schema equivalence

productionはread-only query、stagingはreview済みqueryで次を正規化比較する。

- table、column順、型、default分類、nullability
- PK、FKとaction、UNIQUE、CHECK、validation状態
- 43 indexのname、column、sort、predicate、uniqueness
- function signature、属性、normalized definition hash
- 7 triggerのdefinitionとenabled状態
- view、materialized view、sequence、foreign tableの不存在
- extension依存
- RLS、FORCE RLS、policy
- schema/table/function/default privilege

baseline候補の未確定項目は差分として残るのが正しい。全差分に承認済み理由が付くまでequivalentと判定しない。

## 10. productionへ触れない確認

各external commandの直前に次を読み上げて確認する。

- target project name
- target project refの末尾4文字だけ
- target region
- staging owner
- expected migration version

禁止:

- production refで`link`
- productionへ`db push`
- productionへ`db reset --linked`
- production migration historyのrepair
- production data/secretのstagingコピー
- Dashboard SQL Editorでのmanual schema変更

production read-only MCPはschema equivalence取得だけに使う。

## 11. rollbackとstaging再作成

baseline適用前:

- local migration fileを修正し、local stackを`db reset --local`で作り直す。

staging適用後:

1. stagingに実データがないことを確認する。
2. linked projectがstagingであることを二者確認する。
3. project自体を削除・再作成する方法を第一候補とする。
4. disposable stagingで明示承認された場合だけ`db reset --linked`を検討する。
5. 新staging refへlinkし直し、空のmigration historyから再実行する。

production rollbackにはこの手順を使わない。

## 12. 費用

費用が発生し得るもの:

- 追加staging project
- compute size
- disk/database容量
- egress
- Storage
- Auth利用量
- backup/PITR
- log retention/log drains
- custom domain
- CI runner時間とartifact保存

Supabaseの現在のpricingではFree project数に上限があり、有料planでは追加project料金が発生し得る。project作成前に組織のplanと見積りを確認する。

参考:

- [Supabase Pricing](https://supabase.com/pricing)
- [Billing FAQ](https://supabase.com/docs/guides/platform/billing-faq)
