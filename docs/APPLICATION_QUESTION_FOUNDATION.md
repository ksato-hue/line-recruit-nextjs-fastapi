# 応募質問ツリー・応募開始メッセージ基盤

調査日: 2026-08-06

基準コミット: `cbc249c`

状態: 実装前の承認用設計。DB、API、LINE会話、管理画面には未反映。

## 1. 目的と範囲

企業が応募質問の表示、必須性、順序、追加項目を変更しても、応募者の固定列、回答の意味、進行中セッションを壊さない質問基盤を定義する。応募開始案内、進捗表示、確認付き中止も同じ応募会話の設計として扱う。

## 2. 確認済みの現状

### 質問設定

- 現行defaultはv2で、`name/phone/job/motivation`の4問である。希望職種の既存内部キーと固定列は`job`であり、`desired_job`ではない（`backend/main.py:200-212`, `frontend/app/page.tsx:1237-1242`）。
- Backendは質問を1〜30件に限定し、型を`text/tel/textarea/select`、system fieldを`name/phone/job/motivation/null`に限定する。質問OFFや基本/追加の区別はない（`backend/main.py:2347-2387`）。
- 管理画面は質問文、型、必須、選択肢、順序を編集でき、最後の1件以外は基本項目も削除できる。追加IDは現在時刻から作る（`frontend/app/page.tsx:1211-1232`, `frontend/app/page.tsx:1293-1308`）。
- `question_tree_settings`は企業ごとにJSONBのtreeを1件保持する（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:163-169`）。
- `shared/faq_templates.json`はFAQカテゴリとFAQ質問の静的catalogであり、応募質問treeではない（`shared/faq_templates.json:1-366`）。本機能では流用・変更せず、FAQフローとの責務を分ける。

### 応募会話と保存

- 現行session answerは`question_id/answer`だけへ正規化され、質問文・型・選択肢のsnapshotを持たない（`backend/main.py:1035-1044`）。
- 再起動時の復元は保存済みtreeではなく、その時点の最新質問treeを読み直す（`backend/main.py:1076-1097`）。
- 基本4項目以外の回答は`motivation`へ文章連結される（`backend/main.py:1182-1202`）。
- 質問表示は`【応募情報入力中】`と質問文だけで、現在位置を出さない（`backend/main.py:1226-1247`）。
- 応募開始文のdefaultは「応募ありがとうございます。必要事項を順番に入力してください。」で、`app_settings.application_start_message`から変更できる（`backend/main.py:153-157`, `frontend/app/page.tsx:1512`）。
- 完了RPCは`name/phone/job/motivation`を`applicants`の固定列へinsertし、session answersを空配列へする（`supabase/migrations/202607200001_application_sessions.sql:111-170`）。
- Python側は確認時に非空のin-memory applicant dataを要求するため、全質問OFFで固定項目NULLの応募をそのまま完了できない（`backend/main.py:1339-1369`）。
- 現在のcancelは確認なしでsessionを`cancelled`にし、answersを消す（`backend/main.py:1158-1179`, `backend/main.py:1303-1309`）。

### スキーマ

- `applicants`には`name/phone/job/motivation`があるが、`current_status`と構造化answersはない（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:30-48`）。
- `application_sessions`には状態、現在質問キー、answers、event IDがあるが、質問tree snapshotと中止確認状態はない（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:50-72`）。
- session statusは`active/completed/cancelled`に制約されている（同ファイル`68-71`）。

### 未確認の実環境事項

DB接続は禁止されているため、現在の本番・stagingの質問tree、v1形式の残存数、active session数、回答分布は未確認である。実装前にread-onlyで、個人回答を取得せず、tree version別件数、active session件数、NULL/JSON型件数、schema/RLS/grantだけを確認する。

### 確認された問題

- 基本項目の識別・削除制約がなく、表示編集が固定保存先を壊し得る。
- 回答snapshotがないため、質問名・選択肢・削除後に過去回答の意味を復元できない。
- 進行中sessionが最新treeを再読込するため、設定変更が途中応募へ混入する。
- 追加回答の`motivation`連結では質問別表示・検索・CSV・分析へ安全に拡張できない。
- 現行の1問以上制約と確認guardにより、全項目OFFの受付を表現できない。
- cancelが即時破棄で、利用者の誤操作を回復できない。

## 3. 採用する質問モデル

### 3.1 v3 tree

```json
{
  "version": 3,
  "questions": [
    {
      "id": "name",
      "kind": "basic",
      "system_field": "name",
      "label": "お名前",
      "type": "text",
      "enabled": true,
      "required": true
    }
  ]
}
```

全質問は配列位置ではなくimmutableな`id`で識別する。順序は配列順とし、並び替えてもIDと保存先は変えない。

### 3.2 基本項目

| 表示名 | 固定ID | system field | 固定入力型 | default |
|---|---|---|---|---|
| お名前 | `name` | `name` | text | enabled / required |
| 電話番号 | `phone` | `phone` | tel | enabled / required |
| 現在の状況 | `current_status` | `current_status` | select | enabled / required |
| 希望職種 | `job` | `job` | select | enabled / required |

`desired_job`へのrenameは採用しない。既存tree、session、RPC、`applicants.job`との互換性を守るため、表示名は希望職種のまま内部キー`job`を継続する。

基本項目は削除不可だが、`enabled`、`required`、順序、表示文言を変更できる。表示文言変更は柔軟性があり、回答snapshotが過去の意味を守れるため採用する。入力型の自由変更は固定列の意味とvalidationを壊すため不採用とし、型は上表で固定する。管理画面は「基本項目・削除できません」を表示し、削除buttonを描画しない。

### 3.3 現在の状況

default option:

1. 高校卒業予定
2. 大学・短大・専門学校を卒業予定
3. 既卒・第二新卒
4. 社会人
5. その他

「その他」の自由入力は別の補足質問を作らず、同じ回答オブジェクトへ`other_text`として保持する。1つの基本項目として進捗を数えられ、選択と補足の対応を失わないためである。`applicants.current_status`には選択label、その他なら`その他: <入力>`の表示用文字列を保存する。

選択肢は`{id,label}`とし、回答にはoption IDと回答時点のlabel snapshotを保存する。企業が後からlabelを変更しても過去回答の意味を変えない。既存v2の文字列optionは、企業が最初にv3保存する時にBackendが一度だけUUIDを割り当て、返却されたIDを以後維持する。

### 3.4 追加項目

- 新規項目にはUUIDv4のIDを作成時に一度だけ割り当て、UIで編集させず、削除後も別質問へ再利用しない。既存v2の質問IDは互換IDとして書き換えず維持する。
- `enabled/required/order/label/type/options/allow_other`を編集できる。
- 削除は将来のtreeから外すだけで、応募者に保存済みのanswer snapshotを削除しない。
- `motivation`は既存互換用の追加項目としてv3変換時にID/system fieldを維持するが、基本4項目には含めない。企業はOFFまたは削除できる。
- 新規v3管理画面では条件分岐編集を増やさない。既存`show_when`は読込・進行互換のため保持する。

## 4. 構造化回答

### 比較

| 案 | 評価 |
|---|---|
| A: `motivation`へ連結 | 検索、質問別表示、質問名変更、削除後の意味を保持できないため不採用。 |
| B: `applicants.answers JSONB` | 1応募者と一緒に取得でき、snapshotと固定列dual-writeを低い複雑性で実現できるため採用。 |
| C: `applicant_answers` 1回答1行 | 大規模分析には有利だが、現在規模ではjoin、RLS、migration、transactionが増えるため将来案。 |

### answer snapshot

```json
{
  "question_id": "current_status",
  "system_field": "current_status",
  "question_label": "現在の状況",
  "question_type": "select",
  "answer": {
    "kind": "option",
    "option_id": "UUID",
    "label_snapshot": "その他",
    "other_text": "フリーランス"
  },
  "answered_at": "UTC ISO 8601"
}
```

text/tel/textareaは`answer.kind=text`と`answer.text`を使う。本文を配列indexや現在の質問labelだけで識別しない。

### 固定列とのdual-write

- `name → applicants.name`
- `phone → applicants.phone`
- `current_status → applicants.current_status`
- `job → applicants.job`
- すべての有効質問 → `applicants.answers`

`motivation`は移行期間だけ互換出力とする。新規応募では既存の追加回答を人が読めるlabel/value形式へ連結してdual-writeするが、構造化表示の正は`applicants.answers`とする。既存応募者でanswersが空なら、詳細画面は`motivation`を「従来の応募内容」として表示する。既存motivationを推測で質問別JSONへbackfillしない。

## 5. 全項目OFF

- 基本項目を含む全questionの`enabled=false`を保存できる。
- 設定画面は「現在、応募時に質問する項目がありません。新しい応募者の基本情報は空欄になります。」と警告するが、保存は許可する。
- LINEで応募開始時、質問開始メッセージと確認画面を出さず、同じtransaction/RPCでsessionと応募者を完了する。
- applicantには`line_user_id/company_id/created_at/status/application_session_id`を保存し、name/phone/current_status/jobはNULL、answersは`[]`とする。
- 現行RPCのtext引数と固定列はNULLを受けられるが、Pythonの非空data guardは対応していない。実装PRでv2 RPCと会話処理を同時にテストする。

## 6. 応募者一覧と過去データ

一覧列は質問設定から独立して固定する。

1. 名前
2. 電話番号
3. 現在の状況
4. 希望職種
5. 選考ステータス
6. 面接状況
7. 面接日時
8. 登録日時
9. 操作

質問OFFでも列を消さない。NULL/空は見た目を`—`、screen reader向けlabelを「未入力」とする。設定変更で既存応募者をUPDATEせず、OFF/削除/label変更/option変更後も過去固定列とsnapshotを保持する。追加質問は一覧列へ自動追加せず詳細へ表示する。将来の「一覧に表示」は最大2項目、管理者選択、列overflow設計を伴う別機能とする。

## 7. session snapshotと設定変更

`application_sessions.question_tree_snapshot jsonb`を追加し、新規session開始時にv3 treeを保存する。再開、順序、進捗、回答validationはsnapshotだけを正とし、最新設定へ差し替えない。

既存active sessionでsnapshotがない場合は、次のevent処理前に現在のtreeを一度だけsnapshotとして保存し、既存answerを質問IDで対応させる。対応しない回答を消さず、確認画面へ「従来回答」として残す。これはstagingでv1/v2 session fixtureを使って検証する。

質問をOFF・削除・並び替えた後も開始済みsessionの質問経路は変えない。新設定は新規sessionからだけ反映する。

## 8. 応募開始文と進捗

保存済みの企業独自メッセージは上書きしない。設定値が未登録の場合の新defaultだけを次へ変更する。

```text
ご応募ありがとうございます！
これから応募に必要な情報を、
1項目ずつお伺いします。
画面に表示される質問に沿って、
順番に入力してください。
```

質問は次の形式にする。

```text
応募情報の入力（1/5）
まず、お名前を入力してください。
```

- 分母はsession snapshot内でenabledかつ現在の回答条件から質問対象となる項目だけとし、任意質問も含める。
- v3の通常質問には条件分岐を新規追加しないため、開始から完了まで分母は安定する。
- 既存`show_when`を含むsessionだけは親回答後に経路が確定するため、その時点の実際の対象集合で分母を再計算する。非表示質問を分母に残さない。
- 分子は実際に表示する質問の1始まり位置で、再開時は保存済み現在質問IDから計算する。
- 全OFFなら開始文・質問文・確認文を送らず受付完了を返す。
- `【応募情報入力中】`は廃止し、上記の具体的見出しへ統一する。

## 9. 応募中止

### UIと会話

quick replyは「応募を中止する」とし、押しただけでは破棄しない。

```text
応募を中止しますか？
ここまで入力した内容は破棄されます。

