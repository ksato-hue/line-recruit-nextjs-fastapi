# LINE採用自動化：FastAPI + Next.js 構成

今の `main.py` で動いている LINE Bot / Supabase 連携を活かしながら、管理画面を Next.js に分離した構成です。

```text
backend/   FastAPI：LINE Webhook、Supabase API
frontend/  Next.js：管理画面UI
```

## 起動順

### 1. FastAPI

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

Supabase SQL Editorでマイグレーションを番号順に実行してから起動してください。

1. [`202607190001_mvp_security_foundation.sql`](supabase/migrations/202607190001_mvp_security_foundation.sql)
2. [`202607190002_admin_configuration.sql`](supabase/migrations/202607190002_admin_configuration.sql)
3. [`202607200001_application_sessions.sql`](supabase/migrations/202607200001_application_sessions.sql)

### 2. Next.js

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。

## 環境変数

### backend

| 変数 | 用途 |
|---|---|
| `SUPABASE_URL` | SupabaseプロジェクトURL |
| `SUPABASE_KEY` | backend専用のSupabaseキー。ブラウザへ公開しない |
| `LINE_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン |
| `LINE_CHANNEL_SECRET` | `X-Line-Signature`検証用のチャネルシークレット |
| `ADMIN_ORIGIN` | 許可する管理画面オリジン。例: `https://example.onrender.com` |
| `ADMIN_API_KEY` | Next.jsサーバーとの間で使う長くランダムな共有キー |
| `COMPANY_ID` | 現在の企業識別子。既存データは`default`を前提とする |
| `APPLICATION_DROPOUT_HOURS` | activeな応募セッションを離脱状態とみなす最終操作からの時間。既定値24 |

### frontend

| 変数 | 用途 |
|---|---|
| `BACKEND_API_BASE_URL` | Next.jsサーバーから接続するFastAPIのURL |
| `ADMIN_API_KEY` | backendと同一の共有キー。`NEXT_PUBLIC_`を付けない |
| `ADMIN_BASIC_USERNAME` | 管理画面のBasic認証ユーザー名 |
| `ADMIN_BASIC_PASSWORD` | 管理画面のBasic認証パスワード。十分に長いランダム値 |

`ADMIN_API_KEY`と`LINE_CHANNEL_SECRET`は未設定時に保護を無効化せず、対象リクエストを拒否します。ローカル設定は[`backend/.env.example`](backend/.env.example)と[`frontend/.env.local.example`](frontend/.env.local.example)を参照してください。

Renderのfrontendサービスには`BACKEND_API_BASE_URL`、`ADMIN_API_KEY`、`ADMIN_BASIC_USERNAME`、`ADMIN_BASIC_PASSWORD`を設定してください。Basic認証は管理画面HTMLと同一オリジンの`/api/admin/*`をサーバー側で保護し、認証情報をブラウザ保存領域へ書き込みません。将来はこの入口の認証層をSupabase Authのセッション検証へ置き換えられます。

## ドキュメント

- [要件定義](docs/requirements.md)
- [サービス構想](docs/concept.md)
- [MVPセキュリティ判断メモ](docs/security-decisions.md)

## 構成方針

- FastAPIはLINE BotとAPI提供に集中
- Next.jsは管理画面UIに集中
- Supabaseは既存の `applicants` / `inquiries` テーブルを維持し、マイグレーションで設定テーブルと`company_id`を追加
- 既存の `/webhook` は残してあります
- 管理画面のAPI通信はNext.jsサーバープロキシを経由し、管理キーをブラウザへ公開しない
- 既存の `/applicants-view` などのHTML画面も互換用に残していますが、管理APIキーが必要です

## 今回追加した安全対策

- LINE WebhookのHMAC-SHA256署名検証
- 管理APIのfail-closed共有キー認証
- Next.js管理プロキシのパス・メソッド許可リスト
- `ADMIN_ORIGIN`だけを許可するCORS
- 個人情報を標準出力へ出さないイベントログ
- ローカル環境ファイルと生成物のGit除外
- 設定テーブル、企業ID、インデックス、`updated_at`トリガーのマイグレーション

## 公開前に残る重要事項

- MVPでは管理画面入口をBasic認証で保護します。`ADMIN_API_KEY`は引き続きサーバー間認証専用です。正式運用ではSupabase Auth等による利用者別認証・認可へ移行します。
- RLSは認証方式と企業権限が未確定のため、今回有効化していません。
- `company_id`は追加済みですが、すべての業務クエリで企業境界を強制する完全なマルチテナント対応は未完了です。
- 応募途中状態は`application_sessions`へ永続化します。リマインド自動送信、包括的なWebhook冪等性、レート制限、監視・アラートは未実装です。
- 詳細は[MVPセキュリティ判断メモ](docs/security-decisions.md)を参照してください。

## 管理画面の設定

- トップレベルは「ダッシュボード」「応募者一覧」「お問い合わせ」「簡易分析」「設定」です。面接候補日の送信・確定状況の確認は応募者一覧と応募者詳細から行います。
- 設定配下で基本設定、企業別ステータス、FAQ、質問ツリー、リマインド・メッセージを管理します。
- ステータスの追加・名称変更・順序・有効状態はDBへ保存されます。使用中ステータスは削除できません。
- 定期送信ジョブは未接続です。既存のリマインド設定値は保持し、管理画面ではON/OFF・時間・テンプレート選択を読み取り専用で表示します。
- メッセージテンプレートと質問ツリーは保存後のLINE Bot処理で使用されます。
