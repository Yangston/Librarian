"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Library, Settings2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { warmWorkspaceApi } from "@/lib/api";
import { type AppDensity, type AppTheme } from "@/lib/settings";
import { AppSettingsProvider, useAppSettings } from "@/components/AppSettingsProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "@/components/ui/sheet";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar
} from "@/components/ui/sidebar";

import AppNav from "./AppNav";

const SIDEBAR_STORAGE_KEY = "librarian.shell.sidebarCollapsed.v1";
const APP_ROUTES_TO_PREFETCH = [
  "/app",
  "/app/chat",
  "/app/graph",
  "/app/conversations",
  "/app/entities",
  "/app/schema",
  "/app/search"
];
const ROUTE_MODULE_PRELOADERS: Array<() => Promise<unknown>> = [
  () => import("@/app/app/page"),
  () => import("@/app/app/chat/page"),
  () => import("@/app/app/graph/page"),
  () => import("@/app/app/conversations/page"),
  () => import("@/app/app/entities/page"),
  () => import("@/app/app/schema/page"),
  () => import("@/app/app/search/page")
];

function readSidebarPreference(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
}

function NewChatSidebarButton() {
  const router = useRouter();
  const { isMobile, setOpenMobile } = useSidebar();

  function handleNewChat() {
    if (isMobile) {
      setOpenMobile(false);
    }
    router.push(`/app/chat?new=1&ts=${Date.now()}`);
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="w-full group-data-[collapsible=icon]:hidden"
        onClick={handleNewChat}
      >
        <Sparkles className="h-4 w-4" />
        New Chat
      </Button>
      <Button
        variant="outline"
        size="icon"
        className="hidden h-8 w-8 group-data-[collapsible=icon]:inline-flex"
        aria-label="New chat"
        onClick={handleNewChat}
      >
        <Sparkles className="h-4 w-4" />
      </Button>
    </>
  );
}

function SettingsSheetButton() {
  const { settings, resetSettings, setDensity, setDevMode, setReducedMotion, setTheme } =
    useAppSettings();

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" type="button" aria-label="Open settings">
          <Settings2 className="h-4 w-4" />
          <span className="hidden sm:inline">Settings</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[360px] space-y-5 overflow-y-auto sm:max-w-[420px]">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
          <SheetDescription>Appearance, mode, and accessibility preferences for this browser.</SheetDescription>
        </SheetHeader>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Appearance</h3>
          <label className="field">
            <Label htmlFor="settings-theme">Theme</Label>
            <Select value={settings.theme} onValueChange={(value) => setTheme(value as AppTheme)}>
              <SelectTrigger id="settings-theme">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">System</SelectItem>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="field">
            <Label htmlFor="settings-density">Density</Label>
            <Select value={settings.density} onValueChange={(value) => setDensity(value as AppDensity)}>
              <SelectTrigger id="settings-density">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="comfortable">Comfortable</SelectItem>
                <SelectItem value="compact">Compact</SelectItem>
              </SelectContent>
            </Select>
          </label>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Mode</h3>
          <div className="flex items-start gap-2 rounded-md border border-border/70 px-3 py-2">
            <Checkbox
              id="settings-dev-mode"
              checked={settings.devMode}
              onCheckedChange={(checked) => setDevMode(Boolean(checked))}
            />
            <div className="space-y-0.5">
              <Label htmlFor="settings-dev-mode">Dev mode</Label>
              <p className="text-xs text-muted-foreground">
                On keeps all technical and provenance details visible.
              </p>
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Accessibility</h3>
          <div className="flex items-start gap-2 rounded-md border border-border/70 px-3 py-2">
            <Checkbox
              id="settings-reduced-motion"
              checked={settings.reducedMotion}
              onCheckedChange={(checked) => setReducedMotion(Boolean(checked))}
            />
            <div className="space-y-0.5">
              <Label htmlFor="settings-reduced-motion">Reduced motion</Label>
              <p className="text-xs text-muted-foreground">
                Disables route and interaction animations.
              </p>
            </div>
          </div>
        </section>

        <Button type="button" variant="outline" onClick={resetSettings}>
          Reset to defaults
        </Button>
      </SheetContent>
    </Sheet>
  );
}

