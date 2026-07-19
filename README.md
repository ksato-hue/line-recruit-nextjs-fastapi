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

Supabase SQL Editorで[`supabase/migrations/202607190001_mvp_security_foundation.sql`](supabase/migrations/202607190001_mvp_security_foundation.sql)を実行してから起動してください。

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

### frontend

| 変数 | 用途 |
|---|---|
| `BACKEND_API_BASE_URL` | Next.jsサーバーから接続するFastAPIのURL |
| `ADMIN_API_KEY` | backendと同一の共有キー。`NEXT_PUBLIC_`を付けない |

`ADMIN_API_KEY`と`LINE_CHANNEL_SECRET`は未設定時に保護を無効化せず、対象リクエストを拒否します。ローカル設定は[`backend/.env.example`](backend/.env.example)と[`frontend/.env.local.example`](frontend/.env.local.example)を参照してください。

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

- `ADMIN_API_KEY`はサーバー間認証であり、採用担当者のログイン機能ではありません。正式公開前に利用者認証・認可が必要です。
- RLSは認証方式と企業権限が未確定のため、今回有効化していません。
- `company_id`は追加済みですが、すべての業務クエリで企業境界を強制する完全なマルチテナント対応は未完了です。
- 応募途中状態のDB永続化、Webhook冪等性、レート制限、監視・アラートは未実装です。
- 詳細は[MVPセキュリティ判断メモ](docs/security-decisions.md)を参照してください。
