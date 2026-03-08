"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAppSettings } from "@/components/AppSettingsProvider";
import {
  enrichWorkspaceRowV3,
  getWorkspaceRowV3,
  type WorkspaceRowDetailRead,
  updateWorkspaceCellV3,
  updateWorkspaceRowV3
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { useWorkspaceEnrichmentMonitor } from "@/lib/use-workspace-enrichment-monitor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function WorkspaceRowDetailPage() {
  const { settings } = useAppSettings();
  const params = useParams<{ space_slug: string; collection_slug: string; row_id: string }>();
  const rowId = Number.parseInt(params.row_id, 10);
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

      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-2xl">{row.title}</CardTitle>
              <CardDescription>
                <Link href={`/app/spaces/${params.space_slug}/${row.collection_slug}`} className="hover:underline">
                  {row.collection_name}
                </Link>{" "}
                • updated {formatTimestamp(row.updated_at)}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => void enrichRow()}
                disabled={rowEnrichment.isStartingRun || hasActiveRowRun}
              >
                {rowEnrichment.isStartingRun ? "Starting..." : "Refresh enrichment"}
              </Button>
              {hasActiveRowRun ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void rowEnrichment.refreshStatus()}
                  disabled={rowEnrichment.isStartingRun}
                >
                  Refresh status
                </Button>
              ) : null}
            </div>
          </div>
          {rowEnrichment.statusMessage ? (
            <p className="text-xs text-muted-foreground">{rowEnrichment.statusMessage}</p>
          ) : null}
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-4">
            <div className="grid gap-2">
              <label className="field">
                <span className="text-sm font-medium">Title</span>
                <Input defaultValue={row.title} onBlur={(event) => void saveRowField({ title: event.target.value })} />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Summary</span>
                <Textarea
                  defaultValue={row.summary ?? ""}
                  rows={3}
                  onBlur={(event) => void saveRowField({ summary: event.target.value || null })}
                />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Detail blurb</span>
                <Textarea
                  defaultValue={row.detail_blurb ?? ""}
                  rows={3}
                  onBlur={(event) => void saveRowField({ detail_blurb: event.target.value || null })}
                />
              </label>
              <label className="field">
                <span className="text-sm font-medium">Notes</span>
                <Textarea
                  defaultValue={row.notes_markdown ?? ""}
                  rows={8}
                  onBlur={(event) => void saveRowField({ notes_markdown: event.target.value || null })}
                />
              </label>
            </div>

            <Card className="border-border/70 bg-background/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Properties</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {row.cells.map((cell) => (
                  <article key={cell.column_id} className="rounded-lg border border-border/70 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{cell.label}</p>
                      <div className="flex gap-1">
                        <span className="tag">{cell.source_kind ?? "missing"}</span>
                        {cell.confidence !== null ? <span className="tag">{Math.round(cell.confidence * 100)}%</span> : null}
                        {cell.pending_suggestion_count > 0 ? (
                          <span className="tag border-amber-300 bg-amber-100 text-amber-900">
                            {cell.pending_suggestion_count} pending
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <Input
                      className="mt-2"
                      defaultValue={cell.display_value ?? ""}
                      placeholder={cell.label}
                      onBlur={(event) => void saveCell(cell.column_id, event.target.value)}
                    />
                    {cell.sources.length > 0 ? (
                      <div className="mt-2 space-y-2 text-xs text-muted-foreground">
                        {cell.sources.map((source) => (
                          <div key={source.id} className="rounded-md border border-border/60 bg-muted/30 p-2">
                            <p className="font-medium text-foreground">{source.title ?? source.uri ?? "Source"}</p>
                            {source.uri ? (
                              <a href={source.uri} target="_blank" rel="noreferrer" className="hover:underline">
                                {source.uri}
                              </a>
                            ) : null}
                            {source.snippet ? <p className="mt-1">{source.snippet}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {cell.pending_suggestions.length > 0 ? (
                      <div className="mt-2 rounded-md border border-amber-300/60 bg-amber-50 p-2 text-xs text-amber-900">
                        Suggested: {cell.pending_suggestions[0]?.suggested_display_value ?? "Pending value"}
                      </div>
                    ) : null}
                  </article>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <Card className="border-border/70 bg-background/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">
                  Relations
                  {row.pending_relation_suggestion_count > 0 ? ` (${row.pending_relation_suggestion_count} pending)` : ""}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {row.relations.length === 0 ? <p className="subtle">No relations yet.</p> : null}
                {row.relations.map((relation) => (
                  <article key={relation.id} className="rounded-lg border border-border/70 p-3">
                    <p className="font-medium">
                      {relation.direction} • {relation.relation_label}
                    </p>
                    <p className="subtle mt-1">{relation.other_row_title}</p>
                    <div className="mt-2 flex gap-1">
                      <span className="tag">{relation.source_kind}</span>
                      {relation.suggested ? (
                        <span className="tag border-amber-300 bg-amber-100 text-amber-900">pending</span>
                      ) : null}
                      {relation.confidence !== null ? (
                        <span className="tag">{Math.round(relation.confidence * 100)}%</span>
                      ) : null}
                    </div>
                  </article>
                ))}
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
