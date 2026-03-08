"use client";

import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { useAppSettings } from "@/components/AppSettingsProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  acceptWorkspaceCollectionSuggestionsV3,
  createWorkspaceCollectionV3,
  createWorkspaceColumnV3,
  createWorkspaceRowV3,
  createWorkspaceSpaceV3,
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
  rejectWorkspaceCollectionSuggestionsV3,
  updateWorkspaceCellV3,
  updateWorkspaceCollectionV3,
  updateWorkspaceColumnV3,
  updateWorkspaceRowV3,
  updateWorkspaceSpaceV3,
  type WorkspaceCatalogRow,
  type WorkspaceCollectionRead,
  type WorkspaceOverviewResponse,
  type WorkspaceRowsResponse,
  type WorkspaceSpaceRead
} from "@/lib/api";
import { useWorkspaceEnrichmentMonitor } from "@/lib/use-workspace-enrichment-monitor";
import { cn } from "@/lib/utils";

import { WorkspaceCollectionCanvas } from "./WorkspaceCollectionCanvas";
import { WorkspaceInspector, type WorkspaceInspectorMode } from "./WorkspaceInspector";
import { WorkspaceNavigationRail } from "./WorkspaceNavigationRail";

type WorkspaceShellProps = {
  spaceSlug: string;
  collectionSlug?: string;
};

