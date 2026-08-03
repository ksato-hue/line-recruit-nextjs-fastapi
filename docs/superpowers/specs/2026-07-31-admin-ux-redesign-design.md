# 管理画面UX再設計 Design Spec

作成日: 2026-07-31

状態: 実装候補。production codeは未変更

参照: `docs/ADMIN_UX_AUDIT.md`, `docs/ADMIN_INFORMATION_ARCHITECTURE.md`, `docs/ADMIN_UI_DESIGN_DIRECTION.md`

## 1. 目的

採用担当者が説明なしで次を完遂できる管理画面へ段階的に移行する。

1. 新着応募、未対応問い合わせ、面接調整、期限超過を把握する。
2. 優先対象の一覧へ直接移動する。
3. 応募内容と対応履歴を確認する。
4. 状態、メモ、タグを更新する。
5. LINEと面接候補を誤送信せず送る。
6. 結果を確認し、対応漏れが解消したことを判断する。
7. 影響範囲を理解して設定を変更する。

## 2. 設計決定

- 基本方向は「行動中心オペレーション画面」とする。
- visualはneutral surface、border中心、控えめなshadowを使う。
- navigationは「日常業務」と「設定」を分離した左sidebarとする。
- mobileはnavigation sheet、card list、full-screen detailを使う。
- LINE送信と面接候補送信は必ず確認stepを通す。
- Error、empty、stale、partialを別状態として表示する。
- 現在のBasic認証と管理APIキー境界はAuth移行phaseまで維持する。
- 権限、企業状態、MFAの正式判定はBackendを正とし、Frontendへ同じpolicyを複製しない。
- 自動リマインド、Supabase Auth、RLS、会社切替は接続済みと表示しない。

## 3. 非対象

- 本specの文書作成時点でFrontend/Backend/CSS/API/DBを変更しない。
- Auth/RLS、migration、scheduler、LINE retry/idempotencyをUX変更へ混ぜない。
- 旧FAQ API廃止、`main.py` router分割、design system全体の構築は別作業とする。
- 高度な分析、担当者割当、bulk updateは基礎導線の完了後に行う。

## 4. Screen contract

### 4.1 Home

#### Layout order

1. `PageHeader`: page名、最終成功取得時刻、refresh、stale/partial。
2. `ActionQueue`: 未対応問い合わせ、期限超過session、面接調整中、新規応募。
3. `CurrentSnapshot`: 現在状態のsummary。
4. `ApplicationFunnel`: 応募開始、完了、率。期間未実装時は全て「累計」。
5. `RecentActivity`: 応募者と問い合わせのclickable list。
6. `MetricDefinition`: 折りたたみ可能な定義説明。

#### Action queue behavior

| Item | Destination | Initial filter |
|---|---|---|
| 未対応問い合わせ | 問い合わせ | status=`未対応`または未設定 |
| 期限超過 | 応募session一覧または応募者一覧 | activeかつthreshold超過 |
| 面接調整中 | 応募者 | interview status=`面接調整中` |
| 新規応募 | 応募者 | applicant statusの`new`対応名 |

期限超過の対象一覧APIがない期間は、そのitemをclickableに見せず「対象一覧は未接続」と表示する。countだけをactionに見せない。

#### Acceptance

- 利用者が最初のviewportで要対応件数を確認できる。
- Action itemはdestinationが存在する場合だけbutton/linkになる。
- 0件時は「現在、要対応はありません」と表示する。
- Countに現在/累計/期間labelがある。
- Refresh失敗時は直前dataを残し、stale表示と再試行を出す。

### 4.2 Applicants

#### List

- Search対象をUI copyと一致させる。
- Filterはstatus、interview status、要対応を独立させる。
- Sortは最終対応の古い順、新しい順、登録日時順を提供する。最終対応fieldが未接続の期間は登録日時順だけを提供する。
- Desktopはrow全体をbutton相当にし、detail openを1clickにする。
- Selected rowを`aria-current`または同等のtext/styleで示す。
- Mobileは名前、status、要対応、最終対応をcardへ表示する。

#### Detail sections

1. Summary: name、status、job、面接、最終対応。
2. Application: phone、応募内容、登録日時。任意回答の構造化dataがない期間は`motivation`を「応募内容」としてpre-wrap表示する。
3. Activity: LINE履歴。loading/error/emptyを分離する。
4. Notes: memo、tags、保存状態。
5. Interview: 現在status、候補、送信action。
6. Sticky actions: status、面接、LINE。

