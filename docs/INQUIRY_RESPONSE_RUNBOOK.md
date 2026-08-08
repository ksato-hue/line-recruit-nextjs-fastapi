# 問い合わせ返信ワークフロー運用runbook

更新日: 2026-08-08

## 現在の判定

repository実装とlocal/offline test evidenceは存在する。Task 14のstaging preflight、staging migration適用、staging application behavior確認は実行されていない。このsessionでもproduction、staging、Supabase、LINE本番には接続せず、4 migrationはいずれも適用していない。

したがって、staging deploymentとproduction deploymentはともに **NO-GO** である。repository実装、local/offline proof、staging proof、production deploymentは別の証拠であり、いずれかを他から推定してはならない。

## Production preflight

production作業は、次のすべてについて承認済みの証拠を変更記録へ添付できる場合だけ開始する。1項目でも不足、失敗、または判定不能なら停止する。

- 承認済みbackupがあり、復旧担当者と復旧手順が確認されている。
- remote migration historyをchecked-in baselineと照合し、不一致が解消されている。
- **production/staging適用前baseline equivalence:** productionとapproved stagingの双方について、4 migration適用前のschema/catalog baselineと既存row-count基準が同等である。
- **staging 4 migration適用後expected catalog/contract:** approved stagingへ同じ4 migrationを順番に適用した後、各migrationのexpected catalog、row-count保持、tenant/idempotency/finalizer contractを満たした証拠がある。この適用後状態はproductionの適用前baseline equivalenceとは別のgateである。
- `inquiries.status`に許可外値がなく、`inquiries.company_id`のNULL件数が0である。
- Backend credentialがserver-onlyの非公開credentialであり、RLS有効tableとRPCをBackend経路から利用できることがstagingで確認されている。
- FrontendとBackendの配備versionが同じ問い合わせAPI contractを含む。
- `INQUIRY_REPLY_WORKFLOW_ENABLED=false`である。
- 承認済みchange window、作業者、監視担当者、rollback判断者が決まっている。
- LINE Push APIの`X-Line-Retry-Key`、accepted 409、結果不明、24時間の再試行期限を作業者が確認している。
- smoke test用に承認済みのnon-PII recordがあり、実在応募者を一切使用しない。
- staging proofにはschema/catalog、row-count保持、tenant拒否、idempotency、最終化の原子性、失敗時rollback、LINE非配信contractの結果が含まれる。

現在はstaging proofがないため、このgateは未通過である。

## Migration order

production作業は次の順番を変えない。

1. 旧appを稼働したままにし、新しいschemaを参照するapp codeはまだ配備しない。
2. additiveなmigration 1→4を次の順で1つずつ適用・検証する。
   1. `202608070001_inquiry_workflow_columns.sql`を適用し、対象列、status CHECK、company NOT NULL、複合UNIQUE、index、triggerをcatalogで確認する。適用前後の既存row countが一致しなければ停止する。
   2. `202608070002_inquiry_replies.sql`を適用し、列、FK、UNIQUE、index、RLS enabled、`anon`/`authenticated`へのpolicy・table grantなし、Backend accessを確認する。適用前後の既存table row countを記録する。
   3. `202608070003_line_message_log_inquiry_reply.sql`を適用し、nullableなlegacy column、複合FK、index、およびlegacy row count不変を確認する。
   4. `202608070004_finalize_inquiry_reply.sql`を適用し、function signature、security、grant、company predicateを確認する。
3. 同じ問い合わせAPI contractを含むBackendとFrontendを、`INQUIRY_REPLY_WORKFLOW_ENABLED=false`のまま配備する。
4. 承認済みnon-PII test recordだけを使い、一覧、詳細、PATCHをsmoke testする。実在応募者への返信送信は行わない。
5. smoke test通過後に限り、固定`COMPANY_ID`で表す現在の1社だけを対象にflagを明示的に有効化する。

各migrationは1つずつ適用し、その場でcatalogとrow countを確認する。失敗または差分不明時は次へ進まない。履歴を書き換えず、既存値を推測してbackfillせず、RLSを弱めない。

