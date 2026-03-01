"use client";

import Link from "next/link";
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
} from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../components/ui/delete-controls";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

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

  const pendingDeleteTarget = useMemo(() => {
    if (!pendingDeleteKey || !overview) {
      return null;
    }
    const match = /^(node|field|relation)-(\d+)$/.exec(pendingDeleteKey);
    if (!match) {
      return null;
    }
    const kind = match[1] as "node" | "field" | "relation";
    const id = Number.parseInt(match[2], 10);
    if (!Number.isFinite(id)) {
      return null;
    }
    if (kind === "node") {
      const row = overview.nodes.find((node) => node.id === id);
      return row ? { kind, id, label: row.label } : null;
    }
    if (kind === "field") {
      const row = overview.fields.find((field) => field.id === id);
      return row ? { kind, id, label: row.label } : null;
    }
    const row = overview.relations.find((relation) => relation.id === id);
    return row ? { kind, id, label: row.label } : null;
  }, [overview, pendingDeleteKey]);

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
    <div className="stackLg routeFade schemaExplorer">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-3">
          <div className="viewHeader">
            <div className="viewTitle">
              <CardTitle className="text-xl">Schema Explorer</CardTitle>
              <p className="subtle">
                Read-only transparency view of learned types, fields, relations, and stabilization proposals.
              </p>
            </div>
            <div className="viewActions">
              <Button asChild variant="outline">
                <Link href="/app/search">Search by Schema Terms</Link>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {refreshing ? <p className="subtle">Refreshing schema changes...</p> : null}
          <div className="toolbar">
            <Input
              placeholder="Filter schema + proposals..."
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}
      {loading ? (
        <Card>
          <CardContent className="py-6">Loading schema...</CardContent>
        </Card>
      ) : filtered ? (
        <>
          <Card className="border-border/70 bg-card/95">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Types (schema_nodes)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <Table className="min-w-[960px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Examples</TableHead>
                    <TableHead>Frequency</TableHead>
                    <TableHead>Last Seen Conversation</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.nodes.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No learned types.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.nodes.slice(0, nodeLimit).map((node) => {
                      const rowKey = `node-${node.id}`;
                      const isEditing = editingKey === rowKey;
                      return (
                        <TableRow key={node.id} id={`node-${sanitizeAnchor(node.label)}`}>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8 max-w-[260px]"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              node.label
                            )}
                          </TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              node.description ?? "-"
                            )}
                          </TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              node.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </TableCell>
                          <TableCell>{node.frequency}</TableCell>
                          <TableCell>{node.last_seen_conversation_id ?? "-"}</TableCell>
                          <TableCell>
                            {isEditing ? (
                              <div className="inlineActions">
                                <Button
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
                                </Button>
                                <Button
                                  variant="outline"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <Button
                                  variant="outline"
                                  type="button"
                                  onClick={() =>
                                    beginInlineEdit(rowKey, node.label, node.description, node.examples)
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </Button>
                                <DeleteActionButton
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                />
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
              {filtered.nodes.length > nodeLimit ? (
                <Button variant="outline" type="button" onClick={() => setNodeLimit((current) => current + PAGE_SIZE)}>
                  Load more types
                </Button>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/95">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Fields (schema_fields)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <Table className="min-w-[1020px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Canonical</TableHead>
                    <TableHead>Cluster Hint</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Examples</TableHead>
                    <TableHead>Frequency</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.fields.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">
                        No learned fields.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.fields.slice(0, fieldLimit).map((field) => {
                      const rowKey = `field-${field.id}`;
                      const isEditing = editingKey === rowKey;
                      return (
                        <TableRow key={field.id} id={`field-${sanitizeAnchor(field.label)}`}>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8 max-w-[260px]"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              field.label
                            )}
                          </TableCell>
                          <TableCell>{field.canonical_label ?? field.label}</TableCell>
                          <TableCell>
                            {field.canonical_label && field.canonical_label !== field.label
                              ? `clustered under ${field.canonical_label}`
                              : "canonical root"}
                          </TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              field.description ?? "-"
                            )}
                          </TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              field.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </TableCell>
                          <TableCell>{field.frequency}</TableCell>
                          <TableCell>
                            {isEditing ? (
                              <div className="inlineActions">
                                <Button
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
                                </Button>
                                <Button
                                  variant="outline"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <Button
                                  variant="outline"
                                  type="button"
                                  onClick={() =>
                                    beginInlineEdit(rowKey, field.label, field.description, field.examples)
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </Button>
                                <DeleteActionButton
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                />
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            {filtered.fields.length > fieldLimit ? (
              <Button variant="outline" type="button" onClick={() => setFieldLimit((current) => current + PAGE_SIZE)}>
                Load more fields
              </Button>
            ) : null}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/95">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Relations (schema_relations)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <Table className="min-w-[960px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Canonical</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Examples</TableHead>
                    <TableHead>Frequency</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.relations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No learned relations.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.relations.slice(0, relationLimit).map((relation) => {
                      const rowKey = `relation-${relation.id}`;
                      const isEditing = editingKey === rowKey;
                      return (
                        <TableRow key={relation.id} id={`relation-${sanitizeAnchor(relation.label)}`}>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8 max-w-[260px]"
                                value={editDraft.label}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, label: event.target.value }))
                                }
                              />
                            ) : (
                              relation.label
                            )}
                          </TableCell>
                          <TableCell>{relation.canonical_label ?? relation.label}</TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.description}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, description: event.target.value }))
                                }
                              />
                            ) : (
                              relation.description ?? "-"
                            )}
                          </TableCell>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                className="h-8"
                                value={editDraft.examples}
                                onChange={(event) =>
                                  setEditDraft((current) => ({ ...current, examples: event.target.value }))
                                }
                              />
                            ) : (
                              relation.examples.slice(0, 4).join(" | ") || "-"
                            )}
                          </TableCell>
                          <TableCell>{relation.frequency}</TableCell>
                          <TableCell>
                            {isEditing ? (
                              <div className="inlineActions">
                                <Button
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
                                </Button>
                                <Button
                                  variant="outline"
                                  type="button"
                                  onClick={cancelInlineEdit}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <Button
                                  variant="outline"
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
                                </Button>
                                <DeleteActionButton
                                  type="button"
                                  onClick={() => requestDelete(rowKey)}
                                  disabled={busyKey === rowKey}
                                />
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            {filtered.relations.length > relationLimit ? (
              <Button variant="outline" type="button" onClick={() => setRelationLimit((current) => current + PAGE_SIZE)}>
                Load more relations
              </Button>
            ) : null}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/95">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Proposals (schema_proposals)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <Table className="min-w-[960px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Affected Items</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Rationale/Evidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.proposals.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No proposals.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.proposals.slice(0, proposalLimit).map((proposal) => {
                      const links = proposalAnchorLinks(proposal.payload);
                      return (
                        <TableRow key={proposal.id}>
                          <TableCell>{proposal.proposal_type}</TableCell>
                          <TableCell>{proposal.status}</TableCell>
                          <TableCell>{proposal.confidence.toFixed(2)}</TableCell>
                          <TableCell>
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
                          </TableCell>
                          <TableCell>{formatTimestamp(proposal.created_at)}</TableCell>
                          <TableCell>
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
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            {filtered.proposals.length > proposalLimit ? (
              <Button variant="outline" type="button" onClick={() => setProposalLimit((current) => current + PAGE_SIZE)}>
                Load more proposals
              </Button>
            ) : null}
            </CardContent>
          </Card>
        </>
      ) : null}

      <DeleteConfirmDialog
        open={pendingDeleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && busyKey === null) {
            cancelDelete();
          }
        }}
        title={
          pendingDeleteTarget
            ? `Delete ${pendingDeleteTarget.kind} "${pendingDeleteTarget.label}"?`
            : "Delete schema item?"
        }
        description="This action cannot be undone."
        onConfirm={() => {
          if (pendingDeleteTarget) {
            void confirmDelete(
              pendingDeleteTarget.kind,
              pendingDeleteTarget.id,
              `${pendingDeleteTarget.kind}-${pendingDeleteTarget.id}`
            );
          }
        }}
        isDeleting={busyKey !== null}
        confirmLabel="Confirm delete"
      />
    </div>
  );
}

