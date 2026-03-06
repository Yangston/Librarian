"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  type LibraryItemsResponseV2,
  type SpacePageV2,
  type SpaceV2,
  createSpaceV2,
  deleteSpaceV2,
  getLibraryItemsV2,
  getSpacePagesV2,
  getSpacesV2,
  updateSpaceV2
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SpacesPage() {
  const [spaces, setSpaces] = useState<SpaceV2[]>([]);
  const [selectedSpaceId, setSelectedSpaceId] = useState<number | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<number | null>(null);
  const [pages, setPages] = useState<SpacePageV2[]>([]);
  const [previewItems, setPreviewItems] = useState<LibraryItemsResponseV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingPages, setLoadingPages] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingSpaceName, setEditingSpaceName] = useState("");
  const [editingSpaceDescription, setEditingSpaceDescription] = useState("");

  const selectedSpace = useMemo(
    () => spaces.find((space) => space.id === selectedSpaceId) ?? null,
    [spaces, selectedSpaceId]
  );

  useEffect(() => {
    let active = true;
    async function loadSpaces() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSpacesV2();
        if (!active) {
          return;
        }
        setSpaces(data);
        setSelectedSpaceId((current) => current ?? data[0]?.id ?? null);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load spaces.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void loadSpaces();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setEditingSpaceName(selectedSpace?.name ?? "");
    setEditingSpaceDescription(selectedSpace?.description ?? "");
  }, [selectedSpace]);

  useEffect(() => {
    if (!selectedSpaceId) {
      setPages([]);
      setSelectedPageId(null);
      return;
    }
    const spaceId = selectedSpaceId;
    let active = true;
    async function loadPages() {
      setLoadingPages(true);
      setError(null);
      try {
        const payload = await getSpacePagesV2(spaceId);
        if (!active) {
          return;
        }
        setPages(payload.items);
        setSelectedPageId((current) => current ?? payload.items[0]?.id ?? null);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load pages.");
      } finally {
        if (active) {
          setLoadingPages(false);
        }
      }
    }
    void loadPages();
    return () => {
      active = false;
    };
  }, [selectedSpaceId]);

  useEffect(() => {
    if (!selectedSpaceId) {
      setPreviewItems(null);
      return;
    }
    const spaceId = selectedSpaceId;
    let active = true;
    async function loadPreview() {
      setLoadingPreview(true);
      setError(null);
      try {
        const payload = await getLibraryItemsV2({
          limit: 8,
          offset: 0,
          sort: "last_active",
          order: "desc",
          space_id: spaceId,
          page_id: selectedPageId ?? undefined
        });
        if (!active) {
          return;
        }
        setPreviewItems(payload);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load preview items.");
      } finally {
        if (active) {
          setLoadingPreview(false);
        }
      }
    }
    void loadPreview();
    return () => {
      active = false;
    };
  }, [selectedSpaceId, selectedPageId]);

  async function refreshSpaces(preferredId?: number | null) {
    const data = await getSpacesV2();
    setSpaces(data);
    const fallback = preferredId ?? selectedSpaceId;
    if (fallback && data.some((space) => space.id === fallback)) {
      setSelectedSpaceId(fallback);
      return;
    }
    setSelectedSpaceId(data[0]?.id ?? null);
  }

  async function handleCreateSpace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = createName.trim();
    if (!name) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createSpaceV2({
        name,
        description: createDescription.trim() || null
      });
      await refreshSpaces(created.id);
      setCreateName("");
      setCreateDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create space.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSpaceDetails() {
    if (!selectedSpace) {
      return;
    }
    const name = editingSpaceName.trim();
    if (!name) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateSpaceV2(selectedSpace.id, {
        name,
        description: editingSpaceDescription.trim() || null
      });
      await refreshSpaces(selectedSpace.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update space.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteSpace() {
    if (!selectedSpace) {
      return;
    }
    if (!window.confirm(`Delete "${selectedSpace.name}" and all assigned conversations?`)) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteSpaceV2(selectedSpace.id);
      await refreshSpaces(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete space.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-3">
          <CardTitle className="text-xl">Spaces</CardTitle>
          <CardDescription>
            Organize your workspace into focused spaces and pages, then browse what matters.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-2 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleCreateSpace}>
            <label className="field">
              <Label htmlFor="space-name">New space</Label>
              <Input
                id="space-name"
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="Product research"
              />
            </label>
            <label className="field">
              <Label htmlFor="space-description">Description</Label>
              <Input
                id="space-description"
                value={createDescription}
                onChange={(event) => setCreateDescription(event.target.value)}
                placeholder="Optional"
              />
            </label>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Create Space"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="grid gap-3 lg:grid-cols-[260px_minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Spaces</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? <p className="subtle">Loading spaces...</p> : null}
            {!loading && spaces.length === 0 ? <p className="subtle">No spaces yet.</p> : null}
            {spaces.map((space) => (
              <button
                key={space.id}
                type="button"
                className={`treeNodeButton ${space.id === selectedSpaceId ? "active" : ""}`}
                onClick={() => {
                  setSelectedSpaceId(space.id);
                  setSelectedPageId(null);
                }}
              >
                <span>{space.name}</span>
                <span className="muted">{space.item_count}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Pages</CardTitle>
            <CardDescription>
              {selectedSpace ? `${selectedSpace.name} has ${pages.length} pages` : "Select a space"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {selectedSpace ? (
              <div className="grid gap-2 rounded-lg border border-border/70 p-3 md:grid-cols-[1fr_1fr_auto_auto]">
                <Input
                  value={editingSpaceName}
                  onChange={(event) => setEditingSpaceName(event.target.value)}
                  placeholder="Space name"
                />
                <Input
                  value={editingSpaceDescription}
                  onChange={(event) => setEditingSpaceDescription(event.target.value)}
                  placeholder="Description"
                />
                <Button variant="outline" onClick={() => void handleSaveSpaceDetails()} disabled={saving}>
                  Save
                </Button>
                <Button variant="destructive" onClick={() => void handleDeleteSpace()} disabled={saving}>
                  Delete
                </Button>
              </div>
            ) : null}

            {loadingPages ? <p className="subtle">Loading pages...</p> : null}
            {!loadingPages && pages.length === 0 ? (
              <p className="subtle">No pages in this space yet.</p>
            ) : (
              pages.map((page) => (
                <button
                  key={page.id}
                  type="button"
                  className={`treeNodeButton ${page.id === selectedPageId ? "active" : ""}`}
                  onClick={() => setSelectedPageId(page.id)}
                >
                  <span>{page.name}</span>
                  <span className="muted">
                    {page.kind} · {page.item_count}
                  </span>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card/95">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Preview</CardTitle>
            <CardDescription>
              {selectedPageId ? "Showing selected page" : "Showing recent items in this space"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loadingPreview ? <p className="subtle">Loading preview...</p> : null}
            {!loadingPreview && (previewItems?.items.length ?? 0) === 0 ? (
              <p className="subtle">No items yet.</p>
            ) : (
              previewItems?.items.map((item) => (
                <article key={item.id} className="rounded-lg border border-border/70 bg-background/60 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="subtle">{item.type_label}</p>
                    </div>
                    <span className="subtle">{item.mention_count} mentions</span>
                  </div>
                  {item.summary ? <p className="mt-2 text-sm text-muted-foreground">{item.summary}</p> : null}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {item.key_properties.map((property) => (
                      <span key={`${item.id}-${property.property_key}`} className="tag">
                        {property.label}: {property.value}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Last active {formatTimestamp(item.last_seen_at)}
                  </p>
                </article>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