#### Manual LINE send

1. Composerで本文を入力する。
2. 5000 UTF-16符号単位のcounterを表示し、Backendと同じ境界で送信buttonを制御する。
3. Confirm dialogに応募者表示名、本文、取消不能を表示する。raw LINE user IDは表示しない。
4. Confirmで1回だけrequestを送る。request中はconfirm、close、対象切替を無効にする。
5. Success時は履歴を再取得し、送信結果を操作領域へ残す。
6. Network errorで送信成否が不明な場合は自動再送しない。

Backendのidempotencyがないため、Frontend制御だけで厳密な一回送信を保証したとは表現しない。

#### Interview send

1. 面接種別と2〜5件の日時を入力する。
2. Confirm dialogでJST表記、候補順、宛先表示名を確認する。
3. Success時はapplicant status、候補、LINE履歴を再取得する。
4. Partial failureをBackendが表現できるまで、失敗copyでDB未更新やLINE未送信を断定しない。
5. Backend側の原子的処理または冪等性は別PRで先に契約testを追加する。

#### Acceptance

- Search結果からdetail、status更新、memo保存、LINE送信確認までkeyboardだけで完遂できる。
- Drawer/dialogはname、Esc、focus trap、focus restoreを持つ。
- 未保存memoを閉じると確認が出る。
- API failureをemptyに変換しない。
- LINE/面接の確認前に外部送信requestが発生しない。

### 4.3 Inquiries

#### Layout

- Desktop: 左40% list、右60% detail。
- Tablet: compact list + overlay detail。
- Mobile: list routeとdetail routeを分ける。

#### List

- Initial filterは未対応。
- Row/cardはstatus、受信日時、経過時間、本文冒頭、関連応募者有無を表示する。
- 未対応件数をheading横へ表示する。

#### Detail

- 全文、status、受信日時、関連応募者summary、LINE履歴を表示する。
- Status変更はBackendが許可する正式status setを共有する。現在の自由文字列PATCHへUI独自enumだけを接続しない。
- 関連応募者は企業scope済みBackend responseで確認する。Frontendが`line_user_id`だけで別datasetを結合しない。
- 返信はManual LINE sendと同じconfirm componentを使う。

#### Acceptance

- 一覧から詳細、状態更新、関連応募者、返信へ移動できる。
- 他社または関連なしの応募者存在を推測表示しない。
- Status save成功後、list countとDashboard countが更新される。
- 返信成功とstatus更新の順序が定義され、partial failure時の表示がBackend responseと一致する。

### 4.4 Analytics

- 現在の重複指標はHomeへ移す。
- 独立Analytics screenはserver-side aggregate、期間、母数、metric definitionが揃うまでprimary navから外す案を採用する。
- 独立screen再導入時は期間を必須にし、Dashboardと同じaggregate sourceを使う。
- Clientへ取得したpage内のapplicantだけで全体件数を算出しない。

### 4.5 Settings

#### Category

- Auth前: 会社情報、応募フロー、自動応答、通知・リマインド。
- Auth後: メンバー・権限、セキュリティ、会社・契約。
- 実装されていないcategoryは表示しない。

#### Common behavior

- Headerに保存単位、反映先、最終保存時刻を表示する。
- Dirty時はsticky save barを出し、保存、変更破棄、未保存状態を示す。
- Page navigation、Browser back、drawer openによるdraft損失を防ぐ。
- Save中は対象formとnavigation破棄actionを制御する。
- Validation errorはfieldへ関連付け、最初のerrorへfocusを移す。

#### Specific behavior

- 応募受付OFF: LINE応募が停止する影響と返却messageをpreviewする。
- Status rename/delete: 使用中件数またはBackend拒否結果を表示する。
- FAQ: 回答、公開状態、LINE previewを同じcardに表示する。
- Question tree: 質問順、形式、必須、選択肢をLINE previewへ反映する。
- Reminder: 「自動送信未接続」を維持し、保存が配信開始を意味しないと明示する。

## 5. Global states

全screen/componentは次の状態を明示的に扱う。

- `initial`
- `loading`
- `success`
- `empty`
- `partial`
- `stale`
- `validation_error`
- `network_error`
- `permission_denied`
- `read_only`
- `saving`
- `saved`
- `send_confirmation`
- `send_success`
- `send_failure`

