# Frontend / Next.js 管理画面

FastAPI の `/api/*` を呼び出す管理画面です。

## 起動

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

`.env.local`にはNext.jsサーバー専用のbackend URLと管理キーを設定してください。管理キーに`NEXT_PUBLIC_`を付けないでください。

```env
BACKEND_API_BASE_URL=http://localhost:8000
ADMIN_API_KEY=replace_with_the_same_long_random_secret_as_backend
ADMIN_BASIC_USERNAME=admin
ADMIN_BASIC_PASSWORD=replace_with_a_long_random_password
```

Renderでは上記4変数をfrontendサービスへ設定します。`ADMIN_API_KEY`とBasic認証情報はいずれも`NEXT_PUBLIC_`を付けず、サーバー側だけで保持してください。

## 画面

- ダッシュボード
- 応募者一覧
- 応募者詳細スライドパネル
- LINEメッセージ履歴
- リマインド設定
- 質問ツリー設定
- メッセージテンプレート設定
- 面接候補日管理
- 簡易分析
- 設定
