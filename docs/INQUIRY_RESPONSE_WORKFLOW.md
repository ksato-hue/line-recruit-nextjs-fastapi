# お問い合わせ詳細・担当者・LINE返信フロー

調査日: 2026-08-06

基準コミット: `cbc249c`

状態: 実装前の承認用設計。DB、API、LINE送信、画面には未反映。

## 1. 目的と範囲

管理画面内で「問い合わせを開く → 担当者と返答を確認 → 送信確認 → LINE返信 → 履歴確認 → 対応済み」を完結させる。ダッシュボードに返信欄は置かず、詳細画面を唯一の返信導線とする。

対象は問い合わせ一覧、詳細、担当者、返信履歴、専用返信API、ダッシュボード導線である。Supabase Auth、全テーブルのRLS、メンバー管理、非同期ジョブはこの機能の完了条件に含めない。

## 2. 確認済みの現状

### コードとスキーマの事実

- Backendには企業スコープ済みの一覧、詳細、status更新がある。更新モデルは`status`だけで、許可値の列挙はない（`backend/main.py:1654-1655`, `backend/main.py:2436-2476`）。
- 管理画面は一覧のみで、日時、マスク済みLINE ID、本文、statusを表示する。行選択、詳細、担当者、返信UIはない（`frontend/app/page.tsx:1142-1177`）。
- API clientには`getInquiry`があるが画面では未使用で、問い合わせ更新・返信関数はない（`frontend/lib/api.ts:40-46`）。
- 現在の`Inquiry`型は`id/created_at/line_user_id/message/status`だけである（`frontend/types/index.ts:180-186`）。
- ダッシュボードの直近問い合わせはクリック不能で、本文をそのまま表示している（`frontend/app/page.tsx:460-477`）。
- `inquiries`の確認済み列は`id/line_user_id/message/status/created_at/company_id`で、担当者・返信・更新日時はない（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:122-131`）。
- `line_message_logs`は送受信本文を保持するが、問い合わせIDや返信IDを持たない（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:151-161`）。
- 手動LINE送信はLINE成功後にログ保存を試みる。ログ失敗は例外を外へ返さないため、返信ワークフローの整合性要件には流用できない（`backend/main.py:1608-1618`, `backend/main.py:2479-2492`）。
- 採用担当者名は`app_settings`の`recruiter_name`として存在する（`backend/main.py:153-157`, `frontend/app/page.tsx:1705`）。
- `ConfirmationDialog`は既に共通部品として存在する（`frontend/components/ui/ConfirmationDialog.tsx:5-36`）。
- 純粋認可ポリシーには`message_send`が定義されているが、現在の問い合わせAPIへ利用者JWT/roleとして接続されてはいない（`backend/authz_policy.py:16-27`, `backend/authz_policy.py:116-145`）。

### 未確認の実環境事項

この設計ではDBへ接続していない。2026-07-24の調査用スナップショット以後の本番・staging差分、`inquiries.status`の実データ中のdistinct値、実際のgrant/RLS状態は未確認である。migration作成前に、stagingのread-only catalogと集計で次を確認する。

1. `inquiries.status`の値別件数（本文やLINE IDは取得しない）。
2. 列、制約、index、RLS、grantがスナップショットと一致するか。
3. `line_message_logs.message_type`の使用値とNULL件数。
4. orphanとなる問い合わせや重複返信履歴が存在しないこと。

### 確認された問題

- 一覧から詳細・返信へ進めず、未対応を業務上完了させる導線がない。
- 任意文字列status、担当者なし、履歴なしのため、誰がどこまで対応したかを一貫して判断できない。
- 汎用LINE送信と問い合わせPATCHを別々に呼ぶと、LINEだけ成功またはDBだけ更新という部分成功が起きる。
- dashboardの長文は行動導線がなく、狭い幅で読みにくい。
- 現行の固定company条件はAuth利用者・RLSによる認可の代替ではない。

## 3. 採用する設計

### 3.1 保存方式

案Bの「返信履歴テーブル」を採用し、`inquiries`には一覧・絞り込み用の現在状態だけを持たせる。

| 案 | 評価 |
|---|---|
| A: `inquiries`へ最新返答を直接追加 | MVPは小さいが、複数回返信、監査、送信失敗履歴を上書きするため不採用。 |
| B: `inquiry_replies`を追加 | 返信ごとの担当者・送信状態・冪等性を保持でき、現在規模でも1テーブル追加に収まるため採用。 |
| C: `line_message_logs`だけを利用 | 問い合わせとの対応、担当者、再試行状態、業務上の返信履歴を表現できないため不採用。 |

`line_message_logs`は会話タイムライン、`inquiry_replies`は問い合わせ対応の監査可能な送信意図、`inquiries`は現在の業務状態という責務に分ける。

### 3.2 データモデル

`inquiries`へ加える列:

