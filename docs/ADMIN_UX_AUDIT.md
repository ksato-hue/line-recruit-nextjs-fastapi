# 管理画面 UX/UI 監査

調査日: 2026-07-31

対象: `main` の `4feeeb7` を起点とする `agent/admin-ux-audit`

実装変更: なし（文書のみ）

## 1. 判定の読み方

- **確認済み事実**: 現在のcheckoutにあるコード、設定、テスト、ビルド結果から直接確認した内容。
- **推測**: 確認済み事実から導いた利用上の可能性。実利用者テストでは未検証。
- **改善提案**: 承認後の実装候補。現在動作しているとは扱わない。
- **未確認**: 実ブラウザ、production、実利用者、外部サービスの確認が必要な内容。

今回、production / staging DB、Supabase MCP、LINE APIには接続していない。合成データ用のローカル起動を試みたが、ローカル待受が `listen EACCES 127.0.0.1:3100` で失敗し、操作可能なブラウザも0件だった。このため375px、768px、1440pxでの実画面目視は**未確認**であり、レスポンシブと視覚評価は現行JSX/CSSを根拠にしたコードレビューである。

## 2. 結論

### 良い点

- **確認済み事実:** 管理画面の通信は同一オリジンの`/api/admin/*`へ集約され、BFFがサーバー側で管理APIキーを付与する。ブラウザへ管理APIキーを渡すコードはない（`frontend/lib/api.ts:3-13`, `frontend/app/api/admin/[...path]/route.ts:3-6`, `frontend/app/api/admin/[...path]/route.ts:36-48`）。
- **確認済み事実:** 応募者の選考ステータスは変更前後を表示し、保存中の再操作を止め、成功・失敗を同じ操作領域に表示する（`frontend/app/page.tsx:777-793`）。
- **確認済み事実:** 設定画面間の移動とブラウザ離脱には未保存変更の警告がある（`frontend/app/page.tsx:84-104`, `frontend/app/page.tsx:155-190`, `frontend/app/page.tsx:372-383`）。
- **確認済み事実:** FAQ、質問ツリー、リマインドはloading / error / saving / successの基本状態を持つ。リマインドは自動送信未接続を明示している（`frontend/app/page.tsx:1095-1119`, `frontend/app/page.tsx:1237-1314`, `frontend/app/page.tsx:1402-1427`）。
- **確認済み事実:** ステータスは色だけでなく文字も表示し、LINEユーザーIDは画面上でマスクされる（`frontend/app/page.tsx:27-39`, `frontend/app/page.tsx:797-820`）。
- **確認済み事実:** レガシーHTML管理画面は削除済みで、管理UIはNext.jsに一本化されている。現在のJSON API、Webhook、health routeは残っている（`backend/main.py:1729-1734`, `backend/main.py:1828-1965`, `backend/main.py:2400-2456`）。

### 最大の課題

- **UX:** ダッシュボードの「今日やること」が操作先へつながらず、未対応問い合わせ、離脱、面接調整、新規応募を見つけても処理へ移れない（`frontend/app/page.tsx:402-436`, `frontend/app/page.tsx:486-495`）。
- **視覚:** 7枚のKPI、同じ強さの白いカード、大きな角丸と影が並び、行動の優先度よりカードの均一性が目立つ（`frontend/app/page.tsx:393-420`, `frontend/app/globals.css:71-91`）。
- **情報設計:** 日常業務、分析、設定は存在するが、問い合わせ対応と面接調整の完了導線が欠け、ダッシュボードから主要フローへ遷移できない。到達可能な「LINE履歴」専用画面もなく、定義済みコンポーネントだけが残る（`frontend/app/page.tsx:11-20`, `frontend/app/page.tsx:857-948`, `frontend/app/page.tsx:1431-1439`）。

## 3. 現在の画面・機能一覧

