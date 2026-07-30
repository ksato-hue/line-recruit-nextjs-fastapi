# 応募未完了リマインド判定ポリシー

調査・実装日: 2026-07-30

## 今回のスコープ

`backend/reminder_policy.py`は、応募未完了sessionについて次を判定する副作用のないPython moduleである。

- リマインド予定日時
- 現在時刻における送信可否
- 完了・取消・不明sessionの除外
- 送信済み`reminder_id`の除外
- 重複`reminder_id`の拒否
- 応募受付と企業状態による停止
- 不正設定のfail-closedな拒否
- 複数リマインドから最古の未送信1件を選ぶ決定的な順序

Supabase、DB、FastAPI、LINE API、scheduler、HTTP、環境変数、ファイルI/Oには接続しない。既存API、設定保存形式、migration、frontendも変更しない。

## 確認済みの既存契約

### 設定形式

**事実:** backendの可変設定は`id`、`name`、`enabled`、`delay`、`unit`、`message`を持つ（`backend/main.py:179-188`, `backend/main.py:2269-2292`）。frontendの`ReminderSetting`も同じ形である（`frontend/types/index.ts:135-144`）。

**事実:** 対応単位と上限は次のとおりである（`backend/main.py:2270-2292`, `frontend/app/page.tsx:1418-1422`）。

| unit | 最大interval |
|---|---:|
| `minutes` | 525600 |
| `hours` | 8760 |
| `days` | 365 |

定義は最大20件、本文はtrim後に1文字以上5000文字以下である。純粋ポリシーでは`name`を送信判定に使わないため`ReminderDefinition`へ含めない。表示名のvalidationは既存設定APIと将来のadapterの責務として維持する。

### 固定設定と可変設定

**事実:** 旧固定設定は1時間、24時間、3日を個別のenabled・hours・message keyとして保持する（`backend/main.py:167-178`）。`reminders`が保存されていない場合、backendとfrontendは次の安定IDを持つ可変形式へ変換する（`backend/main.py:264-283`, `frontend/app/page.tsx:1332-1338`）。

| 旧設定 | 安定したreminder_id | 既存送信日時列 |
|---|---|---|
| 1時間 | `legacy_1h` | `reminder_1h_sent_at` |
| 24時間 | `legacy_24h` | `reminder_24h_sent_at` |
| 3日 | `legacy_3d` | `reminder_3d_sent_at` |

**事実:** 可変リマインドの新規IDは現在frontendで`reminder_${Date.now()}`として生成され、保存済みIDは並び替え時にも維持される（`frontend/app/page.tsx:1367-1381`）。

**未実装:** 可変ID単位の送信履歴を保存するtableまたは列は存在しない。現行`application_sessions`が持つ送信履歴は上記3本の固定timestampだけである（`supabase/migrations/202607200001_application_sessions.sql:8-29`）。

## 公開する型と関数

`backend/reminder_policy.py`は次を公開する。

- `ReminderUnit`: `minutes`、`hours`、`days`
- `ReminderReasonCode`: 構造化された判定理由
- `ReminderDefinition`: 安定ID、enabled、interval、unit、message、明示的なorder
- `ReminderSchedule`: 設定と`activity_at`から計算した予定
- `ReminderDecision`: 単件の`should_send`、理由、予定・評価時刻、遅延秒数
- `ReminderBatchDecision`: 全件の評価結果と、今回送る最大1件
- `calculate_due_at(...)`: 予定日時の計算
- `evaluate_reminder(...)`: 単件評価
- `evaluate_reminders(...)`: 一括評価

すべてimmutable dataclassまたはstring Enumであり、呼び出しによる外部状態変更はない。

## activity_at

`activity_at`は「応募者の最新操作を表す基準時刻」である。policyはDB column名を知らず、呼び出し元が明示的に渡す。

**事実:** 現行`application_sessions`には`started_at`、`last_activity_at`、`completed_at`、`cancelled_at`があり、回答保存と取消では`last_activity_at`が更新される（`supabase/migrations/202607200001_application_sessions.sql:15-21`, `backend/main.py:1079-1099`, `backend/main.py:1132-1150`）。

**提案:** 後続DB adapterでは通常`last_activity_at`を渡す。ただし列のfallback、NULL、時刻品質はadapterで確認し、policy内へ推測を埋め込まない。

`activity_at`がない場合は`MISSING_ACTIVITY_TIME`、naive datetimeは`INVALID_DATETIME`となる。UTC以外のtimezone-aware datetimeはUTCへ正規化する。

## 送信判定フロー

単件評価は次の順でfail-closedに判定する。

1. `now`がtimezone-awareか
2. reminder定義と`activity_at`が有効か
3. reminderがenabledか
4. sessionが`active`か
5. 応募受付がONか
6. 企業状態がLINE受付可能か
7. `reminder_id`が送信済みでないか
8. `now >= due_at`か

先に拒否された理由を構造化結果へ返し、例外でscheduler全体を停止させない。

## 時刻境界

`due_at = activity_at + interval`で計算する。calendar月のような曖昧な単位は扱わない。

- 予定時刻の1秒前: `NOT_DUE`
- 予定時刻ちょうど: `DUE`
- 予定時刻の1秒後: `DUE`
- `now < activity_at`: `NOT_DUE`
- naive `now`または`activity_at`: `INVALID_DATETIME`
- UTC以外のaware値: UTCへ正規化

`delay_seconds`は`evaluated_at - due_at`の秒数であり、未到達なら負、ちょうどなら0、期限超過なら正となる。

