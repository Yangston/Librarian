"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { useIsDevMode } from "@/components/AppSettingsProvider";
import { ExplainSidePanel, type ExplainTarget } from "@/components/explain/ExplainSidePanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type LibraryItemRowV2,
  type LibraryItemsResponseV2,
  type SpacePageV2,
  type SpaceV2,
  getLibraryItemsV2,
  getSpacePagesV2,
  getSpacesV2,
  updateLibraryItemV2
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

const PAGE_SIZE = 25;

export default function LibraryPage() {
  const isDevMode = useIsDevMode();
  const [spaces, setSpaces] = useState<SpaceV2[]>([]);
  const [pages, setPages] = useState<SpacePageV2[]>([]);
  const [spaceDraft, setSpaceDraft] = useState("__all__");
  const [pageDraft, setPageDraft] = useState("__all__");
  const [typeDraft, setTypeDraft] = useState("__all__");
  const [queryDraft, setQueryDraft] = useState("");
  const [sort, setSort] = useState<"last_active" | "name" | "mentions" | "type">("last_active");
  const [offset, setOffset] = useState(0);
  const [showTechnicalColumns, setShowTechnicalColumns] = useState(false);
  const [payload, setPayload] = useState<LibraryItemsResponseV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rowBusyId, setRowBusyId] = useState<number | null>(null);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ canonical_name: "", type_label: "" });
  const [error, setError] = useState<string | null>(null);
  const [explainTarget, setExplainTarget] = useState<ExplainTarget | null>(null);
  const [explainOpen, setExplainOpen] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadSpaces() {
      try {
        const rows = await getSpacesV2();
        if (!active) {
          return;
        }
        setSpaces(rows);
      } catch {
        // Keep library functional even if spaces fail.
      }
    }
    void loadSpaces();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (spaceDraft === "__all__") {
      setPages([]);
      setPageDraft("__all__");
      return;
    }
    let active = true;
    async function loadPages() {
      try {
        const data = await getSpacePagesV2(Number.parseInt(spaceDraft, 10));
        if (!active) {
          return;
        }
        setPages(data.items);
      } catch {
        if (!active) {
          return;
        }
        setPages([]);
      }
      setPageDraft("__all__");
    }
    void loadPages();
    return () => {
      active = false;
    };
  }, [spaceDraft]);

  useEffect(() => {
    let active = true;
    async function loadLibrary(isRefresh: boolean) {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const data = await getLibraryItemsV2({
          limit: PAGE_SIZE,
          offset,
          q: queryDraft.trim() || undefined,
          type_label: typeDraft === "__all__" ? undefined : typeDraft,
          space_id: spaceDraft === "__all__" ? undefined : Number.parseInt(spaceDraft, 10),
          page_id: pageDraft === "__all__" ? undefined : Number.parseInt(pageDraft, 10),
          sort,
          order: sort === "name" || sort === "type" ? "asc" : "desc",
          include_technical: isDevMode || showTechnicalColumns
        });
        if (!active) {
          return;
        }
        setPayload(data);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load library.");
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }
    void loadLibrary(offset > 0 || payload !== null);
    return () => {
      active = false;
    };
  }, [isDevMode, offset, pageDraft, queryDraft, showTechnicalColumns, sort, spaceDraft, typeDraft]);

  const types = useMemo(() => {
    const set = new Set((payload?.items ?? []).map((item) => item.type_label).filter(Boolean));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [payload?.items]);

  function beginEdit(item: LibraryItemRowV2) {
    setEditingItemId(item.id);
    setEditDraft({
      canonical_name: item.name,
      type_label: item.type_label || "Unspecified"
    });
  }

  function cancelEdit() {
    setEditingItemId(null);
    setEditDraft({ canonical_name: "", type_label: "" });
  }

  async function saveEdit(itemId: number) {
    const name = editDraft.canonical_name.trim();
    const typeLabel = editDraft.type_label.trim();
    if (!name || !typeLabel) {
      setError("Name and type are required.");
      return;
    }
    setRowBusyId(itemId);
    setError(null);
    try {
      await updateLibraryItemV2(itemId, {
        canonical_name: name,
        type_label: typeLabel,
        include_technical: isDevMode || showTechnicalColumns
      });
      setPayload((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((item) =>
            item.id === itemId ? { ...item, name, type_label: typeLabel } : item
          )
        };
      });
      cancelEdit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update item.");
    } finally {
      setRowBusyId(null);
    }
  }

  function handleSubmitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
  }

  function openExplain(claimIndexId: number, title: string) {
    setExplainTarget({ claimIndexId, title });
    setExplainOpen(true);
  }

  const total = payload?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;
  const technicalEnabled = showTechnicalColumns || isDevMode;

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl">Library</CardTitle>
          <CardDescription>
            Find items quickly, review key properties, and open explainability context inline.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-2 md:grid-cols-[1fr_180px_180px_180px_160px_auto_auto] md:items-end"
            onSubmit={handleSubmitFilters}
          >
            <label className="field">
              <Label htmlFor="library-query">Search</Label>
              <Input
                id="library-query"
                value={queryDraft}
                onChange={(event) => setQueryDraft(event.target.value)}
                placeholder="Search name, type, summary..."
              />
            </label>
            <label className="field">
              <Label htmlFor="library-type">Type</Label>
              <Select value={typeDraft} onValueChange={setTypeDraft}>
                <SelectTrigger id="library-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All types</SelectItem>
                  {types.map((typeLabel) => (
                    <SelectItem key={typeLabel} value={typeLabel}>
                      {typeLabel}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="field">
              <Label htmlFor="library-space">Space</Label>
              <Select value={spaceDraft} onValueChange={setSpaceDraft}>
                <SelectTrigger id="library-space">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All spaces</SelectItem>
                  {spaces.map((space) => (
                    <SelectItem key={space.id} value={String(space.id)}>
                      {space.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="field">
              <Label htmlFor="library-page">Page</Label>
              <Select value={pageDraft} onValueChange={setPageDraft}>
                <SelectTrigger id="library-page">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All pages</SelectItem>
                  {pages.map((page) => (
                    <SelectItem key={page.id} value={String(page.id)}>
                      {page.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="field">
              <Label htmlFor="library-sort">Sort</Label>
              <Select
                value={sort}
                onValueChange={(value) => setSort(value as "last_active" | "name" | "mentions" | "type")}
              >
                <SelectTrigger id="library-sort">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="last_active">Last active</SelectItem>
                  <SelectItem value="mentions">Mentions</SelectItem>
                  <SelectItem value="name">Name</SelectItem>
                  <SelectItem value="type">Type</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <Checkbox
                checked={showTechnicalColumns}
                onCheckedChange={(value) => setShowTechnicalColumns(Boolean(value))}
              />
              Show technical columns
            </label>
            <Button type="submit" variant="outline">
              Apply
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-lg">Items</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{total} total</Badge>
              {refreshing ? <Badge variant="outline">Refreshing</Badge> : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="subtle">Loading library...</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Last active</TableHead>
                  <TableHead>Mentions</TableHead>
                  <TableHead>Key properties</TableHead>
                  {technicalEnabled ? <TableHead>Technical</TableHead> : null}
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(payload?.items ?? []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={technicalEnabled ? 7 : 6} className="text-center text-muted-foreground">
                      No items found.
                    </TableCell>
                  </TableRow>
                ) : (
                  payload?.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        {editingItemId === item.id ? (
                          <Input
                            className="h-8 max-w-[260px]"
                            value={editDraft.canonical_name}
                            onChange={(event) =>
                              setEditDraft((current) => ({ ...current, canonical_name: event.target.value }))
                            }
                          />
                        ) : (
                          <div>
                            <Link href={`/app/entities/${item.entity_id}`} className="font-medium">
                              {item.name}
                            </Link>
                            {item.summary ? <p className="subtle text-xs">{item.summary}</p> : null}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {editingItemId === item.id ? (
                          <Input
                            className="h-8 max-w-[180px]"
                            value={editDraft.type_label}
                            onChange={(event) =>
                              setEditDraft((current) => ({ ...current, type_label: event.target.value }))
                            }
                          />
                        ) : (
                          item.type_label
                        )}
                      </TableCell>
                      <TableCell>{formatTimestamp(item.last_seen_at)}</TableCell>
                      <TableCell>{item.mention_count}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {item.key_properties.length === 0 ? <span className="subtle">No properties</span> : null}
                          {item.key_properties.map((property) =>
                            property.claim_index_id ? (
                              <button
                                key={`${item.id}-${property.property_key}`}
                                type="button"
                                className="tag"
                                onClick={() =>
                                  openExplain(
                                    property.claim_index_id as number,
                                    `${property.label}: ${property.value}`
                                  )
                                }
                              >
                                {property.label}: {property.value}
                              </button>
                            ) : (
                              <span key={`${item.id}-${property.property_key}`} className="tag">
                                {property.label}: {property.value}
                              </span>
                            )
                          )}
                        </div>
                      </TableCell>
                      {technicalEnabled ? (
                        <TableCell>
                          <p className="text-xs text-muted-foreground">item_id: {item.id}</p>
                          <p className="text-xs text-muted-foreground">space_id: {item.space_id ?? "-"}</p>
                          <p className="text-xs text-muted-foreground">page_id: {item.page_id ?? "-"}</p>
                        </TableCell>
                      ) : null}
                      <TableCell>
                        {editingItemId === item.id ? (
                          <div className="inlineActions">
                            <Button type="button" onClick={() => void saveEdit(item.id)} disabled={rowBusyId === item.id}>
                              Save
                            </Button>
                            <Button type="button" variant="outline" onClick={cancelEdit}>
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="inlineActions">
                            <Button type="button" variant="outline" onClick={() => beginEdit(item)}>
                              Quick edit
                            </Button>
                            <Button asChild type="button" variant="outline">
                              <Link href={`/app/entities/${item.entity_id}`}>Open</Link>
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
          <div className="flex items-center justify-between gap-3">
            <Button variant="outline" disabled={!canPrev} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              {total === 0 ? 0 : offset + 1} - {Math.min(total, offset + PAGE_SIZE)} of {total}
            </span>
            <Button variant="outline" disabled={!canNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </CardContent>
      </Card>

      <ExplainSidePanel open={explainOpen} target={explainTarget} onOpenChange={setExplainOpen} />
    </div>
  );
}
