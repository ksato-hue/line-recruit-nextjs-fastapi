# 管理画面 UIデザイン方向性

作成日: 2026-07-31

状態: 実装前の提案

関連: `docs/ADMIN_UX_AUDIT.md`, `docs/ADMIN_INFORMATION_ARCHITECTURE.md`

## 1. 現在のvisual baseline

**確認済み事実:** 現在は青灰background、白surface、青accent、LINE greenを使い、22px角丸と広いshadowのcardを主体とする。sidebarは260px fixed、contentは左margin 260pxである（`frontend/app/globals.css:1-14`, `frontend/app/globals.css:28-80`）。

**確認済み事実:** 780px以下でsidebarはpage上部の全幅blockになり、tableは最小幅980pxのまま横scrollする（`frontend/app/globals.css:100-103`, `frontend/app/globals.css:277-299`）。

**未確認:** Browser backendとlocal portを利用できなかったため、色、密度、長文、scroll、focusを実renderでは確認できていない。以下はcurrent codeと業務目的から作成した設計案であり、実装時のvisual QAが必要である。

## 2. 方向性A: 静かな業務ツール

- **Concept:** 長時間利用しても疲れにくく、情報階層を静かに読む。
- **色:** 白、neutral gray、濃紺text。色は状態とprimary actionへ限定。
- **余白/文字:** 8px基準、14〜16px本文、明確なheading。装飾的shadowを減らす。
- **Navigation:** desktop固定sidebar。active itemは背景と左borderで表示。
- **Dashboard:** compactなtask listとtable、KPIは補助領域。
- **応募者detail:** data denseなsection、履歴を読みやすくする。
- **Settings:** label/help/errorを規則的に縦配置。
- **メリット:** 信頼感、可読性、長時間利用、実装しやすさ。
- **デメリット:** 初心者への案内や緊急actionの強調が弱くなりやすい。
- **実装難易度:** 中。
- **相性:** 現在の青灰paletteを活かしやすい。

## 3. 方向性B: 柔らかい採用アシスタント

- **Concept:** 採用経験が浅い利用者へ次の操作と影響をやさしく案内する。
- **色:** warm neutral、soft blue/green。errorは明確なred。
- **余白/文字:** 余白を広くし、説明copyとempty stateを充実。
- **Navigation:** 業務stepを説明付きで表示。
- **Dashboard:** 「まず3件を確認しましょう」のようなguidanceを中心にする。
- **応募者detail:** 次の推奨actionを説明し、formをstep化する。
- **Settings:** previewとexampleを並べる。
- **メリット:** 初心者に優しく、空状態・設定の理解を支援。
- **デメリット:** data量が増えると説明が画面を占有し、熟練者には遅い。
- **実装難易度:** 中〜高。
- **相性:** 中小企業の採用初心者には高いが、毎日の高頻度操作には情報密度調整が必要。

## 4. 方向性C: 行動中心オペレーション画面

- **Concept:** 未対応と次のactionを最上位にし、対応漏れと処理時間を減らす。
- **色:** neutral surfaceを基準に、期限超過、未対応、成功、LINE送信へsemantic colorを使う。
- **余白/文字:** task listはcompact、detailは読みやすい中密度。
- **Navigation:** 日常業務と設定を分離したsidebar。
- **Dashboard:** KPIより要対応queueを上に置き、全itemを対象一覧へつなぐ。
- **応募者detail:** sticky action、履歴、送信確認、状態結果を中心にする。
- **Settings:** 日常業務から分離し、影響範囲と保存状態を強調。
- **メリット:** 対応漏れ防止、速度、朝の判断、業務完了の明確さ。
- **デメリット:** 優先度・期限・状態定義が曖昧だと誤誘導する。Backend集計の整備が必要。
- **実装難易度:** 高。Quick Win部分は中。
- **相性:** 本プロジェクトの「新着確認→対応→LINE/面接→完了」に最も合う。

## 5. 比較と採用方針

| 観点 | A | B | C |
|---|---:|---:|---:|
| 長時間の読みやすさ | ◎ | ○ | ○ |
| 初心者支援 | △ | ◎ | ○ |
| 対応漏れ防止 | ○ | ○ | ◎ |
| 高頻度操作 | ○ | △ | ◎ |
| 現行APIだけでの開始 | ◎ | ○ | ○ |
| Backend改善後の拡張 | ○ | ○ | ◎ |