function AppShellFrame({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setOpen(!readSidebarPreference());
    setHydrated(true);
  }, []);

  useEffect(() => {
    type IdleWindow = Window & {
      requestIdleCallback?: (
        callback: (deadline: { didTimeout: boolean; timeRemaining: () => number }) => void,
        options?: { timeout: number }
      ) => number;
      cancelIdleCallback?: (id: number) => void;
    };

    const idleWindow = window as IdleWindow;
    let idleId: number | null = null;
    let moduleTimerId: number | null = null;

    const timerId = window.setTimeout(() => {
      APP_ROUTES_TO_PREFETCH.forEach((href) => {
        void router.prefetch(href);
      });
      void warmWorkspaceApi();

      const preloadRouteModules = () => {
        ROUTE_MODULE_PRELOADERS.forEach((loadModule) => {
          void loadModule();
        });
      };
      if (idleWindow.requestIdleCallback) {
        idleId = idleWindow.requestIdleCallback(() => {
          preloadRouteModules();
        }, { timeout: 1500 });
      } else {
        moduleTimerId = window.setTimeout(preloadRouteModules, 500);
      }
    }, 250);

    return () => {
      window.clearTimeout(timerId);
      if (moduleTimerId !== null) {
        window.clearTimeout(moduleTimerId);
      }
      if (idleId !== null && idleWindow.cancelIdleCallback) {
        idleWindow.cancelIdleCallback(idleId);
      }
    };
  }, [router]);

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, nextOpen ? "0" : "1");
    }
  }

  return (
    <SidebarProvider
      open={open}
      onOpenChange={handleOpenChange}
      className={hydrated ? undefined : "[&_*]:!transition-none"}
    >
      <a className="skipLink" href="#product-content">
        Skip to content
      </a>
      <Sidebar collapsible="icon" variant="inset" className="overflow-hidden">
        <SidebarHeader className="gap-3 p-3">
          <Link
            href="/app"
            className="flex items-center justify-between gap-2 rounded-md border border-sidebar-border bg-background/80 px-3 py-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
          >
            <span className="font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
              Librarian
            </span>
            <Library className="hidden h-4 w-4 text-primary group-data-[collapsible=icon]:inline" aria-hidden />
            <Badge
              variant="secondary"
              className="text-[10px] uppercase tracking-wide group-data-[collapsible=icon]:hidden"
            >
              v3.5
            </Badge>
          </Link>
          <p className="text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
            Structured memory from conversation, built for inspection.
          </p>
        </SidebarHeader>
        <SidebarSeparator />
        <SidebarContent>
          <AppNav />
        </SidebarContent>
        <SidebarFooter className="p-3">
          <div className="group-data-[collapsible=icon]:hidden">
            <p className="text-xs text-muted-foreground">System Status</p>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <Activity className="h-3.5 w-3.5 text-primary" />
              <span>API connected</span>
            </div>
          </div>
          <NewChatSidebarButton />
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-h-screen">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/85 px-4 backdrop-blur">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-4" />
            <div className="leading-tight">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Product Workspace</p>
              <p className="text-sm font-medium">Browse, inspect, and shape learned knowledge.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <SettingsSheetButton />
            <div className="hidden items-center gap-2 sm:flex">
              <Button asChild variant="outline" size="sm">
                <Link href="/app/search">Search</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/app/graph">Graph Studio</Link>
              </Button>
            </div>
          </div>
        </header>
        <main id="product-content" className="productContent px-4 pb-6 pt-4 md:px-6">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default function AppShell({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <AppSettingsProvider>
      <AppShellFrame>{children}</AppShellFrame>
    </AppSettingsProvider>
  );
}