| 機能 | 到達方法 | 主な操作 / API | loading / empty / error | 未接続・到達不能 | 現在の問題 |
|---|---|---|---|---|---|
| ダッシュボード | サイドバー「ダッシュボード」 | `GET /dashboard`。KPI、現在状態、直近応募者・問い合わせ | 初回loading、API error、応募者・問い合わせのemptyあり | なし | KPIと状態項目が非クリック。期間がない。最近の問い合わせは非操作要素 |
| 応募者一覧 | サイドバー「応募者一覧」 | `GET /applicants`, `GET /status-settings`。検索、状態絞り込み、詳細表示 | loading、API error、全件0と検索0を区別 | 応募途中session一覧はない | 並び替え、ページング、新着、最終対応、応募途中/完了の識別がない |
| 応募者詳細ドロワー | 応募者一覧または直近応募者のボタン | `PATCH /applicants/{id}`, `POST /applicants/{id}/interview-slots`, `POST /line/send`, `GET /line-messages` | 操作別saving/error/successの一部あり | 構造化した全回答、タグ編集、候補履歴 | LINE/面接送信に最終確認なし。履歴の取得失敗を0件にする。ドロワーのdialog要件不足 |
| お問い合わせ | サイドバー「お問い合わせ」 | `GET /inquiries`のみ画面から使用 | loading、API error、emptyあり | 詳細、更新、返信、応募者関連付け | APIには詳細・更新があるがUI未接続。未対応を処理完了へ進められない |
| 簡易分析 | サイドバー「簡易分析」 | `GET /dashboard`, `GET /applicants`, `GET /status-settings` | loading、API error、emptyあり | 期間、推移、流入、FAQ効果 | ダッシュボードと重複。面接・採用・状態別件数はfrontend再集計 |
| 基本設定 | 設定 > 基本設定 | `GET/PATCH /settings`。応募受付、会社名等 | loading/error/saving/success | 契約、メンバー、権限、セキュリティ | 通知メールは保存のみ。設定の分類と影響範囲が弱い |
| ステータス設定 | 設定 > ステータス設定 | `GET/PATCH /status-settings`。追加、名称、順序、有効、削除 | 外側loading/error、内部saving/success/error | なし | 並べ替えボタンの名前不足。名称変更の影響確認が弱い |
| FAQ設定 | 設定 > FAQ設定 | `GET /faq-settings`, `PATCH /faq-settings/{key}`。検索、絞り込み、回答、公開 | loading/error/saving/success/検索0 | 旧FAQ CRUDは画面未使用 | 248質問を個別保存。プレビューなし。質問ツリーとの差は説明文だけ |
| 質問ツリー設定 | 設定 > 質問ツリー設定 | `GET/PATCH /question-tree`。質問追加、形式、必須、順序、削除 | loading/error/saving/success | 実際のLINEプレビュー | 入力label不足。質問単位の削除確認なし。初心者が分岐との関係を把握しにくい |
| リマインド・文面 | 設定 > リマインド・メッセージテンプレート | `GET/PATCH /settings`。追加、順序、削除、ON/OFF、文面 | loading/error/saving/success | scheduler、DB adapter、LINE送信は未接続 | 未接続表示は適切。上限20件到達時の明示、送信例、実行履歴はない |
| LINE履歴（定義のみ） | 到達経路なし | `GET /line-messages?limit=200` | 定義上はloading/error/emptyあり | ナビゲーションなし | `HistoryView`は定義だけで使用されない |
| 面接関連（定義のみ） | 到達経路なし | 応募者詳細を開く案内 | なし | ナビゲーションなし | `InterviewDateSettings`は定義だけで使用されない |

根拠: メニューと画面切替は`frontend/app/page.tsx:11-20`, `frontend/app/page.tsx:264-354`、API clientは`frontend/lib/api.ts:32-143`、Backend routeは`backend/main.py:1734-2456`。

## 4. 主要業務フロー

### 4.1 朝の確認

**確認済み事実**

1. `new_count`はAPI responseにあるが、KPIカードにも「今日やること」にも表示されない（`backend/main.py:1780-1824`, `frontend/app/page.tsx:393-406`）。
2. 未対応問い合わせ、離脱、面接調整中、応募途中は件数表示だけで、クリックやfilter連携がない（`frontend/app/page.tsx:402-436`, `frontend/app/page.tsx:486-495`）。
3. 離脱件数の元になるapplication sessionを管理画面で開く画面がない。
4. KPIは累計または現在値で、基準期間・更新時刻・前回差がない（`backend/main.py:1780-1818`, `frontend/app/page.tsx:393-421`）。

