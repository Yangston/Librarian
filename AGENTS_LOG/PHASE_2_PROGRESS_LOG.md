# Phase 2 Progress Log

Last updated: 2026-02-27

## Progress Status

- [x] Step 1: `extractor_runs` table + logging
- [x] Step 2: LLM structured extraction with validation (dynamic schema format)
- [x] Step 3: Entity resolution + resolution logging (`resolution_events`)
- [x] Step 4: Schema registry tables (`schema_nodes`, `schema_fields`, `schema_relations`, `schema_proposals`)
- [x] Step 5: Schema-on-write logic
- [x] Step 6: Schema stabilization job
- [x] Step 7: Embeddings integration
- [x] Step 8: Search endpoint
- [x] Step 9: Knowledge query endpoints
- [x] Step 10: Explain endpoints expansion

## Change Log

### Step 1 completion (Extractor runs)

- Added extractor run model:
  - `backend/app/models/extractor_run.py`
- Added migration:
  - `backend/alembic/versions/20260227_0004_extractor_runs.py`
- Wired logging into extraction service:
  - `backend/app/services/extraction.py`
- Extended extraction response schema with `extractor_run_id`:
  - `backend/app/schemas/extraction.py`
- Added LLM extractor metadata exposure (`prompt_version`, `model_name`, raw/validated payload capture):
  - `backend/app/extraction/llm_extractor.py`
- Added/updated tests:
  - `backend/tests/test_extractor_runs.py`
  - `backend/tests/test_phase2_resolution_integration.py`
  - `backend/tests/test_live_chat_service.py`

### Step 2 completion (Dynamic extraction contract, no hardcoded type list)

- Refactored extraction data contract to dynamic labels:
  - Entities: `name`, `aliases`, `type_label`, `confidence`, `source_message_ids`
  - Facts: `entity_name`, `field_label`, `value_text`, `confidence`, `source_message_ids`
  - Relations: `from_entity`, `relation_label`, `to_entity`, `qualifiers`, `confidence`, `source_message_ids`
- Updated extraction typed outputs:
  - `backend/app/extraction/types.py`
- Updated LLM JSON schema, prompt guidance, parsing, dedupe, and normalization:
  - `backend/app/extraction/llm_extractor.py`
- Updated persistence mapping to new contract and removed fixed type normalization:
  - `backend/app/services/extraction.py`
- Updated entity resolver to use free-form optional `type_label` matching:
  - `backend/app/entity_resolution/resolver.py`
- Updated smoke script output to new extraction format:
  - `backend/scripts/smoke_llm_extractor.py`
- Removed obsolete fixed-type module/tests:
  - deleted `backend/app/schema/entity_types.py`
  - deleted `backend/tests/test_entity_types.py`
- Updated schema package exports:
  - `backend/app/schema/__init__.py`
- Updated integration/unit tests for new extraction fields:
  - `backend/tests/test_entity_resolver.py`
  - `backend/tests/test_phase2_resolution_integration.py`
  - `backend/tests/test_live_chat_service.py`
  - `backend/tests/test_extractor_runs.py`

### Step 3 completion (Resolution events logging)

- Added resolution event model + migration:
  - `backend/app/models/resolution_event.py`
  - `backend/alembic/versions/20260227_0005_resolution_events.py`
- Registered model for metadata loading:
  - `backend/app/models/__init__.py`
  - `backend/app/db/base.py`
- Added resolution event schema + database endpoint:
  - `backend/app/schemas/resolution_event.py`
  - `backend/app/services/database.py`
  - `backend/app/routers/database.py`
- Added extraction-time resolution event logging (`match`, `merge`, `alias_add`) and rerun cleanup:
  - `backend/app/services/extraction.py`
- Updated tests and table resets:
  - `backend/tests/test_phase2_resolution_integration.py`
  - `backend/tests/test_live_chat_service.py`
  - `backend/tests/test_extractor_runs.py`
- Added extractor contract regression test (prevent duplicate name/null-type entity rows):
  - `backend/tests/test_llm_extractor_contract.py`
- Improved extractor entity reconciliation and confidence handling after live API validation:
  - `backend/app/extraction/llm_extractor.py`
  - `backend/app/extraction/types.py`
- Updated documentation endpoint list:
  - `README.md`

### Step 4 completion (Schema registry tables)

- Added schema registry models:
  - `backend/app/models/schema_node.py`
  - `backend/app/models/schema_field.py`
  - `backend/app/models/schema_relation.py`
  - `backend/app/models/schema_proposal.py`
