"use client";

import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Pin, PinOff } from "lucide-react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  type ConversationListItem,
  type MessageRead,
  deleteConversation,
  deleteMessage,
  getConversationMessages,
  getConversations,
  runLiveChatTurn,
  updateMessage
} from "../../../lib/api";
import {
  ensureConversationNameFromFirstText,
  readConversationNames,
  removeConversationName
} from "../../../lib/conversationNames";
import { formatTimestamp } from "../../../lib/format";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../components/ui/delete-controls";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";
import { Checkbox } from "../../../components/ui/checkbox";

const PIN_STORAGE_KEY = "librarian.chat.pins.v1";
const LAST_CONVERSATION_KEY = "librarian.chat.lastConversation.v1";
const CONTEXT_PANEL_STORAGE_KEY = "librarian.chat.contextVisible.v1";

function createConversationId(now = new Date()): string {
  const year = now.getFullYear();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  const hours = `${now.getHours()}`.padStart(2, "0");
  const minutes = `${now.getMinutes()}`.padStart(2, "0");
  const seconds = `${now.getSeconds()}`.padStart(2, "0");
  return `chat-${year}${month}${day}-${hours}${minutes}${seconds}`;
}

function readStoredPins(): string[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PIN_STORAGE_KEY) ?? "[]");
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map((item) => String(item)).filter((item) => item.trim().length > 0);
  } catch {
    return [];
  }
}

function readStoredConversationId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const value = window.localStorage.getItem(LAST_CONVERSATION_KEY);
  return value?.trim() ? value.trim() : null;
}

function readContextPanelPreference(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(CONTEXT_PANEL_STORAGE_KEY) === "1";
}

function writeContextPanelPreference(value: boolean) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(CONTEXT_PANEL_STORAGE_KEY, value ? "1" : "0");
}

type DeleteIntent =
  | { kind: "message"; messageId: number }
  | { kind: "conversation"; conversationId: string }
  | null;