**推測:** 採用担当者は件数を見た後、別メニューへ移動し、同じ条件を再現して対象を探す必要がある。離脱sessionは対象一覧へ到達できないため、件数確認で止まる。

**改善提案:** ページ上部を「要対応キュー」にし、未対応問い合わせ、離脱、面接調整中、新規応募を優先順位順に並べ、クリック時に条件付き一覧へ移動する。累計KPIはその下へ移し、各数値に「現在」または対象期間を必ず表示する。

### 4.2 応募者対応

**確認済み事実**

- 検索は名前、電話、職種、LINE IDを対象にするがplaceholderはLINE IDを説明しない（`frontend/app/page.tsx:204-213`, `frontend/app/page.tsx:519-524`）。
- 一覧から詳細を開き、ステータス、メモ、LINE、面接候補を操作できる（`frontend/app/page.tsx:526-558`, `frontend/app/page.tsx:697-826`）。
- 任意質問の回答は応募確定時に`motivation`へラベル付き文字列として連結され、UIは「応募動機」1枠として表示する（`backend/main.py:1157-1177`, `frontend/app/page.tsx:709-716`）。
- タグは表示だけで、`Applicant`型とBackend update modelには更新余地があるが、編集UIはない（`frontend/types/index.ts:1-14`, `frontend/app/page.tsx:796-801`）。
- LINE送信・面接候補送信は入力画面からそのまま送信され、宛先・本文・候補日の確認stepがない（`frontend/app/page.tsx:649-695`, `frontend/app/page.tsx:718-775`）。

**推測:** 初心者でも一連の操作は発見できるが、優先順が同じ高さのblockに分散する。長い応募内容、履歴、メモを行き来しながら送信する際に誤送信や文脈見落としが起きやすい。

**改善提案:** 詳細を「概要」「応募内容」「対応履歴」「面接」の4領域へ整理し、主要操作はsticky action areaへまとめる。LINEと面接候補は必ず確認stepを挟み、送信中は閉じる・二重操作・別応募者への切替を止める。

### 4.3 問い合わせ対応

**確認済み事実**

- 画面は一覧表示のみで行クリック、詳細、状態変更、返信がない（`frontend/app/page.tsx:950-985`）。
- Backendには企業scope付き詳細GETと状態PATCHがある（`backend/main.py:2412-2440`）。frontend clientには詳細GETだけあり、現在の画面から呼ばれず、更新関数はない（`frontend/lib/api.ts:40-46`）。
- 問い合わせ型は`line_user_id`, `message`, `status`を持つがapplicant IDや担当者を持たない（`frontend/types/index.ts:180-186`）。

**推測:** 採用担当者は「未対応」を確認できても完了を記録できず、応募者詳細やLINE返信へつなげられないため、対応漏れを管理画面内で解消できない。

**改善提案:** PCでは一覧＋詳細の2ペイン、mobileでは一覧から詳細screenへ遷移する。詳細に状態変更、関連応募者、LINE履歴、返信導線を置く。関連付けが確認できない問い合わせは、存在を推測せず「応募者未関連」と明示する。

### 4.4 初期設定

**確認済み事実:** 現在の設定は基本、ステータス、FAQ、質問ツリー、リマインド・文面の5分類である（`frontend/app/page.tsx:18-20`）。質問ツリー保存はLINEフローへ反映する確認がある。応募受付OFFの影響、リマインド未接続も説明される（`frontend/app/page.tsx:1062-1069`, `frontend/app/page.tsx:1402-1406`, `frontend/app/page.tsx:1593-1604`）。

**推測:** 「FAQ」と「質問ツリー」、「文面」と「リマインド」の業務上の違いは、初回利用者にはメニュー名だけで判断しにくい。保存単位も画面単位、FAQ単位で異なる。

**改善提案:** 現時点は「会社情報」「応募フロー」「自動応答」「通知・リマインド」の4群へ整理する。Auth実装後にだけ「メンバー・権限」「セキュリティ」「会社・契約」を表示し、未実装項目を操作可能に見せない。

## 5. 画面別レビュー

### 5.1 ダッシュボード

