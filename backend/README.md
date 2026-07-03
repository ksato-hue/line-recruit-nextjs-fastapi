# Backend / FastAPI

LINE Bot と Supabase API サーバーです。

## 起動

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 主なAPI

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/applicants`
- `GET /api/applicants/{id}`
- `PATCH /api/applicants/{id}`
- `GET /api/inquiries`
- `POST /api/line/send`

既存の `/webhook` はそのまま残しています。
