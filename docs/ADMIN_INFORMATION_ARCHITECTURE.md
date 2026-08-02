# 管理画面 情報設計

作成日: 2026-07-31

状態: 実装前の提案

根拠: `docs/ADMIN_UX_AUDIT.md`

## 1. 対象利用者と利用目的

### 現在対象にする利用者

- 採用担当者: 新着確認、応募者対応、問い合わせ対応、面接調整、設定変更を行う。
- 採用責任者: 対応漏れ、応募進捗、採用状況を把握する。

### Auth接続後に扱う利用者

- owner: 全設定、メンバー管理、CSV出力を行う。
- admin: 日常業務と設定変更を行い、メンバー管理とCSVは行わない。
- member: 日常業務と必要最低限の設定閲覧を行う。
- platform admin: 企業業務データを操作せず、運営専用画面を使用する。

このroleは純粋policyに定義済みだが、現在のFastAPI/Next.jsへ未接続である（`backend/authz_policy.py:9-65`, `docs/AUTHORIZATION_POLICY.md`）。現在の画面へrole別表示があるとは扱わない。

## 2. 情報設計の原則

1. **数値より行動を先に置く。** 最初のviewportで「誰に、何を、いつまでに」が分かる。
2. **日常業務と設定を分離する。** 毎日使う導線へ設定項目を混ぜない。
3. **同じ対象を再検索させない。** Dashboardの件数から条件付き一覧・detailへ直接移動する。
4. **現在・累計・期間を混ぜない。** 全metricへ基準を表示する。
5. **失敗と0件を分ける。** stale、partial、network error、emptyを別状態にする。
6. **送信は確認し、更新は結果を残す。** LINEと面接候補は取消不能actionとして扱う。
7. **未実装機能を操作可能に見せない。** Auth、RLS、自動リマインド、契約管理を運用済みと表示しない。
8. **PCを主、mobileを緊急対応可能にする。** mobileでも応募者確認、LINE送信、状態変更を完遂できる。

## 3. Navigation候補の比較

| 候補 | 内容 | メリット | デメリット | 判定 |
|---|---|---|---|---|
| 1. 現行メニュー維持 | 現在のsidebar項目とhash切替を維持 | 変更量が最小 | 業務と設定の階層、問い合わせ/面接の不足、stable route keyの問題が残る | Quick Win期間だけ維持 |
| 2. 単純な左sidebar | 全項目を同じ階層で並べる | PCで一覧性が高い | 項目が増えるほど日常業務と設定が混ざる | 不採用 |
| 3. 日常業務と設定を分離 | Primary navとSettings groupを分ける | 頻度と責務が明確。Auth後の項目も段階追加しやすい | route/component整理が必要 | **採用** |

## 4. 推奨navigation

### 4.1 目標構成

```text
管理画面
├─ ホーム
├─ 応募者
├─ 問い合わせ
├─ 面接
├─ 分析
└─ 設定
   ├─ 会社情報
   ├─ 応募フロー
   │  ├─ 応募受付
   │  ├─ ステータス
   │  └─ 質問ツリー
   ├─ 自動応答
   │  ├─ FAQ
   │  └─ メッセージテンプレート
   └─ 通知・リマインド

Auth接続後にだけ追加
├─ メンバー・権限
├─ セキュリティ
└─ 会社・契約
```

### 4.2 段階導入

- **Auth前:** ホーム、応募者、問い合わせ、分析、設定を表示する。面接は応募者filterとDashboardの「面接調整中」から開き、global面接一覧APIができるまで独立navを表示しない。
- **面接一覧API後:** 「面接」をprimary navへ追加する。
- **Auth/RLS後:** user roleとcompany capabilityをserver判定し、メンバー・権限、セキュリティ、会社・契約を表示する。CSSで隠すだけの権限制御にはしない。
- **Platform admin:** tenant画面へ混在させず、設計済みの`/admin`運営画面へ分離する。

### 4.3 Route key

現在は日本語表示名をhash値と状態識別子に使う（`frontend/app/page.tsx:11-20`, `frontend/app/page.tsx:84-104`）。改善後はroute keyとlabelを分ける。

| Key | Label | 例 |
|---|---|---|
| `home` | ホーム | `/` または `?view=home` |
| `applicants` | 応募者 | `/applicants` |
| `inquiries` | 問い合わせ | `/inquiries` |
| `analytics` | 分析 | `/analytics` |
| `settings.general` | 会社情報 | `/settings/general` |
| `settings.flow` | 応募フロー | `/settings/application-flow` |
| `settings.faq` | FAQ | `/settings/faq` |
| `settings.reminders` | 通知・リマインド | `/settings/reminders` |