- **確認済み事実:** KPIは7枚。応募者累計、開始累計、完了累計、完了率、問い合わせ全件、面接確定現在値、採用現在値が混在する（`frontend/app/page.tsx:392-421`）。
- **確認済み事実:** 「今日やること」は時刻や期限ではなく現在状態4種の合計である（`frontend/app/page.tsx:402-435`）。
- **確認済み事実:** 直近応募者はbuttonで詳細を開くが、直近問い合わせは`div`で操作できない（`frontend/app/page.tsx:447-478`）。
- **改善提案の配置順:** 1) 更新時刻と接続状態、2) 要対応キュー、3) 新規応募と未対応の短いsummary、4) 累計ファネル、5) 直近応募者と問い合わせ、6) 補助情報。
- **改善提案:** 0件時は「0」を並べるだけでなく「本日の要対応はありません」と次回確認時刻を示す。期間未対応の間は「累計」「現在」を明記し、「今日」「今週」と誤認させない。

### 5.2 応募者一覧・詳細

- **検索/絞り込み:** 現状はclient-side、全件対象、単一状態filter。サーバーページング導入時には結果が不完全になるため、検索・filter・sortをAPI契約へ移す。
- **新着/最終対応:** 現在の型には`last_contact_at`やapplication session状態がない（`frontend/types/index.ts:1-14`）。表示にはAPI/DB側の正式な基準が必要。
- **行操作:** 行全体はクリック不可で、選択中行の表現もない（`frontend/app/page.tsx:541-553`）。
- **ドロワー:** 520px固定上限、mobileで全幅になるが、dialog role、名前、Esc、focus trap、close後focus復帰がない（`frontend/app/page.tsx:697-707`, `frontend/app/globals.css:124-126`）。
- **履歴:** `GET /line-messages`の例外をBackendが空配列へ変換し、Frontendもcatchで空配列へ変換するため、障害と履歴0件を区別できない（`backend/main.py:2381-2397`, `frontend/app/page.tsx:595-604`, `frontend/app/page.tsx:809-825`）。
- **メモ:** 保存中はbuttonを止めるが、未保存メモを閉じる警告とローカル成功表示がない（`frontend/app/page.tsx:230-241`, `frontend/app/page.tsx:803-807`）。
- **長文:** LINE本文は`pre-wrap`とword-breakを持つ。応募動機のdetailはword-breakのみで、長い構造化回答としての見出しはない（`frontend/app/globals.css:127-130`, `frontend/app/globals.css:153-161`）。

### 5.3 お問い合わせ

- **確認済み事実:** 未対応件数はdashboard APIにあるが、問い合わせ画面にfilterや未対応summaryがない（`backend/main.py:1797-1824`, `frontend/app/page.tsx:950-985`）。
- **改善提案:** 状態は少なくとも「未対応」「対応中」「対応済み」を設計で固定してからUIを接続する。現在のBackendは任意の空でないstatus文字列を受け入れるため、UIだけで正式enumを作らない（`backend/main.py:2426-2439`）。
- **改善提案:** 問い合わせdetail responseへ関連応募者summaryを同一企業scopeで返す契約を追加し、同じ`line_user_id`だけをclient側で推測結合しない。

### 5.4 簡易分析

- **確認済み事実:** 応募開始・完了・率はdashboardと重複する。面接確定、採用、状態別件数は取得済み応募者配列をfrontendで再集計する（`frontend/app/page.tsx:1441-1467`）。
- **推測:** ページングを導入すると、frontend再集計は全体集計ではなく表示page集計になる。
- **提案比較:** 現状の内容だけならダッシュボードへ統合する方がよい。分析を独立維持する条件は、Backend集計、期間指定、母数、推移、ファネル、定義文が揃うことである。

### 5.5 設定

- **保存単位:** 基本・ステータス・質問ツリー・リマインドは画面単位、FAQは質問単位。保存単位を見出し直下に表示する。
- **未保存:** global guardはあるが、各screenに常設のdirty表示や「変更を破棄」がない。FAQは個別保存と複数draftが併存する。
- **影響表示:** 応募受付OFFとリマインド未接続は説明済み。ステータス名称変更、質問削除、公開FAQ変更は影響対象を確認dialogで具体化する。
- **reset:** 質問ツリーだけにclient固定の初期値resetがある。サーバー既定値と誤認しないcopyへ変える（`frontend/app/page.tsx:1043-1051`）。
- **プレビュー:** LINEでの質問、FAQ回答、共通文面、リマインド文面のpreviewはない。

