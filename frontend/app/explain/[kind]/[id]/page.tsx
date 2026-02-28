"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  type FactExplainData,
  type RelationExplainData,
  getFactExplain,
  getRelationExplain
} from "../../../../lib/api";
import { formatTimestamp } from "../../../../lib/format";

export default function ExplainRecordPage() {
  const params = useParams<{ kind: string; id: string }>();
  const kind = params.kind;
  const recordId = useMemo(() => Number.parseInt(params.id, 10), [params.id]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [factData, setFactData] = useState<FactExplainData | null>(null);
  const [relationData, setRelationData] = useState<RelationExplainData | null>(null);

  useEffect(() => {
    if (!Number.isFinite(recordId) || recordId < 1) {
      setError("Invalid record id.");
      setLoading(false);
      return;
    }
    if (kind !== "facts" && kind !== "relations") {
      setError("Kind must be 'facts' or 'relations'.");
      setLoading(false);
      return;
    }
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        if (kind === "facts") {
          const data = await getFactExplain(recordId);
          if (active) {
            setFactData(data);
            setRelationData(null);
          }
        } else {
          const data = await getRelationExplain(recordId);
          if (active) {
            setRelationData(data);
            setFactData(null);
          }
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load explainability details.");
        }
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
  }, [kind, recordId]);

  return (
    <div className="stackLg">
      <section className="panel">
        <h2>Explain: {kind}</h2>
        <p className="subtle">Record-level provenance, extraction metadata, and canonicalization context.</p>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}
      {loading ? (
        <section className="panel">Loading explain data...</section>
      ) : factData ? (
        <>
          <section className="panel">
            <h3>Record</h3>
            <p>
              {factData.fact.subject_entity_name} {factData.fact.predicate} {factData.fact.object_value}
            </p>
            <p className="subtle">Extractor run: {factData.extractor_run_id ?? "-"}</p>
            <p className="subtle">Confidence: {factData.fact.confidence.toFixed(2)}</p>
            <p className="subtle">
              Model: {factData.extraction_metadata?.model_name ?? "-"} | Prompt:{" "}
              {factData.extraction_metadata?.prompt_version ?? "-"} | Run at{" "}
              {formatTimestamp(factData.extraction_metadata?.created_at)}
            </p>
          </section>
          <section className="panel">
            <h3>Canonicalization</h3>
            <p className="subtle">Observed: {factData.schema_canonicalization.observed_label}</p>
            <p className="subtle">
              Canonical: {factData.schema_canonicalization.canonical_label ?? "(none)"} (
              {factData.schema_canonicalization.status})
            </p>
            {factData.schema_canonicalization.proposal ? (
              <p className="subtle">
                Proposal #{factData.schema_canonicalization.proposal.proposal_id} (
                {factData.schema_canonicalization.proposal.status}) confidence{" "}
                {factData.schema_canonicalization.proposal.confidence.toFixed(2)}
              </p>
            ) : (
              <p className="subtle">Proposal: none</p>
            )}
          </section>
          <section className="panel">
            <h3>Snippets</h3>
            <ul className="simpleList">
              {factData.snippets.length === 0 ? (
                <li className="muted">No snippet matches found.</li>
              ) : (
                factData.snippets.map((snippet, index) => <li key={`${index}-${snippet}`}>{snippet}</li>)
              )}
            </ul>
          </section>
          <section className="panel">
            <h3>Source Messages</h3>
            <ul className="simpleList">
              {factData.source_messages.map((message) => (
                <li key={message.id}>
                  <strong>{message.role}</strong> #{message.id} at {formatTimestamp(message.timestamp)}
                  <p>{message.content}</p>
                </li>
              ))}
            </ul>
          </section>
          <section className="panel">
            <h3>Resolution Events</h3>
            <ul className="simpleList">
              {factData.resolution_events.length === 0 ? (
                <li className="muted">No related resolution events.</li>
              ) : (
                factData.resolution_events.map((event) => (
                  <li key={event.id}>
                    {event.event_type} | entities [{event.entity_ids_json.join(", ")}] |{" "}
                    {event.rationale}
                  </li>
                ))
              )}
            </ul>
          </section>
        </>
      ) : relationData ? (
        <>
          <section className="panel">
            <h3>Record</h3>
            <p>
              {relationData.relation.from_entity_name} {relationData.relation.relation_type}{" "}
              {relationData.relation.to_entity_name}
            </p>
            <p className="subtle">Extractor run: {relationData.extractor_run_id ?? "-"}</p>
            <p className="subtle">Confidence: {relationData.relation.confidence.toFixed(2)}</p>
            <p className="subtle">
              Model: {relationData.extraction_metadata?.model_name ?? "-"} | Prompt:{" "}
              {relationData.extraction_metadata?.prompt_version ?? "-"} | Run at{" "}
              {formatTimestamp(relationData.extraction_metadata?.created_at)}
            </p>
          </section>
          <section className="panel">
            <h3>Canonicalization</h3>
            <p className="subtle">Observed: {relationData.schema_canonicalization.observed_label}</p>
            <p className="subtle">
              Canonical: {relationData.schema_canonicalization.canonical_label ?? "(none)"} (
              {relationData.schema_canonicalization.status})
            </p>
            {relationData.schema_canonicalization.proposal ? (
              <p className="subtle">
                Proposal #{relationData.schema_canonicalization.proposal.proposal_id} (
                {relationData.schema_canonicalization.proposal.status}) confidence{" "}
                {relationData.schema_canonicalization.proposal.confidence.toFixed(2)}
              </p>
            ) : (
              <p className="subtle">Proposal: none</p>
            )}
          </section>
          <section className="panel">
            <h3>Snippets</h3>
            <ul className="simpleList">
              {relationData.snippets.length === 0 ? (
                <li className="muted">No snippet matches found.</li>
              ) : (
                relationData.snippets.map((snippet, index) => (
                  <li key={`${index}-${snippet}`}>{snippet}</li>
                ))
              )}
            </ul>
          </section>
          <section className="panel">
            <h3>Source Messages</h3>
            <ul className="simpleList">
              {relationData.source_messages.map((message) => (
                <li key={message.id}>
                  <strong>{message.role}</strong> #{message.id} at {formatTimestamp(message.timestamp)}
                  <p>{message.content}</p>
                </li>
              ))}
            </ul>
          </section>
          <section className="panel">
            <h3>Resolution Events</h3>
            <ul className="simpleList">
              {relationData.resolution_events.length === 0 ? (
                <li className="muted">No related resolution events.</li>
              ) : (
                relationData.resolution_events.map((event) => (
                  <li key={event.id}>
                    {event.event_type} | entities [{event.entity_ids_json.join(", ")}] |{" "}
                    {event.rationale}
                  </li>
                ))
              )}
            </ul>
          </section>
        </>
      ) : (
        <section className="panel">No explain payload found.</section>
      )}
    </div>
  );
}
