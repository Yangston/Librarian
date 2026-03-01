"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, ChartNetwork, MessageSquare, Search, Shapes, Users } from "lucide-react";

import {
  type ConversationsListResponse,
  type RecentEntitiesResponse,
  type SchemaOverviewData,
  getConversations,
  getRecentEntities,
  getSchemaOverview
} from "../../lib/api";
import { formatTimestamp } from "../../lib/format";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";

const ACTIONS = [
  {
    href: "/app/chat",
    title: "Chat Workspace",
    description: "Live turns, extraction controls, and pinned conversation rail.",
    icon: MessageSquare
  },
  {
    href: "/app/graph",
    title: "Graph Studio",
    description: "Hover-preview and pin-edit graph inspector experience.",
    icon: ChartNetwork
  },
  {
    href: "/app/entities",
    title: "Entity Catalog",
    description: "Global records with canonical names, relations, and timelines.",
    icon: Users
  },
  {
    href: "/app/schema",
    title: "Schema Explorer",
    description: "Types, fields, proposals, and rationale in one place.",
    icon: Shapes
  }
];

export default function WorkspacePage() {
  const router = useRouter();
  const [searchDraft, setSearchDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationsListResponse | null>(null);
  const [recentEntities, setRecentEntities] = useState<RecentEntitiesResponse | null>(null);
  const [schemaOverview, setSchemaOverview] = useState<SchemaOverviewData | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [conversationData, recentEntityData, schemaData] = await Promise.all([
          getConversations({ limit: 8, offset: 0 }),
          getRecentEntities(8),
          getSchemaOverview({ limit: 20, proposal_limit: 20 })
        ]);
        if (!active) {
          return;
        }
        setConversations(conversationData);
        setRecentEntities(recentEntityData);
        setSchemaOverview(schemaData);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workspace data.");
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
  }, []);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = searchDraft.trim();
    if (!clean) {
      return;
    }
    router.push(`/app/search?q=${encodeURIComponent(clean)}`);
  }

  return (
    <div className="space-y-4 routeFade">
      <Card className="hero overflow-hidden border-border/80 bg-card/95">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <Badge variant="secondary">Workspace Dashboard</Badge>
              <CardTitle className="text-3xl tracking-tight">Inspect the system state at a glance.</CardTitle>
              <CardDescription className="max-w-3xl text-sm sm:text-base">
                Start with semantic search, then drill into conversations, entities, and schema changes with a
                shared product shell.
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button asChild>
                <Link href="/app/chat">New Chat</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/app/graph">Open Graph</Link>
              </Button>
            </div>
          </div>
          <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={submitSearch}>
            <Input
              placeholder="Search entities and facts..."
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              className="sm:max-w-xl"
            />
            <Button type="submit">
              <Search className="h-4 w-4" />
              Search
            </Button>
          </form>
        </CardHeader>
        <CardContent className="grid gap-3 pb-6 sm:grid-cols-2 xl:grid-cols-4">
          {ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.href}
                href={action.href}
                className="group rounded-lg border border-border/70 bg-background/70 p-4 transition-colors hover:bg-accent/10"
              >
                <div className="flex items-center justify-between">
                  <Icon className="h-4 w-4 text-primary" />
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </div>
                <p className="mt-3 font-medium">{action.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{action.description}</p>
              </Link>
            );
          })}
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Card key={index}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-28" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-20" />
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardContent className="py-6">
              <Skeleton className="h-56 w-full" />
            </CardContent>
          </Card>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Conversations</CardDescription>
                <CardTitle className="text-3xl">{conversations?.total ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Recent Entities</CardDescription>
                <CardTitle className="text-3xl">{recentEntities?.items.length ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Schema Fields</CardDescription>
                <CardTitle className="text-3xl">{schemaOverview?.fields.length ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Open Proposals</CardDescription>
                <CardTitle className="text-3xl">
                  {schemaOverview?.proposals.filter((proposal) => proposal.status === "proposed").length ?? 0}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          <Tabs defaultValue="conversations" className="space-y-3">
            <TabsList>
              <TabsTrigger value="conversations">Conversations</TabsTrigger>
              <TabsTrigger value="entities">Entities</TabsTrigger>
              <TabsTrigger value="schema">Schema</TabsTrigger>
            </TabsList>

            <TabsContent value="conversations">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-xl">Recent Conversations</CardTitle>
                    <CardDescription>Latest activity and extracted counts.</CardDescription>
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/conversations">View all</Link>
                  </Button>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Conversation</TableHead>
                        <TableHead>Updated</TableHead>
                        <TableHead>Entities</TableHead>
                        <TableHead>Facts</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(conversations?.items ?? []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-muted-foreground">
                            No conversations yet.
                          </TableCell>
                        </TableRow>
                      ) : (
                        conversations?.items.map((item) => (
                          <TableRow key={item.conversation_id}>
                            <TableCell>
                              <Link href={`/app/conversations/${encodeURIComponent(item.conversation_id)}`}>
                                {item.conversation_id}
                              </Link>
                            </TableCell>
                            <TableCell>{formatTimestamp(item.last_message_at)}</TableCell>
                            <TableCell>{item.entity_count}</TableCell>
                            <TableCell>{item.fact_count}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="entities">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-xl">Recently Updated Entities</CardTitle>
                    <CardDescription>Canonical names and current type labels.</CardDescription>
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/entities">Open catalog</Link>
                  </Button>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm">
                    {(recentEntities?.items ?? []).length === 0 ? (
                      <li className="text-muted-foreground">No entities yet.</li>
                    ) : (
                      recentEntities?.items.map((entity) => (
                        <li key={entity.entity_id}>
                          <Link href={`/app/entities/${entity.entity_id}`} className="font-medium">
                            {entity.canonical_name}
                          </Link>
                          <span className="ml-1 text-muted-foreground">({entity.type_label || "untyped"})</span>
                        </li>
                      ))
                    )}
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="schema">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-xl">Recent Schema Changes</CardTitle>
                    <CardDescription>Proposal stream with confidence and timestamps.</CardDescription>
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/app/schema">Open schema explorer</Link>
                  </Button>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Confidence</TableHead>
                        <TableHead>Created</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(schemaOverview?.proposals ?? []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-muted-foreground">
                            No schema proposals yet.
                          </TableCell>
                        </TableRow>
                      ) : (
                        schemaOverview?.proposals.slice(0, 12).map((proposal) => (
                          <TableRow key={proposal.id}>
                            <TableCell>{proposal.proposal_type}</TableCell>
                            <TableCell>{proposal.status}</TableCell>
                            <TableCell>{proposal.confidence.toFixed(2)}</TableCell>
                            <TableCell>{formatTimestamp(proposal.created_at)}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
