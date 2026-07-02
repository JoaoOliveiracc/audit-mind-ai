import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Auditor-IA",
  description: "Auditoria de projetos de desenvolvimento com IA (LangGraph).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="border-b border-border">
          <div className="mx-auto max-w-5xl px-5 py-4 flex items-center gap-3">
            <Link href="/" className="text-lg font-semibold">
              🕵️ Auditor-IA
            </Link>
            <span className="text-sm text-info">auditoria de projetos com IA</span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-5 py-8">{children}</main>
      </body>
    </html>
  );
}