| 列 | 型・制約 | 用途 |
|---|---|---|
| `assignee_name` | `text null` | 現時点の担当者表示。文字列でありAuthユーザーIDではない。 |
| `last_replied_at` | `timestamptz null` | 最後にLINE側で受理された返信時刻。 |
| `updated_at` | `timestamptz not null default now()` | 楽観ロックと更新順。triggerで更新。 |
| `status` | `text not null` + CHECK | `未対応 / 対応中 / 対応済み`だけを許可。既存値確認後に追加。 |

`inquiry_replies`を追加する:

| 列 | 型・制約 | 用途 |
|---|---|---|
| `id` | `uuid primary key` | 返信行ID。 |
| `company_id` | `text not null` | 企業境界。 |
| `inquiry_id` | `uuid not null` FK | 対象問い合わせ。 |
| `assignee_name` | `text not null` | 送信時に確定した担当者名のsnapshot。 |
| `message` | `text not null` | 送信した返答本文。 |
| `delivery_status` | CHECK | `pending / sending / sent / failed / delivery_unknown`。 |
| `idempotency_key` | `uuid not null` | UIの確認snapshotと再試行を同一操作として扱う。 |
| `line_retry_key` | `uuid not null` | 最初のLINE Pushから同じ値を使う。 |
| `created_at/sent_at/updated_at` | `timestamptz` | 作成、受理、状態更新時刻。 |
| `safe_error_code` | `text null` | 許可リスト化した非PIIの失敗分類だけ。 |
| `actor_user_id` | `uuid null` | Auth導入後の`profiles`参照用。導入前はNULL。 |

制約・index:

- `inquiries`はNULL company件数が0であることをread-only確認してから`company_id NOT NULL`とUNIQUE `(company_id, id)`を追加する。NULLがあれば企業を推測してbackfillせず、migrationを停止する。
- `inquiry_replies`のFKは`(company_id, inquiry_id) → inquiries(company_id, id)`の複合参照にする。
- UNIQUE `(company_id, inquiry_id, idempotency_key)`。
- INDEX `(company_id, inquiry_id, created_at desc)`。
- INDEX `(company_id, delivery_status, created_at)`。
- FKは問い合わせ削除時も監査履歴を誤って消さないよう`ON DELETE RESTRICT`。
- 新規テーブルは作成時点からRLSを有効化し、`anon/authenticated`へ直接policy・table grantを与えない。Backendのサーバー秘密鍵経路だけを使用する。利用者JWTに基づくpolicyはAuth/RLSフェーズで追加する。

`line_message_logs`にはnullableな`inquiry_reply_id`を追加し、最終化時に返信行と会話ログを関連付ける。新規返信ログはcompany_idを必須にし、複合FK `(company_id, inquiry_reply_id) → inquiry_replies(company_id, id)`で他社行との誤結合を防ぐ。既存ログはNULLのまま保持する。

### 3.3 問い合わせ状態

```text
未対応 --担当開始/担当保存--> 対応中
対応中 --LINE受理＋DB最終化--> 対応済み
対応済み --再対応を開始------> 対応中
```

- 返信本文の編集中、送信失敗、結果不明では`対応済み`にしない。
- 「返信不要で完了」は誤操作防止の確認と完了理由を別途要するため初回MVPには含めない。
- 既存の未知statusはmigrationで推測変換しない。staging事前検査で見つけた値ごとの明示的な対応表をレビューしてからCHECKを追加する。

## 4. 担当者名

### 正とする層

Backendの副作用のないhelperを唯一の正とする。問い合わせ詳細APIが`app_settings.recruiter_name`から`default_assignee_name`を計算して返し、Frontendはその値を初期表示する。同じ分割規則をFrontendへ複製しない。返信時にBackendが最終入力も検証する。

### 名字抽出規則

1. 前後の半角・全角空白を除去する。
2. 半角空白または全角空白が1個以上続く箇所で分割する。
3. 最初の空でない要素を返す。
4. 区切りがなければ全文を返す。
5. 基本設定が空または空白だけなら空文字を返す。

例: `佐藤 太郎`、`佐藤　太郎`、`佐藤   太郎`は`佐藤`、`佐藤太郎`は`佐藤太郎`。

返信時の担当者入力は必須、前後空白を除いた1〜80文字とする。手動修正後の文字列は再び名字へ切り詰めず、その確定値を保存する。Auth導入後は`actor_user_id`を正とし、`assignee_name`は送信時の表示名snapshotとして残す。

## 5. API設計

すべて管理APIキーを維持し、各select/insert/update/RPC内で`company_id = COMPANY_ID`を必須にする。別企業IDは404とし、存在を漏らさない。

### 一覧

`GET /api/inquiries?status=未対応&sort=oldest&limit=50&cursor=...`

