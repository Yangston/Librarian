"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  type EntityListingResponse,
  deleteEntityRecord,
  getEntitiesCatalog,
  updateEntityRecord
} from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../components/ui/delete-controls";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "../../../components/ui/select";
import { Checkbox } from "../../../components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

const PAGE_SIZE = 25;

type SortKey = "canonical_name" | "type_label" | "last_seen" | "conversation_count" | "alias_count";
type SortOrder = "asc" | "desc";

export default function EntitiesPage() {
  const [queryDraft, setQueryDraft] = useState("");
  const [typeDraft, setTypeDraft] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [appliedType, setAppliedType] = useState("");
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("last_seen");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [offset, setOffset] = useState(0);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rowBusyId, setRowBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<EntityListingResponse | null>(null);
  const [editingEntityId, setEditingEntityId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ canonical_name: "", type_label: "" });
  const [pendingDeleteEntityId, setPendingDeleteEntityId] = useState<number | null>(null);
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
        const data = await getEntitiesCatalog({
          limit: PAGE_SIZE,
          offset,
          sort,
          order,
          q: appliedQuery || undefined,
          type_label: appliedType || undefined,
          fields: selectedFields
        });
        if (!active) {
          return;
        }
        setPayload(data);
        hasLoadedOnceRef.current = true;
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load entities.");
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
  }, [appliedQuery, appliedType, offset, order, refreshNonce, selectedFields, sort]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setAppliedQuery(queryDraft.trim());
    setAppliedType(typeDraft.trim());
  }

  function toggleField(field: string) {
    setOffset(0);
    setSelectedFields((current) =>
      current.includes(field) ? current.filter((item) => item !== field) : [...current, field]
    );
  }

  function beginEditEntity(entityId: number, currentName: string, currentType: string) {
    setEditingEntityId(entityId);
    setEditDraft({
      canonical_name: currentName,
      type_label: currentType || "untyped"
    });
    setPendingDeleteEntityId(null);
  }

  function cancelEditEntity() {
    setEditingEntityId(null);
    setEditDraft({ canonical_name: "", type_label: "" });
  }

  async function saveEntityEdit(entityId: number, currentName: string, currentType: string) {
    const nextCanonicalName = editDraft.canonical_name.trim();
    const nextTypeLabel = editDraft.type_label.trim();
    if (!nextCanonicalName || !nextTypeLabel) {
      setError("Canonical name and type label are required.");
      return;
    }
    setRowBusyId(entityId);
    setError(null);
    try {
      await updateEntityRecord(entityId, {
        canonical_name: nextCanonicalName || currentName,
        type_label: nextTypeLabel || currentType || "untyped"
      });
      cancelEditEntity();
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update entity.");
    } finally {
      setRowBusyId(null);
    }
  }

  function requestDeleteEntity(entityId: number) {
    if (editingEntityId === entityId) {
      cancelEditEntity();
    }
    setPendingDeleteEntityId(entityId);
  }

  function cancelDeleteEntity() {
    setPendingDeleteEntityId(null);
  }

  async function confirmDeleteEntity(entityId: number) {
    setRowBusyId(entityId);
    setError(null);
    try {
      await deleteEntityRecord(entityId);
      setPendingDeleteEntityId((current) => (current === entityId ? null : current));
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entity.");
    } finally {
      setRowBusyId(null);
    }
  }

  const total = payload?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;
  const fieldChoices = payload?.available_fields ?? [];
  const visibleFields = useMemo(
    () => selectedFields.filter((field) => fieldChoices.includes(field) || selectedFields.includes(field)),
    [fieldChoices, selectedFields]
  );
  const pendingDeleteEntity =
    pendingDeleteEntityId === null
      ? null
      : (payload?.items.find((item) => item.id === pendingDeleteEntityId) ?? null);

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <CardTitle className="text-xl">Entities</CardTitle>
            <p className="subtle">Global record table with dynamic columns generated from learned fields.</p>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link href="/app/search">Search Knowledge</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <form className="grid gap-3 md:grid-cols-[1.2fr_1.2fr_1fr_1fr_auto] md:items-end" onSubmit={applyFilters}>
            <label className="field">
              <Label>Search</Label>
              <Input
                placeholder="Canonical name..."
                value={queryDraft}
                onChange={(event) => setQueryDraft(event.target.value)}
              />
            </label>
            <label className="field">
              <Label>Type Label</Label>
              <Input
                placeholder="Company, Person..."
                value={typeDraft}
                onChange={(event) => setTypeDraft(event.target.value)}
              />
            </label>
            <label className="field">
              <Label>Sort</Label>
              <Select value={sort} onValueChange={(value) => setSort(value as SortKey)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="last_seen">Last seen</SelectItem>
                  <SelectItem value="canonical_name">Canonical name</SelectItem>
                  <SelectItem value="type_label">Type label</SelectItem>
                  <SelectItem value="conversation_count">Conversation count</SelectItem>
                  <SelectItem value="alias_count">Alias count</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="field">
              <Label>Order</Label>
              <Select value={order} onValueChange={(value) => setOrder(value as SortOrder)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">Descending</SelectItem>
                  <SelectItem value="asc">Ascending</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <Button type="submit">Apply</Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Dynamic Columns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {fieldChoices.slice(0, 16).map((field) => (
              <label
                className="inline-flex items-center gap-2 rounded-md border border-border/70 px-2.5 py-1.5 text-xs"
                key={field}
                htmlFor={`field-${field}`}
              >
                <Checkbox
                  id={`field-${field}`}
                  checked={selectedFields.includes(field)}
                  onCheckedChange={() => toggleField(field)}
                />
                <span>{field}</span>
              </label>
            ))}
            {fieldChoices.length === 0 ? <span className="muted">No dynamic fields available yet.</span> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-lg">Entity Records</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">Total: {total}</Badge>
              <Badge variant="outline">Columns: {visibleFields.length + 6}</Badge>
              {refreshing ? <Badge variant="outline">Refreshing...</Badge> : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading entities...</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Canonical Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Aliases</TableHead>
                  <TableHead>Last Seen</TableHead>
                  <TableHead>Conversations</TableHead>
                  <TableHead>Actions</TableHead>
                  {visibleFields.map((field) => (
                    <TableHead key={field}>{field}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                  {(payload?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6 + visibleFields.length} className="text-center text-muted-foreground">
                        No entities found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    payload?.items.map((entity) => (
                      <TableRow key={entity.id}>
                        <TableCell>
                          {editingEntityId === entity.id ? (
                            <Input
                              className="h-8"
                              value={editDraft.canonical_name}
                              onChange={(event) =>
                                setEditDraft((current) => ({ ...current, canonical_name: event.target.value }))
                              }
                            />
                          ) : (
                            <Link href={`/app/entities/${entity.id}`}>{entity.canonical_name}</Link>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingEntityId === entity.id ? (
                            <Input
                              className="h-8"
                              value={editDraft.type_label}
                              onChange={(event) =>
                                setEditDraft((current) => ({ ...current, type_label: event.target.value }))
                              }
                            />
                          ) : (
                            entity.type_label || "-"
                          )}
                        </TableCell>
                        <TableCell>{entity.alias_count}</TableCell>
                        <TableCell>{formatTimestamp(entity.last_seen)}</TableCell>
                        <TableCell>{entity.conversation_count}</TableCell>
                        <TableCell>
                          {editingEntityId === entity.id ? (
                            <div className="flex items-center gap-2">
                              <Button
                                type="button"
                                onClick={() =>
                                  void saveEntityEdit(entity.id, entity.canonical_name, entity.type_label)
                                }
                                disabled={rowBusyId === entity.id}
                              >
                                Save
                              </Button>
                              <Button
                                variant="outline"
                                type="button"
                                onClick={cancelEditEntity}
                                disabled={rowBusyId === entity.id}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                type="button"
                                onClick={() =>
                                  beginEditEntity(entity.id, entity.canonical_name, entity.type_label)
                                }
                                disabled={rowBusyId === entity.id}
                              >
                                Edit
                              </Button>
                              <DeleteActionButton
                                type="button"
                                onClick={() => requestDeleteEntity(entity.id)}
                                disabled={rowBusyId === entity.id}
                              />
                            </div>
                          )}
                        </TableCell>
                        {visibleFields.map((field) => (
                          <TableCell key={`${entity.id}-${field}`}>{entity.dynamic_fields[field] ?? "-"}</TableCell>
                        ))}
                      </TableRow>
                    ))
                  )}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between gap-3 text-sm">
              <Button
                variant="outline"
                type="button"
                disabled={!canPrev}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <span>
                {total === 0 ? 0 : offset + 1} - {Math.min(total, offset + PAGE_SIZE)} of {total}
              </span>
              <Button variant="outline" type="button" disabled={!canNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          </>
        )}
        </CardContent>
      </Card>

      <DeleteConfirmDialog
        open={pendingDeleteEntityId !== null}
        onOpenChange={(open) => (!open ? cancelDeleteEntity() : null)}
        title="Delete entity"
        description={
          pendingDeleteEntity
            ? `Delete "${pendingDeleteEntity.canonical_name}"? This action cannot be undone.`
            : "Delete this entity? This action cannot be undone."
        }
        onConfirm={() => (pendingDeleteEntityId ? void confirmDeleteEntity(pendingDeleteEntityId) : null)}
        isDeleting={pendingDeleteEntityId !== null && pendingDeleteEntityId === rowBusyId}
        confirmLabel="Confirm delete"
      />
    </div>
  );
}

