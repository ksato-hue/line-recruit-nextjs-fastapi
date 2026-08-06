# LINE 面接候補ルーティング障害

調査日: 2026-08-06
対象ブランチ: `agent/fix-interview-routing-lock`

## 判定

根本原因は、会話 state がないときの**すべてのテキスト**を、共通コマンドより先に面接候補日時として検索していたルーティング条件です。`interview_slots.slot_datetime` は `timestamptz` ですが、「メニュー」「応募」「よくある質問」などの日付でない文字列もそのまま等価条件へ渡されていました。PostgreSQL/PostgREST がその値を日時へ変換できず例外となり、面接候補確認用の固定エラーへ変換されていました。

全会話用インメモリ state を空にし、DB fixture だけに面接候補を残した再起動相当テストでも、修正前は同じ経路へ入りました。このため、単純なプロセス内 state 残留では説明できません。

## 症状と切り分け

### 確認済みの症状

- Render 再起動後も、LINE で「メニュー」「応募」「よくある質問」「お問い合わせ」を送ると「面接候補日の確認中にエラーが発生しました。」が返信された。
- LINE Webhook の HTTP 応答は 200 だった。
- ダッシュボードの HTTP 500 は、停止していた Supabase production project の再開後に解消した別事象である。
- 送信確認ダイアログはこの障害発生時点で production 未反映であり、Backend Webhook 経路とも独立している。

### 実環境について未確認の事項

- production の例外ログ、該当行の件数、個別の利用者・応募者・候補データは取得していない。
- production / staging Supabase、LINE API、Render 設定への接続・書き込みは行っていない。
- 本文書の実DB構造に関する記載は、調査用スナップショット `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql` と checked-in migration に基づく。

## 正確な発生経路

1. `POST /webhook` は署名を検証し、text message を `handle_message` へ渡す（`backend/main.py:352`）。
2. 修正前の `handle_message` は event 重複確認と応募セッション復元後、面接確認 state を評価した。
3. state がない場合、文字列の形式を確認せず `handle_interview_slot_selection` を呼んだ。
4. `_find_active_interview_slot` は入力を `T` から空白へ置換するだけで、`interview_slots.slot_datetime` の等価条件へ渡した。
5. `slot_datetime` は `timestamptz`（`docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:144`）であるため、「メニュー」等は日時変換エラーになり得る。
6. `handle_interview_slot_selection` の広い `try/except` が例外を捕捉し、固定文言を返した（`backend/main.py:985`）。
7. Webhook はこの返信を通常の bot response として処理し、最後に常に `{"status":"ok"}` を返すため HTTP 200 になった（`backend/main.py:352`）。

固定文言の発生箇所は `backend/main.py` の `handle_interview_slot_selection` 内の1箇所だけである。

## Webhook の分岐順序

### 修正前

| 順序 | 条件・処理 | 問題 |
|---:|---|---|
| 1 | LINE 署名検証 | 正常 |
| 2 | `application_sessions.last_event_id` による event 重複確認 | 応募セッションの再送を防止 |
| 3 | 永続化された active 応募セッションの復元 | 面接ルーティングとは別 |
| 4 | インメモリの面接確認待ち | 任意 text を確認回答として案内し得る |
| 5 | state がなければ面接候補日時検索 | **任意 text を `timestamptz` 条件へ渡す** |
| 6 | FAQ セッション／FAQ コマンド | 5の例外時は到達不能 |
| 7 | `メニュー` | 5の例外時は到達不能 |
| 8 | `キャンセル` | 面接確認待ちでは4に捕捉され到達不能 |
| 9 | `応募` と応募入力 | 5の例外時は到達不能 |
| 10 | 問い合わせ・fallback | 5の例外時は到達不能 |

### 修正後

```text
署名検証
  -> event重複確認
  -> 応募セッション復元
  -> 明示的global commandなら該当userの面接確認を解除
  -> それ以外は面接確認state
  -> 正しい日時形式だけ面接候補検索
  -> FAQ / メニュー / キャンセル / 応募 / 応募回答 / 問い合わせ / fallback
```

event 重複確認は二重処理防止のため先頭に維持した。明示的な global command は面接確認・候補選択より優先する。現在の候補選択 UI は postback ではなく日時文字列の quick reply なので、既存契約に合わせて完全な日時形式だけを候補識別子として受け付ける。

## 永続データとの関係

