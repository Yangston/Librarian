"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  getWorkspaceLibraryV3,
  getWorkspaceSpacesV3,
  type WorkspaceCatalogRow,
  type WorkspaceSpaceRead
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LibraryPage() {
  const [spaces, setSpaces] = useState<WorkspaceSpaceRead[]>([]);
  const [items, setItems] = useState<WorkspaceCatalogRow[]>([]);
  const [query, setQuery] = useState("");
  const [spaceDraft, setSpaceDraft] = useState("__all__");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [spacesData, libraryData] = await Promise.all([
        getWorkspaceSpacesV3(),
        getWorkspaceLibraryV3({
          limit: 200,
          offset: 0,
          q: query.trim() || undefined,
          space_id: spaceDraft === "__all__" ? undefined : Number.parseInt(spaceDraft, 10)
        })
      ]);
      setSpaces(spacesData);
      setItems(libraryData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load library.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [spaceDraft]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return items;
    }
    return items.filter((item) =>
      `${item.row.title} ${item.collection_name} ${item.space_name} ${item.row.summary ?? ""}`
        .toLowerCase()
        .includes(normalized)
    );
  }, [items, query]);

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl">Library</CardTitle>
          <CardDescription>Global catalog of rows across every space and table.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-[minmax(0,1fr)_220px_auto]">
          <Input
            placeholder="Search rows, spaces, or tables..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={spaceDraft}
            onChange={(event) => setSpaceDraft(event.target.value)}
          >
            <option value="__all__">All spaces</option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
          <Button type="button" variant="outline" onClick={() => void load()}>
            Refresh
          </Button>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Rows</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="subtle">Loading library...</p> : null}
          {!loading && filtered.length === 0 ? <p className="subtle">No rows found.</p> : null}
          {filtered.map((item) => (
            <article key={item.row.id} className="rounded-xl border border-border/70 bg-background/50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link
                    href={`/app/spaces/${item.space_slug}/${item.collection_slug}/${item.row.id}`}
                    className="text-lg font-medium hover:underline"
                  >
                    {item.row.title}
                  </Link>
                  <p className="subtle">
                    {item.space_name} • {item.collection_name}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">{formatTimestamp(item.row.updated_at)}</span>
              </div>
              {item.row.summary ? <p className="mt-2 text-sm text-muted-foreground">{item.row.summary}</p> : null}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {item.row.cells.slice(0, 4).map((cell) => (
                  <span key={`${item.row.id}-${cell.column_id}`} className="tag">
                    {cell.label}: {cell.display_value ?? "—"}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
