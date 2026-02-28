"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  type SchemaOverviewData,
  deleteSchemaField,
  deleteSchemaNode,
  deleteSchemaRelation,
  getSchemaOverview,
  updateSchemaField,
  updateSchemaNode,
  updateSchemaRelation
} from "../../lib/api";
import { formatTimestamp } from "../../lib/format";

const PAGE_SIZE = 25;

function sanitizeAnchor(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function proposalAnchorLinks(payload: Record<string, unknown>): Array<{ label: string; href: string }> {
  const links: Array<{ label: string; href: string }> = [];
  const canonical = typeof payload.canonical_label === "string" ? payload.canonical_label : null;
  const merged = typeof payload.merged_label === "string" ? payload.merged_label : null;
  const table = typeof payload.table_name === "string" ? payload.table_name : null;
  const section =
    table === "schema_fields"
      ? "field"
      : table === "schema_relations"
        ? "relation"
        : table === "schema_nodes"
          ? "node"
          : null;
  if (!section) {
    return links;
  }
  if (canonical) {
    links.push({ label: `canonical:${canonical}`, href: `#${section}-${sanitizeAnchor(canonical)}` });
  }
  if (merged) {
    links.push({ label: `merged:${merged}`, href: `#${section}-${sanitizeAnchor(merged)}` });
  }
  return links;
}

export default function SchemaPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<SchemaOverviewData | null>(null);
  const [filter, setFilter] = useState("");
  const [nodeLimit, setNodeLimit] = useState(PAGE_SIZE);
  const [fieldLimit, setFieldLimit] = useState(PAGE_SIZE);
  const [relationLimit, setRelationLimit] = useState(PAGE_SIZE);
  const [proposalLimit, setProposalLimit] = useState(PAGE_SIZE);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ label: "", description: "", examples: "" });
  const [pendingDeleteKey, setPendingDeleteKey] = useState<string | null>(null);
  const hasLoadedOnceRef = useRef(false);

  useEffect(() => {
    let active = true;
    async function load() {
      if (hasLoadedOnceRef.current) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const data = await getSchemaOverview({ limit: 1000, proposal_limit: 1000 });
        if (!active) {
          return;
        }
        setOverview(data);
        hasLoadedOnceRef.current = true;
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load schema overview.");
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [refreshNonce]);

  const query = filter.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!overview) {
      return null;
    }
    if (!query) {
      return overview;
    }
    return {
      nodes: overview.nodes.filter((node) =>
        `${node.label} ${node.description ?? ""} ${node.examples.join(" ")}`.toLowerCase().includes(query)
      ),
      fields: overview.fields.filter((field) =>
        `${field.label} ${field.canonical_label ?? ""} ${field.description ?? ""} ${field.examples.join(" ")}`
          .toLowerCase()
          .includes(query)
      ),
      relations: overview.relations.filter((relation) =>
        `${relation.label} ${relation.canonical_label ?? ""} ${relation.description ?? ""} ${relation.examples.join(" ")}`
          .toLowerCase()
          .includes(query)
      ),
      proposals: overview.proposals.filter((proposal) =>
        `${proposal.proposal_type} ${proposal.status} ${JSON.stringify(proposal.payload)} ${JSON.stringify(proposal.evidence)}`
          .toLowerCase()
          .includes(query)
      )
    };
  }, [overview, query]);

  function parseExamples(input: string, fallback: string[]): string[] {
    const clean = input.trim();
    if (!clean) {
      return [];
    }
    try {
      const parsed = JSON.parse(clean);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item)).filter((item) => item.trim().length > 0);
      }
    } catch {
      // Fall back to pipe/comma separated values.
    }
    const splitOnPipe = clean.includes("|");
    const chunks = clean.split(splitOnPipe ? "|" : ",");
    const values = chunks.map((item) => item.trim()).filter(Boolean);
    return values.length > 0 ? values : fallback;
  }

  function beginInlineEdit(key: string, label: string, description: string | null, examples: string[]) {
    setEditingKey(key);
    setEditDraft({
      label,
      description: description ?? "",
      examples: JSON.stringify(examples)
    });
    setPendingDeleteKey(null);
  }

  function cancelInlineEdit() {
    setEditingKey(null);
    setEditDraft({ label: "", description: "", examples: "" });
  }

  async function saveInlineEdit(
    kind: "node" | "field" | "relation",
    id: number,
    key: string,
    fallbackLabel: string,
    fallbackDescription: string | null,
    fallbackExamples: string[]
  ) {
    const nextLabel = editDraft.label.trim();
    if (!nextLabel) {
      setError("Label is required.");
      return;
    }
    const nextDescription = editDraft.description.trim();
    const nextExamples = parseExamples(editDraft.examples, fallbackExamples);
    setBusyKey(key);
    setError(null);
    try {
      if (kind === "node") {
        await updateSchemaNode(id, {
          label: nextLabel || fallbackLabel,
          description: nextDescription || fallbackDescription || null,
          examples_json: nextExamples
        });
      } else if (kind === "field") {
        await updateSchemaField(id, {
          label: nextLabel || fallbackLabel,
          description: nextDescription || fallbackDescription || null,
          examples_json: nextExamples
        });
      } else {
        await updateSchemaRelation(id, {
          label: nextLabel || fallbackLabel,
          description: nextDescription || fallbackDescription || null,
          examples_json: nextExamples
        });
      }
      cancelInlineEdit();
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : kind === "node"
            ? "Failed to update schema node."
            : kind === "field"
              ? "Failed to update schema field."
              : "Failed to update schema relation."
      );
    } finally {
      setBusyKey(null);
    }
  }

  function requestDelete(key: string) {
    if (editingKey === key) {
      cancelInlineEdit();
    }
    setPendingDeleteKey(key);
  }

  function cancelDelete() {
    setPendingDeleteKey(null);
  }

  async function confirmDelete(kind: "node" | "field" | "relation", id: number, key: string) {
    setBusyKey(key);
    setError(null);
    try {
      if (kind === "node") {
        await deleteSchemaNode(id);
      } else if (kind === "field") {
        await deleteSchemaField(id);
      } else {
        await deleteSchemaRelation(id);
      }
      setPendingDeleteKey((current) => (current === key ? null : current));
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : kind === "node"
            ? "Failed to delete schema node."
            : kind === "field"
              ? "Failed to delete schema field."
              : "Failed to delete schema relation."
      );
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="stackLg schemaExplorer">
      <section className="panel schemaPanel">
        <h2>Schema Explorer</h2>
        <p className="subtle">
          Read-only transparency view of learned types, fields, relations, and stabilization proposals.
        </p>
        {refreshing ? <p className="subtle">Refreshing schema changes...</p> : null}
        <div className="toolbar">
          <input
            className="input"
            placeholder="Filter schema + proposals..."
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}
      {loading ? (
        <section className="panel">Loading schema...</section>
      ) : filtered ? (
        <>
          <section className="panel schemaPanel">
            <h3>Types (schema_nodes)</h3>
            <div className="tableWrap schemaTableWrap">
              <table className="table schemaTable">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Description</th>
                    <th>Examples</th>
                    <th>Frequency</th>
                    <th>Last Seen Conversation</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.nodes.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="emptyCell">
                        No learned types.
                      </td>
                    </tr>
                  ) : (
                    filtered.nodes.slice(0, nodeLimit).map((node) => {
                      const rowKey = `node-${node.id}`;
                      const isEditing = editingKey === rowKey;
                      const isDeletePending = pendingDeleteKey === rowKey;
                      return (
                        <tr key={node.id} id={`node-${sanitizeAnchor(node.label)}`}>
                          <td>
                            {isEditing ? (
                              <input
                                className="input compactInput"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              node.label
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              node.description ?? "-"
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              node.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </td>
                          <td>{node.frequency}</td>
                          <td>{node.last_seen_conversation_id ?? "-"}</td>
                          <td>
                            {isEditing ? (
                              <div className="inlineActions">
                                <button
                                  className="button"
                                  type="button"
                                  onClick={() =>
                                    void saveInlineEdit(
                                      "node",
                                      node.id,
                                      rowKey,
                                      node.label,
                                      node.description,
                                      node.examples
                                    )
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Save
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : isDeletePending ? (
                              <div className="inlineConfirm">
                                <span className="inlineConfirmText">Delete type "{node.label}"?</span>
                                <button
                                  className="button danger"
                                  type="button"
                                  onClick={() => void confirmDelete("node", node.id, rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Confirm delete
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelDelete}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    beginInlineEdit(rowKey, node.label, node.description, node.examples)
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {filtered.nodes.length > nodeLimit ? (
              <button className="button ghost" type="button" onClick={() => setNodeLimit((current) => current + PAGE_SIZE)}>
                Load more types
              </button>
            ) : null}
          </section>

          <section className="panel schemaPanel">
            <h3>Fields (schema_fields)</h3>
            <div className="tableWrap schemaTableWrap">
              <table className="table schemaTable">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Canonical</th>
                    <th>Cluster Hint</th>
                    <th>Description</th>
                    <th>Examples</th>
                    <th>Frequency</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.fields.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="emptyCell">
                        No learned fields.
                      </td>
                    </tr>
                  ) : (
                    filtered.fields.slice(0, fieldLimit).map((field) => {
                      const rowKey = `field-${field.id}`;
                      const isEditing = editingKey === rowKey;
                      const isDeletePending = pendingDeleteKey === rowKey;
                      return (
                        <tr key={field.id} id={`field-${sanitizeAnchor(field.label)}`}>
                          <td>
                            {isEditing ? (
                              <input
                                className="input compactInput"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              field.label
                            )}
                          </td>
                          <td>{field.canonical_label ?? field.label}</td>
                          <td>
                            {field.canonical_label && field.canonical_label !== field.label
                              ? `clustered under ${field.canonical_label}`
                              : "canonical root"}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              field.description ?? "-"
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              field.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </td>
                          <td>{field.frequency}</td>
                          <td>
                            {isEditing ? (
                              <div className="inlineActions">
                                <button
                                  className="button"
                                  type="button"
                                  onClick={() =>
                                    void saveInlineEdit(
                                      "field",
                                      field.id,
                                      rowKey,
                                      field.label,
                                      field.description,
                                      field.examples
                                    )
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Save
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : isDeletePending ? (
                              <div className="inlineConfirm">
                                <span className="inlineConfirmText">Delete field "{field.label}"?</span>
                                <button
                                  className="button danger"
                                  type="button"
                                  onClick={() => void confirmDelete("field", field.id, rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Confirm delete
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelDelete}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    beginInlineEdit(rowKey, field.label, field.description, field.examples)
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {filtered.fields.length > fieldLimit ? (
              <button className="button ghost" type="button" onClick={() => setFieldLimit((current) => current + PAGE_SIZE)}>
                Load more fields
              </button>
            ) : null}
          </section>

          <section className="panel schemaPanel">
            <h3>Relations (schema_relations)</h3>
            <div className="tableWrap schemaTableWrap">
              <table className="table schemaTable">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Canonical</th>
                    <th>Description</th>
                    <th>Examples</th>
                    <th>Frequency</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.relations.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="emptyCell">
                        No learned relations.
                      </td>
                    </tr>
                  ) : (
                    filtered.relations.slice(0, relationLimit).map((relation) => {
                      const rowKey = `relation-${relation.id}`;
                      const isEditing = editingKey === rowKey;
                      const isDeletePending = pendingDeleteKey === rowKey;
                      return (
                        <tr key={relation.id} id={`relation-${sanitizeAnchor(relation.label)}`}>
                          <td>
                            {isEditing ? (
                              <input
                                className="input compactInput"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              relation.label
                            )}
                          </td>
                          <td>{relation.canonical_label ?? relation.label}</td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              relation.description ?? "-"
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              relation.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </td>
                          <td>{relation.frequency}</td>
                          <td>
                            {isEditing ? (
                              <div className="inlineActions">
                                <button
                                  className="button"
                                  type="button"
                                  onClick={() =>
                                    void saveInlineEdit(
                                      "relation",
                                      relation.id,
                                      rowKey,
                                      relation.label,
                                      relation.description,
                                      relation.examples
                                    )
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Save
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : isDeletePending ? (
                              <div className="inlineConfirm">
                                <span className="inlineConfirmText">Delete relation "{relation.label}"?</span>
                                <button
                                  className="button danger"
                                  type="button"
                                  onClick={() => void confirmDelete("relation", relation.id, rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Confirm delete
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelDelete}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    beginInlineEdit(
                                      rowKey,
                                      relation.label,
                                      relation.description,
                                      relation.examples
                                    )
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {filtered.relations.length > relationLimit ? (
              <button
                className="button ghost"
                type="button"
                onClick={() => setRelationLimit((current) => current + PAGE_SIZE)}
              >
                Load more relations
              </button>
            ) : null}
          </section>

          <section className="panel schemaPanel">
            <h3>Proposals (schema_proposals)</h3>
            <div className="tableWrap schemaTableWrap">
              <table className="table schemaTable">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Confidence</th>
                    <th>Affected Items</th>
                    <th>Created</th>
                    <th>Rationale/Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.proposals.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="emptyCell">
                        No proposals.
                      </td>
                    </tr>
                  ) : (
                    filtered.proposals.slice(0, proposalLimit).map((proposal) => {
                      const links = proposalAnchorLinks(proposal.payload);
                      return (
                        <tr key={proposal.id}>
                          <td>{proposal.proposal_type}</td>
                          <td>{proposal.status}</td>
                          <td>{proposal.confidence.toFixed(2)}</td>
                          <td>
                            {links.length === 0
                              ? "-"
                              : links.map((link) => (
                                  <a
                                    key={`${proposal.id}-${link.href}`}
                                    href={link.href}
                                    className="inlineLink schemaInlineLink"
                                  >
                                    {link.label}
                                  </a>
                                ))}
                          </td>
                          <td>{formatTimestamp(proposal.created_at)}</td>
                          <td>
                            <details className="schemaDetails">
                              <summary>View</summary>
                              <pre className="codeMini schemaCodeMini">
                                {JSON.stringify(
                                  {
                                    payload: proposal.payload,
                                    evidence: proposal.evidence
                                  },
                                  null,
                                  2
                                )}
                              </pre>
                            </details>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {filtered.proposals.length > proposalLimit ? (
              <button
                className="button ghost"
                type="button"
                onClick={() => setProposalLimit((current) => current + PAGE_SIZE)}
              >
                Load more proposals
              </button>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
