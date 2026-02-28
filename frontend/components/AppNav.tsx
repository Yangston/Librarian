"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: Array<{ href: string; label: string }> = [
  { href: "/workspace", label: "Workspace" },
  { href: "/chat", label: "Chat" },
  { href: "/conversations", label: "Conversations" },
  { href: "/graph", label: "Graph" },
  { href: "/entities", label: "Entities" },
  { href: "/schema", label: "Schema" },
  { href: "/search", label: "Search" }
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/workspace") {
    return pathname === "/" || pathname === "/workspace";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="appNav" aria-label="Primary">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={isActive(pathname, link.href) ? "active" : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
