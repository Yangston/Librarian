"use client";

import Link from "next/link";
import { FolderPlus, PanelLeftClose, PanelLeftOpen, Plus, Rows3, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type WorkspaceCollectionRead, type WorkspaceSpaceRead } from "@/lib/api";
import { cn } from "@/lib/utils";

type WorkspaceNavigationRailProps = {
  loading: boolean;
  spaces: WorkspaceSpaceRead[];
  collections: WorkspaceCollectionRead[];
  selectedSpace: WorkspaceSpaceRead | null;
  selectedCollection: WorkspaceCollectionRead | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
  isMobile: boolean;
  onOpenCreateSpace: () => void;
  onOpenCreateCollection: () => void;
};

export function WorkspaceNavigationRail({
  loading,
  spaces,
  collections,
  selectedSpace,
  selectedCollection,
  collapsed,
  onToggleCollapse,
  isMobile,
  onOpenCreateSpace,
  onOpenCreateCollection
}: WorkspaceNavigationRailProps) {
  if (collapsed && !isMobile) {
    return (
      <aside className="spacesRail spacesRailCollapsed routeFade">
        <div className="grid gap-2">
          <Button type="button" size="icon" variant="outline" onClick={onToggleCollapse} aria-label="Expand spaces list">
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
          <Button type="button" size="icon" variant="outline" onClick={onOpenCreateSpace} aria-label="Create space">
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            onClick={onOpenCreateCollection}
            disabled={!selectedSpace}
            aria-label="Create table"
          >
            <FolderPlus className="h-4 w-4" />
          </Button>
        </div>
        <div className="spacesRailCollapsedMeta">
          <Badge variant="secondary">{spaces.length}</Badge>
          {selectedCollection ? <Badge variant="outline">{selectedCollection.row_count}</Badge> : null}
        </div>
      </aside>
    );
  }

  return (
    <aside className="spacesRail routeFade">
      <div className="spacesRailHeader">
        <div className="min-w-0">
          <p className="eyebrow">Spaces</p>
          <h2 className="spacesRailTitle">Focused workspace</h2>
          <p className="subtle mt-1 text-sm">
            Move through spaces and tables without carrying all admin controls in view.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!isMobile ? (
            <Button type="button" size="icon" variant="outline" onClick={onToggleCollapse} aria-label="Collapse spaces list">
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          ) : null}
          <Button type="button" size="sm" variant="outline" onClick={onOpenCreateSpace}>
            <Plus className="h-4 w-4" />
            New space
          </Button>
          <Button type="button" size="sm" onClick={onOpenCreateCollection} disabled={!selectedSpace}>
            <FolderPlus className="h-4 w-4" />
            New table
          </Button>
        </div>
      </div>

      <section className="spacesRailSection">
        <div className="spacesSectionHeading">
          <span>All spaces</span>
          <Badge variant="secondary">{spaces.length}</Badge>
        </div>
        {loading ? <p className="subtle text-sm">Loading spaces...</p> : null}
        <div className="spacesNavStack">
          {spaces.map((space) => {
            const isActive = selectedSpace?.id === space.id;

            return (
              <Link
                key={space.id}
                href={`/app/spaces/${space.slug}`}
                className={cn("spacesNavItem", isActive && "active")}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{space.name}</span>
                    {isActive ? <Badge variant="secondary">Current</Badge> : null}
                  </div>
                  <p className="spacesNavMeta">
                    {space.collection_count} tables - {space.row_count} rows
                  </p>
                  {isActive && space.description ? <p className="spacesNavDescription">{space.description}</p> : null}
                </div>
                <Rows3 className="h-4 w-4 shrink-0 text-muted-foreground" />
              </Link>
            );
          })}
          {!loading && spaces.length === 0 ? (
            <div className="spacesEmptyState">
              <Sparkles className="h-4 w-4 text-primary" />
              <p className="text-sm">Create your first space to start shaping the workspace.</p>
            </div>
          ) : null}
        </div>
      </section>

      <section className="spacesRailSection border-t border-border/60 pt-4">
        <div className="spacesSectionHeading">
          <span>Tables</span>
          <Badge variant="secondary">{collections.length}</Badge>
        </div>
        {selectedSpace ? (
          <p className="subtle text-sm">
            {selectedSpace.name}
            {selectedSpace.description ? ` - ${selectedSpace.description}` : ""}
          </p>
        ) : (
          <p className="subtle text-sm">Select a space to see its tables.</p>
        )}
        <div className="spacesNavStack">
          {collections.map((collection) => {
            const isActive = selectedCollection?.id === collection.id;
            const meta = [
              `${collection.row_count} rows`,
              `${collection.column_count} fields`,
              collection.pending_suggestion_count > 0 ? `${collection.pending_suggestion_count} pending` : null
            ]
              .filter(Boolean)
              .join(" - ");

            return (
              <Link
                key={collection.id}
                href={`/app/spaces/${selectedSpace?.slug ?? ""}/${collection.slug}`}
                className={cn("spacesNavItem spacesNavItemCompact", isActive && "active")}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{collection.name}</span>
                    {collection.pending_suggestion_count > 0 ? (
                      <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">{collection.pending_suggestion_count}</Badge>
                    ) : null}
                  </div>
                  <p className="spacesNavMeta">{meta}</p>
                </div>
              </Link>
            );
          })}
          {selectedSpace && collections.length === 0 ? (
            <div className="spacesEmptyState">
              <p className="text-sm">No tables yet. Use the action above to create the first one.</p>
            </div>
          ) : null}
        </div>
      </section>
    </aside>
  );
}
