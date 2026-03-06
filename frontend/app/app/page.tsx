"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, ChartNetwork, FolderKanban, MessageSquare, Search, Shapes, Users } from "lucide-react";

import {
  type LibraryItemsResponseV2,
  type PropertyCatalogResponseV2,
  type SpaceV2,
  getLibraryItemsV2,
  getPropertiesCatalogV2,
  getSpacesV2
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const ACTIONS = [
  {
    href: "/app/chat",
    title: "Chat",
    description: "Capture new context and let the workspace organize it.",
    icon: MessageSquare
  },
  {
    href: "/app/spaces",
    title: "Spaces",
    description: "Organize your workspace with pages and tables.",
    icon: FolderKanban
  },
  {
    href: "/app/entities",
    title: "Library",
    description: "Review entities, properties, and recent activity.",
    icon: Users
  },
  {
    href: "/app/properties",
    title: "Properties & Types",
    description: "Refine schema labels and relation vocabulary.",
    icon: Shapes
  },
  {
    href: "/app/search",
    title: "Search",
    description: "Find items and claims across your workspace.",
    icon: Search
  },
  {
    href: "/app/graph",
    title: "Graph",
    description: "Explore connected knowledge in advanced view.",
    icon: ChartNetwork
  }
];

export default function WorkspacePage() {
  const router = useRouter();
  const [queryDraft, setQueryDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [spaces, setSpaces] = useState<SpaceV2[]>([]);
  const [library, setLibrary] = useState<LibraryItemsResponseV2 | null>(null);
  const [properties, setProperties] = useState<PropertyCatalogResponseV2 | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [spaceRows, libraryRows, propertyRows] = await Promise.all([
          getSpacesV2(),
          getLibraryItemsV2({ limit: 8, offset: 0, sort: "last_active", order: "desc" }),
          getPropertiesCatalogV2()
        ]);
        if (!active) {
          return;
        }
        setSpaces(spaceRows);
        setLibrary(libraryRows);
        setProperties(propertyRows);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workspace overview.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = queryDraft.trim();
    if (!clean) {
      return;
    }
    router.push(`/app/search?q=${encodeURIComponent(clean)}`);
  }

  return (
    <div className="space-y-4 routeFade">
      <Card className="hero overflow-hidden border-border/80 bg-card/95">
        <CardHeader className="space-y-4">
          <div className="space-y-2">
            <Badge variant="secondary">Workspace</Badge>
            <CardTitle className="text-3xl tracking-tight">Your productivity space for captured knowledge.</CardTitle>
            <CardDescription className="max-w-3xl text-sm sm:text-base">
              Organize information into spaces, review key items in your library, and open explainability when needed.
            </CardDescription>
          </div>
          <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={submitSearch}>
            <Input
              placeholder="Search items or claims..."
              value={queryDraft}
              onChange={(event) => setQueryDraft(event.target.value)}
              className="sm:max-w-xl"
            />
            <Button type="submit">Search</Button>
          </form>
        </CardHeader>
        <CardContent className="grid gap-3 pb-6 sm:grid-cols-2 xl:grid-cols-3">
          {ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.href}
                href={action.href}
                className="group rounded-lg border border-border/70 bg-background/70 p-4 transition-colors hover:bg-accent/10"
              >
                <div className="flex items-center justify-between">
                  <Icon className="h-4 w-4 text-primary" />
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </div>
                <p className="mt-3 font-medium">{action.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{action.description}</p>
              </Link>
            );
          })}
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Spaces</CardDescription>
              <CardTitle className="text-3xl">{spaces.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Library Items</CardDescription>
              <CardTitle className="text-3xl">{library?.total ?? 0}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Properties</CardDescription>
              <CardTitle className="text-3xl">{properties?.total ?? 0}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}
    </div>
  );
}
