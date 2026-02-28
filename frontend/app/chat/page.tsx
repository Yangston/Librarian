"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  type MessageRead,
  deleteMessage,
  getConversationMessages,
  runLiveChatTurn,
  updateMessage
} from "../../lib/api";
import { formatTimestamp } from "../../lib/format";

function createDefaultConversationId(): string {
  return `chat-${new Date().toISOString().slice(0, 10)}`;
}

export default function ChatPage() {
  const [conversationId, setConversationId] = useState(createDefaultConversationId());
  const [autoExtract, setAutoExtract] = useState(true);
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a research assistant. Be concise, explicit about assumptions, and cite uncertainty."
  );
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editingDraft, setEditingDraft] = useState("");
  const [pendingDeleteMessageId, setPendingDeleteMessageId] = useState<number | null>(null);
  const [savingMessageId, setSavingMessageId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastExtractionSummary, setLastExtractionSummary] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (left, right) => new Date(left.timestamp).valueOf() - new Date(right.timestamp).valueOf()
      ),
    [messages]
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const fromQuery = new URLSearchParams(window.location.search).get("conversation_id");
    if (fromQuery && fromQuery.trim()) {
      setConversationId(fromQuery.trim());
    }
  }, []);

  useEffect(() => {
    if (!transcriptRef.current) {
      return;
    }
    transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [sortedMessages, thinking]);

  async function loadMessages(targetConversationId: string) {
    setLoading(true);
    setError(null);
    try {
      const rows = await getConversationMessages(targetConversationId);
      setMessages(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chat log.");
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMessages(conversationId);
  }, [conversationId]);

  async function submitDraft() {
    const content = draft.trim();
    if (!content) {
      return;
    }
    setThinking(true);
    setError(null);
    setLastExtractionSummary(null);
    const pendingUser: MessageRead = {
      id: Date.now() * -1,
      conversation_id: conversationId,
      role: "user",
      content,
      timestamp: new Date().toISOString()
    };
    setMessages((current) => [...current, pendingUser]);
    setDraft("");

    try {
      const result = await runLiveChatTurn(conversationId, {
        content,
        auto_extract: autoExtract,
        system_prompt: systemPrompt.trim() || undefined
      });
      setMessages((current) => [
        ...current.filter((item) => item.id !== pendingUser.id),
        result.user_message,
        result.assistant_message
      ]);
      if (result.extraction) {
        setLastExtractionSummary(
          `Extraction run ${result.extraction.extractor_run_id ?? "n/a"} | entities ${
            result.extraction.entities_created
          }, facts ${result.extraction.facts_created}, relations ${result.extraction.relations_created}`
        );
      }
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
    setPendingDeleteMessageId(messageId);
  }

  function cancelDeleteMessage() {
    setPendingDeleteMessageId(null);
  }

  async function confirmDeleteMessage(messageId: number) {
    setSavingMessageId(messageId);
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
      setSavingMessageId(null);
    }
  }

  return (
    <div className="chatWorkspace">
      <section className="panel chatSidebar">
        <h2>Chat Control</h2>
        <label className="field">
          <span>Conversation ID</span>
          <input
            className="input"
            value={conversationId}
            onChange={(event) => setConversationId(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Instructions (System Prompt)</span>
          <textarea
            className="input chatSystemPrompt"
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
          />
        </label>
        <label className="checkTag">
          <input
            type="checkbox"
            checked={autoExtract}
            onChange={(event) => setAutoExtract(event.target.checked)}
          />
          <span>Auto-run extraction after assistant response</span>
        </label>
        <button className="button ghost" type="button" onClick={() => void loadMessages(conversationId)}>
          Refresh chat log
        </button>
        <p className="subtle">Messages in this conversation: {messages.length}</p>
        {lastExtractionSummary ? <p className="subtle">{lastExtractionSummary}</p> : null}
      </section>

      <section className="panel chatMainPanel">
        <div className="sectionTitleRow">
          <h2>Chatroom</h2>
          <span className="subtle">{conversationId}</span>
        </div>
        {error ? <p className="errorText">{error}</p> : null}
        <div ref={transcriptRef} className="chatTranscriptModern">
          {loading ? (
            <p className="muted">Loading chat log...</p>
          ) : sortedMessages.length === 0 ? (
            <p className="muted">No messages yet. Start the conversation below.</p>
          ) : (
            sortedMessages.map((message) => {
              const isEditing = editingMessageId === message.id;
              const isDeletePending = pendingDeleteMessageId === message.id;
              return (
                <article
                  key={message.id}
                  className={`chatBubbleModern ${message.role === "assistant" ? "assistant" : "user"}`}
                >
                  <div className="messageMeta">
                    <span className="tag">{message.role}</span>
                    <span className="muted">#{message.id}</span>
                    <span className="muted">{formatTimestamp(message.timestamp)}</span>
                  </div>
                  {isEditing ? (
                    <textarea
                      className="input chatEditInput"
                      value={editingDraft}
                      onChange={(event) => setEditingDraft(event.target.value)}
                    />
                  ) : (
                    <p>{message.content}</p>
                  )}
                  {message.id > 0 ? (
                    <div className="chatActions">
                      {isEditing ? (
                        <>
                          <button
                            className="button"
                            type="button"
                            onClick={() => void saveEditedMessage(message.id)}
                            disabled={savingMessageId === message.id}
                          >
                            Save
                          </button>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={cancelEditMessage}
                            disabled={savingMessageId === message.id}
                          >
                            Cancel
                          </button>
                        </>
                      ) : isDeletePending ? (
                        <div className="inlineConfirm">
                          <span className="inlineConfirmText">Delete message #{message.id}?</span>
                          <button
                            className="button danger"
                            type="button"
                            onClick={() => void confirmDeleteMessage(message.id)}
                            disabled={savingMessageId === message.id}
                          >
                            Confirm delete
                          </button>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={cancelDeleteMessage}
                            disabled={savingMessageId === message.id}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={() => beginEditMessage(message)}
                            disabled={savingMessageId === message.id}
                          >
                            Edit
                          </button>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={() => requestDeleteMessage(message.id)}
                            disabled={savingMessageId === message.id}
                          >
                            Delete
                          </button>
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
                <span className="tag">assistant</span>
              </div>
              <p>Thinking...</p>
            </article>
          ) : null}
        </div>

        <form className="chatComposerModern" onSubmit={sendTurn}>
          <textarea
            className="input chatComposerInputModern"
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
            <button className="button" type="submit" disabled={thinking || !draft.trim()}>
              {thinking ? "Sending..." : "Send"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
