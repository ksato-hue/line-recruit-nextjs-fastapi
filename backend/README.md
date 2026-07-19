# Backend / FastAPI

LINE Bot と Supabase API サーバーです。

## 起動

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

`.env.example`を`.env`へコピーし、すべての値を設定してください。`LINE_CHANNEL_SECRET`または`ADMIN_API_KEY`が未設定の場合、対応するWebhookまたは管理APIは安全のため拒否されます。

## 主なAPI

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/applicants`
- `GET /api/applicants/{id}`
- `PATCH /api/applicants/{id}`
- `GET /api/inquiries`
- `POST /api/line/send`

`/webhook`はLINEの`X-Line-Signature`を検証します。`/api/health`以外の管理APIは`X-Admin-Key`が必要で、通常はNext.js管理プロキシ経由で利用します。