## 6. ビジュアルデザイン

### 確認済み事実

- 白いsurface、薄い青灰背景、青い業務accent、LINE緑を使う（`frontend/app/globals.css:1-14`）。
- panelとKPIは22px角丸と広いshadowで統一される（`frontend/app/globals.css:71-81`）。
- bodyはArialと日本語system font、本文tableは14px、補足は12〜13px（`frontend/app/globals.css:17-23`, `frontend/app/globals.css:68-70`, `frontend/app/globals.css:102-104`）。
- statusはbadgeで色と文字を併用する。buttonはprimary / secondary / danger / textがある（`frontend/app/globals.css:104-120`）。

### 評価と提案

- **推測:** 全surfaceに同程度の角丸・border・shadowがあるため、最重要taskと補助情報の視覚差が弱い。
- **提案:** 通常panelは8〜12px角丸・border中心、shadowはdrawer/dialogだけに限定する。LINE緑は送信・LINE固有actionへ限定し、一般保存はprimary blueに分ける。
- **提案:** 新着、未対応、期限超過は色に加えてicon、label、件数、期限copyを併記する。
- **未確認:** 実画面でのcontrast、font rendering、長文折返し、画面密度、視覚疲労はブラウザ未接続のため未検証。実装時に自動contrast検査と実機目視を行う。

## 7. アクセシビリティ

| 項目 | 確認済み事実 | 判定 / 改善提案 |
|---|---|---|
| Keyboard | native button/input/selectを多く使用 | 基本操作は期待できるが実ブラウザ未検証 |
| Focus表示 | input/select/textareaへ`outline: none`、`:focus-visible`定義なし（`frontend/app/globals.css:95-99`） | P2。全interactiveへ一貫したfocus ringを追加 |
| Drawer | `aside`/`section`でdialog属性なし（`frontend/app/page.tsx:697-707`） | `role=dialog`, `aria-modal`, title、Esc、trap、focus復帰が必要 |
| 未保存dialog | role/name/descriptionとautoFocusあり（`frontend/app/page.tsx:372-380`） | 良い土台。Esc、trap、focus復帰は未実装 |
| Label | reminderの一部は`htmlFor`あり。他画面はplaceholderや近接`label`だけ（`frontend/app/page.tsx:1108-1114`, `frontend/app/page.tsx:1415-1423`, `frontend/app/page.tsx:1605-1618`） | 全form controlへprogrammatic labelを付与 |
| Icon button | reminder順序にはaria-labelあり、status順序とdrawer closeにはない（`frontend/app/page.tsx:706`, `frontend/app/page.tsx:1423`, `frontend/app/page.tsx:1503`） | 名前を追加し、closeは「応募者詳細を閉じる」とする |
| 状態通知 | 一部に`role=status/alert`。多くのsuccess/error/loadingにはない | 共通live regionでsaving/saved/errorを通知 |
| 色依存 | badgeに文字がある | 維持。dotだけのLINE方向は隣接textがあるため意味は保持 |
| Touch target | mini button 32px、close 38px（`frontend/app/globals.css:120`, `frontend/app/globals.css:212`） | mobileで最低44pxを確保 |
| 見出し | h1/h2/h3はある | 画面切替・drawer・cardの順序を実ブラウザとscreen readerで検証 |
| WCAG | 完全な試験なし | 準拠を断定しない。実装PRごとにkeyboard、contrast、name/role/valueを検証 |

## 8. レスポンシブ

### 確認済み事実

- 1180px以下でKPIは3列、2カラムsectionは1列になる（`frontend/app/globals.css:272-276`）。
- 780px以下ではfixed sidebarが通常flowの全幅になり、contentは下へ続く（`frontend/app/globals.css:277-299`）。
- KPIはmobileでも2列、tableは`min-width: 980px`の横scrollである（`frontend/app/globals.css:72`, `frontend/app/globals.css:100-103`, `frontend/app/globals.css:277-285`）。
- drawerは最大520pxか全幅で、mobile専用sticky header/actionはない（`frontend/app/globals.css:124-126`）。

### 推測

