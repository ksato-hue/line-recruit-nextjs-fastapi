import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LINE採用自動化 管理画面",
  description: "LINE採用自動化のMVP管理画面"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
