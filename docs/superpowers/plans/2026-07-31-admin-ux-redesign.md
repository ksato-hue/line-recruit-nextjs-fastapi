# Admin UX Redesign Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan one task at a time. Use `superpowers:test-driven-development` for behavior changes and `superpowers:verification-before-completion` before each commit.

**Goal:** 採用担当者が要対応を発見し、応募者・問い合わせを安全に処理できる行動中心の管理画面へ、小さいPRで段階移行する。

**Architecture:** 現在のNext.js BFFとFastAPI JSON API境界を維持する。Frontendはfeature単位へ分割し、overlay/feedback等の小さい共通componentだけを共有する。API/DB/Auth変更が必要な機能はFrontend-only変更と分離し、Backendの企業scopeと認可を正とする。

**Tech Stack:** Next.js 14.2.35、React 18.3.1、TypeScript 5.9.3、FastAPI 0.139.2、Python 3.12.10、標準`unittest`。Frontend test runnerはTask 1で独立導入し、versionは実装時のlockfile互換性と公式supportを確認してexact pinする。

**Design sources:**

- `docs/ADMIN_UX_AUDIT.md`
- `docs/ADMIN_INFORMATION_ARCHITECTURE.md`
- `docs/ADMIN_UI_DESIGN_DIRECTION.md`
- `docs/superpowers/specs/2026-07-31-admin-ux-redesign-design.md`

## Dependency graph

```text
Task 1 Frontend test foundation
  ├─ Task 2 feedback/focus/overlay safety
  │    ├─ Task 3 Dashboard Quick Win
  │    └─ Task 4 Applicant send safety
  └─ Task 5 characterization + feature split
         ├─ Task 6 responsive navigation/list/detail
         ├─ Task 7 inquiry workflow + API contract
         ├─ Task 8 applicant data/API improvements
         └─ Task 9 analytics consolidation

Task 10 Auth/RLS-aware UX depends on auth foundation and RLS implementation
```

Task 2〜4は同一phaseでも別PRにする。Task 7〜9はAPIごとにBackend testを先行し、DB migrationが必要な部分をさらに分離する。

## Phase 1: Frontendだけで可能なQuick Win（1〜2日）

