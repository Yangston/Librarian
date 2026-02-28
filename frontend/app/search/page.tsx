"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { type SemanticSearchData, runSemanticSearch } from "../../lib/api";
import { formatScore, formatTimestamp } from "../../lib/format";

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
      router.replace(`/search?${query.toString()}`);
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
    <div className="stackLg">
      <section className="panel">
        <h2>Search</h2>
        <p className="subtle">Semantic-first navigation with conversation/type/time filters.</p>
        <form className="gridForm searchForm" onSubmit={handleSubmit}>
          <label className="field">
            <span>Query</span>
            <input
              className="input"
              placeholder="Apple supply chain risk"
              value={queryDraft}
              onChange={(event) => setQueryDraft(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Conversation Scope</span>
            <input
              className="input"
              placeholder="conversation id"
              value={conversationScope}
              onChange={(event) => setConversationScope(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Type Label</span>
            <input
              className="input"
              placeholder="Company"
              value={typeLabel}
              onChange={(event) => setTypeLabel(event.target.value)}
            />
          </label>
          <label className="field">
            <span>From Date</span>
            <input
              className="input"
              type="date"
              value={fromDate}
              onChange={(event) => setFromDate(event.target.value)}
            />
          </label>
          <label className="field">
            <span>To Date</span>
            <input
              className="input"
              type="date"
              value={toDate}
              onChange={(event) => setToDate(event.target.value)}
            />
          </label>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </form>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}

      {result ? (
        <section className="stackLg">
          <section className="panel">
            <h3>Active Filters</h3>
            <p className="subtle">
              Query: <strong>{result.query}</strong> | Conversation: {result.conversation_id ?? "-"} | Type:{" "}
              {result.type_label ?? "-"} | From: {formatTimestamp(result.start_time)} | To:{" "}
              {formatTimestamp(result.end_time)}
            </p>
          </section>

          <article className="panel">
            <h3>Entities</h3>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Entity</th>
                    <th>Preview</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {result.entities.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="emptyCell">
                        No entity hits.
                      </td>
                    </tr>
                  ) : (
                    result.entities.map((hit) => (
                      <tr key={hit.entity.id}>
                        <td>{formatScore(hit.similarity, 3)}</td>
                        <td>
                          <Link href={`/entities/${hit.entity.id}`}>{hit.entity.canonical_name}</Link>
                        </td>
                        <td>
                          aliases:{" "}
                          {(hit.entity.known_aliases_json ?? []).slice(0, 3).join(", ") || "(none)"} | updated{" "}
                          {formatTimestamp(hit.entity.updated_at)}
                        </td>
                        <td>{hit.entity.type_label || "-"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <article className="panel">
            <h3>Facts</h3>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Fact</th>
                    <th>Preview</th>
                    <th>Explain</th>
                  </tr>
                </thead>
                <tbody>
                  {result.facts.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="emptyCell">
                        No fact hits.
                      </td>
                    </tr>
                  ) : (
                    result.facts.map((hit) => (
                      <tr key={hit.fact.id}>
                        <td>{formatScore(hit.similarity, 3)}</td>
                        <td>
                          {hit.fact.subject_entity_name} {hit.fact.predicate} {hit.fact.object_value}
                        </td>
                        <td>
                          scope: {hit.fact.scope} | created: {formatTimestamp(hit.fact.created_at)}
                        </td>
                        <td>
                          <Link href={`/explain/facts/${hit.fact.id}`}>Explain</Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      ) : (
        <section className="panel muted">Run a search to see grouped results.</section>
      )}
    </div>
  );
}

