"use client";
import { useEffect, useMemo, useState } from "react";

import {
  getWorkspacePropertiesV3,
  getWorkspaceSpacesV3,
  type WorkspacePropertyCatalogRow,
  type WorkspaceSpaceRead,
  updateWorkspaceColumnV3
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function PropertiesPage() {
  const [spaces, setSpaces] = useState<WorkspaceSpaceRead[]>([]);
  const [rows, setRows] = useState<WorkspacePropertyCatalogRow[]>([]);
  const [spaceDraft, setSpaceDraft] = useState("__all__");
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [spacesData, properties] = await Promise.all([
        getWorkspaceSpacesV3(),
        getWorkspacePropertiesV3({
          space_id: spaceDraft === "__all__" ? undefined : Number.parseInt(spaceDraft, 10)
        })
      ]);
      setSpaces(spacesData);
      setRows(properties.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load property catalog.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [spaceDraft]);

  const filtered = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    if (!normalized) {
      return rows;
    }
    return rows.filter((row) =>
      `${row.label} ${row.collection_name} ${row.space_name} ${row.key} ${row.origin}`
        .toLowerCase()
        .includes(normalized)
    );
  }, [filter, rows]);

  async function renameColumn(columnId: number, label: string) {
    if (!label.trim()) {
      return;
    }
    try {
      await updateWorkspaceColumnV3(columnId, { label: label.trim(), user_locked: true });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename column.");
    }
  }

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl">Properties & Types</CardTitle>
          <CardDescription>Collection schema coverage, ownership, and column curation.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-[minmax(0,1fr)_220px_auto]">
          <Input
            placeholder="Filter properties..."
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
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
          <CardTitle className="text-lg">Column Catalog</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="subtle">Loading properties...</p> : null}
          {!loading && filtered.length === 0 ? <p className="subtle">No properties found.</p> : null}
          {filtered.map((row) => (
            <article key={row.id} className="rounded-xl border border-border/70 bg-background/50 p-4">
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_200px_200px]">
                <div className="space-y-2">
                  <Input defaultValue={row.label} onBlur={(event) => void renameColumn(row.id, event.target.value)} />
                  <p className="subtle">
                    {row.space_name} • {row.collection_name}
                  </p>
                </div>
                <div className="space-y-1 text-sm">
                  <p>Type: {row.data_type}</p>
                  <p>Origin: {row.origin}</p>
                  <p>Coverage: {Math.round(row.coverage_ratio * 100)}%</p>
                </div>
                <div className="space-y-1 text-sm">
                  <p>Rows filled: {row.coverage_count}/{row.row_count}</p>
                  <p>Planner locked: {row.planner_locked ? "Yes" : "No"}</p>
                  <p>User locked: {row.user_locked ? "Yes" : "No"}</p>
                  <p className="text-xs text-muted-foreground">Updated {formatTimestamp(row.updated_at)}</p>
                </div>
              </div>
            </article>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