function ChatPageInner() {
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState("");
  const [conversationSearch, setConversationSearch] = useState("");
  const [autoExtract, setAutoExtract] = useState(true);
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a research assistant. Be concise, explicit about assumptions, and cite uncertainty."
  );
  const [contextPanelVisible, setContextPanelVisible] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [pinnedConversationIds, setPinnedConversationIds] = useState<string[]>([]);
  const [conversationNames, setConversationNames] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editingDraft, setEditingDraft] = useState("");
  const [deleteIntent, setDeleteIntent] = useState<DeleteIntent>(null);
  const [savingMessageId, setSavingMessageId] = useState<number | null>(null);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastExtractionSummary, setLastExtractionSummary] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const appliedNewTokenRef = useRef<string | null>(null);

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (left, right) => new Date(left.timestamp).valueOf() - new Date(right.timestamp).valueOf()
      ),
    [messages]
  );

  const visibleConversations = useMemo(() => {
    const cleanSearch = conversationSearch.trim().toLowerCase();
    const filtered = cleanSearch
      ? conversations.filter((item) => {
          const conversationName = conversationNames[item.conversation_id] ?? "";
          return (
            item.conversation_id.toLowerCase().includes(cleanSearch) ||
            conversationName.toLowerCase().includes(cleanSearch)
          );
        })
      : conversations;
    const pinned = filtered.filter((item) => pinnedConversationIds.includes(item.conversation_id));
    const regular = filtered.filter((item) => !pinnedConversationIds.includes(item.conversation_id));
    return [...pinned, ...regular];
  }, [conversationNames, conversationSearch, conversations, pinnedConversationIds]);

  async function loadConversationList() {
    setLoadingConversations(true);
    try {
      const data = await getConversations({ limit: 200, offset: 0 });
      setConversations(data.items);
    } finally {
      setLoadingConversations(false);
    }
  }

  function refreshConversationNamesState() {
    setConversationNames(readConversationNames());
  }

  function maybeCaptureConversationName(targetConversationId: string, rows: MessageRead[]) {
    const firstUserMessage = rows.find(
      (message) => message.role === "user" && message.content.trim().length > 0
    );
    if (!firstUserMessage) {
      return;
    }
    const previous = conversationNames[targetConversationId];
    const generated = ensureConversationNameFromFirstText(targetConversationId, firstUserMessage.content);
    if (generated && generated !== previous) {
      refreshConversationNamesState();
    }
  }

  async function loadMessages(targetConversationId: string) {
    setLoading(true);
    setError(null);
    try {
      const rows = await getConversationMessages(targetConversationId);
      setMessages(rows);
      maybeCaptureConversationName(targetConversationId, rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chat log.");
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConversationList();
  }, []);

  useEffect(() => {
    const storedConversationId = readStoredConversationId() ?? "";
    setConversationId(storedConversationId || createConversationId());
    setPinnedConversationIds(readStoredPins());
    setConversationNames(readConversationNames());
    setContextPanelVisible(readContextPanelPreference());
    setInitialized(true);
  }, []);

  useEffect(() => {
    if (!initialized) {
      return;
    }
    const fromQuery = searchParams.get("conversation_id")?.trim() ?? "";
    const newMode = searchParams.get("new") === "1";
    if (newMode) {
      const token = searchParams.get("ts")?.trim() || `conversation:${fromQuery || "generated"}`;
      if (appliedNewTokenRef.current === token) {
        return;
      }
      appliedNewTokenRef.current = token;
      const nextConversationId = fromQuery || createConversationId();
      setConversationId(nextConversationId);
      setMessages([]);
      setLastExtractionSummary(null);
      setDeleteIntent(null);
      setEditingMessageId(null);
      setEditingDraft("");
      setError(null);
      return;
    }
    if (!fromQuery) {
      return;
    }
    setConversationId((current) => (current === fromQuery ? current : fromQuery));
  }, [initialized, searchParams]);

  useEffect(() => {
    if (!initialized || !conversationId.trim()) {
      return;
    }
    window.localStorage.setItem(LAST_CONVERSATION_KEY, conversationId.trim());
    void loadMessages(conversationId);
  }, [conversationId, initialized]);

  useEffect(() => {
    if (!transcriptRef.current) {
      return;
    }
    transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [sortedMessages, thinking]);

  function togglePin(conversation: string) {
    setPinnedConversationIds((current) => {
      const next = current.includes(conversation)
        ? current.filter((item) => item !== conversation)
        : [conversation, ...current];
      window.localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  function startNewConversation() {
    const nextConversationId = createConversationId();
    setConversationId(nextConversationId);
    setMessages([]);
    setLastExtractionSummary(null);
    setDeleteIntent(null);
  }

  async function submitDraft() {
    const content = draft.trim();
    if (!content) {
      return;
    }
    const cleanConversationId = conversationId.trim();
    if (!cleanConversationId) {
      setError("Conversation id is required.");
      return;
    }
    setThinking(true);
    setError(null);
    setLastExtractionSummary(null);
    const pendingUser: MessageRead = {
      id: Date.now() * -1,
      conversation_id: cleanConversationId,
      role: "user",
      content,
      timestamp: new Date().toISOString()
    };
    setMessages((current) => [...current, pendingUser]);
    setDraft("");

    try {
      const result = await runLiveChatTurn(cleanConversationId, {
        content,
        auto_extract: autoExtract,
        system_prompt: systemPrompt.trim() || undefined
      });
      setMessages((current) => [
        ...current.filter((item) => item.id !== pendingUser.id),
        result.user_message,
        result.assistant_message
      ]);
      const generatedName = ensureConversationNameFromFirstText(cleanConversationId, content);
      if (generatedName) {
        refreshConversationNamesState();
      }
      if (result.extraction) {
        setLastExtractionSummary(
          `Extraction run ${result.extraction.extractor_run_id ?? "n/a"} | entities ${
            result.extraction.entities_created
          }, facts ${result.extraction.facts_created}, relations ${result.extraction.relations_created}`
        );
      }
      await loadConversationList();
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== pendingUser.id));
      setError(err instanceof Error ? err.message : "Failed to send turn.");
    } finally {
      setThinking(false);
    }
  }

  async function sendTurn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitDraft();
  }

  function beginEditMessage(message: MessageRead) {
    setEditingMessageId(message.id);
    setEditingDraft(message.content);
    setDeleteIntent(null);
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
    setSavingMessageId(messageId);
    setError(null);
    try {
      const updated = await updateMessage(messageId, { content: next });
      setMessages((current) => current.map((item) => (item.id === messageId ? updated : item)));
      cancelEditMessage();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update message.");
    } finally {
      setSavingMessageId(null);
    }
  }

  function requestDeleteMessage(messageId: number) {
    if (editingMessageId === messageId) {
      cancelEditMessage();
    }
    setDeleteIntent({ kind: "message", messageId });
  }

  function requestDeleteConversation(targetConversationId: string) {
    setDeleteIntent({ kind: "conversation", conversationId: targetConversationId });
  }

  async function confirmDeleteMessage(messageId: number) {
    setSavingMessageId(messageId);
    setError(null);
    try {
      await deleteMessage(messageId);
      setMessages((current) => current.filter((item) => item.id !== messageId));
      if (editingMessageId === messageId) {
        cancelEditMessage();
      }
      setDeleteIntent(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete message.");
    } finally {
      setSavingMessageId(null);
    }
  }

  async function confirmDeleteConversation(targetConversationId: string) {
    setDeletingConversationId(targetConversationId);
    setError(null);
    try {
      await deleteConversation(targetConversationId);
      setConversations((current) =>
        current.filter((item) => item.conversation_id !== targetConversationId)
      );
      setPinnedConversationIds((current) => {
        const next = current.filter((item) => item !== targetConversationId);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(next));
        }
        return next;
      });
      if (typeof window !== "undefined") {
        const storedLastConversation = window.localStorage.getItem(LAST_CONVERSATION_KEY);
        if (storedLastConversation === targetConversationId) {
          window.localStorage.removeItem(LAST_CONVERSATION_KEY);
        }
      }
      removeConversationName(targetConversationId);
      refreshConversationNamesState();
      setDeleteIntent(null);
      if (conversationId === targetConversationId) {
        const nextConversationId = createConversationId();
        setConversationId(nextConversationId);
        setMessages([]);
        setLastExtractionSummary(null);
      }
      await loadConversationList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete conversation.");
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function confirmDeleteIntent() {
    if (deleteIntent?.kind === "message") {
      await confirmDeleteMessage(deleteIntent.messageId);
      return;
    }
    if (deleteIntent?.kind === "conversation") {
      await confirmDeleteConversation(deleteIntent.conversationId);
    }
  }

  function closeDeleteDialog() {
    if (savingMessageId !== null || deletingConversationId !== null) {
      return;
    }
    setDeleteIntent(null);
  }

  function toggleContextPanel() {
    setContextPanelVisible((current) => {
      const next = !current;
      writeContextPanelPreference(next);
      return next;
    });
  }

  const activeConversationName = conversationNames[conversationId];

  return (
    <div className={`chatWorkspace routeFade ${contextPanelVisible ? "" : "contextHidden"}`}>
      <Card className="chatRail border-border/80 bg-card/95 overflow-hidden">
        <CardHeader className="pb-2">
          <div className="sectionTitleRow">
            <CardTitle className="text-lg">Conversations</CardTitle>
            <Button type="button" size="sm" onClick={startNewConversation}>
              New Chat
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col space-y-3 pt-0">
          <Input
            placeholder="Search conversations..."
            value={conversationSearch}
            onChange={(event) => setConversationSearch(event.target.value)}
          />
          <div className="min-h-0 flex-1 overflow-y-auto pr-2">
            <div className="conversationList">
              {loadingConversations ? (
                <p className="muted">Loading list...</p>
              ) : visibleConversations.length === 0 ? (
                <p className="muted">No conversations yet.</p>
              ) : (
                visibleConversations.map((item) => {
                  const isPinned = pinnedConversationIds.includes(item.conversation_id);
                  return (
                    <div key={item.conversation_id} className="conversationMeta">
                      <button
                        className={`conversationItem justify-start overflow-hidden ${conversationId === item.conversation_id ? "active" : ""} ${
                          isPinned ? "pinned" : ""
                        }`}
                        type="button"
                        onClick={() => setConversationId(item.conversation_id)}
                        aria-pressed={conversationId === item.conversation_id}
                      >
                        <div className="conversationTitleRow">
                          <strong className="conversationItemName">
                            {conversationNames[item.conversation_id] ?? item.conversation_id}
                          </strong>
                        </div>
                      </button>
                      <div className="conversationActions">
                        <Button
                          variant={isPinned ? "secondary" : "ghost"}
                          size="icon"
                          className="h-7 w-7"
                          type="button"
                          onClick={() => togglePin(item.conversation_id)}
                          aria-label={`${isPinned ? "Unpin" : "Pin"} ${item.conversation_id}`}
                        >
                          {isPinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
                        </Button>
                        <DeleteActionButton
                          iconOnly
                          type="button"
                          onClick={() => requestDeleteConversation(item.conversation_id)}
                          aria-label={`Delete conversation ${item.conversation_id}`}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="chatMainPanel border-border/80 bg-card/95 overflow-hidden">
        <CardHeader className="pb-2">
          <div className="sectionTitleRow">
            <div className="chatHeaderMeta">
              <CardTitle className="text-xl">{activeConversationName ?? "Chatroom"}</CardTitle>
            </div>
            <Button variant="outline" type="button" onClick={toggleContextPanel}>
              {contextPanelVisible ? "Hide Context" : "Show Context"}
            </Button>
          </div>
          {error ? <p className="errorText">{error}</p> : null}
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
          <div
            ref={transcriptRef}
            className="chatTranscriptModern"
            tabIndex={0}
            aria-label={`Chat transcript for conversation ${conversationId}`}
          >
            {loading ? (
              <p className="muted">Loading chat log...</p>
            ) : sortedMessages.length === 0 ? (
              <p className="muted">No messages yet. Start the conversation below.</p>
            ) : (
              sortedMessages.map((message) => {
                const isEditing = editingMessageId === message.id;
                return (
                  <article
                    key={message.id}
                    className={`chatBubbleModern ${message.role === "assistant" ? "assistant" : "user"} ${
                      message.id < 0 ? "pending" : ""
                    }`}
                  >
                    <div className="messageMeta">
                      <Badge variant={message.role === "assistant" ? "secondary" : "default"}>{message.role}</Badge>
                      <span className="muted">{formatTimestamp(message.timestamp)}</span>
                    </div>
                    {isEditing ? (
                      <Textarea
                        className="chatEditInput"
                        value={editingDraft}
                        onChange={(event) => setEditingDraft(event.target.value)}
                      />
                    ) : (
                      <div className="chatMessageMarkdown">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ node: _node, ...props }) => (
                              <a {...props} target="_blank" rel="noreferrer noopener" />
                            )
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
                    {message.id > 0 ? (
                      <div className="chatActions">
                        {isEditing ? (
                          <>
                            <Button
                              type="button"
                              onClick={() => void saveEditedMessage(message.id)}
                              disabled={savingMessageId === message.id}
                            >
                              Save
                            </Button>
                            <Button
                              variant="outline"
                              type="button"
                              onClick={cancelEditMessage}
                              disabled={savingMessageId === message.id}
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
                              disabled={savingMessageId === message.id}
                            >
                              Edit
                            </Button>
                            <DeleteActionButton
                              type="button"
                              onClick={() => requestDeleteMessage(message.id)}
                              disabled={savingMessageId === message.id}
                            />
                          </>
                        )}
                      </div>
                    ) : null}
                  </article>
                );
              })
            )}
            {thinking ? (
              <article className="chatBubbleModern assistant thinking">
                <div className="messageMeta">
                  <Badge variant="secondary">assistant</Badge>
                </div>
                <p>Thinking...</p>
              </article>
            ) : null}
          </div>

          <form className="chatComposerModern" onSubmit={sendTurn}>
            <Textarea
              className="chatComposerInputModern"
              placeholder="Ask a question... (Ctrl+Enter to send)"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  void submitDraft();
                }
              }}
            />
            <div className="sectionTitleRow">
              <p className="subtle">Chat logs and instructions are persisted per conversation id.</p>
              <Button type="submit" disabled={thinking || !draft.trim()}>
                {thinking ? "Sending..." : "Send"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {contextPanelVisible ? (
        <Card className="chatMetaPanel border-border/80 bg-card/95 overflow-hidden">
          <CardHeader className="pb-2">
            <div className="sectionTitleRow">
              <CardTitle className="text-lg">Context Controls</CardTitle>
              <Button variant="outline" size="sm" type="button" onClick={toggleContextPanel}>
                Hide
              </Button>
            </div>
          </CardHeader>
          <CardContent className="flex min-h-0 flex-1 flex-col space-y-3 overflow-y-auto">
            <div className="field">
              <Label>Conversation ID</Label>
              <Input
                value={conversationId}
                onChange={(event) => setConversationId(event.target.value)}
              />
            </div>
            <div className="field">
              <Label>Instructions (System Prompt)</Label>
              <Textarea
                className="chatSystemPrompt"
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
              />
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="auto-extract"
                checked={autoExtract}
                onCheckedChange={(checked) => setAutoExtract(Boolean(checked))}
              />
              <Label htmlFor="auto-extract">Auto-run extraction after assistant response</Label>
            </div>
            <Button variant="outline" type="button" onClick={() => void loadMessages(conversationId)}>
              Refresh chat log
            </Button>
            <p className="subtle">Messages in this conversation: {messages.length}</p>
            {lastExtractionSummary ? (
              <p className="subtle" aria-live="polite">
                {lastExtractionSummary}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <DeleteConfirmDialog
        open={Boolean(deleteIntent)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            closeDeleteDialog();
          }
        }}
        title={
          deleteIntent?.kind === "message"
            ? `Delete message #${deleteIntent.messageId}?`
            : deleteIntent?.kind === "conversation"
              ? `Delete conversation ${
                  conversationNames[deleteIntent.conversationId] ?? deleteIntent.conversationId
                }?`
              : "Delete item?"
        }
        description={
          deleteIntent?.kind === "conversation"
            ? "Messages and conversation-scoped extracted data for this conversation will be removed."
            : "This action cannot be undone."
        }
        onConfirm={() => void confirmDeleteIntent()}
        isDeleting={savingMessageId !== null || deletingConversationId !== null}
      />
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="routeFade">
          <Card className="border-border/80 bg-card/95">
            <CardContent className="py-6">Loading chat workspace...</CardContent>
          </Card>
        </div>
      }
    >
      <ChatPageInner />
    </Suspense>
  );
}
