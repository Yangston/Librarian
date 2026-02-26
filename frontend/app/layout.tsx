import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Librarian Test Console",
  description: "Structured conversation memory testing console for Phase 2"
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
              LIBRARIAN / PHASE 2 TEST CONSOLE
            </p>
            <h1 className="title">Structured conversation memory.</h1>
            <p className="subtitle">
              Test batch ingestion and live GPT chat in one place, then inspect entities, facts,
              relations, merges, and explanations with full traceability.
            </p>
          </header>
          <nav className="nav" aria-label="Primary">
            <Link href="/">Home</Link>
            <Link href="/conversation">Conversation</Link>
            <Link href="/live">Live Chat</Link>
            <Link href="/database">Database</Link>
            <Link href="/explain">Explain</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