| 対象 | 実際の列・用途 | 今回事象への影響 |
|---|---|---|
| `applicants` | `status`, `interview_status`, `interview_date`, `company_id` | status だけを理由に通常 text を面接候補扱いしてはいない。候補一致後の応募者検証・確定更新に利用する。 |
| `interview_slots` | `line_user_id`, `slot_datetime`, `status`, `selected_at`, `company_id` | 問題の検索先。修正後は company、user、日時、`status = 候補`をクエリ自体で限定する。 |
| `application_sessions` | `status`, `current_question_key`, `answers`, `last_event_id`, `company_id` | 応募フロー復元と event 重複確認に使用する。`current_step` 列は存在しない。 |
| `line_message_logs` | 送受信ログと `company_id` | 会話ルーティング条件には使用しない。 |

未確定の面接候補がDBに残ること自体は、修正前の日時型エラーの必須条件ではありません。直接原因は、候補の有無を調べる前に任意 text を日時条件として送ったことです。ただし `確認待ち` 行は再起動後にも残るため、global command 受信時に該当 user の候補だけを `候補` へ戻して回復させます。

候補の有効期限を表す列は調査済みスキーマにありません。そのため本修正では推測による期限計算を追加せず、候補検索を既存の明示的な `候補` status に限定します。`選択済み`、`確認待ち`、`キャンセル`、`期限切れ`等は候補として返しません。

## 修正

- 日時候補を完全な `YYYY-MM-DD HH:MM` または `YYYY-MM-DD HH:MM:SS` 形式へ限定し、形式不正ならDBへ問い合わせず通常ルーティングを継続する。
- 面接候補 select に `company_id = COMPANY_ID`、`line_user_id`、`slot_datetime`、`status = 候補`を含める。
- 「メニュー」「応募」「よくある質問」「お問い合わせ」「キャンセル」と既存別名を global command とし、面接確認・候補検索より優先する。
- global command 時は該当 user の `確認待ち`だけを解除する。他利用者の state や候補は変更しない。
- 面接候補検索中の回復不能なDB例外では、該当 user の `user_states` と `interview_confirmations` だけを消去する。
- 正常な日時候補の選択、確認、同一event再送防止、company境界は維持する。

## ログと情報保護

既存の `_log_event` は、event名、result、SHA-256で匿名化した12文字のsubject ID、HTTP status、例外型だけをJSONへ記録します（`backend/main.py:45`）。生のLINE user ID、応募者名、電話番号、message本文、候補日時、secret、token、例外メッセージは記録しません。

今回、次の安全なeventを利用します。

- `interview.slot.select`: 候補検索・更新処理の例外型
- `interview.confirm.release`: global command に伴う確認解除処理の例外型

利用者へ内部例外を露出せず、既存の固定メッセージを維持します。

## 回帰テスト

`backend/tests/test_interview_routing_recovery.py` に、Supabase・LINE APIへ接続しない17件を追加しました。

- 5つの会話用 global dict を空にした再起動相当状態で、メニュー・応募・FAQが正常に動く。
- 面接確認中でも「お問い合わせ」が確認stateを解除して問い合わせ入力へ進む。
- インメモリ state が空でも、キャンセルが該当 user の永続 `確認待ち`候補を解除する。
- 他利用者の面接確認を変更しない。
- 通常 text と存在しない候補IDを面接候補扱いしない。
- 正常な日時候補だけ確認へ進む。
- `選択済み`と`期限切れ` statusを除外する。
- DB例外後、次のメニューで回復する。
- 同一event再送で確定更新を重複実行しない。
- 同日時でも別companyの候補を取得・変更しない。
- 安全ログに生のuser IDやmessageを含めない。
- 内部例外を返信へ変換した場合にWebhookが200を返す既存挙動を固定する。

修正前のREDでは8 failures / 1 errorとなり、global command と通常 text が面接エラーへ誤ルーティングされること、キャンセルが面接確認handlerに捕捉されること、DB例外後に一時stateが残ること、無効statusを選べることを再現しました。

## 別課題

`user_states`、`applicants`、`interview_confirmations`、`faq_sessions`、`application_tree_sessions` は引き続きプロセス内メモリです。複数worker、再起動、途中会話の完全復元を保証するには、会話stateのDB設計と移行が別タスクとして必要です。本修正ではその移行、migration、Auth/RLS、retry、rate limit、productionデータ修正を行いません。
