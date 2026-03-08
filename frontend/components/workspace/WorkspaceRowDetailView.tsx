"use client";

import Link from "next/link";
import { ChevronRight, ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { useAppSettings } from "@/components/AppSettingsProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  enrichWorkspaceRowV3,
  getWorkspaceRowV3,
  type WorkspaceCellRead,
  type WorkspaceRowDetailRead,
  updateWorkspaceCellV3,
  updateWorkspaceRowV3
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { useWorkspaceEnrichmentMonitor } from "@/lib/use-workspace-enrichment-monitor";

type WorkspaceRowDetailViewProps = {
  rowId: number;
  spaceSlug: string;
  collectionSlug: string;
};

function EvidenceDisclosure({ cell }: { cell: WorkspaceCellRead }) {
  if (cell.sources.length === 0 && cell.pending_suggestions.length === 0) {
    return null;
  }

  return (
    <details className="workspaceDisclosure">
      <summary>
        Review evidence
        {cell.sources.length > 0 ? ` - ${cell.sources.length} source${cell.sources.length === 1 ? "" : "s"}` : ""}
        {cell.pending_suggestions.length > 0
          ? ` - ${cell.pending_suggestions.length} pending suggestion${cell.pending_suggestions.length === 1 ? "" : "s"}`
          : ""}
      </summary>
      <div className="workspaceDisclosureBody">
        {cell.pending_suggestions.length > 0 ? (
          <div className="spacesSuggestionHint">
            Suggested: {cell.pending_suggestions[0]?.suggested_display_value ?? "Pending value"}
          </div>
        ) : null}
        {cell.sources.map((source) => (
          <article key={source.id} className="workspaceEvidenceCard">
            <p className="font-medium text-foreground">{source.title ?? source.uri ?? "Source"}</p>
            {source.uri ? (
              <a href={source.uri} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1">
                <ExternalLink className="h-3.5 w-3.5" />
                {source.uri}
              </a>
            ) : null}
            {source.snippet ? <p className="subtle text-sm">{source.snippet}</p> : null}
          </article>
        ))}
      </div>
    </details>
  );
}

export function WorkspaceRowDetailView({ rowId, spaceSlug, collectionSlug }: WorkspaceRowDetailViewProps) {
  const { settings } = useAppSettings();
  const [row, setRow] = useState<WorkspaceRowDetailRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const rowEnrichment = useWorkspaceEnrichmentMonitor({
    onCompleted: async () => {
      await load();
    },
    onFailed: (message) => {
      setError(message);
    }
  });

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRow(await getWorkspaceRowV3(rowId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load row.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [rowId]);

  async function saveRowField(payload: {
    title?: string;
    summary?: string | null;
    detail_blurb?: string | null;
    notes_markdown?: string | null;
  }) {
    try {
      setRow(await updateWorkspaceRowV3(rowId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update row.");
    }
  }

  async function saveCell(columnId: number, value: string) {
    try {
      setRow(await updateWorkspaceCellV3(rowId, columnId, { display_value: value, value_json: value, status: "manual" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update cell.");
    }
  }

  async function enrichRow() {
    setError(null);
    try {
      await rowEnrichment.startRun(() =>
        enrichWorkspaceRowV3(rowId, { include_sources: settings.enrichmentSources })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enrich row.");
    }
  }

  const hasActiveRowRun = rowEnrichment.run?.status === "queued" || rowEnrichment.run?.status === "running";

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">Loading row...</CardContent>
      </Card>
    );
  }

  if (!row) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">{error ?? "Row not found."}</CardContent>
      </Card>
    );
  }

  return (
    <div className="stackLg routeFade">
      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="rowDetailHero">
        <div className="spacesBreadcrumbs">
          <Link href="/app/spaces">Spaces</Link>
          <ChevronRight className="h-4 w-4" />
          <Link href={`/app/spaces/${spaceSlug}`}>{spaceSlug}</Link>
          <ChevronRight className="h-4 w-4" />
          <Link href={`/app/spaces/${spaceSlug}/${collectionSlug}`}>{row.collection_name}</Link>
          <ChevronRight className="h-4 w-4" />
          <span>{row.title}</span>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div>
              <h1 className="spacesHeroTitle">{row.title}</h1>
              <p className="spacesHeroDescription">
                {row.summary ?? "Edit the essential narrative here, then inspect evidence and relations in the side panel."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{row.collection_name}</Badge>
              <Badge variant="outline">Updated {formatTimestamp(row.updated_at)}</Badge>
              {row.pending_relation_suggestion_count > 0 ? (
                <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">
                  {row.pending_relation_suggestion_count} pending relation
                  {row.pending_relation_suggestion_count === 1 ? "" : "s"}
                </Badge>
              ) : null}
            </div>
          </div>

          <div className="spacesHeroActions">
            <Button type="button" onClick={() => void enrichRow()} disabled={rowEnrichment.isStartingRun || hasActiveRowRun}>
              <Sparkles className="h-4 w-4" />
              {rowEnrichment.isStartingRun ? "Starting..." : "Refresh enrichment"}
            </Button>
            {hasActiveRowRun ? (
              <Button type="button" variant="outline" onClick={() => void rowEnrichment.refreshStatus()}>
                <RefreshCw className="h-4 w-4" />
                Refresh status
              </Button>
            ) : null}
          </div>
        </div>

        {rowEnrichment.statusMessage ? <p className="subtle text-sm">{rowEnrichment.statusMessage}</p> : null}
      </section>

      <section className="rowDetailLayout">
        <div className="space-y-4">
          <div className="spacesCanvasPanel">
            <div className="spacesSectionHeading">
              <span>Essentials</span>
              <Badge variant="secondary">Editable</Badge>
            </div>
            <div className="mt-4 grid gap-4">
              <label className="field">
                <span className="text-sm font-medium">Title</span>
                <Input defaultValue={row.title} onBlur={(event) => void saveRowField({ title: event.target.value })} />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Summary</span>
                <Textarea
                  defaultValue={row.summary ?? ""}
                  rows={4}
                  onBlur={(event) => void saveRowField({ summary: event.target.value || null })}
                />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Detail blurb</span>
                <Textarea
                  defaultValue={row.detail_blurb ?? ""}
                  rows={4}
                  onBlur={(event) => void saveRowField({ detail_blurb: event.target.value || null })}
                />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Notes</span>
                <Textarea
                  defaultValue={row.notes_markdown ?? ""}
                  rows={10}
                  onBlur={(event) => void saveRowField({ notes_markdown: event.target.value || null })}
                />
              </label>
            </div>
          </div>

          <div className="spacesCanvasPanel">
            <div className="spacesSectionHeading">
              <span>Properties</span>
              <Badge variant="secondary">{row.cells.length}</Badge>
            </div>
            <div className="mt-4 grid gap-3">
              {row.cells.map((cell) => (
                <article key={cell.column_id} className="workspaceFieldCard">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{cell.label}</p>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary">{cell.source_kind ?? "missing"}</Badge>
                      {cell.confidence !== null ? <Badge variant="outline">{Math.round(cell.confidence * 100)}%</Badge> : null}
                      {cell.pending_suggestion_count > 0 ? (
                        <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">
                          {cell.pending_suggestion_count} pending
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <Input
                    className="mt-3"
                    defaultValue={cell.display_value ?? ""}
                    placeholder={cell.label}
                    onBlur={(event) => void saveCell(cell.column_id, event.target.value)}
                  />
                  <EvidenceDisclosure cell={cell} />
                </article>
              ))}
            </div>
          </div>
        </div>

        <aside className="rowDetailInspector">
          <div className="spacesInspectorPanel">
            <div className="spacesInspectorCard">
              <div className="spacesSectionHeading">
                <span>Row status</span>
                {hasActiveRowRun ? <Badge variant="secondary">Enriching</Badge> : <Badge variant="secondary">Ready</Badge>}
              </div>
              <p className="subtle text-sm">
                {rowEnrichment.statusMessage ?? "Use enrichment to refresh missing values and relationship evidence."}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div className="spacesInspectorMetric">
                  <span>Properties</span>
                  <strong>{row.cells.length}</strong>
                </div>
                <div className="spacesInspectorMetric">
                  <span>Relations</span>
                  <strong>{row.relations.length}</strong>
                </div>
              </div>
            </div>

            <div className="spacesInspectorCard">
              <div className="spacesSectionHeading">
                <span>Context</span>
                <Badge variant="secondary">{row.collection_name}</Badge>
              </div>
              <p className="subtle text-sm">Updated {formatTimestamp(row.updated_at)}</p>
              {settings.devMode ? (
                <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
                  <p>Row ID: {row.id}</p>
                  <p>Entity ID: {row.entity_id}</p>
                  <p>Collection ID: {row.collection_id}</p>
                </div>
              ) : null}
            </div>

            <div className="spacesInspectorCard">
              <div className="spacesSectionHeading">
                <span>Relations</span>
                {row.pending_relation_suggestion_count > 0 ? (
                  <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">
                    {row.pending_relation_suggestion_count} pending
                  </Badge>
                ) : null}
              </div>
              <div className="mt-3 grid gap-3">
                {row.relations.length === 0 ? <p className="subtle text-sm">No relations yet.</p> : null}
                {row.relations.map((relation) => (
                  <article key={relation.id} className="workspaceFieldCard">
                    <p className="font-medium">
                      {relation.direction} - {relation.relation_label}
                    </p>
                    <p className="subtle text-sm">{relation.other_row_title}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="secondary">{relation.source_kind}</Badge>
                      {relation.suggested ? (
                        <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">pending</Badge>
                      ) : null}
                      {relation.confidence !== null ? <Badge variant="outline">{Math.round(relation.confidence * 100)}%</Badge> : null}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
}
