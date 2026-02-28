"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  type ConversationsListResponse,
  type RecentEntitiesResponse,
  type SchemaOverviewData,
  getConversations,
  getRecentEntities,
  getSchemaOverview
} from "../../lib/api";
import { formatTimestamp } from "../../lib/format";

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
    router.push(`/search?q=${encodeURIComponent(clean)}`);
  }

  return (
    <div className="stackLg">
      <section className="panel hero">
        <h2>Workspace Dashboard</h2>
        <p className="subtle">
          Start with search, then drill down into conversations, entities, and schema stabilization.
        </p>
        <form className="toolbar" onSubmit={submitSearch}>
          <input
            className="input"
            placeholder="Search entities and facts..."
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
          />
          <button className="button" type="submit">
            Search
          </button>
        </form>
        <div className="quickLinks">
          <Link href="/chat" className="quickCard">
            <strong>Chat</strong>
            <span>Live chatroom with extraction</span>
          </Link>
          <Link href="/graph" className="quickCard">
            <strong>Graph Studio</strong>
            <span>Conversation-wide node graph</span>
          </Link>
          <Link href="/entities" className="quickCard">
            <strong>Entities</strong>
            <span>Global records table</span>
          </Link>
          <Link href="/schema" className="quickCard">
            <strong>Schema Explorer</strong>
            <span>Learned types, fields, and relations</span>
          </Link>
          <Link href="/conversations" className="quickCard">
            <strong>Conversations</strong>
            <span>Message logs and extraction summaries</span>
          </Link>
        </div>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}

      {loading ? (
        <section className="panel">Loading workspace...</section>
      ) : (
        <>
          <section className="gridStats">
            <article className="statCard">
              <span>Conversations</span>
              <strong>{conversations?.total ?? 0}</strong>
            </article>
            <article className="statCard">
              <span>Recent Entities</span>
              <strong>{recentEntities?.items.length ?? 0}</strong>
            </article>
            <article className="statCard">
              <span>Schema Fields</span>
              <strong>{schemaOverview?.fields.length ?? 0}</strong>
            </article>
            <article className="statCard">
              <span>Open Proposals</span>
              <strong>
                {schemaOverview?.proposals.filter((proposal) => proposal.status === "proposed").length ?? 0}
              </strong>
            </article>
          </section>

          <section className="gridTwo">
            <article className="panel">
              <div className="sectionTitleRow">
                <h3>Recent Conversations</h3>
                <Link href="/conversations">View all</Link>
              </div>
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Conversation</th>
                      <th>Updated</th>
                      <th>Entities</th>
                      <th>Facts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(conversations?.items ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={4} className="emptyCell">
                          No conversations yet.
                        </td>
                      </tr>
                    ) : (
                      conversations?.items.map((item) => (
                        <tr key={item.conversation_id}>
                          <td>
                            <Link href={`/conversations/${encodeURIComponent(item.conversation_id)}`}>
                              {item.conversation_id}
                            </Link>
                          </td>
                          <td>{formatTimestamp(item.last_message_at)}</td>
                          <td>{item.entity_count}</td>
                          <td>{item.fact_count}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="panel">
              <div className="sectionTitleRow">
                <h3>Recently Updated Entities</h3>
                <Link href="/entities">View all</Link>
              </div>
              <ul className="simpleList">
                {(recentEntities?.items ?? []).length === 0 ? (
                  <li className="muted">No entities yet.</li>
                ) : (
                  recentEntities?.items.map((entity) => (
                    <li key={entity.entity_id}>
                      <Link href={`/entities/${entity.entity_id}`}>
                        {entity.canonical_name}
                        <span className="muted"> ({entity.type_label || "untyped"})</span>
                      </Link>
                    </li>
                  ))
                )}
              </ul>
            </article>
          </section>

          <section className="panel">
            <div className="sectionTitleRow">
              <h3>Recent Schema Changes</h3>
              <Link href="/schema">Open schema explorer</Link>
            </div>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Confidence</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {(schemaOverview?.proposals ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="emptyCell">
                        No schema proposals yet.
                      </td>
                    </tr>
                  ) : (
                    schemaOverview?.proposals.slice(0, 12).map((proposal) => (
                      <tr key={proposal.id}>
                        <td>{proposal.proposal_type}</td>
                        <td>{proposal.status}</td>
                        <td>{proposal.confidence.toFixed(2)}</td>
                        <td>{formatTimestamp(proposal.created_at)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
