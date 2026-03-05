import type { Metadata } from "next";

import { APP_SETTINGS_STORAGE_KEY } from "../lib/settings";
import "./globals.css";

export const metadata: Metadata = {
  title: "Librarian",
  description: "Structured, transparent knowledge workspace built from conversation"
};

const SETTINGS_BOOTSTRAP_SCRIPT = `
  (function () {
    try {
      var raw = window.localStorage.getItem("${APP_SETTINGS_STORAGE_KEY}");
      var parsed = raw ? JSON.parse(raw) : null;
      var settings = parsed && typeof parsed === "object" && parsed.settings && typeof parsed.settings === "object"
        ? parsed.settings
        : {};
      var theme = settings.theme === "light" || settings.theme === "dark" || settings.theme === "system"
        ? settings.theme
        : "system";
      var density = settings.density === "compact" || settings.density === "comfortable"
        ? settings.density
        : "comfortable";
      var reducedMotion = typeof settings.reducedMotion === "boolean"
        ? settings.reducedMotion
        : false;

      var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      var resolvedTheme = theme === "system" ? (prefersDark ? "dark" : "light") : theme;
      var root = document.documentElement;
      root.classList.toggle("dark", resolvedTheme === "dark");
      root.style.colorScheme = resolvedTheme;
      root.dataset.density = density;
      root.dataset.motion = reducedMotion ? "reduced" : "normal";
    } catch (_error) {
      // Ignore storage/bootstrap failures and fall back to CSS defaults.
    }
  })();
`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SETTINGS_BOOTSTRAP_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
