"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";

import { type ConversationsListResponse, deleteConversation, getConversations } from "../../../lib/api";
import { readConversationNames, removeConversationName } from "../../../lib/conversationNames";
import { formatTimestamp } from "../../../lib/format";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../components/ui/delete-controls";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

const PAGE_SIZE = 20;

export default function ConversationsPage() {
  const [queryDraft, setQueryDraft] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<ConversationsListResponse | null>(null);
  const [conversationNames, setConversationNames] = useState<Record<string, string>>({});
  const [pendingDeleteConversationId, setPendingDeleteConversationId] = useState<string | null>(null);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getConversations({
          limit: PAGE_SIZE,
          offset,
          q: appliedQuery || undefined
        });
        if (!active) {
          return;
        }
        setPayload(data);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load conversations.");
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
  }, [appliedQuery, offset]);

  useEffect(() => {
    setConversationNames(readConversationNames());
  }, []);

  useEffect(() => {
    setConversationNames(readConversationNames());
  }, [payload]);

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setAppliedQuery(queryDraft.trim());
  }

  async function confirmDeleteConversation(conversationId: string) {
    setDeletingConversationId(conversationId);
    setError(null);
    try {
      await deleteConversation(conversationId);
      setPayload((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.filter((item) => item.conversation_id !== conversationId),
          total: Math.max(0, current.total - 1)
        };
      });
      removeConversationName(conversationId);
      setConversationNames(readConversationNames());
      if (typeof window !== "undefined") {
        if (window.localStorage.getItem("librarian.chat.lastConversation.v1") === conversationId) {
          window.localStorage.removeItem("librarian.chat.lastConversation.v1");
        }
        const pins = JSON.parse(window.localStorage.getItem("librarian.chat.pins.v1") ?? "[]") as unknown;
        if (Array.isArray(pins)) {
          const nextPins = pins
            .map((item) => String(item))
            .filter((item) => item.trim().length > 0 && item !== conversationId);
          window.localStorage.setItem("librarian.chat.pins.v1", JSON.stringify(nextPins));
        }
      }
      setPendingDeleteConversationId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete conversation.");
    } finally {
      setDeletingConversationId(null);
    }
  }

  const total = payload?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="space-y-4 routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <Badge variant="secondary">Conversation Index</Badge>
              <CardTitle className="text-2xl tracking-tight">Browse and manage chat histories.</CardTitle>
              <CardDescription>Filter by conversation id and jump into per-thread summaries.</CardDescription>
            </div>
            <Button asChild variant="outline">
              <Link href="/app/chat">
                <MessagesSquare className="h-4 w-4" />
                Open Chat Workspace
              </Link>
            </Button>
          </div>
          <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={handleSearchSubmit}>
            <Input
              placeholder="Filter by conversation id..."
              value={queryDraft}
              onChange={(event) => setQueryDraft(event.target.value)}
              className="sm:max-w-md"
            />
            <Button type="submit">Apply</Button>
          </form>
        </CardHeader>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xl">Conversation Records</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading conversations...</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>ID</TableHead>
                    <TableHead>Last Updated</TableHead>
                    <TableHead>Messages</TableHead>
                    <TableHead>Entities</TableHead>
                    <TableHead>Facts</TableHead>
                    <TableHead>Relations</TableHead>
                    <TableHead>Runs</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(payload?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-muted-foreground">
                        No conversations found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    payload?.items.map((item) => (
                      <TableRow key={item.conversation_id}>
                        <TableCell>{conversationNames[item.conversation_id] ?? item.conversation_id}</TableCell>
                        <TableCell>
                          <Link href={`/app/conversations/${encodeURIComponent(item.conversation_id)}`}>
                            {item.conversation_id}
                          </Link>
                        </TableCell>
                        <TableCell>{formatTimestamp(item.last_message_at)}</TableCell>
                        <TableCell>{item.message_count}</TableCell>
                        <TableCell>{item.entity_count}</TableCell>
                        <TableCell>{item.fact_count}</TableCell>
                        <TableCell>{item.relation_count}</TableCell>
                        <TableCell>{item.extractor_run_count}</TableCell>
                        <TableCell>
                          <DeleteActionButton
                            type="button"
                            onClick={() => setPendingDeleteConversationId(item.conversation_id)}
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <Button
                  variant="outline"
                  type="button"
                  disabled={!canPrev}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <p className="text-sm text-muted-foreground">
                  {total === 0 ? 0 : offset + 1} - {Math.min(total, offset + PAGE_SIZE)} of {total}
                </p>
                <Button variant="outline" type="button" disabled={!canNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
                  Next
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <DeleteConfirmDialog
        open={pendingDeleteConversationId !== null}
        onOpenChange={(next) => {
          if (!next && deletingConversationId === null) {
            setPendingDeleteConversationId(null);
          }
        }}
        title={`Delete conversation ${
          pendingDeleteConversationId
            ? (conversationNames[pendingDeleteConversationId] ?? pendingDeleteConversationId)
            : ""
        }?`}
        description="Messages and conversation-scoped extracted data for this conversation will be removed."
        onConfirm={() => {
          if (pendingDeleteConversationId) {
            void confirmDeleteConversation(pendingDeleteConversationId);
          }
        }}
        isDeleting={deletingConversationId !== null}
      />
    </div>
  );
}