App Routerの複数route化はcomponent分割後に行う。最初のQuick Winでは現在のhash routeを維持し、behavior changeを小さくする。

## 5. 画面間の関係

```text
ホーム
 ├─ 新規応募 ───────────────┐
 ├─ 面接調整中 ─────────────┤
 └─ 離脱/応募途中 ──────────┼─> 応募者（条件付き一覧） -> 応募者詳細
                              │      ├─ ステータス更新
                              │      ├─ メモ/タグ
                              │      ├─ LINE履歴/送信
                              │      └─ 面接候補確認/送信
 ホーム                         │
 └─ 未対応問い合わせ ─────────┴─> 問い合わせ（未対応filter） -> 問い合わせ詳細
                                                           ├─ 状態更新
                                                           ├─ 関連応募者
                                                           └─ LINE返信

 設定 -> 会社情報 / 応募フロー / 自動応答 / 通知・リマインド
 分析 -> 期間付きserver集計（実装後）
```

Dashboardのcountから遷移した場合、filter chipと「Dashboardからの条件」を表示し、1操作で条件を解除できるようにする。

## 6. 推奨ユーザーフロー

### 6.1 朝の確認

1. ホームを開く。
2. 「要対応」へ未対応問い合わせ、期限超過、面接調整、新規応募が優先順で表示される。
3. 件数だけでなく最古の経過時間と対象例を確認する。
4. 項目を選び、条件付き一覧へ移動する。
5. detailで対応し、状態を更新する。
6. 戻ると同じfilter・sort・scroll位置へ戻り、件数が更新される。

完了条件: 一覧へ戻ったとき対象が処理済みとしてキューから外れ、更新時刻が表示される。

### 6.2 応募者対応

1. 名前、電話、職種、許可された識別子で検索する。
2. status、面接状態、要対応、最終対応でfilterし、最終対応の古い順にsortする。
3. 行またはcardを選びdetailを開く。
4. 概要、応募内容、履歴を読み、現在の状態を確認する。
5. メモ・タグ・statusを更新する。各操作は独立して保存結果を表示する。
6. LINEはcomposerで入力し、確認画面で宛先表示名と本文を確認して送る。
7. 面接候補は候補日を入力し、確認画面で日時・timezone・面接種別を確認して送る。
8. 成功時は履歴を再取得し、送信記録とstatus反映を表示する。

送信結果が不明な場合は自動再送せず、「結果を確認してから再試行」と表示する。

### 6.3 問い合わせ対応

1. 未対応filterを既定にし、古い順または期限超過順で表示する。
2. detailで全文、受信日時、状態、関連応募者、LINE履歴を確認する。
3. 「対応中」にして作業中を明示する。
4. 関連応募者が確認できる場合だけdetailへ遷移する。
5. 返信する場合はLINE送信確認を通す。
6. 返信成功後に「対応済み」へ更新する。自動更新する場合はAPIの原子的契約を先に定める。

### 6.4 初期設定

1. 会社情報と応募受付を設定する。
2. 選考ステータスを確認する。
3. 質問ツリーを編集し、LINE表示previewを確認する。
4. FAQ回答と公開状態を設定する。
5. 共通メッセージをpreviewする。
6. リマインドは未接続表示を確認した上で保存する。

各screenは「保存単位」「LINEへの反映時点」「影響範囲」を先頭に表示する。

## 7. 情報配置

### 7.1 ホーム

上から次の順とする。

1. Page header: 最終更新時刻、再読み込み、stale状態。
2. 要対応キュー: 未対応問い合わせ、期限超過、面接調整、新規応募。
3. Current snapshot: 応募途中、面接確定、採用など現在状態。
4. Funnel: 応募開始、完了、率。期間が実装されるまでは「累計」。
5. Recent: 応募者と問い合わせのclickable list。
6. 補助説明: 集計定義。普段は折りたたむ。

### 7.2 応募者一覧

- Header: 総件数、表示件数、更新時刻。
- Search/filter bar: keyword、status、面接、要対応、sort。
- Result summary: active filter chip、clear。
- Desktop: table。名前、要対応、status、面接、最終対応、担当者、操作。
- Mobile: card。名前、status、要対応、最終対応、primary action。
- Detail: Desktop split pane / overlay drawer、Mobile full screen。

