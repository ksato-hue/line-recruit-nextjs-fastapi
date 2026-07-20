import { NextRequest, NextResponse } from "next/server";

function unauthorized(message = "認証が必要です") {
  return new NextResponse(message, {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="LINE Recruit Admin", charset="UTF-8"',
      "Cache-Control": "no-store"
    }
  });
}

function safeEqual(left: string, right: string) {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

export function middleware(request: NextRequest) {
  const username = process.env.ADMIN_BASIC_USERNAME || "";
  const password = process.env.ADMIN_BASIC_PASSWORD || "";
  if (!username || !password) {
    return new NextResponse("管理画面認証が設定されていません", {
      status: 503,
      headers: { "Cache-Control": "no-store" }
    });
  }

  const authorization = request.headers.get("authorization") || "";
  if (!authorization.startsWith("Basic ")) return unauthorized();

  try {
    const decoded = atob(authorization.slice(6));
    const separator = decoded.indexOf(":");
    if (separator < 0) return unauthorized();
    const suppliedUsername = decoded.slice(0, separator);
    const suppliedPassword = decoded.slice(separator + 1);
    if (!safeEqual(suppliedUsername, username) || !safeEqual(suppliedPassword, password)) {
      return unauthorized();
    }
  } catch {
    return unauthorized();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"]
};
