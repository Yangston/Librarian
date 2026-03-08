"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAppSettings } from "@/components/AppSettingsProvider";
import {
  acceptWorkspaceCollectionSuggestionsV3,
  createWorkspaceSpaceV3,
  createWorkspaceCollectionV3,
  createWorkspaceColumnV3,
  createWorkspaceRowV3,
  deleteWorkspaceCollectionV3,
  deleteWorkspaceColumnV3,
  deleteWorkspaceRowV3,
  deleteWorkspaceSpaceV3,
  enrichWorkspaceCollectionV3,
  getLatestWorkspaceEnrichmentRunForSpaceV3,
  getWorkspaceLibraryV3,
  getWorkspaceOverviewV3,
  getWorkspaceRowsV3,
  getWorkspaceSpacesV3,
  type WorkspaceCatalogRow,
  type WorkspaceCollectionRead,
  type WorkspaceOverviewResponse,
  type WorkspaceRowsResponse,
  type WorkspaceSpaceRead,
  rejectWorkspaceCollectionSuggestionsV3,
  updateWorkspaceSpaceV3,
  updateWorkspaceCellV3,
  updateWorkspaceCollectionV3,
  updateWorkspaceColumnV3,
  updateWorkspaceRowV3
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { useWorkspaceEnrichmentMonitor } from "@/lib/use-workspace-enrichment-monitor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type WorkspaceShellProps = {
  spaceSlug: string;
  collectionSlug?: string;
};

