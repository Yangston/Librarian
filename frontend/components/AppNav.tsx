"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  ChartNetwork,
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  Search,
  Shapes,
  UsersRound
} from "lucide-react";

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar
} from "@/components/ui/sidebar";

const LINKS: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/app/chat", label: "Chat", icon: Bot },
  { href: "/app/spaces", label: "Spaces", icon: FolderKanban },
  { href: "/app/entities", label: "Library", icon: UsersRound },
  { href: "/app/properties", label: "Properties & Types", icon: Shapes },
  { href: "/app/search", label: "Search", icon: Search },
  { href: "/app/graph", label: "Graph", icon: ChartNetwork }
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/app") {
    return pathname === "/app";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppNav({
  onNavigate
}: Readonly<{
  onNavigate?: () => void;
}>) {
  const pathname = usePathname();
  const { isMobile, setOpenMobile } = useSidebar();

  function handleNavigate() {
    if (isMobile) {
      setOpenMobile(false);
    }
    onNavigate?.();
  }

  return (
    <nav aria-label="Primary">
      <SidebarGroup>
        <SidebarGroupLabel>Workspace</SidebarGroupLabel>
        <SidebarMenu>
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <SidebarMenuItem key={link.href}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive(pathname, link.href)}
                  tooltip={link.label}
                >
                  <Link href={link.href} title={link.label} onClick={handleNavigate}>
                    <Icon />
                    <span>{link.label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroup>
    </nav>
  );
}