## session状態

**事実:** DB制約で許可される状態は`active`、`completed`、`cancelled`である（`supabase/migrations/202607200001_application_sessions.sql:25-28`, `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql:50-71`）。

- `active`: 他条件が通れば送信候補
- `completed`: `SESSION_COMPLETED`
- `cancelled`: `SESSION_NOT_ACTIVE`
- 空、不明値、大文字小文字違い: `SESSION_NOT_ACTIVE`

完全一致だけを許可し、部分一致や大文字小文字の補正は行わない。

## 企業状態と応募受付

応募受付は既存`app_settings.application_enabled`に対応する。`True`だけを受付中とし、`False`またはbool以外は`APPLICATION_RECEPTION_DISABLED`としてfail closedにする。現行Webhookも応募開始時にこの設定を確認する（`backend/main.py:190`, `backend/main.py:1274-1277`）。

企業状態は`backend/authz_policy.py`の`CompanyState`と`CompanyCapability.LINE_ACCEPT`を再利用し、規則を重複定義しない（`backend/authz_policy.py:39-51`, `backend/authz_policy.py:148-213`）。

| company state | リマインド送信 |
|---|---|
| `monitor_active` | 許可 |
| `active` | 許可 |
| `monitor_expired` | 拒否 |
| `suspended` | 拒否 |
| `closed` | 拒否 |
| 不明値 | 拒否 |

**未接続:** live public schemaには`companies`相当tableがなく、企業状態は実DBからまだ取得できない（`docs/AUTH_ENVIRONMENT_PREFLIGHT.md:92-97`）。後続adapterを実装する前にAuth/企業基盤の接続方針を確定する必要がある。

## reminder_idと二重送信防止

`reminder_id`は送信履歴と結びつく安定した識別子であり、配列indexをIDとして使わない。

- 送信済みID集合に同じIDがあれば、期限超過後も`ALREADY_SENT`
- 履歴の順序や同じIDの重複は判定を変えない
- 定義側の同一IDは、該当する全定義を`DUPLICATE_REMINDER_ID`として送信しない
- 並び替えと本文変更では同じIDを維持する
- 削除後も過去の送信履歴は保持する

純粋ポリシーが防止できるのは「評価時点で送信済みと渡されたID」の再選択である。複数workerの同時実行を含む厳密な一回送信は、後続DB adapterがID単位のunique制約、row lockまたは原子的なclaimを実装して保証する。LINE送信成功前後の履歴更新順序と再試行規則もadapter/scheduler設計で確定する。

## 複数リマインド

`evaluate_reminders`は全定義を評価して`decisions`へ保持する。不正な1件があっても、20件以内なら正常な他定義を評価できる。

送信候補は次の順で決定的に並べる。

1. `due_at`の早い順
2. `due_at`が同じなら明示的な`order`
3. さらに同じなら`reminder_id`

`due`へ返すのは最古の未送信1件だけである。1時間・24時間・3日分がすべて期限超過していても同時送信しない。送信・履歴反映後の次回実行で次の1件を評価する。

現行保存形式に`order` fieldはないため、将来のadapterは保存配列の位置を整数`order`として渡す。並び替えでorderが変わっても、履歴の結合はIDで行う。

## reason code

| reason_code | 意味 |
|---|---|
| `DUE` | 予定時刻に到達し、全guardを通過 |
| `NOT_DUE` | 予定時刻前 |
| `ALREADY_SENT` | 同じIDを送信済み |
| `REMINDER_DISABLED` | 定義が無効 |
| `SESSION_COMPLETED` | 応募完了済み |
| `SESSION_NOT_ACTIVE` | 取消・不明などactive以外 |
| `APPLICATION_RECEPTION_DISABLED` | 応募受付停止 |
| `COMPANY_NOT_ACCEPTING_LINE` | 企業状態がLINE受付不可または不明 |
| `INVALID_REMINDER` | ID、型、interval、unit、本文、order、件数が不正 |
| `MISSING_ACTIVITY_TIME` | 基準時刻なし |
| `INVALID_DATETIME` | naiveまたはdatetime以外 |
| `DUPLICATE_REMINDER_ID` | 定義内ID重複 |

理由にはメッセージ本文、応募者情報、メール、LINE IDを含めない。

## 将来の接続

### DB adapterの責務

- 企業scope付きで`active` sessionだけを読み取る
- どのDB値を`activity_at`へ渡すかを明示する
- `app_settings`を`ReminderDefinition`へ変換する
- 旧固定sent timestampを`legacy_1h`、`legacy_24h`、`legacy_3d`の送信済み集合へ変換する
- 可変ID単位の履歴を読み、原子的にclaim・記録する
- 設定削除後も必要な履歴を保持する
- DB障害と対象0件を区別する

### schedulerの責務

- timezone-aware UTCの`now`を渡す
- sessionごとに`evaluate_reminders`を呼ぶ
- `due`の最大1件だけを送信層へ渡す
- 成功、失敗、再試行、claim解放を記録する
- 企業・session間の公平性、batch size、rate limitを管理する

### 意図的に未接続の機能

- Supabase queryとwrite
- 可変reminder履歴schemaとmigration
- LINE push送信
- scheduler、cron、Render Job
- FastAPI endpoint
- 企業状態のDB取得
- 監視、再試行、dead-letter処理

これらを接続するまでは、管理画面にある「自動送信は未接続」という表示と実運用上の状態は変わらない。