- 375pxではnavigationの下に本文が続き、応募者を開くまでのscroll量が大きい。
- 980px tableの横scrollは緊急時の応募者確認には負荷が高い。
- full-width drawerは表示できるが、長い履歴の下に主要actionが埋もれる。

### 改善提案

- 1440px: 240px sidebar + 最大1440px content。応募者は一覧とdetailのsplit view。
- 768px: sidebarをoverlay sheet化し、tableの優先列だけを残す。
- 375px: sticky app bar、検索、応募者card list、full-screen detail、sticky action bar。LINE送信・status更新は片手で到達可能にする。
- 横scrollを唯一のmobile対応にせず、名前・状態・最終対応・要対応labelをcardへ再配置する。

## 9. Frontendコード構成

### 確認済み事実

- `frontend/app/page.tsx`は1,626行で、全ファイルに`useState`呼び出し74回、`useEffect`呼び出し25回、UI関数15個がある。top-level `AdminPage`だけでもstate 23個、effect 7個を持つ（`frontend/app/page.tsx:48-386`）。
- API取得、hash履歴、dirty guard、画面切替、全feature view、drawer、formが同じファイルにある。
- `HistoryView`と`InterviewDateSettings`は定義のみで、現在のrender pathにない（`frontend/app/page.tsx:857-948`, `frontend/app/page.tsx:1431-1439`）。
- `getInquiry`, `getInterviewSlots`, 旧FAQ CRUDは`frontend/lib/api.ts`の定義以外に現在のfrontend利用箇所がない（`frontend/lib/api.ts:44-46`, `frontend/lib/api.ts:55-57`, `frontend/lib/api.ts:80-100`）。
- `updateApplicant`は`Partial<Applicant>`を受け、更新専用型より広い（`frontend/lib/api.ts:48-52`, `frontend/types/index.ts:1-14`）。

### 改善提案

```text
frontend/
  app/
    page.tsx
  components/
    layout/AdminShell.tsx
    ui/{Button,Badge,Dialog,Drawer,FeedbackBanner}.tsx
  features/
    dashboard/
    applicants/
    inquiries/
    analytics/
    settings/
  hooks/
    useAdminNavigation.ts
    useUnsavedChanges.ts
  lib/
    api.ts
    datetime.ts
  types/
    index.ts
```

最初から汎用design systemを作らず、現在2回以上使う`Dialog`, `Drawer`, `FeedbackBanner`, action buttonだけを共通化する。大規模分割前にnav、応募者詳細、LINE送信、設定dirty guardのcharacterization testを追加する。

## 10. Frontendテスト

**確認済み事実:** `frontend`配下で`*.test.*`, `*.spec.*`, `__tests__`, Playwright, Cypress, Vitest, Jestに一致するproject-owned test fileは見つからない。現在のCI gateはTypeScript型検査とNext.js buildである（`frontend/package.json:5-10`, `.github/workflows/ci.yml`）。

**導入順:** 1) 日付・filter・表示判定の純粋関数、2) button/dialog/drawer等のcomponent test、3) API clientのrequest/response/error test、4) 合成APIによる主要user flow、5) mobile/desktop E2E、6) PIIを含まないfixtureだけのvisual regression。

最小構成は純粋関数と誤送信防止component testから始める。将来構成ではBrowser E2Eとvisual regressionを追加する。依存追加は本監査では行わない。

## 11. 優先度一覧

難易度は S（半日以内）、M（1〜2日）、L（数日以上）。「DB」はDB変更の要否、「Auth」はAuth/RLS依存を示す。

