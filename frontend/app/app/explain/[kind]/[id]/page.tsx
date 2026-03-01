"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  type FactExplainData,
  type RelationExplainData,
  getFactExplain,
  getRelationExplain
} from "../../../../../lib/api";
import { formatTimestamp } from "../../../../../lib/format";
import { Badge } from "../../../../../components/ui/badge";
import { Button } from "../../../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../../../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../../../../components/ui/tabs";

function ExplainHeader({ kind }: { kind: string }) {
  return (
    <Card className="border-border/80 bg-card/95">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-2">
          <Badge variant="secondary">Explain: {kind}</Badge>
          <CardTitle className="text-2xl tracking-tight">Record-level provenance and extraction context.</CardTitle>
          <CardDescription>Inspect snippets, source messages, and schema canonicalization details.</CardDescription>
        </div>
        <Button asChild variant="outline">
          <Link href="/app/search">Back to Search</Link>
        </Button>
      </CardHeader>
    </Card>
  );
}

export default function ExplainRecordPage() {
  const params = useParams<{ kind: string; id: string }>();
  const kind = params.kind;
  const recordId = useMemo(() => Number.parseInt(params.id, 10), [params.id]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [factData, setFactData] = useState<FactExplainData | null>(null);
  const [relationData, setRelationData] = useState<RelationExplainData | null>(null);

  useEffect(() => {
    if (!Number.isFinite(recordId) || recordId < 1) {
      setError("Invalid record id.");
      setLoading(false);
      return;
    }
    if (kind !== "facts" && kind !== "relations") {
      setError("Kind must be 'facts' or 'relations'.");
      setLoading(false);
      return;
    }
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        if (kind === "facts") {
          const data = await getFactExplain(recordId);
          if (active) {
            setFactData(data);
            setRelationData(null);
          }
        } else {
          const data = await getRelationExplain(recordId);
          if (active) {
            setRelationData(data);
            setFactData(null);
          }
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load explainability details.");
        }
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
  }, [kind, recordId]);

  const payload = factData ?? relationData;

  return (
    <div className="space-y-4 routeFade">
      <ExplainHeader kind={kind} />

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Card>
          <CardContent className="py-6 text-muted-foreground">Loading explain data...</CardContent>
        </Card>
      ) : null}

      {!loading && payload ? (
        <>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xl">Record</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {"fact" in payload ? (
                <p>
                  {payload.fact.subject_entity_name} {payload.fact.predicate} {payload.fact.object_value}
                </p>
              ) : (
                <p>
                  {payload.relation.from_entity_name} {payload.relation.relation_type}{" "}
                  {payload.relation.to_entity_name}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Extractor run: {payload.extractor_run_id ?? "-"}</Badge>
                <Badge variant="outline">
                  Confidence:{" "}
                  {"fact" in payload ? payload.fact.confidence.toFixed(2) : payload.relation.confidence.toFixed(2)}
                </Badge>
                <Badge variant="outline">Model: {payload.extraction_metadata?.model_name ?? "-"}</Badge>
                <Badge variant="outline">Prompt: {payload.extraction_metadata?.prompt_version ?? "-"}</Badge>
                <Badge variant="outline">
                  Run at: {formatTimestamp(payload.extraction_metadata?.created_at)}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xl">Canonicalization</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>Observed: {payload.schema_canonicalization.observed_label}</p>
              <p>
                Canonical: {payload.schema_canonicalization.canonical_label ?? "(none)"} (
                {payload.schema_canonicalization.status})
              </p>
              {payload.schema_canonicalization.proposal ? (
                <p>
                  Proposal #{payload.schema_canonicalization.proposal.proposal_id} (
                  {payload.schema_canonicalization.proposal.status}) confidence{" "}
                  {payload.schema_canonicalization.proposal.confidence.toFixed(2)}
                </p>
              ) : (
                <p>Proposal: none</p>
              )}
            </CardContent>
          </Card>

          <Tabs defaultValue="snippets" className="space-y-3">
            <TabsList>
              <TabsTrigger value="snippets">Snippets</TabsTrigger>
              <TabsTrigger value="messages">Source Messages</TabsTrigger>
              <TabsTrigger value="resolution">Resolution Events</TabsTrigger>
            </TabsList>

            <TabsContent value="snippets">
              <Card>
                <CardContent className="py-4">
                  <ul className="simpleList">
                    {payload.snippets.length === 0 ? (
                      <li className="muted">No snippet matches found.</li>
                    ) : (
                      payload.snippets.map((snippet, index) => <li key={`${index}-${snippet}`}>{snippet}</li>)
                    )}
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="messages">
              <Card>
                <CardContent className="py-4">
                  <ul className="simpleList">
                    {payload.source_messages.map((message) => (
                      <li key={message.id}>
                        <strong>{message.role}</strong> #{message.id} at {formatTimestamp(message.timestamp)}
                        <p>{message.content}</p>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="resolution">
              <Card>
                <CardContent className="py-4">
                  <ul className="simpleList">
                    {payload.resolution_events.length === 0 ? (
                      <li className="muted">No related resolution events.</li>
                    ) : (
                      payload.resolution_events.map((event) => (
                        <li key={event.id}>
                          {event.event_type} | entities [{event.entity_ids_json.join(", ")}] | {event.rationale}
                        </li>
                      ))
                    )}
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      ) : null}

      {!loading && !payload && !error ? (
        <Card>
          <CardContent className="py-6 text-muted-foreground">No explain payload found.</CardContent>
        </Card>
      ) : null}
    </div>
  );
}
