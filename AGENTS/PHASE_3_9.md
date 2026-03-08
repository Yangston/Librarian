# PHASE_3_9.md - Workspace-First Refactor and Staged Enrichment Review

## Phase Objective

Phase 3.9 turns the Phase 3 workspace into a stable, editable, workspace-first product layer and fixes the first full enrichment pass so it is:

- pod-scoped
- table-aware
- graph-aware
- asynchronous
- reviewable before acceptance

This phase replaces "generate and immediately write inferred data into live rows" with:

1. accepted conversation truth
2. pending enrichment suggestions
3. explicit user review and acceptance

The core outcome is that Librarian now behaves more like a Notion-style workspace with staged AI suggestions instead of a one-shot extractor that mutates records invisibly.

---

## High-Level Product Changes

### 1) Spaces became the primary workspace surface

The Spaces experience was rebuilt around stable pod and collection records instead of temporary projection-only rows.

Users now work through:

- spaces
- tables inside spaces
- rows inside tables
- row detail pages

This replaces the earlier "preview" model where spaces only showed light summaries.

### 2) Library and Properties/Types were moved onto the same stable data model

The global Library now reads row-oriented workspace data across spaces.

Properties and Types now describe real collection columns and their coverage instead of only older schema projection signals.

### 3) Graph view now understands workspace suggestions

Workspace graph mode can now render accepted workspace relations and pending suggested relations.

Suggested edges are visually distinct and reviewable in bulk at the graph-scope level.

---

## Architecture Changes

### Stable workspace model

The workspace is now backed by durable tables instead of rebuild-only v2 projection IDs.

Primary stable records:

- `pods`
- `collections`
- `collection_items`
- `collection_columns`
- `collection_item_values`
- `collection_item_relations`

Projection tables from the v2 experience layer remain compatibility/read-model support, but they are no longer the authoritative editing surface for the new workspace flow.

### Pod-scoped knowledge records

To support true space-local canon and cleaner workspace sync, extracted records were extended with `pod_id` or equivalent pod scoping:

- `entities`
- `facts`
- `relations`
- `extractor_runs`

This keeps canonicalization inside a space instead of merging across unrelated spaces.

---

## New Workspace Data Structures

### Workspace columns and row values

Added:

- `collection_columns`
- `collection_item_values`
- `collection_item_relations`

These provide:

- standardized schema per table
- editable cell values
- workspace-level relation rendering between rows

### Background enrichment runs

Added:

- `workspace_enrichment_runs`

This tracks:

- queued/running/completed/failed enrichment jobs
- target scope (space, collection, row)
- summary counts
- runtime error message when enrichment fails

This replaces the prior synchronous enrich button behavior that could stall the request path.

### Pending suggestion storage

Added:

- `collection_item_value_suggestions`
- `collection_item_relation_suggestions`

These store:

- pending suggestions
- accepted suggestions
- rejected suggestions
- source kind
- confidence
- dedupe keys
- source ids / metadata

Rejected suggestions are remembered so the same suggestion does not keep resurfacing unchanged.

---

## Workspace Sync and Enrichment Flow

### Accepted truth path

`workspace_sync` now materializes accepted workspace truth from conversation-supported facts and relations only.

That means live tables and live graph/workspace relations are grounded in:

- conversation-derived entities
- conversation-derived facts
- conversation-derived relations
- already accepted suggestions

### Suggestion generation path

Enrichment is now a separate path:

1. create enrichment run
2. run background suggestion generation
3. store pending value suggestions
4. store pending relation suggestions
5. poll run status from the UI
6. accept or reject in bulk

### Token and latency reduction

The first implementation used too many calls because it researched one missing cell at a time.

This phase changed that to:

- row-level batch property research
- collection-level batch relation research
- pairwise relation fallback only when the batch result does not cover a candidate

This materially reduces token usage and request fan-out.

### OpenAI Responses parser fix

One major bug was discovered during live testing:

- the Responses API was returning JSON under `output[].content[].text`
- the code only looked at top-level `output_text`

The result was that enrichment runs "completed" with zero suggestions even when OpenAI returned real answers.

That parser is now fixed.

