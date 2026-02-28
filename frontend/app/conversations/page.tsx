"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { type ConversationsListResponse, getConversations } from "../../lib/api";
import { formatTimestamp } from "../../lib/format";

const PAGE_SIZE = 20;

export default function ConversationsPage() {
  const [queryDraft, setQueryDraft] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<ConversationsListResponse | null>(null);

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

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setAppliedQuery(queryDraft.trim());
  }

  const total = payload?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div className="stackLg">
      <section className="panel">
        <h2>Conversations</h2>
        <p className="subtle">Browse chat histories and jump into summary drilldowns.</p>
        <form className="toolbar" onSubmit={handleSearchSubmit}>
          <input
            className="input"
            placeholder="Filter by conversation id..."
            value={queryDraft}
            onChange={(event) => setQueryDraft(event.target.value)}
          />
          <button className="button" type="submit">
            Apply
          </button>
        </form>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}

      <section className="panel">
        {loading ? (
          <p>Loading conversations...</p>
        ) : (
          <>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Conversation</th>
                    <th>Last Updated</th>
                    <th>Messages</th>
                    <th>Entities</th>
                    <th>Facts</th>
                    <th>Relations</th>
                    <th>Runs</th>
                  </tr>
                </thead>
                <tbody>
                  {(payload?.items ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={7} className="emptyCell">
                        No conversations found.
                      </td>
                    </tr>
                  ) : (
                    payload?.items.map((item) => (
                      <tr key={item.conversation_id}>
                        <td>
                          <Link href={`/conversations/${encodeURIComponent(item.conversation_id)}`}>
                            {item.conversation_id}
                          </Link>
                        </td>
                        <td>{formatTimestamp(item.last_message_at)}</td>
                        <td>{item.message_count}</td>
                        <td>{item.entity_count}</td>
                        <td>{item.fact_count}</td>
                        <td>{item.relation_count}</td>
                        <td>{item.extractor_run_count}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button className="button ghost" type="button" disabled={!canPrev} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </button>
              <span>
                {total === 0 ? 0 : offset + 1} - {Math.min(total, offset + PAGE_SIZE)} of {total}
              </span>
              <button className="button ghost" type="button" disabled={!canNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

