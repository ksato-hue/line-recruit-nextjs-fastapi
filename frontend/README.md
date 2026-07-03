# Frontend / Next.js 管理画面

FastAPI の `/api/*` を呼び出す管理画面です。

## 起動

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

`.env.local` の `NEXT_PUBLIC_API_BASE_URL` は FastAPI のURLに合わせてください。

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

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
