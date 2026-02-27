# PHASE_4.md — MVP Completion & Hardening

## Phase Objective

Phase 4 transforms Librarian from a functional prototype into a stable, demo-ready, usable MVP.

Phase 2 built intelligence.
Phase 3 built visibility.
Phase 4 builds reliability.

This phase focuses on:

- Stability
- Performance
- Real-time experience
- Background processing
- UX polish
- Production readiness

No major new intelligence features should be introduced here.

---

# Core Outcomes

By the end of Phase 4:

1) Extraction and stabilization run asynchronously and reliably.
2) The UI feels fast and responsive.
3) Large conversations do not degrade performance.
4) Search is performant at scale.
5) Schema growth does not slow the system.
6) Errors are observable and logged.
7) The product is stable enough for early users and demos.

---

# 1. Background Processing

Extraction, resolution, stabilization, and embedding generation must not block API responses.

Implement:

- Background job system (Celery, RQ, or lightweight async task runner)
- Task queue for:
  - LLM extraction
  - Entity resolution
  - Schema stabilization
  - Embedding generation

Required guarantees:
- Idempotent tasks
- Safe retries
- Failure logging
- Status tracking per conversation

Add:

extraction_jobs table:
- id
- conversation_id
- status (pending | running | complete | failed)
- error_message
- started_at
- completed_at

Expose endpoint:

GET /conversations/{id}/status

So UI can poll for processing state.

---

# 2. Real-Time Ingestion (MVP-Level)

Goal: conversation feels live.

Options:
- WebSocket
- Polling (acceptable for MVP)

Minimum requirement:
- After ingestion, UI updates automatically when extraction completes.

Optional:
- Stream extraction progress states.

Do not over-engineer streaming.

---

# 3. Database Performance Optimization

Add indexes:

entities:
- canonical_name
- embedding (vector index)

facts:
- entity_id
- field_label
- created_at

relations:
- from_entity_id
- to_entity_id
- relation_label

messages:
- conversation_id
- timestamp

schema tables:
- label
- canonical_of_id

Search:
- vector index for pgvector

Run EXPLAIN on heavy queries and optimize.

---

# 4. Pagination & Query Efficiency

All list endpoints must support:

- limit
- offset or cursor-based pagination

Never return unbounded datasets.

Large entity tables must:
- paginate
- lazily load relations
- lazy load graph neighbors

---

# 5. Caching Layer (Lightweight)

Add optional in-memory caching for:

- schema overview
- frequently accessed entities
- search results (short TTL)

Do NOT introduce Redis unless needed.
Keep MVP simple.

---

# 6. Logging & Observability

Implement structured logging.

Log:

- extraction runs
- resolution events
- schema proposals
- background job failures
- search queries (optional)

Add:
- request IDs
- correlation IDs between extraction and resolution

Errors must:
- never fail silently
- always log context
- return meaningful API responses

---

# 7. Error Handling & Validation Hardening

Ensure:

- LLM JSON parsing failures are retried
- Schema canonicalization conflicts do not corrupt data
- Merge operations are reversible
- Invalid embeddings do not crash search
- Background job failures are recoverable

Add defensive validation everywhere:
- Pydantic validation
- Transaction rollbacks
- Explicit error responses

---

# 8. Data Integrity Guarantees

Phase 4 must enforce:

- No orphaned foreign keys
- No broken merged_into chains
- No circular merge chains
- Canonicalization cannot point to itself

Add:
- database constraints where possible
- migration validations

---

# 9. UX Hardening

Frontend must include:

- Loading states everywhere
- Error states everywhere
- Empty state views
- No layout shifts
- Debounced search
- Skeleton loaders for tables

Graph rendering must:
- handle large node counts gracefully
- cap neighbors per render
- support expand-on-click

---

# 10. Export & Interoperability (MVP Scope)

Add export endpoints:

GET /export/entities
GET /export/facts
GET /export/relations

Formats:
- JSON
- CSV

This enables:
- user trust
- investor demo power
- portability

---

# 11. Security & Access (MVP-Level)

Minimum:

- Basic authentication or token-based auth
- Prevent open public API exposure
- Rate limiting for extraction endpoints

Do not implement full multi-tenancy.
Keep MVP simple.

---

# 12. Final MVP Checklist

Before declaring MVP complete:

- Multiple large conversations processed without failure
- Entity resolution stable
- Schema registry stable
- Search returns accurate results
- Explain endpoints always resolve correctly
- Graph view responsive
- No blocking extraction
- Background jobs stable
- Logs show no silent failures
- Export works
- API docs accurate

---

# Phase 4 Completion Criteria

Phase 4 is complete when:

1) The system can handle 10+ substantial conversations.
2) Schema growth does not degrade performance.
3) Search returns results under acceptable latency.
4) Extraction runs asynchronously and reliably.
5) The UI feels smooth and stable.
6) No destructive operations exist.
7) The product can be demoed confidently to:
   - early users
   - technical advisors
   - potential investors

At completion, Librarian is:

- Structurally intelligent
- Visibly transparent
- Persistently organized
- Usable by humans
- Stable enough to ship