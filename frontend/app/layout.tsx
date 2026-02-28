import type { Metadata } from "next";

import AppNav from "../components/AppNav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Librarian Workspace",
  description: "Self-building, transparent relational workspace from conversation"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="appShell">
          <header className="appHeader">
            <p className="eyebrow">Librarian</p>
            <h1>Human-Centered Workspace</h1>
            <p className="subtle">
              Browse conversations, entities, schema evolution, and explainable knowledge traces.
            </p>
          </header>
          <AppNav />
          <main className="pageBody">{children}</main>
        </div>
      </body>
    </html>
  );
}

