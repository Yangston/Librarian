# Phase 3 Progress Log

Last updated: 2026-02-28

## Progress Snapshot

Status legend:
- `DONE`: implemented and validated against current Phase 3 scope
- `IN PROGRESS`: foundation is shipped, but polish/spec depth still pending
- `NOT STARTED`: not yet implemented

Summary:
- `8 / 8 DONE`
- `0 / 8 IN PROGRESS`
- `0 / 8 NOT STARTED`

## Step Status

- `DONE` Step 1: Workspace dashboard + navigation shell
- `DONE` Step 2: Conversations list + conversation detail (chat log + summary)
- `DONE` Step 3: Entities table (pagination/filtering/sorting + dynamic field columns)
- `DONE` Step 4: Entity detail page (facts + relations + timeline + neighborhood hover preview + load-more)
- `DONE` Step 5: Search page (semantic grouping + conversation/type/time filters + previews)
- `DONE` Step 6: Explain pages (facts + relations with enriched metadata/provenance)
- `DONE` Step 7: Schema explorer (read-only nodes/fields/relations/proposals with rationale + affected links)
- `DONE` Step 8: Graph neighborhood visualization (interactive graph rendering)

## Change Log

### Phase 3 foundation implementation

- Added new backend Phase 3 UX support schemas:
  - `backend/app/schemas/workspace.py`
  - `backend/app/schemas/entity_listing.py`
- Added new backend workspace service layer:
  - `backend/app/services/workspace.py`
  - Includes:
    - `GET /conversations` aggregation support
    - `GET /recent/entities` support
    - global entities catalog support for `GET /entities` with sorting/filtering/pagination and `fields=` dynamic columns
    - `GET /schema/overview` aggregation support
- Added new backend workspace router:
  - `backend/app/routers/workspace.py`
  - Routes:
    - `GET /conversations`
    - `GET /recent/entities`
    - `GET /entities`
- Extended schema router:
  - `backend/app/routers/schema.py`
  - Route:
    - `GET /schema/overview`
- Wired workspace router into API app:
  - `backend/app/main.py`
- Added Phase 3 backend service coverage:
  - `backend/tests/test_phase3_workspace_services.py`

### Frontend workspace migration (Phase 3 routes)

- Replaced Phase 2 test-console shell with Phase 3 navigation shell:
  - `frontend/app/layout.tsx`
  - `frontend/components/AppNav.tsx`
  - `frontend/app/globals.css`
- Added/updated routes:
  - `/workspace` -> `frontend/app/workspace/page.tsx`
  - `/conversations` -> `frontend/app/conversations/page.tsx`
  - `/conversations/[conversation_id]` -> `frontend/app/conversations/[conversation_id]/page.tsx`
  - `/entities` -> `frontend/app/entities/page.tsx`
  - `/entities/[entity_id]` -> `frontend/app/entities/[entity_id]/page.tsx`
  - `/schema` -> `frontend/app/schema/page.tsx`
  - `/search` -> `frontend/app/search/page.tsx`
  - `/explain` -> `frontend/app/explain/page.tsx`
  - `/explain/[kind]/[id]` -> `frontend/app/explain/[kind]/[id]/page.tsx`
  - `/` now redirects to `/workspace` (`frontend/app/page.tsx`)
- Replaced frontend API client with Phase 3-oriented contracts/endpoints:
  - `frontend/lib/api.ts`
  - added `frontend/lib/format.ts`
- Removed obsolete Phase 2-only UI routes/components:
  - deleted `frontend/components/LibrarianWorkbench.tsx`
  - deleted legacy route pages under `/conversation`, `/database`, `/live` and old `/explain` implementation

### Documentation update

- Updated project README to reflect Phase 3 app routes + new backend endpoints:
  - `README.md`

### Clarity + explainability depth update (2026-02-28)

- Progress log format improved for readability:
  - replaced checkbox-only view with explicit status labels (`DONE`, `IN PROGRESS`, `NOT STARTED`)
  - added rollup summary counters by status
  - marked Step 3 as `DONE` after validating full requirement coverage