[入力を続ける] [応募を中止する]
```

LINE公式のquick reply action label上限は20文字であり、両labelは上限内である。文字列回答との衝突を避けるため、表示labelとは別のpostback data（`application_cancel_request`、`application_cancel_confirm`、`application_cancel_continue`）で処理する。

参照: [Messaging API reference - label specifications](https://developers.line.biz/en/reference/messaging-api/)

### state

`application_sessions.pending_action text null`を追加し、許可値を`cancel_application`だけに制約する。現在質問キーは上書きしない。

```text
active/collecting --cancel request--> active + pending_action=cancel_application
pending cancel --continue---------> pending_action=null、現在質問を再表示
pending cancel --confirm----------> status=cancelled、answersを消去
```

- 中止確定はraw answersを物理的に空配列へし、個人情報を残さない。session行、status、cancelled_at、last_event_idは監査・冪等性のため論理保持する。
- 同じWebhook eventは`last_event_id`で再処理せず、二重遷移しない。
- global commandは面接ルーティング修正で定めた優先順位を維持する。メニュー、応募、よくある質問、問い合わせ、キャンセル系postbackを会話stateより先に判定する。
- globalメニューを開いてもactive sessionを暗黙破棄しない。「応募」で再開できる。
- rollout中の旧text「キャンセル」は即時破棄せず、中止確認を開く互換aliasとして扱う。
- 問い合わせ・FAQ・面接postbackを応募中止確認として解釈しない。

## 10. APIとFrontend

### API

- `GET /api/question-tree`: v2も読めるが、レスポンスは互換情報を保持したv3 viewを返す。
- `PATCH /api/question-tree`: v3を厳密検証し、基本4IDの存在、kind/system field/type固定、ID重複なし、最大30、有効select option、company scopeを保証する。
- 新規質問・optionのIDはBackendがUUIDv4を発行する作成helperを使い、UIの`Date.now()`を廃止する。
- completionは新規`complete_application_session_v2`を使い、current_status、answer snapshot、全OFF、event idempotencyを1 transactionで処理する。既存functionを直ちに置換・削除しない。

### 設定画面

- 基本項目と追加項目を同じ並び替えlistに置く。
- 基本項目はbadge、ON/OFF、必須、固定型、編集可能label、順序だけを表示し、削除buttonなし。
- 追加項目はON/OFF、必須、label、型、option、順序、削除確認を提供する。
- 状態はloading/saving/saved/validation error/unsaved/all-off warning/delete confirmation/LINE previewを明示する。
- 保存前確認には、active sessionへは即時反映されず、新規応募から反映されることを表示する。

## 11. company境界、Auth/RLS境界

- tree read/upsert、session read/insert/update、completion function、applicant insert/readの全queryにcompany_idを含める。
- company_idは全insertで明示し、defaultに依存しない。
- 回答や質問文をログへ出さず、event名、例外型、匿名化subject、安全な状態だけを記録する。
- 現在は固定`COMPANY_ID`と管理APIキーであり、Supabase Auth/RLS実装済みではない。
- 純粋認可ポリシーには`settings_update`があるが、現在の質問tree APIへ利用者JWT/roleとして接続されてはいない（`backend/authz_policy.py:16-27`, `backend/authz_policy.py:116-145`）。
- Auth/RLS前でも固定company scopeのテスト、additive schema、会話、管理画面は実装できる。
- Auth/RLS後に、設定更新をowner/adminへ限定し、member read、aal2、複数企業切替、JWT由来company、テーブル別RLSを接続する。

## 12. migration方針

今回migrationは作らない。実装PRでは次を独立したstaging検証単位にする。

1. `applicants.current_status text null`と`applicants.answers jsonb not null default []`、JSON array CHECKをadditiveに追加。
2. `application_sessions.question_tree_snapshot jsonb null`と`pending_action text null`、JSON object/CHECKをadditiveに追加。既存active sessionを一度だけ変換した後、`status <> 'active' OR question_tree_snapshot IS NOT NULL`のCHECKを追加し、新規・継続中active sessionではsnapshotを必須にする。completed/cancelledの旧行はNULLを許可する。
3. `complete_application_session_v2`を新しいfunction名で追加。既存RPCを残し、Backend切替後の観測期間を経て別migrationで廃止を判断する。

JSON内のquestion tree version変更はSQL backfillしない。企業が保存する時にBackendがv3へ変換し、保存前後のpayloadをstaging fixtureで検証する。production migration history整合が済むまでは適用しない。

## 13. テスト方針

- 純粋関数: v2→v3変換、基本ID/type固定、option snapshot、progress、all-off、cancel transition。
- Backend: 基本項目削除拒否、全OFF保存許可、UUID安定、並び替え、company scope、他社tree拒否。
- 会話: start文、1/N、任意を含む分母、全OFF即完了、再開位置、snapshot固定、旧session変換、その他入力。
- 保存: 固定列dual-write、answers snapshot、削除/label/option変更後も過去表示、legacy motivation fallback。
- cancel: requestだけでは保持、continue、confirmでanswers消去、event再送、global command、FAQ/問い合わせ/面接非干渉。
- DB/staging: new RPCのtransaction/idempotency、NULL固定項目、JSON CHECK、企業境界。
- Frontend: 基本badge、削除buttonなし、all-off警告、未保存、削除確認、LINE preview、固定一覧列と`—/未入力`。
- 既存305件以上のBackend回帰とFrontend typecheck/buildを維持する。

## 14. rolloutとrollback

Rollout:

1. read-only schema/tree/session件数preflightとバックアップ。
2. 3つのadditive migration単位をstagingへ順次適用。
3. v1/v2 tree、active session、all-off、cancel、event再送fixtureをstagingで検証。
4. Backendをv2/v3 dual-read、新規session v3 writeで配備。
5. Frontend設定UIを配備し、限定企業でv3保存を有効化。
6. 新規応募の固定列/answers整合と旧session完了をPIIなしの件数で監視して展開。

Rollback:

- feature flagでv3編集を停止し、Backendをv2 read/旧RPCへ戻す。
- additive列、snapshot、v2 RPCは削除せず、既に保存された回答を保持する。
- v3 treeをv2へ破壊的に自動変換しない。rollback中もv3 read互換を残す。
- 質問設定変更を理由に既存応募者やsession回答をUPDATE/削除しない。

## 15. 実装PRの境界と受入条件

対象branch候補: `agent/application-question-foundation`

このPRに含む: 独立migration単位、v3質問モデル、設定UI、session snapshot、構造化回答、固定一覧列、応募開始文、進捗、中止確認、tests、文書。問い合わせ返信、担当者、ダッシュボード問い合わせ詳細、Auth/RLS全体は含めない。

受入条件:

- 基本4項目は削除できず、OFF/必須/順序/labelを変更でき、型と固定保存先は変わらない。
- 全OFFでも応募が1件だけ完了し、固定列はNULL、answersは空である。
- 順序、label、option、削除変更が過去回答と進行中sessionの意味を変えない。
- 現在の状況のoption snapshotとその他入力を同じ回答として保持する。
- 固定一覧列は設定OFFでも残り、過去値を消さない。
- 中止は確認後だけ実行され、確定時に回答PIIを破棄し、event再送で二重処理しない。
- 全DB操作がcompany scopeを持ち、Auth/RLS未接続を実装済みと表現しない。
