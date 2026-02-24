import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Librarian MVP",
  description: "Transparent structured memory for AI conversations"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="header">
            <p className="mono" style={{ margin: 0, color: "var(--accent)" }}>
              LIBRARIAN / PHASE 1
            </p>
            <h1 className="title">Structured conversation memory.</h1>
            <p className="subtitle">
              Conversations become entities, facts, and relations with traceable source messages.
            </p>
          </header>
          <nav className="nav" aria-label="Primary">
            <Link href="/">Home</Link>
            <Link href="/conversation">Conversation</Link>
            <Link href="/database">Database</Link>
            <Link href="/explain">Explain</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}

