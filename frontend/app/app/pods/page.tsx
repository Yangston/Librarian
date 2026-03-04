"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  type CollectionItemsResponse,
  type CollectionTreeNode,
  type PodRead,
  createPod,
  deletePod,
  getCollectionItems,
  getPodTree,
  getPods
} from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

function TreeNode({
  node,
  selectedCollectionId,
  onSelect
}: Readonly<{
  node: CollectionTreeNode;
  selectedCollectionId: number | null;
  onSelect: (collectionId: number) => void;
}>) {
  return (
    <li>
      <button
        type="button"
        className={`treeNodeButton ${selectedCollectionId === node.collection.id ? "active" : ""}`}
        onClick={() => onSelect(node.collection.id)}
      >
        <span>{node.collection.name}</span>
        <span className="muted">({node.collection.kind})</span>
      </button>
      {node.children.length > 0 ? (
        <ul className="treeList">
          {node.children.map((child) => (
            <TreeNode
              key={child.collection.id}
              node={child}
              selectedCollectionId={selectedCollectionId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function PodsPage() {
  const [pods, setPods] = useState<PodRead[]>([]);
  const [selectedPodId, setSelectedPodId] = useState<number | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<number | null>(null);
  const [collectionQuery, setCollectionQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingItems, setLoadingItems] = useState(false);
  const [creatingPod, setCreatingPod] = useState(false);
  const [deletingPod, setDeletingPod] = useState(false);
  const [newPodName, setNewPodName] = useState("");
  const [newPodDescription, setNewPodDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [tree, setTree] = useState<CollectionTreeNode[]>([]);
  const [itemsPayload, setItemsPayload] = useState<CollectionItemsResponse | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const podRows = await getPods();
        if (!active) {
          return;
        }
        setPods(podRows);
        if (podRows.length > 0) {
          setSelectedPodId(podRows[0].id);
        }
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load pods.");
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

  useEffect(() => {
    if (selectedPodId === null) {
      setTree([]);
      setSelectedCollectionId(null);
      return;
    }
    const podId = selectedPodId;
    let active = true;
    async function loadTree() {
      setError(null);
      try {
        const payload = await getPodTree(podId);
        if (!active) {
          return;
        }
        setTree(payload.tree);
        const firstCollection = payload.tree[0]?.collection?.id ?? null;
        setSelectedCollectionId((current) => current ?? firstCollection);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load pod tree.");
      }
    }
    void loadTree();
    return () => {
      active = false;
    };
  }, [selectedPodId]);

  useEffect(() => {
    if (selectedCollectionId === null) {
      setItemsPayload(null);
      return;
    }
    const collectionId = selectedCollectionId;
    let active = true;
    async function loadItems() {
      setLoadingItems(true);
      setError(null);
      try {
        const payload = await getCollectionItems({
          collection_id: collectionId,
          limit: 25,
          offset: 0,
          sort: "last_seen",
          order: "desc",
          q: collectionQuery || undefined
        });
        if (!active) {
          return;
        }
        setItemsPayload(payload);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load collection items.");
      } finally {
        if (active) {
          setLoadingItems(false);
        }
      }
    }
    void loadItems();
    return () => {
      active = false;
    };
  }, [collectionQuery, selectedCollectionId]);

  const selectedPod = useMemo(
    () => pods.find((pod) => pod.id === selectedPodId) ?? null,
    [pods, selectedPodId]
  );

  async function handleCreatePod() {
    const name = newPodName.trim();
    if (!name) {
      setError("Pod name is required.");
      return;
    }
    setCreatingPod(true);
    setError(null);
    try {
      const created = await createPod({
        name,
        description: newPodDescription.trim() || undefined
      });
      const nextPods = [...pods, created].sort((left, right) => left.name.localeCompare(right.name));
      setPods(nextPods);
      setSelectedPodId(created.id);
      setNewPodName("");
      setNewPodDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create pod.");
    } finally {
      setCreatingPod(false);
    }
  }

  async function handleDeletePod() {
    if (!selectedPodId) {
      return;
    }
    if (!window.confirm("Delete this pod and all assigned conversations + derived data?")) {
      return;
    }
    setDeletingPod(true);
    setError(null);
    try {
      await deletePod(selectedPodId);
      const remaining = pods.filter((pod) => pod.id !== selectedPodId);
      setPods(remaining);
      setSelectedPodId(remaining[0]?.id ?? null);
      setSelectedCollectionId(null);
      setItemsPayload(null);
      setTree([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete pod.");
    } finally {
      setDeletingPod(false);
    }
  }

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <div className="sectionTitleRow">
            <CardTitle className="text-xl">Pods</CardTitle>
            <CardDescription>Manually manage pods. Themes and rows are auto-generated.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
            <Input
              placeholder="New pod name"
              value={newPodName}
              onChange={(event) => setNewPodName(event.target.value)}
            />
            <Input
              placeholder="Description (optional)"
              value={newPodDescription}
              onChange={(event) => setNewPodDescription(event.target.value)}
            />
            <Button type="button" onClick={() => void handleCreatePod()} disabled={creatingPod}>
              {creatingPod ? "Creating..." : "Create Pod"}
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
          {loading ? (
            <span className="muted">Loading pods...</span>
          ) : pods.length === 0 ? (
            <span className="muted">No pods found.</span>
          ) : (
            pods.map((pod) => (
              <button
                key={pod.id}
                type="button"
                className={`pillButton ${pod.id === selectedPodId ? "active" : ""}`}
                onClick={() => setSelectedPodId(pod.id)}
              >
                <span>{pod.name}</span>
                {pod.is_default ? <Badge variant="secondary">Default</Badge> : null}
              </button>
            ))
          )}
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleDeletePod()}
              disabled={!selectedPodId || deletingPod}
            >
              {deletingPod ? "Deleting..." : "Delete Selected Pod"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="gridTwo">
        <Card className="border-border/80 bg-card/95 p-4">
          <div className="sectionTitleRow">
            <h3>Theme Tree</h3>
            {selectedPod ? <span className="subtle">{selectedPod.name}</span> : null}
          </div>
          {tree.length === 0 ? (
            <p className="muted">No auto-generated themes found for this pod yet.</p>
          ) : (
            <ul className="treeList">
              {tree.map((node) => (
                <TreeNode
                  key={node.collection.id}
                  node={node}
                  selectedCollectionId={selectedCollectionId}
                  onSelect={setSelectedCollectionId}
                />
              ))}
            </ul>
          )}
        </Card>

        <Card className="border-border/80 bg-card/95 p-4">
          <div className="sectionTitleRow">
            <h3>Theme Rows</h3>
            <div className="toolbar">
              {selectedCollectionId ? (
                <Button asChild variant="outline">
                  <Link
                    href={`/app/graph?scope_mode=collection&collection_id=${selectedCollectionId}${
                      selectedPodId ? `&pod_id=${selectedPodId}` : ""
                    }`}
                  >
                    Open Scoped Graph
                  </Link>
                </Button>
              ) : null}
            </div>
          </div>
          <label className="field">
            <Label>Filter items</Label>
            <Input
              placeholder="Canonical name..."
              value={collectionQuery}
              onChange={(event) => setCollectionQuery(event.target.value)}
            />
          </label>
          {loadingItems ? (
            <p className="muted">Loading collection items...</p>
          ) : itemsPayload ? (
            <>
              <p className="subtle">
                {itemsPayload.collection.name} | Total: {itemsPayload.total}
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Entity</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Conversations</TableHead>
                    <TableHead>Last Seen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {itemsPayload.items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        No entities in this collection.
                      </TableCell>
                    </TableRow>
                  ) : (
                    itemsPayload.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Link href={`/app/entities/${item.id}`}>{item.canonical_name}</Link>
                        </TableCell>
                        <TableCell>{item.type_label}</TableCell>
                        <TableCell>{item.conversation_count}</TableCell>
                        <TableCell>{formatTimestamp(item.last_seen)}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </>
          ) : (
            <p className="muted">Select a collection to view items.</p>
          )}
        </Card>
      </section>
    </div>
  );
}
