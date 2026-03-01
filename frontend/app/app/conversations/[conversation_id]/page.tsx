"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  type ConversationSummaryData,
  type MessageRead,
  deleteMessage,
  getConversationMessages,
  getConversationSummary,
  rerunExtraction,
  updateMessage
} from "../../../../lib/api";
import { formatTimestamp } from "../../../../lib/format";
import { Badge } from "../../../../components/ui/badge";
import { Button } from "../../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../../components/ui/card";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../../components/ui/delete-controls";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../../../components/ui/tabs";
import { Textarea } from "../../../../components/ui/textarea";

type Tab = "chat" | "summary";

export default function ConversationDetailPage() {
  const params = useParams<{ conversation_id: string }>();
  const conversationId = useMemo(() => decodeURIComponent(params.conversation_id), [params.conversation_id]);
  const [tab, setTab] = useState<Tab>("chat");
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [summary, setSummary] = useState<ConversationSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editingDraft, setEditingDraft] = useState("");
  const [pendingDeleteMessageId, setPendingDeleteMessageId] = useState<number | null>(null);
  const [busyMessageId, setBusyMessageId] = useState<number | null>(null);

  async function loadConversation() {
    setLoading(true);
    setError(null);
    try {
      const [messageData, summaryData] = await Promise.all([
        getConversationMessages(conversationId),
        getConversationSummary(conversationId)
      ]);
      setMessages(messageData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation detail.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConversation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  async function handleRerunExtraction() {
    setRerunning(true);
    setError(null);
    try {
      await rerunExtraction(conversationId);
      await loadConversation();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rerun extraction.");
    } finally {
      setRerunning(false);
    }
  }

  function beginEditMessage(message: MessageRead) {
    setEditingMessageId(message.id);
    setEditingDraft(message.content);
    setPendingDeleteMessageId(null);
  }

  function cancelEditMessage() {
    setEditingMessageId(null);
    setEditingDraft("");
  }

  async function saveEditedMessage(messageId: number) {
    const next = editingDraft.trim();
    if (!next) {
      setError("Message cannot be empty.");
      return;
    }
    setBusyMessageId(messageId);
    setError(null);
    try {
      const updated = await updateMessage(messageId, { content: next });
      setMessages((current) => current.map((item) => (item.id === messageId ? updated : item)));
      cancelEditMessage();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update message.");
    } finally {
      setBusyMessageId(null);
    }
  }

  function requestDeleteMessage(messageId: number) {
    if (editingMessageId === messageId) {
      cancelEditMessage();
    }
    setPendingDeleteMessageId(messageId);
  }

  function cancelDeleteMessage() {
    setPendingDeleteMessageId(null);
  }

  async function confirmDeleteMessage(messageId: number) {
    setBusyMessageId(messageId);
    setError(null);
    try {
      await deleteMessage(messageId);
      setMessages((current) => current.filter((item) => item.id !== messageId));
      setPendingDeleteMessageId((current) => (current === messageId ? null : current));
      if (editingMessageId === messageId) {
        cancelEditMessage();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete message.");
    } finally {
      setBusyMessageId(null);
    }
  }

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <Badge variant="secondary">Conversation Detail</Badge>
              <CardTitle className="text-2xl tracking-tight">{conversationId}</CardTitle>
              <CardDescription>
                Inspect the raw chat log or the structured summary generated from it.
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button asChild variant="outline">
                <Link href={`/app/graph?conversation_id=${encodeURIComponent(conversationId)}`}>Graph Studio</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/app/chat?conversation_id=${encodeURIComponent(conversationId)}`}>Open Chatroom</Link>
              </Button>
              <Button type="button" onClick={handleRerunExtraction} disabled={rerunning}>
                {rerunning ? "Re-running..." : "Re-run Extraction"}
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Tabs value={tab} onValueChange={(next) => setTab(next as Tab)} className="space-y-4">
        <TabsList>
          <TabsTrigger value="chat">Chat Log</TabsTrigger>
          <TabsTrigger value="summary">Conversation Summary</TabsTrigger>
        </TabsList>

        <TabsContent value="chat" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Messages</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <p className="text-sm text-muted-foreground">Loading conversation details...</p>
              ) : messages.length === 0 ? (
                <p className="text-sm text-muted-foreground">No messages found for this conversation.</p>
              ) : (
                messages.map((message) => {
                  const isEditing = editingMessageId === message.id;
                  return (
                    <article key={message.id} className="rounded-lg border border-border/70 bg-background/70 p-3">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{message.role}</Badge>
                        <span className="text-xs text-muted-foreground">#{message.id}</span>
                        <span className="text-xs text-muted-foreground">{formatTimestamp(message.timestamp)}</span>
                      </div>
                      {isEditing ? (
                        <Textarea
                          className="min-h-[96px]"
                          value={editingDraft}
                          onChange={(event) => setEditingDraft(event.target.value)}
                        />
                      ) : (
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {isEditing ? (
                          <>
                            <Button
                              type="button"
                              onClick={() => void saveEditedMessage(message.id)}
                              disabled={busyMessageId === message.id}
                            >
                              Save
                            </Button>
                            <Button
                              variant="outline"
                              type="button"
                              onClick={cancelEditMessage}
                              disabled={busyMessageId === message.id}
                            >
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              type="button"
                              onClick={() => beginEditMessage(message)}
                              disabled={busyMessageId === message.id}
                            >
                              Edit
                            </Button>
                            <DeleteActionButton
                              type="button"
                              onClick={() => requestDeleteMessage(message.id)}
                              disabled={busyMessageId === message.id}
                            />
                          </>
                        )}
                      </div>
                    </article>
                  );
                })
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="summary" className="space-y-4">
          {loading ? (
            <Card>
              <CardContent className="py-6">Loading conversation details...</CardContent>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Key Entities</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="simpleList">
                    {(summary?.key_entities ?? []).length === 0 ? (
                      <li className="muted">No entities found.</li>
                    ) : (
                      summary?.key_entities.map((entity) => (
                        <li key={entity.id}>
                          <Link href={`/app/entities/${entity.id}`}>{entity.canonical_name}</Link>
                          <span className="muted"> ({entity.type_label || "untyped"})</span>
                        </li>
                      ))
                    )}
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Key Facts</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Entity</TableHead>
                        <TableHead>Field</TableHead>
                        <TableHead>Value</TableHead>
                        <TableHead>Confidence</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(summary?.key_facts ?? []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-muted-foreground">
                            No facts found.
                          </TableCell>
                        </TableRow>
                      ) : (
                        summary?.key_facts.map((fact) => (
                          <TableRow key={fact.id}>
                            <TableCell>{fact.subject_entity_name}</TableCell>
                            <TableCell>{fact.predicate}</TableCell>
                            <TableCell>{fact.object_value}</TableCell>
                            <TableCell>{fact.confidence.toFixed(2)}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Schema Learned in This Conversation</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-sm text-muted-foreground">
                      Types: {(summary?.schema_changes_triggered.node_labels ?? []).join(", ") || "-"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Fields: {(summary?.schema_changes_triggered.field_labels ?? []).join(", ") || "-"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Relations: {(summary?.schema_changes_triggered.relation_labels ?? []).join(", ") || "-"}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Relation Clusters</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="simpleList">
                      {(summary?.relation_clusters ?? []).length === 0 ? (
                        <li className="muted">No clusters available.</li>
                      ) : (
                        summary?.relation_clusters.map((cluster) => (
                          <li key={cluster.relation_label}>
                            <strong>{cluster.relation_label}</strong> ({cluster.relation_count})
                          </li>
                        ))
                      )}
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>

      <DeleteConfirmDialog
        open={pendingDeleteMessageId !== null}
        onOpenChange={(open) => {
          if (!open && busyMessageId === null) {
            cancelDeleteMessage();
          }
        }}
        title={`Delete message #${pendingDeleteMessageId ?? ""}?`}
        description="This action cannot be undone."
        onConfirm={() => {
          if (pendingDeleteMessageId !== null) {
            void confirmDeleteMessage(pendingDeleteMessageId);
          }
        }}
        isDeleting={busyMessageId !== null}
      />
    </div>
  );
}
