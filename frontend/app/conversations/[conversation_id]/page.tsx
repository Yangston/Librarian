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
} from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";

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
    <div className="stackLg">
      <section className="panel">
        <div className="sectionTitleRow">
          <h2>{conversationId}</h2>
          <button className="button" type="button" onClick={handleRerunExtraction} disabled={rerunning}>
            {rerunning ? "Re-running..." : "Re-run Extraction"}
          </button>
        </div>
        <p className="subtle">Inspect the raw chat log or the structured summary generated from it.</p>
        <p className="subtle">
          <Link href={`/graph?conversation_id=${encodeURIComponent(conversationId)}`}>Open graph studio</Link> |{" "}
          <Link href={`/chat?conversation_id=${encodeURIComponent(conversationId)}`}>Open chatroom</Link>
        </p>
        <div className="tabRow">
          <button className={tab === "chat" ? "button" : "button ghost"} type="button" onClick={() => setTab("chat")}>
            Chat Log
          </button>
          <button className={tab === "summary" ? "button" : "button ghost"} type="button" onClick={() => setTab("summary")}>
            Conversation Summary
          </button>
        </div>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}

      {loading ? (
        <section className="panel">Loading conversation details...</section>
      ) : tab === "chat" ? (
        <section className="panel">
          <h3>Messages</h3>
          <div className="messageStack">
            {messages.length === 0 ? (
              <p className="muted">No messages found for this conversation.</p>
            ) : (
              messages.map((message) => (
                (() => {
                  const isEditing = editingMessageId === message.id;
                  const isDeletePending = pendingDeleteMessageId === message.id;
                  return (
                    <article key={message.id} className="messageCard">
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
                      <div className="toolbar">
                        {isEditing ? (
                          <>
                            <button
                              className="button"
                              type="button"
                              onClick={() => void saveEditedMessage(message.id)}
                              disabled={busyMessageId === message.id}
                            >
                              Save
                            </button>
                            <button
                              className="button ghost"
                              type="button"
                              onClick={cancelEditMessage}
                              disabled={busyMessageId === message.id}
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
                              disabled={busyMessageId === message.id}
                            >
                              Confirm delete
                            </button>
                            <button
                              className="button ghost"
                              type="button"
                              onClick={cancelDeleteMessage}
                              disabled={busyMessageId === message.id}
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
                              disabled={busyMessageId === message.id}
                            >
                              Edit
                            </button>
                            <button
                              className="button ghost"
                              type="button"
                              onClick={() => requestDeleteMessage(message.id)}
                              disabled={busyMessageId === message.id}
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </article>
                  );
                })()
              ))
            )}
          </div>
        </section>
      ) : (
        <section className="stackLg">
          <article className="panel">
            <h3>Key Entities</h3>
            <ul className="simpleList">
              {(summary?.key_entities ?? []).length === 0 ? (
                <li className="muted">No entities found.</li>
              ) : (
                summary?.key_entities.map((entity) => (
                  <li key={entity.id}>
                    <Link href={`/entities/${entity.id}`}>{entity.canonical_name}</Link>
                    <span className="muted"> ({entity.type_label || "untyped"})</span>
                  </li>
                ))
              )}
            </ul>
          </article>

          <article className="panel">
            <h3>Key Facts</h3>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>Field</th>
                    <th>Value</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.key_facts ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="emptyCell">
                        No facts found.
                      </td>
                    </tr>
                  ) : (
                    summary?.key_facts.map((fact) => (
                      <tr key={fact.id}>
                        <td>{fact.subject_entity_name}</td>
                        <td>{fact.predicate}</td>
                        <td>{fact.object_value}</td>
                        <td>{fact.confidence.toFixed(2)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <article className="gridTwo">
            <div className="panel">
              <h3>Schema Learned in This Conversation</h3>
              <p className="muted">
                Types: {(summary?.schema_changes_triggered.node_labels ?? []).join(", ") || "-"}
              </p>
              <p className="muted">
                Fields: {(summary?.schema_changes_triggered.field_labels ?? []).join(", ") || "-"}
              </p>
              <p className="muted">
                Relations: {(summary?.schema_changes_triggered.relation_labels ?? []).join(", ") || "-"}
              </p>
            </div>
            <div className="panel">
              <h3>Relation Clusters</h3>
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
            </div>
          </article>
        </section>
      )}
    </div>
  );
}
