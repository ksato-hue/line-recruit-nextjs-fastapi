# Legacy Admin HTML Removal Plan

**Goal:** FastAPIに残る未使用の管理用HTML 3画面を削除し、DB由来文字列の未エスケープ出力による保存型XSS経路と、Next.js管理画面との重複をなくす。

**Architecture:** Next.js管理画面を唯一の管理UIとして維持し、ブラウザからの管理操作は既存のNext.js Route Handlerを通してFastAPIの `/api/*` JSON APIへ送る。FastAPIからは対象HTMLルートと、そのルート内だけに存在するHTML・CSS・リンク生成を削除する。JSON API、Webhook、企業スコープ、認証境界、Supabase共通処理には触れない。

## 削除理由

- `/applicants-view`、`/applicant/{applicant_id}`、`/inquiries-view` は現在のNext.js管理画面と機能が重複している。
- リポジトリ内の本番コード、Next.js、README、テストを検索した結果、対象ルートを呼び出す現行UI、リダイレクト、health checkは確認できなかった。
- 対象ルートは応募者名、電話番号、志望動機、メモ、問い合わせ本文などのDB由来文字列をHTMLへ直接挿入している。HTMLエスケープ処理がないため、保存型XSSの攻撃面になる。
- 配備済み環境の外部ブックマークや直接アクセスの有無はリポジトリからは確認不能だが、プロジェクト要件としてNext.js管理画面への移行完了が確認されたため削除する。

## 削除対象

- `backend/main.py`
  - GET `/applicants-view`
  - GET `/applicant/{applicant_id}`
  - GET `/inquiries-view`
  - 上記3ルート内だけで使うHTML、CSS、JavaScript、リンク、集計・表示コード
  - 他のレスポンスで使われていない `HTMLResponse` import
- `backend/tests/test_legacy_routes_tenant_scope.py`
  - 旧HTMLが表示できることを期待するテストを、URL非公開を固定するセキュリティ回帰テストへ置換する。

## 削除対象外

- `/applicants` の互換JSONルート
- `/api/applicants` と `/api/applicants/{applicant_id}`
- `/api/inquiries` と `/api/inquiries/{inquiry_id}`
- `/api/health`
- `/webhook`
- 応募者・問い合わせモデル、面接候補日、LINE送受信、FAQ処理
- Supabaseアクセス、`company_id` 条件、Basic認証、`ADMIN_API_KEY`
- Next.js管理画面、BFF Route Handler、APIクライアント
- `backend/authz_policy.py` と認証設計

## 実装手順

1. 削除前のFastAPIルート一覧を記録する。
2. 有効な管理APIキーで対象3 URLをGETして404を要求するテストを追加する。
3. 削除前には3テストが200応答を理由に失敗し、JSON API、health、Webhook確認は成功することを確認する。
4. `backend/main.py` から対象3ルートの連続した専用コードだけを削除する。
5. 旧HTML表示を期待する既存テストを削除し、404、JSON API、health、Webhook、管理API認証境界を固定する回帰テストへ整理する。
6. READMEと監査文書に残る現行互換画面の記述だけを更新する。履歴用の過去計画は変更しない。
7. 削除前後のFastAPIルート集合を機械比較し、対象3ルート以外の差分がないことを確認する。

## テスト方法

```powershell
cd backend
python -m unittest tests.test_legacy_routes_tenant_scope.LegacyAdminHtmlRemovalTests -v
python -m unittest discover -s tests -v
cd ..
python -c "import ast, pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8')); print('Python AST: OK')"
cd frontend
npm exec tsc -- --noEmit --incremental false
npm run build
cd ..
git diff --check
git status --short
```

追加の静的確認:

- 対象3ルートがFastAPI route一覧から消えている。
- `/api/applicants`、`/api/inquiries`、`/api/health`、`/webhook` が残っている。
- `HTMLResponse` と対象URLへの本番コード内リンクが残っていない。
- `origin/main` のルート集合との差分が対象3ルートだけである。
- JSON APIの関数本体と管理API依存関係に差分がない。

## ロールバック

- 本変更の単一コミットを通常のrevertで戻す。
- 緊急時に旧画面を戻す場合も、未エスケープHTMLをそのまま再公開せず、先に出力エスケープまたはテンプレートの自動エスケープを導入してから復元する。
- Supabase、migration、環境変数、外部サービス設定を変更しないため、DBや外部設定のロールバックは不要。