- Explainability payloads enriched with extractor metadata and schema proposal linkage:
  - `backend/app/schemas/explain.py`
  - `backend/app/services/explain.py`
  - Added fields:
    - `extraction_metadata` (`extractor_run_id`, `model_name`, `prompt_version`, `created_at`)
    - `schema_canonicalization.proposal` (`proposal_id`, `proposal_type`, `status`, `confidence`, `created_at`)
- Frontend explain view updated to render new metadata:
  - `frontend/lib/api.ts`
  - `frontend/app/explain/[kind]/[id]/page.tsx`
- Explainability integration test extended:
  - `backend/tests/test_explain_expanded.py`
  - now asserts enriched extraction metadata is present in explain responses

### Steps 4-7 completion pass (2026-02-28)

- Step 4 completion updates (Entity detail page):
  - Added canonical-vs-raw field display with default canonical-only view and raw-variant toggle
  - Added relation qualifiers + confidence rendering
  - Added mixed timeline stream (facts + relations) with explain links
  - Added graph neighborhood quality pass:
    - load-more neighbors
    - hover preview card with edge counts/labels
  - Files:
    - `frontend/app/entities/[entity_id]/page.tsx`
    - `frontend/app/globals.css`
- Step 5 completion updates (Search):
  - Added type-label and time-range filters end-to-end:
    - backend search router/service + frontend query UI
  - Added result previews for entities/facts and visible active filter summary
  - Files:
    - `backend/app/routers/search.py`
    - `backend/app/services/search.py`
    - `backend/app/schemas/search.py`
    - `frontend/app/search/page.tsx`
    - `frontend/lib/api.ts`
- Step 6 completion updates (Explain pages):
  - Added extractor metadata and schema proposal linkage in explain payloads
  - Added confidence display and snippet/provenance polish in UI
  - Added confidence persistence for relations model + migration
  - Files:
    - `backend/app/schemas/explain.py`
    - `backend/app/services/explain.py`
    - `backend/app/models/relation.py`
    - `backend/app/schemas/relation.py`
    - `backend/app/services/extraction.py`
    - `backend/alembic/versions/20260228_0009_phase3_relation_confidence.py`
    - `frontend/app/explain/[kind]/[id]/page.tsx`
    - `frontend/lib/api.ts`
- Step 7 completion updates (Schema explorer):
  - Added searchable, paginated client-side explorer presentation
  - Added richer rows (description/examples/cluster hints/last seen)
  - Added proposal rationale/evidence expanders and affected-item anchors
  - Files:
    - `frontend/app/schema/page.tsx`
    - `frontend/app/globals.css`
- Test updates:
  - Added search filter coverage:
    - `backend/tests/test_search_and_knowledge.py`
  - Kept explain metadata coverage:
    - `backend/tests/test_explain_expanded.py`

### Step 8 completion pass (2026-02-28)

- Step number:
  - `Step 8`
- Added interactive entity neighborhood graph rendering on entity detail:
  - SVG-based graph view with:
    - center node (current entity)
    - navigable neighbor nodes (click-through to entity pages)
    - directed/labeled edge overlays for incoming/outgoing relation groups
    - hover-linked highlight and existing hover preview integration
    - continued load-more neighbors behavior for progressive expansion
  - Files:
    - `frontend/app/entities/[entity_id]/page.tsx`
    - `frontend/app/globals.css`
- Migration status:
  - `No migration required` (frontend-only change)
- Test/build status:
  - `npm run build` (from `frontend/`) passed
- Next step:
  - `Phase 3 complete` -> begin Phase 4 hardening scope

### Phase 3 polish expansion pass (2026-02-28)

- Step number:
  - `Phase 3 polish extension (post Step 8)`
