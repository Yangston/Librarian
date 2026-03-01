import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Librarian",
  description: "Structured, transparent knowledge workspace built from conversation"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
