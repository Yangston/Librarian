"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  type EntityListingResponse,
  deleteEntityRecord,
  getEntitiesCatalog,
  updateEntityRecord
} from "../../lib/api";
import { formatTimestamp } from "../../lib/format";

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

  return (
    <div className="stackLg">
      <section className="panel">
        <h2>Entities</h2>
        <p className="subtle">Global record table with dynamic columns generated from learned fields.</p>
        <form className="gridForm" onSubmit={applyFilters}>
          <label className="field">
            <span>Search</span>
            <input
              className="input"
              placeholder="Canonical name..."
              value={queryDraft}
              onChange={(event) => setQueryDraft(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Type Label</span>
            <input
              className="input"
              placeholder="Company, Person..."
              value={typeDraft}
              onChange={(event) => setTypeDraft(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Sort</span>
            <select className="input" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
              <option value="last_seen">Last seen</option>
              <option value="canonical_name">Canonical name</option>
              <option value="type_label">Type label</option>
              <option value="conversation_count">Conversation count</option>
              <option value="alias_count">Alias count</option>
            </select>
          </label>
          <label className="field">
            <span>Order</span>
            <select className="input" value={order} onChange={(event) => setOrder(event.target.value as SortOrder)}>
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
          <button className="button" type="submit">
            Apply
          </button>
        </form>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}

      <section className="panel">
        <h3>Dynamic Columns</h3>
        <div className="tagWrap">
          {fieldChoices.slice(0, 16).map((field) => (
            <label className="checkTag" key={field}>
              <input
                type="checkbox"
                checked={selectedFields.includes(field)}
                onChange={() => toggleField(field)}
              />
              <span>{field}</span>
            </label>
          ))}
          {fieldChoices.length === 0 ? <span className="muted">No dynamic fields available yet.</span> : null}
        </div>
      </section>

      <section className="panel">
        {loading ? (
          <p>Loading entities...</p>
        ) : (
          <>
            {refreshing ? <p className="subtle">Refreshing entities...</p> : null}
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Canonical Name</th>
                    <th>Type</th>
                    <th>Aliases</th>
                    <th>Last Seen</th>
                    <th>Conversations</th>
                    <th>Actions</th>
                    {visibleFields.map((field) => (
                      <th key={field}>{field}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(payload?.items ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={6 + visibleFields.length} className="emptyCell">
                        No entities found.
                      </td>
                    </tr>
                  ) : (
                    payload?.items.map((entity) => (
                      <tr key={entity.id}>
                        <td>
                          {editingEntityId === entity.id ? (
                            <input
                              className="input compactInput"
                              value={editDraft.canonical_name}
                              onChange={(event) =>
                                setEditDraft((current) => ({ ...current, canonical_name: event.target.value }))
                              }
                            />
                          ) : (
                            <Link href={`/entities/${entity.id}`}>{entity.canonical_name}</Link>
                          )}
                        </td>
                        <td>
                          {editingEntityId === entity.id ? (
                            <input
                              className="input compactInput"
                              value={editDraft.type_label}
                              onChange={(event) =>
                                setEditDraft((current) => ({ ...current, type_label: event.target.value }))
                              }
                            />
                          ) : (
                            entity.type_label || "-"
                          )}
                        </td>
                        <td>{entity.alias_count}</td>
                        <td>{formatTimestamp(entity.last_seen)}</td>
                        <td>{entity.conversation_count}</td>
                        <td>
                          {editingEntityId === entity.id ? (
                            <div className="inlineActions">
                              <button
                                className="button"
                                type="button"
                                onClick={() =>
                                  void saveEntityEdit(entity.id, entity.canonical_name, entity.type_label)
                                }
                                disabled={rowBusyId === entity.id}
                              >
                                Save
                              </button>
                              <button
                                className="button ghost"
                                type="button"
                                onClick={cancelEditEntity}
                                disabled={rowBusyId === entity.id}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : pendingDeleteEntityId === entity.id ? (
                            <div className="inlineConfirm">
                              <span className="inlineConfirmText">Delete "{entity.canonical_name}"?</span>
                              <button
                                className="button danger"
                                type="button"
                                onClick={() => void confirmDeleteEntity(entity.id)}
                                disabled={rowBusyId === entity.id}
                              >
                                Confirm delete
                              </button>
                              <button
                                className="button ghost"
                                type="button"
                                onClick={cancelDeleteEntity}
                                disabled={rowBusyId === entity.id}
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
                                  beginEditEntity(entity.id, entity.canonical_name, entity.type_label)
                                }
                                disabled={rowBusyId === entity.id}
                              >
                                Edit
                              </button>
                              <button
                                className="button ghost"
                                type="button"
                                onClick={() => requestDeleteEntity(entity.id)}
                                disabled={rowBusyId === entity.id}
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </td>
                        {visibleFields.map((field) => (
                          <td key={`${entity.id}-${field}`}>{entity.dynamic_fields[field] ?? "-"}</td>
                        ))}
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
