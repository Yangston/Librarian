"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Filter, Search as SearchIcon } from "lucide-react";

import { type SemanticSearchData, runSemanticSearch } from "../../../lib/api";
import { formatScore, formatTimestamp } from "../../../lib/format";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../../components/ui/tabs";

function toStartTimestamp(dateValue: string): string | undefined {
  if (!dateValue) {
    return undefined;
  }
  return `${dateValue}T00:00:00Z`;
}

function toEndTimestamp(dateValue: string): string | undefined {
  if (!dateValue) {
    return undefined;
  }
  return `${dateValue}T23:59:59Z`;
}

export default function SearchPage() {
  const router = useRouter();
  const [queryDraft, setQueryDraft] = useState("");
  const [conversationScope, setConversationScope] = useState("");
  const [typeLabel, setTypeLabel] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SemanticSearchData | null>(null);

  async function performSearch(params: {
    query: string;
    conversationScope?: string;
    typeLabel?: string;
    fromDate?: string;
    toDate?: string;
  }) {
    const clean = params.query.trim();
    if (!clean) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await runSemanticSearch({
        q: clean,
        conversation_id: params.conversationScope?.trim() || undefined,
        type_label: params.typeLabel?.trim() || undefined,
        start_time: toStartTimestamp(params.fromDate ?? ""),
        end_time: toEndTimestamp(params.toDate ?? ""),
        limit: 20
      });
      setResult(data);

      const query = new URLSearchParams();
      query.set("q", clean);
      if (params.conversationScope?.trim()) {
        query.set("conversation_id", params.conversationScope.trim());
      }
      if (params.typeLabel?.trim()) {
        query.set("type_label", params.typeLabel.trim());
      }
      if (params.fromDate?.trim()) {
        query.set("from", params.fromDate.trim());
      }
      if (params.toDate?.trim()) {
        query.set("to", params.toDate.trim());
      }
      router.replace(`/app/search?${query.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q") ?? "";
    const initialScope = params.get("conversation_id") ?? "";
    const initialType = params.get("type_label") ?? "";
    const initialFrom = params.get("from") ?? "";
    const initialTo = params.get("to") ?? "";
    setQueryDraft(initialQuery);
    setConversationScope(initialScope);
    setTypeLabel(initialType);
    setFromDate(initialFrom);
    setToDate(initialTo);
    if (initialQuery.trim()) {
      void performSearch({
        query: initialQuery,
        conversationScope: initialScope || undefined,
        typeLabel: initialType || undefined,
        fromDate: initialFrom || undefined,
        toDate: initialTo || undefined
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void performSearch({
      query: queryDraft,
      conversationScope,
      typeLabel,
      fromDate,
      toDate
    });
  }

  return (
    <div className="space-y-4 routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <Badge variant="secondary">Semantic Search</Badge>
              <CardTitle className="text-2xl tracking-tight">Search entities, facts, and provenance trails.</CardTitle>
              <CardDescription>
                Apply conversation, type, and date filters to quickly isolate relevant knowledge.
              </CardDescription>
            </div>
            <Button asChild variant="outline">
              <Link href="/app/entities">Browse Entities</Link>
            </Button>
          </div>
          <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-6" onSubmit={handleSubmit}>
            <div className="space-y-1.5 xl:col-span-2">
              <Label htmlFor="search-query">Query</Label>
              <Input
                id="search-query"
                placeholder="Apple supply chain risk"
                value={queryDraft}
                onChange={(event) => setQueryDraft(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="search-conversation">Conversation Scope</Label>
              <Input
                id="search-conversation"
                placeholder="conversation id"
                value={conversationScope}
                onChange={(event) => setConversationScope(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="search-type">Type Label</Label>
              <Input
                id="search-type"
                placeholder="Company"
                value={typeLabel}
                onChange={(event) => setTypeLabel(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="search-from">From Date</Label>
              <Input
                id="search-from"
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="search-to">To Date</Label>
              <Input
                id="search-to"
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={loading} className="w-full">
                <SearchIcon className="h-4 w-4" />
                {loading ? "Searching..." : "Search"}
              </Button>
            </div>
          </form>
        </CardHeader>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {result ? (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Active Filters</CardTitle>
              <CardDescription>Current query context for this result set.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Badge variant="outline">
                <Filter className="mr-1 h-3.5 w-3.5" />
                Query: {result.query}
              </Badge>
              <Badge variant="outline">Conversation: {result.conversation_id ?? "-"}</Badge>
              <Badge variant="outline">Type: {result.type_label ?? "-"}</Badge>
              <Badge variant="outline">From: {formatTimestamp(result.start_time)}</Badge>
              <Badge variant="outline">To: {formatTimestamp(result.end_time)}</Badge>
            </CardContent>
          </Card>

          <Tabs defaultValue="entities" className="space-y-3">
            <TabsList>
              <TabsTrigger value="entities">Entities ({result.entities.length})</TabsTrigger>
              <TabsTrigger value="facts">Facts ({result.facts.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="entities">
              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">Entity Hits</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Score</TableHead>
                        <TableHead>Entity</TableHead>
                        <TableHead>Preview</TableHead>
                        <TableHead>Type</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.entities.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-muted-foreground">
                            No entity hits.
                          </TableCell>
                        </TableRow>
                      ) : (
                        result.entities.map((hit) => (
                          <TableRow key={hit.entity.id}>
                            <TableCell>{formatScore(hit.similarity, 3)}</TableCell>
                            <TableCell>
                              <Link href={`/app/entities/${hit.entity.id}`}>{hit.entity.canonical_name}</Link>
                            </TableCell>
                            <TableCell>
                              aliases: {(hit.entity.known_aliases_json ?? []).slice(0, 3).join(", ") || "(none)"} |
                              {" "}updated {formatTimestamp(hit.entity.updated_at)}
                            </TableCell>
                            <TableCell>{hit.entity.type_label || "-"}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="facts">
              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">Fact Hits</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Score</TableHead>
                        <TableHead>Fact</TableHead>
                        <TableHead>Preview</TableHead>
                        <TableHead>Explain</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.facts.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-muted-foreground">
                            No fact hits.
                          </TableCell>
                        </TableRow>
                      ) : (
                        result.facts.map((hit) => (
                          <TableRow key={hit.fact.id}>
                            <TableCell>{formatScore(hit.similarity, 3)}</TableCell>
                            <TableCell>
                              {hit.fact.subject_entity_name} {hit.fact.predicate} {hit.fact.object_value}
                            </TableCell>
                            <TableCell>
                              scope: {hit.fact.scope} | created: {formatTimestamp(hit.fact.created_at)}
                            </TableCell>
                            <TableCell>
                              <Link href={`/app/explain/facts/${hit.fact.id}`}>Explain</Link>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Run a search to see grouped results.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