---

## UI and UX Changes

### Spaces workspace shell

The workspace shell now supports:

- space create/edit/delete
- table create/edit/delete
- column create/edit/delete/reorder
- row create/delete/reorder
- inline cell editing

### Pending suggestion review in tables

Tables now show:

- pending counts at the collection level
- pending counts at the cell level
- suggested values inline
- bulk `Accept all suggestions`
- bulk `Reject all suggestions`

Pending suggestions are visible before they are applied.

### Row detail pages

Row detail pages now show:

- pending cell suggestions
- pending relation suggestion counts
- staged enrichment refresh with polling

### Graph Studio

Workspace graph mode now supports:

- pending suggestion count badges
- asynchronous enrichment refresh
- bulk accept/reject for the current graph scope
- visually distinct suggested edges

Suggested edges are rendered as pending workspace suggestions rather than normal accepted relations.

---

## API Surface Added or Changed

### Core workspace v3 routes

The stable workspace-first API continues to use `/v3`.

Notable routes now include:

- `GET /v3/spaces`
- `POST /v3/spaces`
- `PATCH /v3/spaces/{space_id}`
- `DELETE /v3/spaces/{space_id}`
- `GET /v3/spaces/{space_id}/workspace`
- `POST /v3/spaces/{space_id}/enrich`
- `GET /v3/enrichment-runs/{run_id}`
- `POST /v3/collections/{collection_id}/suggestions/accept`
- `POST /v3/collections/{collection_id}/suggestions/reject`
- `POST /v3/graph/scopes/{scope_key}/suggestions/accept`
- `POST /v3/graph/scopes/{scope_key}/suggestions/reject`

### Graph payload changes

Scoped graph payloads now include suggestion metadata:

- suggested edges
- source kind
- status
- pending suggestion counts on nodes and graph scope

This lets the graph UI render live and pending relations together without pretending they are the same thing.

---

## Files and Subsystems Touched

The main implementation landed across:

- backend workspace sync and v3 services
- backend organization graph service
- backend background jobs and migrations
- frontend workspace shell, row detail, graph page, and API client

The most important implementation areas are:

- `backend/app/services/workspace_sync.py`
- `backend/app/services/workspace_v3.py`
- `backend/app/routers/workspace_v3.py`
- `backend/app/services/organization.py`
- `frontend/components/workspace/WorkspaceShell.tsx`
- `frontend/app/app/graph/page.tsx`
- `frontend/lib/api.ts`

---

## Verification Performed

### Static / local verification

Ran:

- `python -m compileall backend/app`
- `backend/.venv/Scripts/python.exe -m pytest tests/test_workspace_v3_sync.py tests/test_workspace_enrichment_suggestions.py -q`
- `npm run build`
- `backend/.venv/Scripts/alembic.exe upgrade head`

### Live OpenAI validation

Multiple live OpenAI smoke tests were executed against in-memory databases using the real `backend/.env` configuration.

Results observed:

- live enrichment suggestion generation created pending value suggestions
- live enrichment suggestion generation created pending relation suggestions
- bulk table acceptance materialized pending value suggestions into live cell values
- bulk graph acceptance materialized pending relation suggestions into live workspace/graph relations

Example live outcomes:

- value suggestions created: `6`
- relation suggestions created: `2`
- bulk table accept applied: `2`
- bulk graph accept applied: `1`

This confirms:

- OpenAI config is loading
- enrichment now parses real Responses payloads correctly
- suggestions are being produced
- acceptance path works end to end

---

## Important Behavioral Defaults

- Entities remain conversation-derived only.
- External enrichment may suggest properties and relations, but does not create new entities.
- Suggestions are bulk-reviewed, not individually accepted per cell/edge.
- Rejected suggestions are remembered and suppressed unless future evidence materially differs.
- Accepted suggestions copy provenance into live workspace values and relations.

---

## Known Caveat

There is still an existing Pydantic warning in tests related to `schema_json` shadowing a BaseModel attribute on `CollectionRead`.

It does not currently block:

- backend compile
- tests
- frontend build
- migrations
- live enrichment

but it remains a cleanup item for a later pass.