State messageへsecret、raw LINE ID、email、message本文をlog用reasonとして含めない。

## 6. Accessibility contract

- 全interactiveはnative elementを優先する。
- 全form controlはaccessible nameを持つ。
- `:focus-visible`を削除しない。
- Dialog/Drawerは`role=dialog`, `aria-modal`, labelled title, Esc, focus trap, focus restoreを持つ。
- Loading/Success/Errorは適切なlive regionで通知する。
- Statusは色だけで区別しない。
- Mobile action targetは44×44px以上。
- Heading順序をpage titleからsection titleへ連続させる。
- 実装PRはkeyboard操作とname/role/valueを手動確認する。現時点でWCAG完全準拠とは表現しない。

## 7. Responsive contract

- 1440px: fixed sidebar、action queue、applicant/inquiry split view。
- 768px: overlay navigation、優先列list、overlay detail。
- 375px: sticky app bar、card list、full-screen detail、sticky action。
- 長い名前、memo、LINE本文、FAQ回答はcontainer外へはみ出さない。
- Page全体のhorizontal overflowを禁止し、必要なtable scrollはcomponent内部だけに限定する。

## 8. API/UI boundary

### 現在利用可能

- Dashboard、Applicants、Applicant update、Interview create、LINE send/log、Inquiries list/detail/update、Settings、Status、FAQ settings、Question tree（`frontend/lib/api.ts:32-143`, `backend/main.py:1734-2456`）。

### UIだけで先行可能

- Send confirm、action link、feedback semantics、focus、memo dirty guard、responsive navigation、component分割。

### Backend契約変更が必要

- Application session対象一覧。
- Applicant server search/filter/sort/page、`last_contact_at`。
- Inquiry正式status set、関連応募者summary、返信とstatusの整合。
- Interview partial result/idempotency。
- Dashboard period aggregateと更新時刻。
- LINE log障害を空配列と区別するerror response。

### DB/Auth依存

- 構造化した応募回答snapshot。
- 担当者割当、member、role、company switch、audit。
- 可変reminder送信履歴。

## 9. Security and privacy

- Basic認証と`ADMIN_API_KEY`の境界をAuth移行まで維持する。
- 管理APIキーをbrowser bundle、client env、error messageへ含めない。
- Screenshot/test fixtureへ実名、電話、LINE ID、問い合わせ本文、emailを含めない。
- UIでactionを非表示にしても認可完了とは扱わず、Backend/RLSで同じ操作を拒否する。
- Manual LINE validationは既存Pydantic modelを維持する（`backend/line_send_validation.py`）。
- `COMPANY_ID`固定を本番multi-tenant実装済みと表現しない。

## 10. Test strategy

### Minimum

1. 純粋関数: filter、sort、metric label、UTF-16 counter。
2. Component: FeedbackBanner、Dialog、Drawer、Send confirmation。
3. API client: request method/path/body、401/403/422/5xx、stale behavior。
4. User flow: Dashboard→filtered list→detail、manual send confirm、settings dirty guard。

### Extended

5. E2E: 375/768/1440、keyboard、back navigation、API error、long content、many rows/statuses。
6. Visual regression: synthetic fixtureだけを使用。
7. Accessibility: automated scan + keyboard/screen reader smoke test。

Frontend test基盤の依存追加は実装計画の最初の独立PRで行い、本spec作成では変更しない。

## 11. Rollout and rollback

- Feature単位のsmall PRで導入し、API契約変更とvisual refactorを同一PRへ混ぜない。
- Characterization testを追加してから`page.tsx`を分割する。
- Hash navigationはcomponent split完了まで維持する。
- 各PRは直前のroute/componentを残したままtest greenにし、切替commitを小さくする。
- Rollbackは該当PRのrevertで行えるよう、migrationを伴う変更を別PRにする。
- Auth/RLS前のUIは既存Basic/API key経路を維持し、Auth phaseで明示的に切り替える。

## 12. 完了判定

- AuditのP0がBackend依存を含め解消または正式なguardで隔離される。
- 朝の確認から対象処理まで再検索なしで到達できる。
- Manual LINEと面接候補が確認前に送信されない。
- Inquiryを一覧から対応済みまで処理できる。
- Mobileで応募者検索、detail、status、LINE送信を完遂できる。
- Error/empty/stale/partialを区別できる。
- Keyboard、typecheck、build、Frontend test、Backend regressionが成功する。
- Auth未接続機能をoperationalと表示しない。
