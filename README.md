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

### 2. Next.js

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。

## ドキュメント

- [要件定義](docs/requirements.md)
- [サービス構想](docs/concept.md)

## 構成方針

- FastAPIはLINE BotとAPI提供に集中
- Next.jsは管理画面UIに集中
- Supabaseは既存の `applicants` / `inquiries` テーブルをそのまま利用
- 既存の `/webhook` は残してあります
- 既存の `/applicants-view` などのHTML画面も互換用に残しています

## 次にやると良いこと

1. `PATCH /api/applicants/{id}` でステータス・メモ更新を確認
2. `POST /api/line/send` をLINE push APIに接続
3. 管理画面ログインを追加
4. 企業IDを追加してマルチテナント化
5. リマインド処理を定期実行にする