### Task 1: Frontend test foundationと現行behavior固定

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/app/__tests__/admin-page.characterization.test.tsx`
- Create: `frontend/components/ui/__tests__/test-fixtures.ts`

**Tests first:**

1. Dashboard、応募者、問い合わせ、設定のnavigation labelが表示される。
2. Dashboardの直近応募者からdetailが開く。
3. 応募者detailのstatusは明示保存までAPIを呼ばない。
4. 設定dirty時の画面移動で確認dialogが出る。
5. APIは全て合成responseでmockし、Supabase/LINE/productionへ接続しない。

**Implementation:**

- Vitest、jsdom、React Testing Library、user-eventの必要最小限だけをexact pinする。
- `npm test`または`npm run test:unit`を追加し、CI変更は別commitにする。
- 現行`page.tsx`を変更せずcharacterization testをgreenにする。

**Verification:**

```bash
cd frontend
npm ci
npm run test:unit
npm run typecheck
npm run build
```

**Completion:** 現行nav、detail、status、dirty guardをtestが保護し、production secret参照がない。

### Task 2: Focus、feedback、accessible overlay

**Files:**

- Create: `frontend/components/ui/FeedbackBanner.tsx`
- Create: `frontend/components/ui/Dialog.tsx`
- Create: `frontend/components/ui/Drawer.tsx`
- Create: `frontend/components/ui/__tests__/FeedbackBanner.test.tsx`
- Create: `frontend/components/ui/__tests__/Dialog.test.tsx`
- Create: `frontend/components/ui/__tests__/Drawer.test.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`

**Tests first:**

1. Dialog/Drawerがaccessible name、`aria-modal`を持つ。
2. Escで閉じ、閉じた後に起点へfocusが戻る。
3. Tabがopen overlay内へ留まる。
4. Error/Success/Loadingが適切なlive regionを持つ。
5. Drawer close buttonに「応募者詳細を閉じる」のnameがある。

**Implementation:**

- 現在の未保存dialogと応募者drawerを共通primitiveへ置換する。
- `outline: none`だけの定義を廃止し、`:focus-visible` ringを追加する。
- mini/close buttonのmobile targetを44pxへする。

**Verification:** Task 1のcommandに加え、keyboardでopen/close/tab順を手動確認する。

**Completion:** 対象overlayのrole/name/value/focus lifecycleがtestと手動確認を通る。

### Task 3: Dashboardをactionableにする

**Files:**

- Create: `frontend/features/dashboard/dashboardPresentation.ts`
- Create: `frontend/features/dashboard/DashboardView.tsx`
- Create: `frontend/features/dashboard/__tests__/dashboardPresentation.test.ts`
- Create: `frontend/features/dashboard/__tests__/DashboardView.test.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`

**Tests first:**

1. 未対応問い合わせ、面接調整、新規応募がdestination付きactionになる。
2. 離脱一覧routeが未接続ならlinkとしてrenderしない。
3. 0件時は「現在、要対応はありません」。
4. KPIに「累計」または「現在」が表示される。
5. 直近問い合わせがお問い合わせへ遷移する。

**Implementation:**

- Existing `dashboard.new_count`を使い、新規応募を表示する。
- 現在のhash navigationを維持し、filter intentだけをstateへ渡す。
- 7枚KPIを要対応queueの下へ移し、現在/累計を明示する。
- Dashboard APIは変更しない。

**Verification:** unit/component test、typecheck、build、375/768/1440 synthetic fixture目視。

**Completion:** Action可能なitemだけがbutton/linkで、destinationへ1操作で移動する。

### Task 4: Manual LINE/面接送信の確認とdraft保護

**Files:**

- Create: `frontend/components/ui/SendConfirmationDialog.tsx`
- Create: `frontend/components/ui/__tests__/SendConfirmationDialog.test.tsx`
- Create: `frontend/features/applicants/ApplicantActions.tsx`
- Create: `frontend/features/applicants/__tests__/ApplicantActions.test.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`

**Tests first:**

1. Composer入力だけでは`sendLineMessage`を呼ばない。
2. 確認dialogが宛先表示名、本文、取消不能copyを表示する。
3. Confirm 1回でrequest 1回、送信中の再clickで追加request 0回。
4. 5000 UTF-16符号単位は許可し、5001はconfirmへ進まない。
5. 面接候補は2〜5件を確認dialogへJST表示する。
6. Network errorで自動再送しない。
7. Memo draftがある状態でdrawer closeすると確認が出る。

**Implementation:**

- Backend request/response契約を変えず、確認stepだけを追加する。
- UTF-16 helperは純粋関数としてtestする。
- Success後にLINE履歴を再取得する。履歴取得失敗は送信失敗と混同しない。
- 面接APIのpartial persistenceは解消済みと表現せず、unknown copyを使う。

**Verification:** Frontend test/typecheck/buildに加え、既存Backend 288件以上を実行する。

**Completion:** 確認前の送信0件、二重click 0件、draft loss guardがtestで固定される。

## Phase 2: 情報設計とcomponent分割（数日）

### Task 5: `page.tsx`のfeature分割

**Files:**

- Create: `frontend/components/layout/AdminShell.tsx`
- Create: `frontend/hooks/useAdminNavigation.ts`
- Create: `frontend/hooks/useUnsavedChanges.ts`
- Create: `frontend/features/applicants/ApplicantsView.tsx`
- Create: `frontend/features/applicants/ApplicantDetail.tsx`
- Create: `frontend/features/inquiries/InquiriesView.tsx`
- Create: `frontend/features/settings/GeneralSettings.tsx`
- Create: `frontend/features/settings/StatusSettings.tsx`
- Create: `frontend/features/settings/FAQSettings.tsx`
- Create: `frontend/features/settings/QuestionTreeSettings.tsx`
- Create: `frontend/features/settings/ReminderSettings.tsx`
- Create: `frontend/features/analytics/AnalyticsView.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/types/index.ts`
- Delete after caller check: unreachable `HistoryView` and `InterviewDateSettings` definitions from `frontend/app/page.tsx`

**Tests first:**

- Task 1〜4のcharacterization testをそのまま実行し、split前後でDOM上の主要labelとAPI callが変わらないことを確認する。
- `useAdminNavigation`へback/forward、dirty guard、stable route keyの純粋testを追加する。

**Implementation:**

- 1 featureずつextractし、各extract後にtestを実行する。
- API callはfeature hookまたはpage orchestrationに残し、抽象data layerを同時導入しない。
- 日本語labelとstable route keyを分離する。App Router分割は次Taskに残す。
- 未使用API exportはrepo callerを再検索し、別commitで削除する。

**Verification:** Frontend全test、typecheck、build、`git diff --check`。

**Completion:** `page.tsx`はshell/orchestration中心となり、各featureが独立test可能になる。

### Task 6: Responsive navigation、list、detail

**Files:**

- Modify: `frontend/components/layout/AdminShell.tsx`
- Modify: `frontend/features/applicants/ApplicantsView.tsx`
- Modify: `frontend/features/applicants/ApplicantDetail.tsx`
- Modify: `frontend/app/globals.css`
- Create: `frontend/components/layout/__tests__/AdminShell.test.tsx`
- Modify/Create: applicant responsive component tests

**Tests first:**

1. Mobile navigationはbuttonで開閉し、選択後に閉じる。
2. Desktop tableとmobile cardは同じapplicant actionを提供する。
3. Mobile detailにstatus/面接/LINE sticky actionがある。
4. Long name、memo、LINE本文がaccessible textとして保持される。

**Implementation:** 1440/768/375のcontractに従い、page全体のhorizontal overflowを除去する。Table data自体は変更しない。

**Verification:** component test、3幅E2E/manual、keyboard、typecheck、build。

**Completion:** 3幅で主要flowが完遂し、PIIを含まないscreenshotだけを検証artifactに使う。

## Phase 3: API接続を伴う機能改善

### Task 7: 問い合わせdetail・status・返信

**Files:**

- Modify: `backend/main.py`
- Create: `backend/tests/test_inquiry_workflow.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/types/index.ts`
- Modify: `frontend/features/inquiries/InquiriesView.tsx`
- Create: `frontend/features/inquiries/InquiryDetail.tsx`
- Create: `frontend/features/inquiries/__tests__/InquiryDetail.test.tsx`
- Modify: `docs/requirements.md`

**Backend failing tests first:**

1. 正式status以外を400で拒否する。
2. Detail responseの関連応募者は同一companyだけ。
3. 他社問い合わせ/応募者の存在を404またはnullで隠す。
4. Update実queryに`company_id`がある。
5. 返信とstatus更新のpartial failure契約を固定する。

**Frontend failing tests first:**

1. 未対応filter→detail→status更新。
2. 関連応募者がない場合に存在を推測しない。
3. 返信はTask 4の確認componentを通る。
4. Successでlist/dashboard countをrefreshする。

**Implementation:** `updateInquiry`と必要なdetail型を追加し、Desktop split/Mobile routeを接続する。DB schema追加が必要ならBackend契約PRとmigration PRを分離する。

**Verification:** Backend unittest/compileall、Frontend test/typecheck/build、企業境界test、`git diff --check`。

**Completion:** 問い合わせを一覧から対応済みまで処理でき、他社情報を表示/更新しない。

### Task 8: Applicantsのserver query、last contact、tags

**Files:**

- Modify: `backend/main.py`
- Create: `backend/tests/test_applicant_query_contract.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/types/index.ts`
- Modify: `frontend/features/applicants/ApplicantsView.tsx`
- Modify: `frontend/features/applicants/ApplicantDetail.tsx`
- Create if schema reconciliation and staging replay are approved: `supabase/migrations/202608010001_applicant_activity_fields.sql`
- Update: `docs/SUPABASE_COMPANY_SCOPE.md`

**Tests first:**

1. Search/filter/sort/pageの全queryがcompany scopeを持つ。
2. Same filterで他社applicantを返さない。
3. `last_contact_at`の定義とNULL順序を固定する。
4. Tags update payloadは`tags`だけを型付けし、他社updateは404。
5. Page metadataとresult countが一致する。

**Implementation:** Query parameter、pagination metadata、last-contact定義をBackendで実装する。Migrationはstaging replayとRLS方針が承認された場合だけ作成・適用する。

**Completion:** 多件数でも一覧の検索・優先順が正しく、全queryが企業境界testを通る。

### Task 9: Dashboard/Analytics集計の一本化

**Files:**

- Modify: `backend/main.py`
- Create: `backend/tests/test_dashboard_metric_contract.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/types/index.ts`
- Modify: `frontend/features/dashboard/DashboardView.tsx`
- Delete: `frontend/features/analytics/AnalyticsView.tsx`
- Modify: `frontend/components/layout/AdminShell.tsx`
- Update: `docs/requirements.md`

**Tests first:**

1. 各metricの期間、母数、company scopeを固定する。
2. 0母数は`null` rateとする。
3. Frontend page sizeに依存せずserver aggregateを表示する。
4. DashboardとAnalyticsの同名metricが同じ値・定義を使う。

**Implementation:** 最初は重複AnalyticsをHomeへ統合する。独立screenは期間・推移が揃った後にserver aggregateだけで再導入する。

**Completion:** Client-side全件集計を廃止し、metric definitionが画面と文書で一致する。

## Phase 4: Auth・RLS後のUX

### Task 10: login、MFA、company、role、read-only

**Dependencies:** `docs/superpowers/plans/2026-07-23-supabase-auth-rbac-mfa-implementation.md`のDB/Auth/RLS phaseがstagingで完了し、Backendがsession/capabilityを返せること。

**Files:**

- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/auth/callback/route.ts`
- Create: `frontend/components/auth/MfaChallenge.tsx`
- Create: `frontend/components/layout/CompanySwitcher.tsx`
- Create: `frontend/features/settings/MembersSettings.tsx`
- Create: `frontend/features/settings/SecuritySettings.tsx`
- Create: `frontend/features/admin/PlatformAdminShell.tsx`
- Modify: `frontend/middleware.ts`
- Modify: `frontend/components/layout/AdminShell.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: Backend auth dependency files defined by the Auth implementation plan
- Create/Modify: corresponding Backend and Frontend tests

**Tests first:**

1. `aal1`はMFA challengeへ進み、企業dataを取得しない。
2. pending/suspended membershipは業務画面を表示しない。
3. `monitor_expired`/保持期間内`closed`はread-only、`suspended`は拒否。
4. memberは設定update/member/CSV actionを実行できない。
5. platform adminはtenant業務dataを取得できない。
6. 会社切替後、旧company dataをcache/画面へ残さない。

**Implementation:** `backend/authz_policy.py`のdecisionをBackend dependency/RLSへ接続し、Frontendはserver capabilityを表示へ変換する。Basic/Auth併存と撤去は正式Auth計画に従う。

**Completion:** Role、company、AAL、membershipの全境界をBackend/RLS/E2Eで固定し、Frontendの非表示だけに依存しない。

## Small PR sequence

1. `test(frontend): characterize critical admin flows`
2. `fix(ui): add accessible feedback and overlays`
3. `feat(ui): make dashboard actions navigable`
4. `security: confirm admin LINE and interview sends`
5. `refactor(frontend): split admin features`
6. `feat(ui): improve responsive admin navigation`
7. `feat(inquiries): add detail and response workflow`
8. `feat(applicants): add scoped query and activity context`
9. `feat(analytics): unify admin metrics`
10. Auth/RLSの正式計画に沿った複数PR

## Common verification for every PR

```bash
python -m pip check
python -m compileall backend
cd backend
python -m unittest discover -s tests -p "test_*.py" -v

cd ../frontend
npm ci
npm run test:unit
npm run typecheck
npm run build

cd ..
git diff --check
git status
```

Frontend test scriptが導入される前のTask 1だけは、test runner install後に同じPR内で`npm run test:unit`を実行する。External API、Supabase production/staging、LINE APIへ接続しないfixtureを使う。

## Rollback

- 各small PRを独立revertできるようにする。
- Frontend component splitとAPI behavior changeを同一PRにしない。
- MigrationはUI/API PRと分離し、staging replay、backup、rollback SQLを準備してから扱う。
- Hash navigationはApp Router route移行がE2E greenになるまで保持する。
- Auth切替はBasic併存期間を設け、正式Auth計画のcutover/rollbackを使用する。

## Plan completion criteria

- P0の誤送信・部分結果・権限境界がそれぞれtest可能な層で保護される。
- Dashboardから主要対象へ再検索なしで到達する。
- ApplicantとInquiryの主要flowがPC/mobile/keyboardで完遂する。
- Error、empty、partial、stale、permission、read-onlyが区別される。
- Frontendの大規模分割前にcharacterization testがある。
- Backend企業境界testを削除・弱体化しない。
- production secret、DB接続、LINE APIをtest/CIで要求しない。