export function WorkspaceShell({ spaceSlug, collectionSlug }: WorkspaceShellProps) {
  const router = useRouter();
  const isMobile = useIsMobile();
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
  const [selectedEntityId, setSelectedEntityId] = useState("");
  const [quickFilter, setQuickFilter] = useState("");
  const [inspectorMode, setInspectorMode] = useState<WorkspaceInspectorMode>("table");
  const [inspectorVisible, setInspectorVisible] = useState(true);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [inspectorSheetOpen, setInspectorSheetOpen] = useState(false);
  const [createSpaceOpen, setCreateSpaceOpen] = useState(false);
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false);
  const [addRowOpen, setAddRowOpen] = useState(false);

  const deferredQuickFilter = useDeferredValue(quickFilter);

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

  useEffect(() => {
    setQuickFilter("");
    setSelectedEntityId("");
    if (!selectedCollection) {
      setInspectorMode("space");
    } else if (inspectorMode === "space") {
      setInspectorMode("table");
    }
  }, [selectedCollection?.id]);

  useEffect(() => {
    if (isMobile) {
      setInspectorVisible(false);
      setInspectorSheetOpen(false);
      setRailCollapsed(false);
    }
  }, [isMobile]);

  const addableEntities = useMemo(() => {
    const existingEntityIds = new Set((rowsPayload?.rows ?? []).map((row) => row.entity_id));
    return library.filter((item) => !existingEntityIds.has(item.row.entity_id));
  }, [library, rowsPayload?.rows]);

  const filteredRows = useMemo(() => {
    const query = deferredQuickFilter.trim().toLowerCase();
    const rows = rowsPayload?.rows ?? [];
    if (!query) {
      return rows;
    }

    return rows.filter((row) => {
      const haystack = [
        row.title,
        row.summary ?? "",
        row.detail_blurb ?? "",
        ...row.cells.map((cell) => `${cell.label} ${cell.display_value ?? ""}`)
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [deferredQuickFilter, rowsPayload?.rows]);

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
      setCreateCollectionOpen(false);
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
      setCreateSpaceOpen(false);
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
      const updated = await updateWorkspaceSpaceV3(spaceId, {
        name: payload.name?.trim(),
        description: payload.description ?? undefined
      });
      const spacesData = await getWorkspaceSpacesV3();
      setSpaces(spacesData);
      if (selectedSpace?.id === spaceId) {
        await loadOverview(spacesData.find((item) => item.id === spaceId) ?? null);
        if (updated.slug !== spaceSlug) {
          router.replace(
            selectedCollection ? `/app/spaces/${updated.slug}/${selectedCollection.slug}` : `/app/spaces/${updated.slug}`
          );
        }
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

  async function handleUpdateCollection(collectionId: number, payload: { name?: string; description?: string | null }) {
    if (payload.name !== undefined && !payload.name.trim()) {
      return;
    }
    setError(null);
    try {
      const updated = await updateWorkspaceCollectionV3(collectionId, {
        name: payload.name?.trim(),
        description: payload.description ?? undefined
      });
      await loadOverview();
      if (selectedCollection?.id === collectionId && updated.slug !== collectionSlug) {
        router.replace(`/app/spaces/${spaceSlug}/${updated.slug}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update collection.");
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
      setAddRowOpen(false);
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

  function openInspector(mode: WorkspaceInspectorMode) {
    setInspectorMode(mode);
    if (isMobile) {
      setInspectorSheetOpen(true);
    } else {
      setInspectorVisible(true);
    }
  }

  const hasActiveCollectionRun =
    collectionEnrichment.run?.status === "queued" || collectionEnrichment.run?.status === "running";

  const inspectorContent = (
    <WorkspaceInspector
      mode={inspectorMode}
      onModeChange={setInspectorMode}
      selectedSpace={selectedSpace}
      selectedCollection={selectedCollection}
      rowsPayload={rowsPayload}
      newColumn={newColumn}
      onNewColumnChange={setNewColumn}
      onCreateColumn={() => void handleCreateColumn()}
      onUpdateSpace={(spaceId, payload) => void handleUpdateSpace(spaceId, payload)}
      onDeleteSpace={(spaceId, slug, name) => void handleDeleteSpace(spaceId, slug, name)}
      onUpdateCollection={(collectionId, payload) => void handleUpdateCollection(collectionId, payload)}
      onDeleteCollection={(collectionId) => void handleDeleteCollection(collectionId)}
      onRenameColumn={(columnId, label) => void handleRenameColumn(columnId, label)}
      onDeleteColumn={(columnId) => void handleDeleteColumn(columnId)}
      onMoveColumn={(columnId, direction) => void handleMoveColumn(columnId, direction)}
      statusMessage={collectionEnrichment.statusMessage}
    />
  );

  return (
    <div className="stackLg">
      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div
        className={cn(
          "spacesLayout",
          !isMobile && !inspectorVisible && "spacesLayoutInspectorHidden",
          !isMobile && railCollapsed && "spacesLayoutRailCollapsed"
        )}
      >
        <WorkspaceNavigationRail
          loading={loading}
          spaces={spaces}
          collections={overview?.collections ?? []}
          selectedSpace={selectedSpace}
          selectedCollection={selectedCollection}
          collapsed={railCollapsed}
          onToggleCollapse={() => setRailCollapsed((current) => !current)}
          isMobile={isMobile}
          onOpenCreateSpace={() => setCreateSpaceOpen(true)}
          onOpenCreateCollection={() => setCreateCollectionOpen(true)}
        />

        <WorkspaceCollectionCanvas
          spaceSlug={spaceSlug}
          selectedSpace={selectedSpace}
          selectedCollection={selectedCollection}
          rowsPayload={rowsPayload}
          filteredRows={filteredRows}
          loadingRows={loadingRows}
          quickFilter={quickFilter}
          onQuickFilterChange={setQuickFilter}
          onOpenAddRow={() => setAddRowOpen(true)}
          onOpenSchema={() => openInspector("schema")}
          onOpenManageTable={() => openInspector(selectedCollection ? "table" : "space")}
          onToggleInspector={() => setInspectorVisible((current) => !current)}
          onRefreshEnrichment={() => void handleEnrichCollection()}
          onRefreshStatus={() => void collectionEnrichment.refreshStatus()}
          onAcceptSuggestions={() => void handleAcceptSuggestions()}
          onRejectSuggestions={() => void handleRejectSuggestions()}
          onDeleteRow={(rowId) => void handleDeleteRow(rowId)}
          onMoveRow={(rowId, direction) => void handleMoveRow(rowId, direction)}
          onUpdateCell={(rowId, columnId, value) => void handleUpdateCell(rowId, columnId, value)}
          hasActiveCollectionRun={hasActiveCollectionRun}
          statusMessage={collectionEnrichment.statusMessage}
          isStartingRun={collectionEnrichment.isStartingRun}
          inspectorVisible={inspectorVisible}
          isMobile={isMobile}
        />

        {!isMobile && inspectorVisible ? <aside className="rowDetailInspector">{inspectorContent}</aside> : null}
      </div>

      <Sheet open={createSpaceOpen} onOpenChange={setCreateSpaceOpen}>
        <SheetContent side="right" className="w-[92vw] space-y-5 overflow-y-auto sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Create space</SheetTitle>
            <SheetDescription>Start a new focused container for related tables and work.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-3">
            <Input
              placeholder="Space name"
              value={newSpace.name}
              onChange={(event) => setNewSpace((current) => ({ ...current, name: event.target.value }))}
            />
            <Textarea
              rows={4}
              placeholder="Description"
              value={newSpace.description}
              onChange={(event) => setNewSpace((current) => ({ ...current, description: event.target.value }))}
            />
          </div>
          <SheetFooter>
            <SheetClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </SheetClose>
            <Button type="button" onClick={() => void handleCreateSpace()}>
              Create space
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={createCollectionOpen} onOpenChange={setCreateCollectionOpen}>
        <SheetContent side="right" className="w-[92vw] space-y-5 overflow-y-auto sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Create table</SheetTitle>
            <SheetDescription>
              Add a new table to {selectedSpace?.name ?? "the current space"} without cluttering the main view.
            </SheetDescription>
          </SheetHeader>
          <div className="grid gap-3">
            <Input
              placeholder="Table name"
              value={newCollection.name}
              onChange={(event) => setNewCollection((current) => ({ ...current, name: event.target.value }))}
            />
            <Textarea
              rows={4}
              placeholder="Description"
              value={newCollection.description}
              onChange={(event) => setNewCollection((current) => ({ ...current, description: event.target.value }))}
            />
          </div>
          <SheetFooter>
            <SheetClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </SheetClose>
            <Button type="button" onClick={() => void handleCreateCollection()} disabled={!selectedSpace}>
              Create table
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={addRowOpen} onOpenChange={setAddRowOpen}>
        <SheetContent side="right" className="w-[92vw] space-y-5 overflow-y-auto sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Add row</SheetTitle>
            <SheetDescription>Add an existing library row into the active table.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-3">
            <select
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={selectedEntityId}
              onChange={(event) => setSelectedEntityId(event.target.value)}
            >
              <option value="">Select an existing row...</option>
              {addableEntities.map((item) => (
                <option key={item.row.entity_id} value={item.row.entity_id}>
                  {item.row.title} ({item.collection_name})
                </option>
              ))}
            </select>
            {addableEntities.length === 0 ? (
              <p className="subtle text-sm">No additional library rows are available for this table.</p>
            ) : null}
          </div>
          <SheetFooter>
            <SheetClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </SheetClose>
            <Button type="button" onClick={() => void handleCreateRow()} disabled={!selectedEntityId}>
              Add row
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={inspectorSheetOpen} onOpenChange={setInspectorSheetOpen}>
        <SheetContent side="right" className="w-[94vw] overflow-y-auto sm:max-w-[440px]">
          <SheetHeader className="pb-4">
            <SheetTitle>Workspace inspector</SheetTitle>
            <SheetDescription>Secondary actions stay here so the table remains focused.</SheetDescription>
          </SheetHeader>
          {inspectorContent}
        </SheetContent>
      </Sheet>
    </div>
  );
}