**推奨は方向性C「行動中心オペレーション画面」**とする。ただしvisual languageはAの静けさを採用し、Bの説明copyはempty state、初回設定、危険操作だけへ限定する。つまり優先順位はC、見た目はA、案内は必要箇所だけBであり、3案を同率に混ぜない。

## 6. 推奨visual system

以下は実装時の初期token候補であり、実装PRでcontrastを測定して確定する。

### Color

| 用途 | 候補 | 使い方 |
|---|---|---|
| Page background | `#F6F8FA` | 全画面background |
| Surface | `#FFFFFF` | panel、table、form |
| Border | `#DDE3EA` | 通常の区切り |
| Primary text | `#172033` | heading、本文 |
| Secondary text | `#52606D` | 補足、metadata |
| Primary action | `#1D4ED8` | 保存、詳細、navigation active |
| LINE action | `#06C755` | LINE送信だけ |
| Warning | `#A15C00` / pale amber | 期限、read-only、未接続 |
| Danger | `#B42318` / pale red | 失敗、破棄、取消不能警告 |
| Success | `#067647` / pale green | 保存/送信成功 |

LINE greenを一般的な保存buttonへ使わず、「LINEへ送る」という意味を保持する。

### Typography

- Page title: 28px / 700。
- Section title: 20px / 700。
- Card title: 16px / 700。
- Body: 14〜16px / line-height 1.6。
- Metadata: 12〜13px。ただし重要説明を12pxだけにしない。
- Numeric metric: tabular numeralを使い、unitを隣接表示する。

### Spacing / Shape / Elevation

- Spacing scale: 4, 8, 12, 16, 24, 32px。
- Panel radius: 10〜12px。input/button: 8〜10px。
- Shadow: drawer、dialog、sticky barだけ。通常panelはborder中心。
- Touch target: mobileは最低44×44px。
- Content width: dashboardは最大1440px、settings formは720px前後。

### Status

- 色 + text + iconの3要素を許容し、色だけに依存しない。
- 「未対応」「対応中」「対応済み」「期限超過」は同じcomponent variantで表す。
- `new`, interview, applicant statusを色名へ直接結合せず、semantic tokenへmapする。

## 7. Component方針

最初に共通化するcomponent:

- `AdminShell`: desktop sidebar、mobile app bar/navigation sheet。
- `PageHeader`: title、description、updatedAt、refresh、stale。
- `ActionQueueItem`: priority、count、oldest age、destination。
- `StatusBadge`: text/icon/semantic color。
- `FeedbackBanner`: loading、partial、stale、error、success、read-only。
- `Drawer` / `Dialog`: focus、Esc、trap、label、restoreを共通化。
- `SendConfirmationDialog`: recipient summary、preview、cancel、confirm。
- `EmptyState`: 状態説明と次のaction。
- `StickySaveBar`: dirty、discard、save、saving、saved。

現在2回未満しか使わないform blockを先に抽象化しない。feature-specificなApplicant/FAQ/QuestionTreeのdata shapeは各featureに残す。

## 8. ASCII wireframe

### 8.1 Desktop: ホーム 1440px