返却項目は本文冒頭、受付日時、状態、担当者、最後の返信日時、同一企業内の関連応募者有無、未対応経過秒を含む。経過秒の正はBackendのUTC時刻とする。本文の2行省略はFrontend表示責務。

### 詳細

`GET /api/inquiries/{inquiry_id}`

問い合わせ本文、状態、担当者、返信履歴、マスク済み送信先、同一`company_id + line_user_id`で検索した関連応募者の最小情報を返す。生のLINE IDはレスポンスへ新規公開しない。該当応募者が複数なら勝手に1件へ関連付けず、候補として表示する。

### 状態・担当者更新

`PATCH /api/inquiries/{inquiry_id}`

```json
{
  "status": "対応中",
  "assignee_name": "佐藤",
  "expected_updated_at": "UTC ISO 8601"
}
```

許可された遷移だけを受け付け、同時更新の競合は`409`で返す。実update queryにも`id`と`company_id`を含める。

### 専用返信API

`POST /api/inquiries/{inquiry_id}/replies`

```json
{
  "assignee_name": "佐藤",
  "message": "お問い合わせありがとうございます。",
  "idempotency_key": "UUID",
  "expected_updated_at": "UTC ISO 8601"
}
```

- ブラウザから`line_user_id`を受け取らない。Backendが企業スコープ済み問い合わせから解決する。
- 本文は既存のLINE検証と同じく文字列、空白のみ不可、最大5,000 UTF-16符号単位、前後空白・改行を保持する。
- 同じidempotency keyの再送は既存replyを返し、新しい送信を作らない。
- 正常応答は返信行、更新済み問い合わせ、`delivery_status=sent`を返す。内部例外、本文、生LINE IDは返さない。

## 6. 送信と保存の整合性

### 比較

| 方法 | 結論 |
|---|---|
| FrontendでLINE送信後に問い合わせPATCH | 2リクエスト間の部分成功を回復できないため不採用。 |
| DB transaction内でLINE送信 | 外部HTTPはDB transactionに含められず、lock長期化と結果不明が残るため不採用。 |
| 完全な非同期outbox/worker | 最も堅牢だがworker監視と運用が増える。将来の大量送信段階で採用候補。 |
| 専用API＋durable intent＋LINE retry key＋原子的最終化 | 現行規模で部分成功を回復できるためMVPに採用。 |

### 採用シーケンス

1. Backendが問い合わせを`id + company_id`で取得し、本文・担当者・競合versionを検証する。
2. UNIQUEなidempotency keyで`pending`返信をinsertする。insertできなければLINEへ送らない。
3. 同じ`line_retry_key`を最初のLINE Pushから`X-Line-Retry-Key`へ付ける。
4. LINEが受理したら、1つのDB function/transactionでreplyを`sent`、`line_message_logs`をinsert、問い合わせを`対応済み`・担当者・返信日時へ更新する。すべての対象条件にcompany_idを含める。
5. LINEが明確に拒否したら`failed`とし、問い合わせは完了させない。
6. timeout/5xxで結果不明なら`delivery_unknown`とし、新しいキーで自動再送しない。同じ操作を再試行すると同じLINE retry keyを使う。
7. LINEの再試行応答が「同じretry keyは既に受理済み」を示す場合も受理済みとしてDB最終化を再実行する。

LINE公式ドキュメントは、Push APIの初回から`X-Line-Retry-Key`を付けることで同一リクエストの重複実行を防げる一方、配信保証そのものではなく、キー管理期間が24時間であると説明している。したがって24時間を超えた`delivery_unknown`は自動送信せず、管理者が履歴を確認して新規送信するか判断する。