### 7.3 問い合わせ

- 未対応countをtitle横へ置く。
- Desktopは40:60のlist/detail。
- listは日時、状態、冒頭、関連応募者、経過時間。
- detailは全文、状態、関連応募者、履歴、返信、処理結果。
- Mobileはlistとdetailをrouteで分ける。

### 7.4 設定

- 左に設定category、右にform。
- Screen headerに保存単位と反映先。
- 変更中はsticky save barへ「未保存」「破棄」「保存」を表示。
- 危険設定はimpact boxと確認dialogを使う。
- 未実装categoryはnavigationに出さない。

## 8. 状態設計と推奨copy

| State | 表示原則 | Copy例 |
|---|---|---|
| initial | 初期layoutを保ちskeletonを表示 | 「応募者を準備しています」 |
| loading | 対象領域だけをbusyにする | 「応募者を読み込んでいます…」 |
| success | 内容と最終取得時刻を表示 | 「10:42に更新」 |
| empty | エラーでないことと次の行動を示す | 「未対応の問い合わせはありません」 |
| partial | 取得できた領域と失敗領域を分ける | 「応募者は表示中です。履歴を取得できませんでした」 |
| stale | 前回成功データを残し古さを示す | 「10:42時点の情報です。更新に失敗しました」 |
| validation error | field近傍に原因と修正方法 | 「候補日を2件以上入力してください」 |
| network error | 送信済み/未送信を推測しない | 「結果を確認できませんでした。履歴を確認してから再試行してください」 |
| permission denied | 隠すだけでなくserver拒否を説明 | 「この操作を行う権限がありません」 |
| read-only | page banner、write action無効 | 「現在は閲覧のみです。変更は保存できません」 |
| saving | 対象actionを止めdraft保持 | 「保存中…」 |
| saved | 結果と時刻 | 「10:45に保存しました」 |
| send confirmation | 宛先、本文、取消不能を表示 | 「送信後は取り消せません。内容を確認してください」 |
| send success | 履歴反映まで確認 | 「LINEを送信し、履歴へ反映しました」 |
| send failure | backend結果に沿い断定 | 「LINEを送信できませんでした」または「結果を確認できませんでした」 |

Error reasonへLINE ID、本文、email等のPIIを埋め込まない。UIで認可済み利用者へ応募者名を表示することと、log/error telemetryへPIIを残すことは分けて扱う。

## 9. Responsive behavior

| 幅 | Navigation | 一覧 | Detail | Settings |
|---|---|---|---|---|
| 1440px | 固定sidebar | table + optional split detail | 520〜640px pane | category sidebar + form |
| 768px | hamburgerでoverlay sidebar | 優先列tableまたはcompact row | full-height overlay | 1column、sticky save |
| 375px | sticky app bar + navigation sheet | card list | full-screen route、sticky action | 1column、44px target |

Mobileのprimary actionは「status」「LINE」「面接」の順で常時見える。危険actionを近接配置せず、送信確認画面へ遷移する。

## 10. Auth/RLSとの境界

- Auth前に実装可能: navigation整理、Dashboard action link、overlay accessibility、feedback state、送信確認、responsive、component分割、問い合わせ既存API接続。
- Auth/RLS後に実装: login、MFA、会社切替、role別nav/action、read-only/suspended/closed状態、member管理、platform admin。
- Frontendは`backend/authz_policy.py`を再実装しない。Backendが返すcapabilityまたは403 reasonを表示へ変換する。
- `platform_admin`へ企業業務データを表示しない。
- `monitor_expired`と保持期間内`closed`は閲覧/CSVだけ、`suspended`は通常画面を拒否する正式policyに従う（`docs/AUTHORIZATION_POLICY.md`）。

## 11. 未確認と検証方法

- 実利用者が用語「離脱」「応募途中」「面接調整中」を区別できるか: 5名程度のtask-based usability testで確認。
- Mobileで応募者検索からLINE送信まで完遂できるか: 375px実機/Browser E2Eで確認。
- Detail split viewの適正幅: 768/1024/1440pxで長文fixtureを用いて確認。
- 問い合わせstatusと担当者運用: 採用業務ownerの承認を得てからAPI enumを固定。
- 期間指標: dashboard endpointに期間引数を追加する前にmetric definitionを承認する。

未確認項目を既定値で実装せず、該当phaseの受入条件へ組み込む。