| ID | 画面 | 現状 / 問題 | 利用者への影響 | 改善案 | 優先度 | 難易度 | 関連ファイル | DB | Auth |
|---|---|---|---|---|---|---|---|---|---|
| UX-001 | 応募者詳細 | LINEを確認なしで即送信 | 誤送信・取消不能 | 宛先/本文確認、二重click防止、不明結果時の再送警告 | P0 | M | `frontend/app/page.tsx`, `backend/main.py` | 不要、厳密な冪等性は必要 | なし |
| UX-002 | 応募者詳細 | 面接候補をDB更新後にLINE送信し、失敗時に部分反映し得る | 失敗表示後の再送で重複・状態不整合 | frontend確認に加え、APIを原子的/冪等にし構造化結果を返す | P0 | L | `frontend/app/page.tsx`, `backend/main.py` | 必要な可能性 | なし |
| UX-003 | 全画面 | Basic認証共有利用者にrole別表示・read-onlyがない | 送信・設定変更を必要以上の利用者が実行可能 | Auth/RBAC/MFA接続後にserver判定を正としてactionを制御 | P0 | L | `frontend/middleware.ts`, `backend/authz_policy.py` | 必要 | 必須 |
| UX-004 | Dashboard | 要対応4項目が非クリック | 対象を再検索し対応漏れ | 条件付き一覧へ遷移 | P1 | S | `frontend/app/page.tsx` | 離脱一覧はAPI必要 | なし |
| UX-005 | Dashboard | 新規応募が表示されず、期間/更新時刻なし | 朝の優先順位を判断できない | `new_count`表示、現在/累計label、更新時刻 | P1 | S | `frontend/app/page.tsx` | 不要 | なし |
| UX-006 | Dashboard | 直近問い合わせが非操作要素 | 詳細へ進めない | 問い合わせ詳細へlink | P1 | S | `frontend/app/page.tsx` | 不要 | なし |
| UX-007 | 応募者一覧 | 最終対応、応募途中、期限、sort、pageなし | 大量データで優先対象を見落とす | server filter/page/sortと優先列 | P1 | L | `frontend/app/page.tsx`, `frontend/lib/api.ts`, `backend/main.py` | `last_contact_at`は必要 | なし |
| UX-008 | 応募者一覧 | 検索対象と説明が不一致、状態filter1個 | 検索可能範囲が分からない | copy修正、filter chip、条件clear | P1 | S | `frontend/app/page.tsx` | 不要 | なし |
| UX-009 | 応募者詳細 | 未保存メモを閉じても警告なし、成功表示なし | 入力損失・保存不安 | dirty表示、close確認、保存時刻 | P1 | S | `frontend/app/page.tsx` | 不要 | なし |
| UX-010 | 応募者詳細 | LINE履歴の障害を空履歴として表示 | 重複・矛盾した連絡の恐れ | loading/error/emptyを分離しretry | P1 | M | `frontend/app/page.tsx`, `backend/main.py` | 不要 | なし |
| UX-011 | 問い合わせ | 一覧だけで詳細・状態・返信なし | 未対応を完了できない | list/detail、状態更新、関連応募者、返信 | P1 | L | `frontend/app/page.tsx`, `frontend/lib/api.ts`, `backend/main.py` | 関連付け方針次第 | なし |
| UX-012 | 応募者詳細 | タグ表示のみ | 分類を管理画面で維持できない | chip入力、候補、保存feedback | P1 | M | `frontend/app/page.tsx`, `frontend/lib/api.ts` | 不要 | なし |
| UX-013 | 応募者詳細 | 任意回答を`motivation`へ連結表示 | 回答の意味を読み違えやすい | 当面は見出し付き本文、将来は構造化回答snapshot | P1 | L | `frontend/app/page.tsx`, `backend/main.py` | 構造化には必要 | なし |
| UX-014 | Mobile | nav、980px table、長いdrawer | 緊急時の確認・送信が遅い | mobile app bar、card list、full-screen detail、sticky action | P1 | L | `frontend/app/page.tsx`, `frontend/app/globals.css` | 不要 | なし |
| UX-015 | 設定 | 分類・保存単位・影響説明が不統一 | 初期設定で迷う | 4群へ整理、screenごとの保存単位と影響を表示 | P1 | M | `frontend/app/page.tsx` | 不要 | なし |
| UX-016 | 簡易分析 | client再集計とdashboard重複 | 将来page導入で誤集計 | 当面dashboard統合、独立時はserver aggregate | P1 | M | `frontend/app/page.tsx`, `backend/main.py` | 不要 | なし |
| UX-017 | 全画面 | stale/partial状態がない | 古い値を最新と誤認 | 最終成功時刻、再試行、stale banner | P1 | M | `frontend/app/page.tsx`, `frontend/lib/api.ts` | 不要 | なし |
| UX-018 | 全画面 | form focus ringなし | Keyboardで現在地を見失う | `:focus-visible` token追加 | P2 | S | `frontend/app/globals.css` | 不要 | なし |
| UX-019 | Drawer/Dialog | Esc、focus trap、focus復帰不足 | Keyboard/screen reader操作困難 | accessible overlay primitives | P2 | M | `frontend/app/page.tsx` | 不要 | なし |
| UX-020 | 設定 | inputのprogrammatic label不足 | 項目名が伝わらない | `id/htmlFor`とaria説明 | P2 | M | `frontend/app/page.tsx` | 不要 | なし |
| UX-021 | Feedback | loading/error/successのlive通知が部分的 | 操作完了を認識しにくい | 共通FeedbackBannerとlive region | P2 | M | `frontend/app/page.tsx` | 不要 | なし |
| UX-022 | Frontend | 1,626行、state/effect集中 | 変更影響が広くtest困難 | characterization後にfeature分割 | P2 | L | `frontend/app/page.tsx` | 不要 | なし |
| UX-023 | Frontend | 到達不能componentと未使用API client | 読解時に実装済みと誤認 | route/caller確認後に削除または接続を別PR化 | P2 | S | `frontend/app/page.tsx`, `frontend/lib/api.ts` | 不要 | なし |
| UX-024 | API型 | update payloadが`Partial<Applicant>` | read-only field送信を型で防げない | 専用payload型へ縮小 | P2 | S | `frontend/lib/api.ts`, `frontend/types/index.ts` | 不要 | なし |
| UX-025 | Navigation | hash文字列と表示名がroute識別子 | rename・deep link・testが脆い | 安定route keyと表示labelを分離 | P2 | M | `frontend/app/page.tsx` | 不要 | なし |
| UX-026 | Visual | 全カードの強さが同じ | 優先度を読み取りにくい | border中心、shadow限定、密度token | P2 | M | `frontend/app/globals.css` | 不要 | なし |
| UX-027 | Tests | Frontend testなし | UI回帰をtype/buildだけで検知できない | 純粋関数→component→flowの順で導入 | P2 | M | `frontend/package.json`, `frontend/` | 不要 | なし |
| UX-028 | Analytics | 期間・推移・母数・流入なし | 改善判断に使えない | 期間付きfunnelと定義済み指標 | P3 | L | `frontend/features/analytics`, `backend/main.py` | event設計に必要 | なし |
| UX-029 | Applicants | 保存view、担当者、bulk actionなし | 大規模運用の反復が多い | Auth後に担当者・保存filter・安全なbulk | P3 | L | Frontend/Backend新規 | 必要 | 必須 |
| UX-030 | Quality | E2E/visual regressionなし | responsive/見た目の回帰を検知しにくい | 合成fixtureで主要幅を自動撮影 | P3 | L | `frontend/e2e`, CI | 不要 | なし |