参照: [Retry failed API requests](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/)、[Messaging API reference](https://developers.line.biz/en/reference/messaging-api/)

## 7. Frontend設計

### ダッシュボード

- 本文はCSSの2行clampと通常の単語折返しを使い、縦1文字折返しを防ぐ。
- 日時と状態を併記し、カード全体または「内容を確認」で問い合わせ詳細へ移動する。
- 未対応件数は`status=未対応`の一覧へ遷移する。
- 0件は「未対応のお問い合わせはありません」と表示する。
- 返信入力欄は置かない。

### 一覧・詳細

- 一覧は本文冒頭、受付日時、状態、担当者、返信日時、関連応募者有無、未対応経過時間を表示する。
- PCは一覧＋詳細ペイン、スマートフォンは詳細を全画面表示し、戻る操作を明示する。
- 詳細は問い合わせ、受付日時、状態、担当者、返信編集、履歴、関連応募者をセクション分けする。
- LINE履歴は必要時に遅延取得し、問い合わせ返信履歴と一般会話ログを見分けられる表示にする。

### 編集・確認

- stateを`idle/editing/confirming/submitting/sent/failed/delivery_unknown`で表現する。
- 確認ダイアログを開く時に`inquiry_id/assignee_name/message/idempotency_key/expected_updated_at`のsnapshotを固定する。
- `ConfirmationDialog`を再利用し、問い合わせ本文、担当者、返答、マスク済み送信先、状態遷移、取り消せない旨を表示する。
- cancelはAPIを呼ばず入力を保持する。失敗・結果不明も入力とsnapshotを保持する。成功時だけ本文とidempotency keyを初期化する。
- 送信中は閉じる、cancel、二重confirmを無効化する。エラーは短い安全な分類だけを`role=alert`で示す。

## 8. 情報保護と認可境界

- 問い合わせ、返信、関連応募者、会話ログの全queryと最終化functionは`company_id`を必須にする。
- 返信insertにもDB defaultへ依存せずcompany_idを明示する。
- ブラウザへ生のLINE ID、サーバー秘密鍵、Backend用管理キーを渡さない。
- application本文、返信本文、担当者名をアプリログへ出さない。許可するのはhandler、処理段階、例外型、安全な結果コード、匿名化subjectだけ。
- 現在は固定`COMPANY_ID`と管理APIキーによる境界であり、Supabase Auth/RLS済みではない。
- Auth後に`actor_user_id`、membership、owner/admin/member権限、aal2、company切替を接続する。memberに返信を許すかは認可ポリシーの`message_send`を正とする。

## 9. migration方針

実装PR内でも、次を独立したstaging適用・検証単位にする。今回migrationファイルは作らない。

1. `inquiries`へadditiveなworkflow列、index、updated_at triggerを追加。既存statusとNULL companyのread-only事前検査後に、status CHECK、company NOT NULL、複合UNIQUEを追加。
2. `inquiry_replies`、制約、index、RLS有効化、直接grantなしを追加。
3. `line_message_logs.inquiry_reply_id`をadditiveに追加。
4. `finalize_inquiry_reply`の新規functionを追加。既存functionを置換しない。

各単位はtransaction、schema検査、空/正常/競合/他社データのstagingテストを通してから次へ進む。productionのremote migration history不整合が解消するまでは適用しない。

## 10. テスト方針

- 純粋関数: 名字抽出、UTF-16文字数、状態遷移、エラー分類。
- Backend unit: 企業スコープ済み一覧・詳細・更新、他社404、返信insertのcompany_id、本文検証、idempotency、競合409。
- Backend failure: LINE拒否、timeout、最終化失敗、同じretry keyの再試行、ログだけ失敗、他社問い合わせ。
- DB/staging: UNIQUE、CHECK、FK、最終化transactionのall-or-nothing、RLS直接アクセス拒否。
- Frontend: filter遷移、2行clamp、detail状態、名字初期値、snapshot、cancel保持、successのみ初期化、failure再試行、mobile。
- 回帰: 既存の管理APIキー境界、手動LINE送信、応募者・問い合わせ企業境界を維持する。

## 11. rolloutとrollback

Rollout:

1. schema preflightとバックアップ。
2. additive migrationをstagingへ順次適用し、schema equivalenceと失敗系を検証。
3. Backendをfeature flag `inquiry_reply_workflow` OFFで配備。
4. Frontendを配備し、stagingのテストLINEアカウントで1件だけ送信・再試行を確認。
5. flagを限定企業でON、`pending/delivery_unknown`件数をPIIなしで監視。
6. 安定後に全対象へ展開。

Rollback:

- flagをOFFにし、旧一覧表示へ戻す。返信APIを停止しても既存履歴は削除しない。
- Backend/Frontendを直前versionへ戻す。additive列・テーブル・functionは残し、送信履歴を失うdown migrationは実行しない。
- `delivery_unknown`は自動再送せず、同じidempotency/retry keyの監査後に復旧する。

## 12. 実装PRの境界と受入条件

対象branch候補: `agent/inquiry-response-workflow`

このPRに含む: 問い合わせschemaの独立migration単位、Backend専用APIとtests、一覧/詳細/返信UI、ダッシュボード導線、文書。質問ツリー、応募開始会話、Auth/RLS全体は含めない。

Auth/RLS前に実施可能: additive schema、固定company scope API、名字helper、返信整合性、管理画面、テスト。

Auth/RLS後へ回す: ログイン利用者を担当者IDにする、role別操作、複数企業切替、利用者JWTによるRLS policy、監査画面。

受入条件:

- 他社問い合わせを一覧・詳細・更新・返信できない。
- cancel/失敗では入力を保持し、成功時だけ初期化する。
- 同じ操作・timeout再試行で二重送信しない。
- LINE受理前に対応済みにならず、受理後のDB最終化は原子的で再実行可能。
- 生LINE ID、本文、担当者、秘密値をログへ追加しない。
- ダッシュボードの長文が2行を超えず、未対応filterへ到達できる。
- Auth/RLS未接続が画面・文書・テストで明示される。