- Added migration for schema registry tables:
  - `backend/alembic/versions/20260227_0006_schema_registry_tables.py`
- Registered models for SQLAlchemy metadata loading:
  - `backend/app/models/__init__.py`
  - `backend/app/db/base.py`
- Added schema registry persistence integration test:
  - `backend/tests/test_schema_registry.py`

### Step 5 completion (Schema-on-write logic)

- Implemented schema-on-write registration inside extraction persistence:
  - Registers `type_label` -> `schema_nodes`
  - Registers canonical `field_label` -> `schema_fields`
  - Registers canonical `relation_label` -> `schema_relations`
  - Updates `examples_json` and `stats_json` on repeated observations
  - `backend/app/services/extraction.py`
- Added integration assertions for schema-on-write behavior in extraction pipeline:
  - `backend/tests/test_phase2_resolution_integration.py`

### Step 6 completion (Schema stabilization job)

- Added stabilization job service:
  - `backend/app/services/schema_stabilization.py`
  - Generates merge proposals for:
    - `schema_fields` -> `merge_fields`
    - `schema_relations` -> `merge_relations`
    - `schema_nodes` -> `merge_nodes`
  - Uses deterministic string similarity as current signal (pre-embeddings), creates `schema_proposals`, and auto-accepts very high-confidence pairs by setting `canonical_of_id`.
- Wired stabilization job into extraction flow after schema-on-write:
  - `backend/app/services/extraction.py`
- Added stabilization tests:
  - `backend/tests/test_schema_stabilization.py`
  - Added extraction integration coverage:
    - `backend/tests/test_phase2_resolution_integration.py`

## Verification

- Ran backend test discovery:
  - `python -m unittest discover -s tests -p "test_*.py" -v`
- Result: all tests passing after Step 2 + Step 3 + Step 4 + Step 5 + Step 6 changes.
- Ran live extractor smoke call (real OpenAI API):
  - `python scripts/smoke_llm_extractor.py`
- Result: succeeded with dynamic `type_label` / `field_label` / `relation_label` output and no duplicate null-vs-typed entities after reconciliation fix.

### Support update (Env loading reliability for live extraction tests)

- Step reference: Phase 2 testing/verification support (non-roadmap step)
- Summary: Fixed settings env resolution so backend always loads `backend/.env` regardless of current working directory.
- Files changed:
  - `backend/app/config.py`
- Migration status:
  - None required.
- Test status:
  - Re-ran live smoke extraction from repo root: `python backend/scripts/smoke_llm_extractor.py` via backend venv.
  - Result: success; extractor used live API path and returned structured entities/facts/relations.
- Next step:
  - Continue Phase 2 Step 7 (embeddings integration) from `AGENTS/PHASE_2.md`.

### Step 7 completion (Embeddings integration)

- Added embedding integration service (OpenAI embeddings + deterministic fallback, cosine similarity helpers):
  - `backend/app/services/embeddings.py`
- Added embedding model config and env example entry:
  - `backend/app/config.py`
  - `backend/.env.example`
- Added embedding columns + extraction linkage columns and conversation-entity links table:
  - `backend/alembic/versions/20260227_0007_embeddings_search_foundation.py`
  - `backend/app/models/entity.py`
  - `backend/app/models/fact.py`
  - `backend/app/models/relation.py`
  - `backend/app/models/conversation_entity_link.py`
  - `backend/app/models/__init__.py`
  - `backend/app/db/base.py`
- Wired extraction-time embedding assignment for entities/facts, schema embedding updates, and `conversation_entity_links` persistence:
  - `backend/app/services/extraction.py`
- Updated schema stabilization to use embedding cosine similarity when available:
  - `backend/app/services/schema_stabilization.py`

### Step 8 completion (Search endpoint)

- Added semantic search schemas:
  - `backend/app/schemas/search.py`
- Added semantic search service over entity/fact embeddings with optional conversation scope:
  - `backend/app/services/search.py`
- Added API route:
  - `backend/app/routers/search.py`
  - `GET /search?q=...&conversation_id=...`

### Step 9 completion (Knowledge query endpoints)

- Added knowledge query response schemas:
  - `backend/app/schemas/knowledge.py`
- Added knowledge services:
  - `backend/app/services/knowledge.py`
- Added endpoints:
  - `backend/app/routers/knowledge.py`
  - `GET /entities/{id}`
  - `GET /entities/{id}/graph`
  - `GET /entities/{id}/timeline`
  - `GET /conversations/{conversation_id}/summary`