このsessionは上記4 migrationのどれも適用していない。remote適用状態は未確認である。

## Feature activation

1. matching app codeと4 migrationの検証が完了するまでflagをfalseに保つ。
2. 一覧、詳細、PATCHのnon-PII smoke testが通った後、Migration orderの最終手順として固定`COMPANY_ID`で表す現在の1社だけを対象にflagを有効化する。
3. この機能の返信は専用`POST /api/inquiries/{inquiry_id}/replies`だけを使用する。汎用`POST /api/line/send`は問い合わせ返信から除外し、問い合わせ状態や返信履歴の最終化に使用しない。
4. 承認されたobservation window中は対象を拡大しない。
5. unexplainedな`delivery_unknown`またはfinalizer mismatchが0である場合だけ、別の承認を得て拡大する。

現在の認可境界は固定`COMPANY_ID`とserver-to-server `ADMIN_API_KEY`である。Supabase Auth、利用者membership/role、利用者JWTに基づくRLS policyは未実装であり、flag有効化はmulti-tenant authorizationの証明にならない。

## PII-safe monitoring

監視では件数、率、時刻、安全な結果分類だけを扱う。

- allowlist済みsafe outcome code別件数。
- `pending`と`delivery_unknown`の件数および滞留時間帯。
- 問い合わせ返信APIの409、5xx件数。
- LINE Pushのaccepted、already accepted、rejected、unknown件数。
- finalizer失敗件数と、返信状態・message log・問い合わせ状態の安全なcount差分。
- flagの状態、app version、migration version、観測window。

本文、担当者名、raw LINE ID、送信先、secret、token、key valueはmetric、log、ticket、screenshotへ含めない。個別追跡が必要な場合も、既存の匿名化subject、安全なreply ID、idempotency key、LINE retry keyだけを承認された運用画面で扱い、それらを公開chatやcommitへ貼らない。

## Delivery unknown

`delivery_unknown`は送信失敗を意味しない。LINEが受理した可能性と、DB finalizerだけが失敗した可能性を保持するため、自動的に新しい送信として扱わない。

1. flagを必要に応じて無効化し、同じreply行の既存idempotency keyとLINE retry keyで記録を特定する。
2. reply状態、safe error code、LINEの安全な受理結果、message log correlation、問い合わせstatusを照合する。本文、担当者、送信先を運用記録へ転記しない。
3. 作成から24時間以内は既存の同じkeyを維持した明示的なreconciliationだけを許可する。新しいkeyによる自動再送をしない。
4. 24時間以内に確定できない場合はoperator reviewへ送る。
5. 24時間経過後は既存操作を再送しない。operatorが監査結果を確認し、必要なら利用者が内容を再確認した新しいactionとして開始する。
6. outcomeが確定するまで問い合わせを`対応済み`へ推測更新せず、unknown rowやcorrelationを削除しない。

すべての`delivery_unknown`を24時間以内に既存keyで照合する。期限を超えたものはoperator reviewと新たに確認されたactionを必須とする。

## Rollback

異常、PII露出、unexplained unknown、finalizer mismatch、tenant境界不明、migration検査失敗のいずれかがあれば、即時rollbackを開始する。

1. `INQUIRY_REPLY_WORKFLOW_ENABLED=false`へ戻し、新規問い合わせ返信を停止する。
2. FrontendとBackendのapp codeを直前の承認済みversionへ戻す。
3. `inquiry_replies`をdropしない。message log、`delivery_unknown`、correlationを削除せず、完了済み送信を逆転させない。
4. additive column、table、functionは監査証拠を保つためdormantのまま残す。
5. すべての`delivery_unknown`を既存idempotency/retry keyで24時間以内にreconcileする。24時間後はoperator reviewと新たに確認されたactionを必要とする。
6. schema rollbackはreply rowまたはmessage-log correlationが1件も存在せず、別の承認済みrollback migrationがstagingで検証済みの場合だけ許可する。

rollback後もsafe metricsを観測し、未解明の送信、finalizer差分、409/5xxが解消した証拠を残す。production再有効化にはProduction preflightを最初からやり直す。