件数: **P0 3件 / P1 14件 / P2 10件 / P3 3件**。

## 12. Quick Win 上位10件

1. 手動LINE送信に宛先・本文の確認stepを追加する（UX-001のfrontend部分）。
2. 面接候補送信に候補日一覧の確認stepを追加し、失敗時は「未送信」と断定しない（UX-002のfrontend部分）。
3. ダッシュボードの未対応問い合わせ・面接調整・新規応募を条件付き画面へつなぐ。
4. 直近問い合わせをお問い合わせ画面へ遷移可能にする。
5. LINE履歴にloading / error / emptyと再試行を分けて表示する。
6. メモにdirty表示、保存成功、閉じる前確認を追加する。
7. 全interactiveへ`:focus-visible`を追加する。
8. Drawerへdialog semantics、Esc、focus復帰を追加する。
9. 応募者検索copyを実際の対象と一致させ、行全体を開けるようにする。
10. 各画面へ最終取得時刻とstale表示を追加する。

## 13. 未確認事項

- 375px / 768px / 1440pxの実render、browser keyboard操作、screen reader、contrast実測。
- 採用担当者によるtask completion時間、誤操作、用語理解、1日のデータ量。
- productionでの実response時間、同時更新、LINE送信失敗率、画面離脱率。
- company role、read-only企業、MFA、会社切替は純粋policyまでで、現在の管理画面へ未接続。
- 問い合わせstatusの正式な業務状態、担当者、返信完了条件。

これらは確認済みとして扱わず、最初の実装PR前に合成データのbrowser testと採用担当者レビューで検証する。