### Step 10 completion (Explain endpoints expansion)

- Expanded explain response schema with:
  - `extractor_run_id`
  - `resolution_events`
  - `schema_canonicalization`
  - `backend/app/schemas/explain.py`
- Expanded explain service to include enriched explainability trail and added global explain lookups:
  - `backend/app/services/explain.py`
- Added global explain endpoints:
  - `GET /facts/{fact_id}/explain`
  - `GET /relations/{relation_id}/explain`
  - `backend/app/routers/explain.py`
- Added `extractor_run_id` serialization support:
  - `backend/app/schemas/fact.py`
  - `backend/app/schemas/relation.py`

### Router wiring and docs updates

- Registered new routers in API app:
  - `backend/app/main.py`
- Updated README endpoint list:
  - `README.md`

### Tests added/updated for Steps 7-10

- Added semantic search + knowledge integration test:
  - `backend/tests/test_search_and_knowledge.py`
- Added expanded explainability integration test:
  - `backend/tests/test_explain_expanded.py`
- Updated reset coverage for new `conversation_entity_links` table:
  - `backend/tests/test_phase2_resolution_integration.py`
  - `backend/tests/test_live_chat_service.py`
  - `backend/tests/test_extractor_runs.py`

### Verification update (Steps 7-10)

- Ran backend test discovery:
  - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
- Result:
  - `19/19` tests passing (including new search/knowledge/explain coverage).
- Ran live extraction smoke from repo root after changes:
  - `.\backend\.venv\Scripts\python.exe backend\scripts\smoke_llm_extractor.py`
- Result:
  - Success; live LLM extraction returned structured output.

### Strict completion closure pass (Delta remediation against `AGENTS/PHASE_2.MD`)

- Step reference: Phase 2 strict-spec deltas after checklist completion.
- Summary: Implemented the remaining gaps identified during strict audit, including global cross-conversation entity linking, resolver embedding + optional LLM disambiguation path, prompt-file versioning, pgvector-compatible embeddings, fact/relation scope fields, and background post-processing jobs for embeddings/stabilization.
- Files changed:
  - `backend/app/extraction/prompts/phase2_v1.txt`
  - `backend/app/extraction/llm_extractor.py`
  - `backend/app/config.py`
  - `backend/.env.example`
  - `backend/app/models/embedding_type.py`
  - `backend/app/models/base.py`
  - `backend/app/models/entity.py`
  - `backend/app/models/fact.py`
  - `backend/app/models/relation.py`
  - `backend/app/models/schema_node.py`
  - `backend/app/models/schema_field.py`
  - `backend/app/models/schema_relation.py`
  - `backend/app/schemas/entity.py`
  - `backend/app/schemas/fact.py`
  - `backend/app/schemas/relation.py`
  - `backend/app/entity_resolution/resolver.py`
  - `backend/app/services/extraction.py`
  - `backend/app/services/search.py`
  - `backend/app/services/embeddings.py`
  - `backend/app/services/background_jobs.py`
  - `backend/app/routers/extraction.py`
  - `backend/tests/test_phase2_resolution_integration.py`
  - `backend/requirements.txt`
  - `backend/alembic/versions/20260227_0008_phase2_strict_completion.py`
- Migration status:
  - Added strict completion migration:
    - `20260227_0008_phase2_strict_completion.py`
  - Adds entity metadata columns (`display_name`, `type_label`, `updated_at`), fact/relation `scope`, and Postgres pgvector conversion hooks (`CREATE EXTENSION vector`, embedding columns to `vector(1536)`).
- Test status:
  - Ran backend tests:
    - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
  - Result:
    - `20/20` tests passing.
  - Added cross-conversation persistence verification:
    - `test_cross_conversation_global_entity_linking_reuses_existing_canonical` in `backend/tests/test_phase2_resolution_integration.py`.
  - Ran live extraction smoke:
    - `.\backend\.venv\Scripts\python.exe backend\scripts\smoke_llm_extractor.py`
  - Result:
    - Success with live API output.
- Strict completion criteria update:
  - `schema-on-write + schema-on-read support`: implemented via canonicalization-aware explain/search/knowledge reads plus dynamic schema registry reads.
  - `entities are global`: enabled cross-conversation canonical reuse and non-destructive entity persistence.
  - `embedding similarity in resolver`: implemented hash/openai embedding similarity path with borderline optional LLM disambiguation gate (`ENABLE_RESOLUTION_LLM_DISAMBIGUATION`).
  - `pgvector`: added dependency + model/migration support with sqlite-safe fallback.
  - `fact/relation scope`: added `scope` fields with default `conversation`.
  - `background jobs`: extraction API now queues post-processing jobs for embeddings and schema stabilization.
  - `versioned prompt files`: extractor prompt now loaded from versioned prompt file (`phase2.v1`).
