import { NextRequest, NextResponse } from "next/server";

// 管理系の更新APIをNext.jsサーバー経由でbackendへ中継します。
// ADMIN_API_KEY はサーバー側の環境変数のみで保持し、ブラウザには一切渡しません。
const BACKEND_BASE =
  process.env.BACKEND_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";
const ADMIN_API_KEY = process.env.ADMIN_API_KEY || "";

// 中継を許可するbackendパスの先頭一覧（それ以外は拒否）
const ALLOWED_PREFIXES = ["faq-settings", "settings", "question-tree"];

async function forward(request: NextRequest, path: string[]) {
  if (!path.length || !ALLOWED_PREFIXES.includes(path[0])) {
    return NextResponse.json({ detail: "このパスは中継できません" }, { status: 404 });
  }

  const target = `${BACKEND_BASE}/api/${path.map(encodeURIComponent).join("/")}`;
  const body = await request.text();

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (ADMIN_API_KEY) headers["X-Admin-Key"] = ADMIN_API_KEY;

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: body || undefined,
    cache: "no-store"
  });

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" }
  });
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(request, params.path);
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(request, params.path);
}