export function WorkspaceShell({ spaceSlug, collectionSlug }: WorkspaceShellProps) {
  const router = useRouter();
  const { settings } = useAppSettings();
  const [spaces, setSpaces] = useState<WorkspaceSpaceRead[]>([]);
  const [overview, setOverview] = useState<WorkspaceOverviewResponse | null>(null);
  const [rowsPayload, setRowsPayload] = useState<WorkspaceRowsResponse | null>(null);
  const [library, setLibrary] = useState<WorkspaceCatalogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newSpace, setNewSpace] = useState({ name: "", description: "" });
  const [newCollection, setNewCollection] = useState({ name: "", description: "" });
  const [newColumn, setNewColumn] = useState({ label: "", data_type: "text" });
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");

  const selectedSpace = useMemo(
    () => spaces.find((space) => space.slug === spaceSlug) ?? null,
    [spaces, spaceSlug]
  );
  const selectedCollection = useMemo(() => {
    const items = overview?.collections ?? [];
    if (items.length === 0) {
      return null;
    }
    if (!collectionSlug) {
      return items[0];
    }
    return items.find((collection) => collection.slug === collectionSlug) ?? items[0];
  }, [collectionSlug, overview?.collections]);

  async function loadOverview(preferredSpace?: WorkspaceSpaceRead | null) {
    const resolvedSpace = preferredSpace ?? selectedSpace;
    if (!resolvedSpace) {
      return;
    }
    const payload = await getWorkspaceOverviewV3(resolvedSpace.id);
    setOverview(payload);
    if (!collectionSlug && payload.collections[0]) {
      router.replace(`/app/spaces/${resolvedSpace.slug}/${payload.collections[0].slug}`);
    }
  }

  async function loadRows(collection: WorkspaceCollectionRead | null) {
    if (!collection) {
      setRowsPayload(null);
      return;
    }
    setLoadingRows(true);
    try {
      const payload = await getWorkspaceRowsV3({ collection_id: collection.id, limit: 100, offset: 0 });
      setRowsPayload(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rows.");
    } finally {
      setLoadingRows(false);
    }
  }

  const collectionEnrichment = useWorkspaceEnrichmentMonitor({
    onCompleted: async () => {
      await loadOverview();
      await loadRows(selectedCollection);
    },
    onFailed: (message) => {
      setError(message);
    }
  });

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const spacesData = await getWorkspaceSpacesV3();
        if (!active) {
          return;
        }
        setSpaces(spacesData);
        const space = spacesData.find((item) => item.slug === spaceSlug) ?? spacesData[0] ?? null;
        if (!space) {
          return;
        }
        if (space.slug !== spaceSlug) {
          router.replace(`/app/spaces/${space.slug}`);
          return;
        }
        const [overviewData, libraryData, latestRun] = await Promise.all([
          getWorkspaceOverviewV3(space.id),
          getWorkspaceLibraryV3({ limit: 200, offset: 0, space_id: space.id }),
          getLatestWorkspaceEnrichmentRunForSpaceV3(space.id)
        ]);
        if (!active) {
          return;
        }
        setOverview(overviewData);
        setLibrary(libraryData.items);
        if (latestRun && (latestRun.status === "queued" || latestRun.status === "running")) {
          collectionEnrichment.beginMonitoring(latestRun);
        } else {
          collectionEnrichment.clearRun();
        }
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workspace.");
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
  }, [router, spaceSlug]);

  useEffect(() => {
    void loadRows(selectedCollection);
  }, [selectedCollection?.id]);

  const addableEntities = useMemo(() => {
    const existingEntityIds = new Set((rowsPayload?.rows ?? []).map((row) => row.entity_id));
    return library.filter((item) => !existingEntityIds.has(item.row.entity_id));
  }, [library, rowsPayload?.rows]);

  async function handleCreateCollection() {
    if (!selectedSpace || !newCollection.name.trim()) {
      return;
    }
    setError(null);
    try {
      const created = await createWorkspaceCollectionV3(selectedSpace.id, {
        name: newCollection.name.trim(),
        description: newCollection.description.trim() || null
      });
      setNewCollection({ name: "", description: "" });
      await loadOverview(selectedSpace);
      router.push(`/app/spaces/${selectedSpace.slug}/${created.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create collection.");
    }
  }

  async function handleCreateSpace() {
    if (!newSpace.name.trim()) {
      return;
    }
    setError(null);
    try {
      const created = await createWorkspaceSpaceV3({
        name: newSpace.name.trim(),
        description: newSpace.description.trim() || null
      });
      setNewSpace({ name: "", description: "" });
      router.push(`/app/spaces/${created.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create space.");
    }
  }

  async function handleUpdateSpace(spaceId: number, payload: { name?: string; description?: string | null }) {
    if (payload.name !== undefined && !payload.name.trim()) {
      return;
    }
    setError(null);
    try {
      await updateWorkspaceSpaceV3(spaceId, {
        name: payload.name?.trim(),
        description: payload.description ?? undefined
      });
      const spacesData = await getWorkspaceSpacesV3();
      setSpaces(spacesData);
      if (selectedSpace?.id === spaceId) {
        await loadOverview(spacesData.find((item) => item.id === spaceId) ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update space.");
    }
  }

  async function handleDeleteSpace(spaceId: number, slug: string, name: string) {
    if (!window.confirm(`Delete "${name}" and all assigned conversations?`)) {
      return;
    }
    setError(null);
    try {
      await deleteWorkspaceSpaceV3(spaceId);
      const spacesData = await getWorkspaceSpacesV3();
      setSpaces(spacesData);
      const fallback = spacesData.find((item) => item.slug !== slug) ?? spacesData[0] ?? null;
      if (fallback) {
        router.push(`/app/spaces/${fallback.slug}`);
      } else {
        router.push("/app/spaces");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete space.");
    }
  }

  async function handleRenameCollection(collectionId: number, name: string) {
    if (!name.trim()) {
      return;
    }
    setError(null);
    try {
      await updateWorkspaceCollectionV3(collectionId, { name: name.trim() });
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename collection.");
    }
  }

  async function handleDeleteCollection(collectionId: number) {
    if (!selectedSpace || !window.confirm("Delete this table?")) {
      return;
    }
    setError(null);
    try {
      await deleteWorkspaceCollectionV3(collectionId);
      await loadOverview(selectedSpace);
      router.push(`/app/spaces/${selectedSpace.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete collection.");
    }
  }

  async function handleCreateColumn() {
    if (!selectedCollection || !newColumn.label.trim()) {
      return;
    }
    setError(null);
    try {
      await createWorkspaceColumnV3(selectedCollection.id, {
        label: newColumn.label.trim(),
        data_type: newColumn.data_type
      });
      setNewColumn({ label: "", data_type: "text" });
      await loadRows(selectedCollection);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create column.");
    }
  }

  async function handleRenameColumn(columnId: number, label: string) {
    if (!label.trim()) {
      return;
    }
    setError(null);
    try {
      await updateWorkspaceColumnV3(columnId, { label: label.trim(), user_locked: true });
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update column.");
    }
  }

  async function handleDeleteColumn(columnId: number) {
    if (!window.confirm("Delete this column?")) {
      return;
    }
    setError(null);
    try {
      await deleteWorkspaceColumnV3(columnId);
      await loadRows(selectedCollection);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete column.");
    }
  }

  async function handleMoveColumn(columnId: number, direction: -1 | 1) {
    const columns = rowsPayload?.columns.filter((column) => column.key !== "title") ?? [];
    const index = columns.findIndex((column) => column.id === columnId);
    if (index < 0) {
      return;
    }
    const swapIndex = index + direction;
    if (swapIndex < 0 || swapIndex >= columns.length) {
      return;
    }
    const current = columns[index];
    const other = columns[swapIndex];
    try {
      await updateWorkspaceColumnV3(current.id, { sort_order: other.sort_order });
      await updateWorkspaceColumnV3(other.id, { sort_order: current.sort_order });
      await loadRows(selectedCollection);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reorder column.");
    }
  }

  async function handleCreateRow() {
    if (!selectedCollection || !selectedEntityId) {
      return;
    }
    setError(null);
    try {
      const created = await createWorkspaceRowV3(selectedCollection.id, {
        entity_id: Number.parseInt(selectedEntityId, 10)
      });
      setSelectedEntityId("");
      await loadRows(selectedCollection);
      router.push(`/app/spaces/${spaceSlug}/${selectedCollection.slug}/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add row.");
    }
  }

  async function handleDeleteRow(rowId: number) {
    if (!window.confirm("Delete this row?")) {
      return;
    }
    setError(null);
    try {
      await deleteWorkspaceRowV3(rowId);
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete row.");
    }
  }

  async function handleMoveRow(rowId: number, direction: -1 | 1) {
    const rows = rowsPayload?.rows ?? [];
    const index = rows.findIndex((row) => row.id === rowId);
    if (index < 0) {
      return;
    }
    const swapIndex = index + direction;
    if (swapIndex < 0 || swapIndex >= rows.length) {
      return;
    }
    const current = rows[index];
    const other = rows[swapIndex];
    try {
      await updateWorkspaceRowV3(current.id, { sort_order: other.sort_order });
      await updateWorkspaceRowV3(other.id, { sort_order: current.sort_order });
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reorder row.");
    }
  }

  async function handleUpdateCell(rowId: number, columnId: number, value: string) {
    try {
      await updateWorkspaceCellV3(rowId, columnId, { display_value: value, value_json: value, status: "manual" });
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update cell.");
    }
  }

  async function handleEnrichCollection() {
    if (!selectedCollection || !selectedSpace) {
      return;
    }
    setError(null);
    try {
      const latestRun = await getLatestWorkspaceEnrichmentRunForSpaceV3(selectedSpace.id);
      if (latestRun && (latestRun.status === "queued" || latestRun.status === "running")) {
        collectionEnrichment.beginMonitoring(latestRun);
        return;
      }
      await collectionEnrichment.startRun(() =>
        enrichWorkspaceCollectionV3(selectedCollection.id, { include_sources: settings.enrichmentSources })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enrich collection.");
    }
  }

  async function handleAcceptSuggestions() {
    if (!selectedCollection) {
      return;
    }
    setError(null);
    try {
      await acceptWorkspaceCollectionSuggestionsV3(selectedCollection.id);
      await loadOverview();
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept suggestions.");
    }
  }

  async function handleRejectSuggestions() {
    if (!selectedCollection) {
      return;
    }
    setError(null);
    try {
      await rejectWorkspaceCollectionSuggestionsV3(selectedCollection.id);
      await loadOverview();
      await loadRows(selectedCollection);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject suggestions.");
    }
  }

  const hasActiveCollectionRun =
    collectionEnrichment.run?.status === "queued" || collectionEnrichment.run?.status === "running";

  return (
    <div className="stackLg routeFade">
      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="grid gap-3 xl:grid-cols-[220px_260px_minmax(0,1fr)]">
        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Spaces</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? <p className="subtle">Loading spaces...</p> : null}
            <div className="grid gap-2 rounded-lg border border-border/70 p-3">
              <Input
                placeholder="New space name"
                value={newSpace.name}
                onChange={(event) => setNewSpace((current) => ({ ...current, name: event.target.value }))}
              />
              <Input
                placeholder="Description"
                value={newSpace.description}
                onChange={(event) => setNewSpace((current) => ({ ...current, description: event.target.value }))}
              />
              <Button type="button" variant="outline" onClick={() => void handleCreateSpace()}>
                Create space
              </Button>
            </div>
            {spaces.map((space) => (
              <div key={space.id} className="rounded-lg border border-border/70 p-2">
                <Link
                  href={`/app/spaces/${space.slug}`}
                  className={`treeNodeButton ${space.slug === spaceSlug ? "active" : ""}`}
                >
                  <span>{space.name}</span>
                  <span className="muted">{space.row_count}</span>
                </Link>
                {space.slug === spaceSlug ? (
                  <div className="mt-2 grid gap-2">
                    <Input
                      defaultValue={space.name}
                      className="h-8"
                      onBlur={(event) => void handleUpdateSpace(space.id, { name: event.target.value })}
                    />
                    <Input
                      defaultValue={space.description ?? ""}
                      className="h-8"
                      placeholder="Space description"
                      onBlur={(event) =>
                        void handleUpdateSpace(space.id, { description: event.target.value || null })
                      }
                    />
                    <Button
                      type="button"
                      variant="destructive"
                      className="h-8"
                      onClick={() => void handleDeleteSpace(space.id, space.slug, space.name)}
                    >
                      Delete space
                    </Button>
                  </div>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Tables</CardTitle>
            <CardDescription>
              {selectedSpace ? `${selectedSpace.name} workspace` : "Select a space"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2">
              <Input
                placeholder="New table name"
                value={newCollection.name}
                onChange={(event) => setNewCollection((current) => ({ ...current, name: event.target.value }))}
              />
              <Input
                placeholder="Description"
                value={newCollection.description}
                onChange={(event) =>
                  setNewCollection((current) => ({ ...current, description: event.target.value }))
                }
              />
              <Button type="button" onClick={() => void handleCreateCollection()} disabled={!selectedSpace}>
                Create table
              </Button>
            </div>

            {(overview?.collections ?? []).map((collection) => (
              <Link
                key={collection.id}
                href={`/app/spaces/${spaceSlug}/${collection.slug}`}
                className={`treeNodeButton ${selectedCollection?.id === collection.id ? "active" : ""}`}
              >
                <span>{collection.name}</span>
                <span className="muted">
                  {collection.row_count}
                  {collection.pending_suggestion_count > 0 ? ` • ${collection.pending_suggestion_count} pending` : ""}
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle className="text-xl">Workspace</CardTitle>
                <CardDescription>
                  {selectedCollection ? `${selectedCollection.name} table` : "Select a table"}
                </CardDescription>
              </div>
              {selectedCollection ? (
                <div className="flex items-center gap-2">
                  {selectedCollection.pending_suggestion_count > 0 ? (
                    <span className="tag border-amber-300 bg-amber-100 text-amber-900">
                      {selectedCollection.pending_suggestion_count} pending
                    </span>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleEnrichCollection()}
                    disabled={collectionEnrichment.isStartingRun || hasActiveCollectionRun}
                  >
                    {collectionEnrichment.isStartingRun ? "Starting..." : "Refresh enrichment"}
                  </Button>
                  {hasActiveCollectionRun ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void collectionEnrichment.refreshStatus()}
                      disabled={collectionEnrichment.isStartingRun}
                    >
                      Refresh status
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
            {collectionEnrichment.statusMessage ? (
              <p className="text-xs text-muted-foreground">{collectionEnrichment.statusMessage}</p>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedCollection ? (
              <>
                {rowsPayload && rowsPayload.pending_suggestion_count > 0 ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-sm">
                    <span className="font-medium text-amber-900">
                      {rowsPayload.pending_suggestion_count} pending suggestions
                    </span>
                    <Button type="button" variant="outline" className="h-8" onClick={() => void handleAcceptSuggestions()}>
                      Accept all suggestions
                    </Button>
                    <Button type="button" variant="outline" className="h-8" onClick={() => void handleRejectSuggestions()}>
                      Reject all suggestions
                    </Button>
                  </div>
                ) : null}

                <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                  <Input
                    defaultValue={selectedCollection.name}
                    onBlur={(event) => void handleRenameCollection(selectedCollection.id, event.target.value)}
                  />
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-muted-foreground">
                      {selectedCollection.row_count} rows • updated {formatTimestamp(selectedCollection.updated_at)}
                    </p>
                    <Button
                      type="button"
                      variant="destructive"
                      className="h-8"
                      onClick={() => void handleDeleteCollection(selectedCollection.id)}
                    >
                      Delete table
                    </Button>
                  </div>
                </div>

                <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_140px_auto]">
                  <Input
                    placeholder="New column"
                    value={newColumn.label}
                    onChange={(event) => setNewColumn((current) => ({ ...current, label: event.target.value }))}
                  />
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={newColumn.data_type}
                    onChange={(event) =>
                      setNewColumn((current) => ({ ...current, data_type: event.target.value }))
                    }
                  >
                    <option value="text">Text</option>
                    <option value="url">URL</option>
                    <option value="number">Number</option>
                  </select>
                  <Button type="button" variant="outline" onClick={() => void handleCreateColumn()}>
                    Add column
                  </Button>
                </div>

                <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={selectedEntityId}
                    onChange={(event) => setSelectedEntityId(event.target.value)}
                  >
                    <option value="">Add existing space row...</option>
                    {addableEntities.map((item) => (
                      <option key={item.row.entity_id} value={item.row.entity_id}>
                        {item.row.title} ({item.collection_name})
                      </option>
                    ))}
                  </select>
                  <Button type="button" variant="outline" onClick={() => void handleCreateRow()}>
                    Add row
                  </Button>
                </div>

                {loadingRows ? <p className="subtle">Loading rows...</p> : null}
                {!loadingRows && !rowsPayload ? (
                  <p className="subtle">
                    {hasActiveCollectionRun ? "Workspace updating. Rows will appear when sync finishes." : "No rows yet."}
                  </p>
                ) : null}
                {!loadingRows && rowsPayload ? (
                  <div className="overflow-x-auto rounded-xl border border-border/70">
                    <table className="w-full min-w-[860px] text-sm">
                      <thead className="bg-muted/30">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">Name</th>
                          {rowsPayload.columns
                            .filter((column) => column.key !== "title")
                            .map((column) => (
                              <th key={column.id} className="px-3 py-2 text-left font-medium">
                                <div className="flex items-center gap-2">
                                  <Input
                                    defaultValue={column.label}
                                    className="h-8"
                                    onBlur={(event) => void handleRenameColumn(column.id, event.target.value)}
                                  />
                                  <Button
                                    type="button"
                                    variant="outline"
                                    className="h-8 px-2"
                                    onClick={() => void handleMoveColumn(column.id, -1)}
                                  >
                                    ↑
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    className="h-8 px-2"
                                    onClick={() => void handleMoveColumn(column.id, 1)}
                                  >
                                    ↓
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    className="h-8 px-2"
                                    onClick={() => void handleDeleteColumn(column.id)}
                                  >
                                    X
                                  </Button>
                                </div>
                              </th>
                            ))}
                          <th className="px-3 py-2 text-left font-medium">Updated</th>
                          <th className="px-3 py-2 text-left font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rowsPayload.rows.map((row) => (
                          <tr key={row.id} className="border-t border-border/70">
                            <td className="px-3 py-2 align-top">
                              <Link
                                href={`/app/spaces/${spaceSlug}/${selectedCollection.slug}/${row.id}`}
                                className="font-medium hover:underline"
                              >
                                {row.title}
                              </Link>
                              {row.summary ? <p className="subtle mt-1 text-xs">{row.summary}</p> : null}
                            </td>
                            {row.cells.map((cell) => (
                              <td key={`${row.id}-${cell.column_id}`} className="px-3 py-2 align-top">
                                <Input
                                  defaultValue={cell.display_value ?? ""}
                                  className="h-8"
                                  placeholder={cell.label}
                                  onBlur={(event) =>
                                    void handleUpdateCell(row.id, cell.column_id, event.target.value)
                                  }
                                />
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {cell.source_kind ? (
                                    <span className="tag">{cell.source_kind}</span>
                                  ) : (
                                    <span className="tag">missing</span>
                                  )}
                                  {cell.sources.length > 0 ? <span className="tag">{cell.sources.length} sources</span> : null}
                                  {cell.pending_suggestion_count > 0 ? (
                                    <span className="tag border-amber-300 bg-amber-100 text-amber-900">
                                      {cell.pending_suggestion_count} pending
                                    </span>
                                  ) : null}
                                </div>
                                {cell.pending_suggestions.length > 0 ? (
                                  <div className="mt-2 rounded-md border border-amber-300/60 bg-amber-50 p-2 text-xs text-amber-900">
                                    Suggested: {cell.pending_suggestions[0]?.suggested_display_value ?? "Pending value"}
                                  </div>
                                ) : null}
                              </td>
                            ))}
                            <td className="px-3 py-2 align-top text-xs text-muted-foreground">
                              {formatTimestamp(row.updated_at)}
                            </td>
                            <td className="px-3 py-2 align-top">
                              <div className="flex gap-2">
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="h-8 px-2"
                                  onClick={() => void handleMoveRow(row.id, -1)}
                                >
                                  ↑
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="h-8 px-2"
                                  onClick={() => void handleMoveRow(row.id, 1)}
                                >
                                  ↓
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="h-8"
                                  onClick={() => void handleDeleteRow(row.id)}
                                >
                                  Delete
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="subtle">Select or create a table to begin.</p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