- Summary:
  - Added dedicated graph workspace page with full conversation graph controls:
    - route: `/graph`
    - full conversation graph fetch via new backend endpoint
    - node/type/edge filters
    - relation highlight selector
    - node inspector with edit/delete
    - relation table with edit/delete
  - Restored dedicated chatbot-style chatroom page:
    - route: `/chat`
    - instruction/system-prompt editor
    - live turn execution (`/conversations/{id}/chat/turn`)
    - visible "Thinking..." state
    - chat log refresh + per-message edit/delete
  - Added editable/deletable row actions across primary tables:
    - entities table: edit/delete entity rows
    - entity detail facts table: edit/delete fact rows
    - entity detail relations tables: edit/delete relation rows
    - conversation detail chat log: edit/delete message rows
    - schema explorer tables (types/fields/relations): edit/delete schema rows
  - Improved schema table header readability:
    - widened schema table minimum width
    - explicit header nowrap + min-width to prevent squashed headers
- Backend additions:
  - New mutation router + service + schemas:
    - `backend/app/routers/mutations.py`
    - `backend/app/services/mutations.py`
    - `backend/app/schemas/mutations.py`
    - includes schema row mutation endpoints:
      - `PATCH/DELETE /schema/nodes/{id}`
      - `PATCH/DELETE /schema/fields/{id}`
      - `PATCH/DELETE /schema/relations/{id}`
  - Added conversation graph endpoint:
    - `GET /conversations/{conversation_id}/graph`
    - files:
      - `backend/app/services/knowledge.py`
      - `backend/app/routers/knowledge.py`
      - `backend/app/schemas/knowledge.py`
  - Wired mutation router:
    - `backend/app/main.py`
- Frontend additions/updates:
  - New pages:
    - `frontend/app/graph/page.tsx`
    - `frontend/app/chat/page.tsx`
  - API client expanded for graph/live chat/mutations:
    - `frontend/lib/api.ts`
  - Navigation/dashboard updates:
    - `frontend/components/AppNav.tsx`
    - `frontend/app/workspace/page.tsx`
    - `frontend/app/conversations/[conversation_id]/page.tsx`
  - Editable table row actions:
    - `frontend/app/entities/page.tsx`
    - `frontend/app/entities/[entity_id]/page.tsx`
  - UI polish styles + schema header fix:
    - `frontend/app/globals.css`
  - Schema explorer edit/delete wiring:
    - `frontend/app/schema/page.tsx`
- Migration status:
  - `No migration required` (API/service/frontend only)
- Test/build status:
  - Backend:
    - `.venv\Scripts\python.exe -m unittest tests.test_phase3_mutations_and_graph -v` -> passing
    - `.venv\Scripts\python.exe -m unittest tests.test_search_and_knowledge -v` -> passing
  - Frontend:
    - `npm run build` (from `frontend/`) -> passing (includes `/chat` and `/graph`)
- Next step:
  - `Phase 4 hardening` (performance + async jobs + export + robustness pass)

### Focused chat+graph UX pass (2026-02-28)

- Step number:
  - `Phase 3 polish refinement (chat + graph UX)`
- Summary:
  - Replaced popup editing with in-place editing for new pages:
    - `/chat`: inline per-message edit mode (textarea + save/cancel)
    - `/graph`: inline node inspector editing + inline relation row editing
  - Improved relationship highlighting in graph with distinct highlight color:
    - highlighted edges now render in high-contrast orange with stronger stroke
    - non-highlighted edges are dimmed while highlight mode is active
    - legend added to clarify edge color semantics
  - Added graph layout mode options:
    - `Ring` layout (existing radial behavior)
    - `Tree` layout (level-based BFS layout from selected node/component roots)
- Files:
  - `frontend/app/chat/page.tsx`
  - `frontend/app/graph/page.tsx`
  - `frontend/app/globals.css`
- Migration status:
  - `No migration required` (frontend-only refinement)
- Test/build status:
  - Frontend:
    - `npm run build` (from `frontend/`) -> passing
- Next step:
  - Optional: replace confirm-based deletes with inline confirmation UI chips for full non-modal CRUD flow

## Verification

- Backend tests:
  - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v` (from `backend/`)
  - Result: `21/21` passing
- Frontend build:
  - `npm run build` (from `frontend/`)
  - Result: success (all routes compiled)
- Frontend build (Step 8 verification):
  - `npm run build` (from `frontend/`)
  - Result: success (graph neighborhood update compiled; all routes compiled)
