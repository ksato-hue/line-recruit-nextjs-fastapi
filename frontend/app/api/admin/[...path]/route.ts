import { NextRequest, NextResponse } from "next/server";

// 管理APIをNext.jsサーバー経由でbackendへ中継します。
// ADMIN_API_KEY はサーバー側の環境変数のみで保持し、ブラウザには一切渡しません。
const BACKEND_BASE = process.env.BACKEND_API_BASE_URL?.replace(/\/$/, "") || "";
const ADMIN_API_KEY = process.env.ADMIN_API_KEY || "";

// 中継を許可するbackendパスの先頭一覧（それ以外は拒否）
const ALLOWED_PREFIXES = new Set([
  "dashboard",
  "applicants",
  "interview-slots",
  "inquiries",
  "line-messages",
  "line",
  "faq-categories",
  "faqs",
  "faq-settings",
  "settings",
  "question-tree",
  "status-settings"
]);
const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH"]);

async function forward(request: NextRequest, path: string[]) {
  if (!BACKEND_BASE || !ADMIN_API_KEY) {
    return NextResponse.json({ detail: "管理API接続が設定されていません" }, { status: 503 });
  }
  if (!ALLOWED_METHODS.has(request.method)) {
    return NextResponse.json({ detail: "許可されていないメソッドです" }, { status: 405 });
  }
  if (!path.length || !ALLOWED_PREFIXES.has(path[0])) {
    return NextResponse.json({ detail: "このパスは中継できません" }, { status: 404 });
  }

  const target = `${BACKEND_BASE}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const body = request.method === "GET" ? undefined : await request.text();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Admin-Key": ADMIN_API_KEY
  };

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

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(request, params.path);
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(request, params.path);
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(request, params.path);
}
