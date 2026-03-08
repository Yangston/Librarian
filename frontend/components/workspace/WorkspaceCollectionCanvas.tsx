"use client";

import Link from "next/link";
import {
  ArrowDown,
  ArrowUp,
  ChevronRight,
  ExternalLink,
  Filter,
  FolderKanban,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Trash2
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type WorkspaceCollectionRead,
  type WorkspaceRowRead,
  type WorkspaceRowsResponse,
  type WorkspaceSpaceRead
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

type WorkspaceCollectionCanvasProps = {
  spaceSlug: string;
  selectedSpace: WorkspaceSpaceRead | null;
  selectedCollection: WorkspaceCollectionRead | null;
  rowsPayload: WorkspaceRowsResponse | null;
  filteredRows: WorkspaceRowRead[];
  loadingRows: boolean;
  quickFilter: string;
  onQuickFilterChange: (value: string) => void;
  onOpenAddRow: () => void;
  onOpenSchema: () => void;
  onOpenManageTable: () => void;
  onToggleInspector: () => void;
  onRefreshEnrichment: () => void;
  onRefreshStatus: () => void;
  onAcceptSuggestions: () => void;
  onRejectSuggestions: () => void;
  onDeleteRow: (rowId: number) => void;
  onMoveRow: (rowId: number, direction: -1 | 1) => void;
  onUpdateCell: (rowId: number, columnId: number, value: string) => void;
  hasActiveCollectionRun: boolean;
  statusMessage: string | null;
  isStartingRun: boolean;
  inspectorVisible: boolean;
  isMobile: boolean;
};

function formatCellMeta(cell: WorkspaceRowRead["cells"][number]) {
  const segments = [];
  segments.push(cell.source_kind ? cell.source_kind : "missing");
  if (cell.sources.length > 0) {
    segments.push(`${cell.sources.length} source${cell.sources.length === 1 ? "" : "s"}`);
  }
  if (cell.pending_suggestion_count > 0) {
    segments.push(`${cell.pending_suggestion_count} pending`);
  }
  return segments.join(" - ");
}

export function WorkspaceCollectionCanvas({
  spaceSlug,
  selectedSpace,
  selectedCollection,
  rowsPayload,
  filteredRows,
  loadingRows,
  quickFilter,
  onQuickFilterChange,
  onOpenAddRow,
  onOpenSchema,
  onOpenManageTable,
  onToggleInspector,
  onRefreshEnrichment,
  onRefreshStatus,
  onAcceptSuggestions,
  onRejectSuggestions,
  onDeleteRow,
  onMoveRow,
  onUpdateCell,
  hasActiveCollectionRun,
  statusMessage,
  isStartingRun,
  inspectorVisible,
  isMobile
}: WorkspaceCollectionCanvasProps) {
  const columns = rowsPayload?.columns.filter((column) => column.key !== "title") ?? [];

  if (!selectedSpace) {
    return (
      <section className="spacesCanvasStack routeFade">
        <div className="spacesCanvasPanel spacesEmptyHero">
          <FolderKanban className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-xl font-semibold tracking-tight">No space selected</h2>
            <p className="subtle mt-1">Select a space from the rail to open its workspace.</p>
          </div>
        </div>
      </section>
    );
  }

  if (!selectedCollection) {
    return (
      <section className="spacesCanvasStack routeFade">
        <div className="spacesCanvasPanel spacesHero">
          <div className="spacesBreadcrumbs">
            <span>Spaces</span>
            <ChevronRight className="h-4 w-4" />
            <span>{selectedSpace.name}</span>
          </div>
          <div className="space-y-3">
            <div>
              <h1 className="spacesHeroTitle">{selectedSpace.name}</h1>
              <p className="spacesHeroDescription">
                {selectedSpace.description ?? "Choose a table or create a new one to begin focused work."}
              </p>
            </div>
            <div className="spacesMetricGrid">
              <article className="spacesMetric">
                <span>Tables</span>
                <strong>{selectedSpace.collection_count}</strong>
              </article>
              <article className="spacesMetric">
                <span>Rows</span>
                <strong>{selectedSpace.row_count}</strong>
              </article>
              <article className="spacesMetric">
                <span>Updated</span>
                <strong className="text-base">{formatTimestamp(selectedSpace.updated_at)}</strong>
              </article>
            </div>
          </div>
        </div>
        <div className="spacesCanvasPanel spacesEmptyHero">
          <Plus className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Create or choose a table</h2>
            <p className="subtle mt-1">
              The active space is ready, but the main canvas stays clean until a table is selected.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="spacesCanvasStack routeFade">
      <div className="spacesCanvasPanel spacesHero">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="spacesBreadcrumbs">
              <Link href="/app/spaces">Spaces</Link>
              <ChevronRight className="h-4 w-4" />
              <Link href={`/app/spaces/${selectedSpace.slug}`}>{selectedSpace.name}</Link>
              <ChevronRight className="h-4 w-4" />
              <span>{selectedCollection.name}</span>
            </div>
            <div>
              <h1 className="spacesHeroTitle">{selectedCollection.name}</h1>
              <p className="spacesHeroDescription">
                {selectedCollection.description ??
                  "A calm table view for editing rows, reviewing enrichment, and moving quickly across the current workspace."}
              </p>
            </div>
          </div>

          <div className="spacesHeroActions">
            {isMobile || !inspectorVisible ? (
              <Button type="button" variant="outline" onClick={onOpenManageTable}>
                <Settings2 className="h-4 w-4" />
                {isMobile ? "Manage" : "Table settings"}
              </Button>
            ) : null}
            <Button type="button" variant="outline" onClick={onOpenSchema}>
              <Filter className="h-4 w-4" />
              Schema
            </Button>
            {!isMobile ? (
              <Button type="button" variant="outline" onClick={onToggleInspector}>
                {inspectorVisible ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
                {inspectorVisible ? "Hide inspector" : "Show inspector"}
              </Button>
            ) : null}
            <Button
              type="button"
              onClick={onRefreshEnrichment}
              disabled={isStartingRun || hasActiveCollectionRun}
            >
              <Sparkles className="h-4 w-4" />
              {isStartingRun ? "Starting..." : "Refresh enrichment"}
            </Button>
            {hasActiveCollectionRun ? (
              <Button type="button" variant="outline" onClick={onRefreshStatus} disabled={isStartingRun}>
                <RefreshCw className="h-4 w-4" />
                Refresh status
              </Button>
            ) : null}
          </div>
        </div>

        <div className="spacesMetricGrid">
          <article className="spacesMetric">
            <span>Rows</span>
            <strong>{selectedCollection.row_count}</strong>
          </article>
          <article className="spacesMetric">
            <span>Fields</span>
            <strong>{selectedCollection.column_count}</strong>
          </article>
          <article className="spacesMetric">
            <span>Updated</span>
            <strong className="text-base">{formatTimestamp(selectedCollection.updated_at)}</strong>
          </article>
          <article className="spacesMetric">
            <span>Status</span>
            <strong className="text-base">
              {hasActiveCollectionRun ? "Enriching" : selectedCollection.pending_suggestion_count > 0 ? "Needs review" : "Ready"}
            </strong>
          </article>
        </div>

        {statusMessage ? <p className="subtle text-sm">{statusMessage}</p> : null}
      </div>

      {rowsPayload && rowsPayload.pending_suggestion_count > 0 ? (
        <div className="spacesReviewStrip">
          <div className="min-w-0">
            <p className="font-medium text-amber-950">
              {rowsPayload.pending_suggestion_count} pending suggestion
              {rowsPayload.pending_suggestion_count === 1 ? "" : "s"}
            </p>
            <p className="text-sm text-amber-900/80">
              Review and clear suggestions without opening the schema or row inspector.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" className="border-amber-300 bg-white/80" onClick={onAcceptSuggestions}>
              Accept all
            </Button>
            <Button type="button" variant="outline" className="border-amber-300 bg-white/80" onClick={onRejectSuggestions}>
              Reject all
            </Button>
          </div>
        </div>
      ) : null}

      <div className="spacesCanvasPanel">
        <div className="spacesCommandBar">
          <div className="spacesQuickFilter">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Input
              value={quickFilter}
              onChange={(event) => onQuickFilterChange(event.target.value)}
              placeholder="Quick filter rows, summaries, and visible values..."
              className="border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">
              {filteredRows.length} visible of {rowsPayload?.rows.length ?? 0}
            </Badge>
            <Button type="button" onClick={onOpenAddRow}>
              <Plus className="h-4 w-4" />
              Add row
            </Button>
            <Button type="button" variant="outline" onClick={onOpenSchema}>
              Schema
            </Button>
          </div>
        </div>

        {loadingRows ? (
          <div className="spacesTableState">
            <p className="subtle">Loading rows...</p>
          </div>
        ) : !rowsPayload ? (
          <div className="spacesTableState">
            <p className="subtle">
              {hasActiveCollectionRun ? "Workspace updating. Rows will appear when sync finishes." : "No rows yet."}
            </p>
          </div>
        ) : filteredRows.length === 0 ? (
          <div className="spacesTableState">
            <p className="subtle">
              {rowsPayload.rows.length === 0
                ? "No rows yet. Add an existing library row to start shaping this table."
                : "No rows match the current quick filter."}
            </p>
          </div>
        ) : (
          <div className="spacesDataCard">
            <div className="spacesTableWrap">
              <table className="spacesTable">
                <thead>
                  <tr>
                    <th>Name</th>
                    {columns.map((column) => (
                      <th key={column.id}>{column.label}</th>
                    ))}
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr key={row.id}>
                      <td className="align-top">
                        <div className="spacesRowTitle">
                          <Link href={`/app/spaces/${spaceSlug}/${selectedCollection.slug}/${row.id}`} className="font-medium">
                            {row.title}
                          </Link>
                          <Button asChild variant="ghost" size="icon" className="h-8 w-8">
                            <Link
                              href={`/app/spaces/${spaceSlug}/${selectedCollection.slug}/${row.id}`}
                              aria-label={`Open ${row.title}`}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Link>
                          </Button>
                        </div>
                        {row.summary ? <p className="spacesRowSummary">{row.summary}</p> : null}
                      </td>
                      {row.cells.map((cell) => (
                        <td key={`${row.id}-${cell.column_id}`} className="align-top">
                          <Input
                            defaultValue={cell.display_value ?? ""}
                            className="spacesCellInput"
                            placeholder={cell.label}
                            onBlur={(event) => onUpdateCell(row.id, cell.column_id, event.target.value)}
                          />
                          <p className="spacesCellMeta">{formatCellMeta(cell)}</p>
                          {cell.pending_suggestions.length > 0 ? (
                            <div className="spacesSuggestionHint">
                              Suggested: {cell.pending_suggestions[0]?.suggested_display_value ?? "Pending value"}
                            </div>
                          ) : null}
                        </td>
                      ))}
                      <td className="align-top text-sm text-muted-foreground">{formatTimestamp(row.updated_at)}</td>
                      <td className="align-top">
                        <div className="spacesRowActions">
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => onMoveRow(row.id, -1)}
                            aria-label={`Move ${row.title} up`}
                          >
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => onMoveRow(row.id, 1)}
                            aria-label={`Move ${row.title} down`}
                          >
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 border-destructive/35 bg-destructive/5 text-destructive hover:bg-destructive hover:text-destructive-foreground dark:border-destructive/45 dark:bg-destructive/10"
                            onClick={() => onDeleteRow(row.id)}
                            aria-label={`Delete ${row.title}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