- Next step:
  - Apply migrations in the target Postgres DB and run a quick API-level smoke to validate background post-processing timing in live mode.

### Support update (pgvector extension missing on host Postgres)

- Step reference: strict completion migration hardening
- Summary: Fixed migration/runtime behavior so environments without system-installed pgvector do not fail migration. pgvector is now opt-in.
- Files changed:
  - `backend/alembic/versions/20260227_0008_phase2_strict_completion.py`
  - `backend/app/models/embedding_type.py`
  - `backend/app/config.py`
  - `backend/.env.example`
- Migration behavior update:
  - `0008` now attempts `CREATE EXTENSION vector` and vector column conversion only when:
    - database is PostgreSQL,
    - `ENABLE_PGVECTOR=true`,
    - and `pg_available_extensions` reports `vector` available.
  - Otherwise migration proceeds without vector conversion (JSON embedding columns remain valid).
- Runtime behavior update:
  - ORM embedding type uses pgvector only when `ENABLE_PGVECTOR=true`; otherwise uses JSON storage.
- Test status:
  - Re-ran backend tests:
    - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
  - Result:
    - `20/20` tests passing.

### Support update (Phase 2 strict pass performance regression mitigation)

- Step reference: strict completion stabilization/performance hardening
- Summary: Addressed post-delta slowdown by removing network embedding calls from the global matching hot path, limiting global candidate scans, and moving live-chat post-processing to background jobs.
- Root cause observed:
  - Global matching evaluated many historical entities and could compute embeddings in-loop, causing heavy latency under real API-key mode.
  - Live chat extraction still executed heavy post-processing inline.
- Files changed:
  - `backend/app/services/extraction.py`
  - `backend/app/services/live_chat.py`
  - `backend/app/routers/live_chat.py`
  - `backend/app/config.py`
  - `backend/.env.example`
- Behavior changes:
  - Global matcher now uses deterministic local hash embedding for missing vectors (no remote API call in matching loop).
  - Added coarse gating + configurable max candidate cap (`GLOBAL_RESOLUTION_MAX_CANDIDATES`, default `500`).
  - Live chat extraction now runs with `post_processing_mode="none"` and queues background post-processing task.
- Test status:
  - Re-ran backend tests:
    - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
  - Result:
    - `20/20` tests passing.

### Support update (Timing logs + frontend Phase 2 endpoint coverage)

- Step reference: Phase 2 observability + transparency hardening
- Summary: Added backend timing logs for extraction/live-chat/background post-processing and expanded frontend coverage for the full Phase 2 endpoint surface (search, summary, graph, timeline, resolution events, and enriched explain metadata).
- Files changed:
  - `backend/app/services/extraction.py`
  - `backend/app/services/live_chat.py`
  - `backend/app/services/background_jobs.py`
  - `frontend/lib/api.ts`
  - `frontend/components/LibrarianWorkbench.tsx`
  - `frontend/app/page.tsx`
- Migration status:
  - None required.
- Behavior changes:
  - Backend now logs structured timing metrics:
    - `phase2.extraction_timing` / `phase2.extraction_failed`
    - `phase2.live_chat_timing` / `phase2.live_chat_failed`
    - `phase2.embedding_backfill_timing` / `phase2.embedding_backfill_failed`
    - `phase2.schema_stabilization_timing` / `phase2.schema_stabilization_failed`
    - `phase2.post_processing_timing`
  - Frontend now captures and renders:
    - `resolution-events` table in structured memory inspector
    - semantic search results (`GET /search`)
    - conversation summary (`GET /conversations/{id}/summary`)
    - entity graph + timeline (`GET /entities/{id}/graph`, `/entities/{id}/timeline`)
    - explain metadata additions (`extractor_run_id`, `resolution_events`, `schema_canonicalization`)
    - global explain endpoint toggle (`/facts/{id}/explain`, `/relations/{id}/explain`)
    - Phase 2 fields in tables (`display_name`, `type_label`, `updated_at`, `scope`, `extractor_run_id`)
- Test status:
  - Not run in this step (code-only update with no migration changes).
- Next step:
  - Run backend + frontend smoke and verify timing logs in server output while triggering `/chat/turn` and `/extract`.