```text
┌──────────────┬──────────────────────────────────────────────────────────┐
│ LINE採用      │ ホーム                           10:42更新  [再読み込み] │
│              ├──────────────────────────────────────────────────────────┤
│ ● ホーム      │ 要対応                                                   │
│   応募者      │ ┌未対応問い合わせ 4件 最古3時間───────[確認する]┐       │
│   問い合わせ  │ ├期限超過          2件 最古1日────────[確認する]┤       │
│   分析        │ ├面接調整中        3件────────────────[確認する]┤       │
│              │ └新規応募          5件────────────────[確認する]┘       │
│ 設定          ├──────────────────────────────────────────────────────────┤
│   会社情報    │ 現在の状況                                               │
│   応募フロー  │ [応募途中 12] [面接確定 8] [採用 3] [問い合わせ 24]       │
│   自動応答    ├──────────────────────────────────────────────────────────┤
│   通知        │ 累計ファネル              直近                           │
│              │ 開始 120 → 完了 72 (60%)  応募者 / 問い合わせ clickable │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### 8.2 Desktop: 応募者一覧 + detail

```text
┌──────────────┬────────────────────────────┬─────────────────────────────┐
│ Navigation   │ 応募者  126件              │ 応募者A    [×]              │
│              │ [検索____________] [状態▼] │ 新規応募 / 面接未設定         │
│              │ [要対応▼] [最終対応順▼]    ├─────────────────────────────┤
│              ├────────────────────────────┤ 概要 / 応募内容              │
│              │ ! 応募者A    新規  2時間前 │ 電話 / 職種 / 回答            │
│              │   応募者B    面接  昨日    ├─────────────────────────────┤
│              │   ...                      │ LINE履歴                       │
│              │                            │ 受信 ...                       │
│              │                            │ 送信 ...                       │
│              │                            ├─────────────────────────────┤
│              │                            │ [状態変更] [面接候補] [LINE]  │
└──────────────┴────────────────────────────┴─────────────────────────────┘
```

### 8.3 Desktop: 問い合わせ

```text
┌──────────────┬──────────────────────────┬───────────────────────────────┐
│ Navigation   │ 問い合わせ 未対応4件     │ 2026/07/31 09:30  [未対応▼]   │
│              │ [未対応] [対応中] [全件] │ 関連応募者: 応募者A   [開く] │
│              ├──────────────────────────┤                               │
│              │ ! 給与について... 3時間 │ 問い合わせ全文                │
│              │   面接日変更...    5時間 │ ...                           │
│              │   ...                    ├───────────────────────────────┤
│              │                          │ LINE履歴                       │
│              │                          │ ...                            │
│              │                          │ [返信を作成] [対応済みにする] │
└──────────────┴──────────────────────────┴───────────────────────────────┘
```

### 8.4 Desktop: 設定

```text
┌──────────────┬──────────────────────────────────────────────────────────┐
│ Navigation   │ 設定 > 応募フロー                                         │
│              ├──────────────┬───────────────────────────────────────────┤
│              │ 会社情報      │ 応募受付                                  │
│              │●応募フロー    │ [ON] OFF時は受付停止文面を返します        │
│              │ 自動応答      │                                           │
│              │ 通知          │ ステータス / 質問ツリー                    │
│              │              │ [preview]                                 │
│              ├──────────────┴───────────────────────────────────────────┤
│              │ 未保存の変更があります      [変更を破棄] [保存する]       │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### 8.5 Mobile: 応募者detail 375px

```text
┌───────────────────────────────┐
│ ‹ 応募者         応募者A      │
├───────────────────────────────┤
│ [新規応募] 最終対応 2時間前   │
│ 電話 / 職種 / 面接状況        │
├───────────────────────────────┤
│ 応募内容                      │
│ 長文は折返し、section単位表示 │
├───────────────────────────────┤
│ LINE履歴                      │
│ 受信 ...                      │
│ 送信 ...                      │
├───────────────────────────────┤
│ メモ / タグ / 面接            │
│                               │
├───────────────────────────────┤
│ [状態変更] [面接] [LINE送信]  │ ← sticky
└───────────────────────────────┘
```

## 9. Responsive詳細

- KPIはmobileで2列固定にせず、要対応を1列、補助metricを2列にする。
- tableはdesktopだけで使い、mobileはcard listへ切り替える。
- drawerはmobileではfull-screen routeとしてhistory/backを自然にする。
- sidebarは768px以下でoverlay sheetにし、現在page名をsticky app barへ表示する。
- settings form、LINE履歴、面接候補は1列。送信/保存actionはsticky bottom areaへ置く。
- 長文は`white-space: pre-wrap`, `overflow-wrap: anywhere`を使い、本文領域の最大高さだけで内容を隠さない。

## 10. Feedbackとmotion

- Loadingはlayout shiftを抑えるskeletonまたは固定領域を使う。
- Errorは対象領域に表示し、全pageを消さない。
- Successは短いstatusと保存時刻を残す。取消不能なLINE送信は履歴反映まで表示する。
- Toastだけに結果を依存せず、操作領域にも状態を残す。
- Animationは150〜200ms程度のopacity/transformに限定し、`prefers-reduced-motion`で停止する。

## 11. 実装時のvisual受入条件

1. 375px、768px、1440pxで横方向にpage全体がoverflowしない。table領域だけに限定したscrollはdesktop/tabletで許可する。
2. Keyboardだけでnavigation、応募者選択、drawer close、送信確認、保存を完遂できる。
3. Focusが常に視認でき、drawer/dialogはfocusを閉じ込め、閉じた後に起点へ戻す。
4. 状態は色以外のtext/iconでも判別できる。
5. 長い名前、長いメモ、5,000 UTF-16符号単位のLINE本文、多数statusでlayoutが崩れない。
6. Contrastは実装されたtokenで自動・手動検査する。現時点ではWCAG準拠を断定しない。
7. Screenshot fixtureへ実データ、LINE ID、email、secretを含めない。
