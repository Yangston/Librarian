"use client";

import { ArrowDown, ArrowUp, Database, LayoutPanelTop, Settings2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  type WorkspaceColumnRead,
  type WorkspaceCollectionRead,
  type WorkspaceRowsResponse,
  type WorkspaceSpaceRead
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { cn } from "@/lib/utils";

export type WorkspaceInspectorMode = "table" | "space" | "schema";

type WorkspaceInspectorProps = {
  mode: WorkspaceInspectorMode;
  onModeChange: (mode: WorkspaceInspectorMode) => void;
  selectedSpace: WorkspaceSpaceRead | null;
  selectedCollection: WorkspaceCollectionRead | null;
  rowsPayload: WorkspaceRowsResponse | null;
  newColumn: { label: string; data_type: string };
  onNewColumnChange: (payload: { label: string; data_type: string }) => void;
  onCreateColumn: () => void;
  onUpdateSpace: (spaceId: number, payload: { name?: string; description?: string | null }) => void;
  onDeleteSpace: (spaceId: number, slug: string, name: string) => void;
  onUpdateCollection: (collectionId: number, payload: { name?: string; description?: string | null }) => void;
  onDeleteCollection: (collectionId: number) => void;
  onRenameColumn: (columnId: number, label: string) => void;
  onDeleteColumn: (columnId: number) => void;
  onMoveColumn: (columnId: number, direction: -1 | 1) => void;
  statusMessage: string | null;
};

function InspectorTabs({
  mode,
  onModeChange
}: {
  mode: WorkspaceInspectorMode;
  onModeChange: (mode: WorkspaceInspectorMode) => void;
}) {
  const items: Array<{ value: WorkspaceInspectorMode; label: string; icon: typeof LayoutPanelTop }> = [
    { value: "table", label: "Table", icon: LayoutPanelTop },
    { value: "schema", label: "Schema", icon: Database },
    { value: "space", label: "Space", icon: Settings2 }
  ];

  return (
    <div className="spacesInspectorTabs">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.value}
            type="button"
            className={cn("spacesInspectorTab", mode === item.value && "active")}
            onClick={() => onModeChange(item.value)}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function ColumnRow({
  column,
  onRename,
  onDelete,
  onMove
}: {
  column: WorkspaceColumnRead;
  onRename: (label: string) => void;
  onDelete: () => void;
  onMove: (direction: -1 | 1) => void;
}) {
  return (
    <article className="spacesInspectorCard">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Input defaultValue={column.label} className="font-medium" onBlur={(event) => onRename(event.target.value)} />
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="secondary">{column.data_type}</Badge>
            <Badge variant="outline">{column.origin}</Badge>
            {column.user_locked ? <Badge variant="outline">locked</Badge> : null}
          </div>
        </div>
        <div className="flex gap-2">
          <Button type="button" size="icon" variant="outline" className="h-8 w-8" onClick={() => onMove(-1)}>
            <ArrowUp className="h-4 w-4" />
          </Button>
          <Button type="button" size="icon" variant="outline" className="h-8 w-8" onClick={() => onMove(1)}>
            <ArrowDown className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8 border-destructive/35 bg-destructive/5 text-destructive hover:bg-destructive hover:text-destructive-foreground dark:border-destructive/45 dark:bg-destructive/10"
            onClick={onDelete}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </article>
  );
}

export function WorkspaceInspector({
  mode,
  onModeChange,
  selectedSpace,
  selectedCollection,
  rowsPayload,
  newColumn,
  onNewColumnChange,
  onCreateColumn,
  onUpdateSpace,
  onDeleteSpace,
  onUpdateCollection,
  onDeleteCollection,
  onRenameColumn,
  onDeleteColumn,
  onMoveColumn,
  statusMessage
}: WorkspaceInspectorProps) {
  const editableColumns = rowsPayload?.columns.filter((column) => column.key !== "title") ?? [];

  return (
    <div className="spacesInspectorPanel">
      <div className="space-y-3">
        <div>
          <p className="eyebrow">Inspector</p>
          <h2 className="spacesRailTitle">Secondary controls</h2>
          <p className="subtle mt-1 text-sm">Manage naming, structure, and destructive actions without crowding the canvas.</p>
        </div>
        <InspectorTabs mode={mode} onModeChange={onModeChange} />
      </div>

      {mode === "table" ? (
        <div className="space-y-4" key={selectedCollection?.id ?? "table-empty"}>
          {selectedCollection ? (
            <>
              <div className="spacesInspectorCard">
                <p className="spacesInspectorLabel">Table name</p>
                <Input
                  defaultValue={selectedCollection.name}
                  onBlur={(event) => onUpdateCollection(selectedCollection.id, { name: event.target.value })}
                />
                <p className="spacesInspectorLabel mt-3">Description</p>
                <Textarea
                  rows={4}
                  defaultValue={selectedCollection.description ?? ""}
                  onBlur={(event) =>
                    onUpdateCollection(selectedCollection.id, { description: event.target.value || null })
                  }
                />
              </div>

              <div className="spacesInspectorCard">
                <div className="spacesSectionHeading">
                  <span>Status</span>
                  {selectedCollection.pending_suggestion_count > 0 ? (
                    <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">
                      {selectedCollection.pending_suggestion_count} pending
                    </Badge>
                  ) : (
                    <Badge variant="secondary">Ready</Badge>
                  )}
                </div>
                <p className="subtle text-sm">
                  {statusMessage ?? "Enrichment is idle. Review state, update details, or move into schema changes."}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="spacesInspectorMetric">
                    <span>Rows</span>
                    <strong>{selectedCollection.row_count}</strong>
                  </div>
                  <div className="spacesInspectorMetric">
                    <span>Fields</span>
                    <strong>{selectedCollection.column_count}</strong>
                  </div>
                </div>
                <p className="subtle mt-3 text-sm">Updated {formatTimestamp(selectedCollection.updated_at)}</p>
              </div>

              <div className="spacesInspectorDanger">
                <p className="font-medium">Delete table</p>
                <p className="subtle text-sm">This removes the current table and its row assignments.</p>
                <Button
                  type="button"
                  variant="destructive"
                  className="mt-3"
                  onClick={() => onDeleteCollection(selectedCollection.id)}
                >
                  Delete table
                </Button>
              </div>
            </>
          ) : (
            <div className="spacesInspectorCard">
              <p className="subtle text-sm">Select a table to manage naming, review state, and destructive actions.</p>
            </div>
          )}
        </div>
      ) : null}

      {mode === "space" ? (
        <div className="space-y-4" key={selectedSpace?.id ?? "space-empty"}>
          {selectedSpace ? (
            <>
              <div className="spacesInspectorCard">
                <p className="spacesInspectorLabel">Space name</p>
                <Input
                  defaultValue={selectedSpace.name}
                  onBlur={(event) => onUpdateSpace(selectedSpace.id, { name: event.target.value })}
                />
                <p className="spacesInspectorLabel mt-3">Description</p>
                <Textarea
                  rows={4}
                  defaultValue={selectedSpace.description ?? ""}
                  onBlur={(event) => onUpdateSpace(selectedSpace.id, { description: event.target.value || null })}
                />
              </div>

              <div className="spacesInspectorCard">
                <div className="grid grid-cols-2 gap-3">
                  <div className="spacesInspectorMetric">
                    <span>Tables</span>
                    <strong>{selectedSpace.collection_count}</strong>
                  </div>
                  <div className="spacesInspectorMetric">
                    <span>Rows</span>
                    <strong>{selectedSpace.row_count}</strong>
                  </div>
                </div>
                <p className="subtle mt-3 text-sm">Updated {formatTimestamp(selectedSpace.updated_at)}</p>
              </div>

              <div className="spacesInspectorDanger">
                <p className="font-medium">Delete space</p>
                <p className="subtle text-sm">This removes the space and all assigned conversations in it.</p>
                <Button
                  type="button"
                  variant="destructive"
                  className="mt-3"
                  onClick={() => onDeleteSpace(selectedSpace.id, selectedSpace.slug, selectedSpace.name)}
                >
                  Delete space
                </Button>
              </div>
            </>
          ) : (
            <div className="spacesInspectorCard">
              <p className="subtle text-sm">Select a space to manage its identity and destructive actions.</p>
            </div>
          )}
        </div>
      ) : null}

      {mode === "schema" ? (
        <div className="space-y-4">
          {selectedCollection ? (
            <>
              <div className="spacesInspectorCard">
                <p className="spacesInspectorLabel">Add a field</p>
                <div className="mt-3 grid gap-3">
                  <Input
                    placeholder="Field label"
                    value={newColumn.label}
                    onChange={(event) => onNewColumnChange({ ...newColumn, label: event.target.value })}
                  />
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={newColumn.data_type}
                    onChange={(event) => onNewColumnChange({ ...newColumn, data_type: event.target.value })}
                  >
                    <option value="text">Text</option>
                    <option value="url">URL</option>
                    <option value="number">Number</option>
                  </select>
                  <Button type="button" onClick={onCreateColumn}>
                    Add field
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <div className="spacesSectionHeading">
                  <span>Current schema</span>
                  <Badge variant="secondary">{editableColumns.length}</Badge>
                </div>
                {editableColumns.map((column) => (
                  <ColumnRow
                    key={column.id}
                    column={column}
                    onRename={(label) => onRenameColumn(column.id, label)}
                    onDelete={() => onDeleteColumn(column.id)}
                    onMove={(direction) => onMoveColumn(column.id, direction)}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="spacesInspectorCard">
              <p className="subtle text-sm">Select a table to edit fields, reorder columns, or add new structure.</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
