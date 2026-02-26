# Librarian — Phase 2 AGENTS.md

You are acting as a senior systems architect and AI infrastructure engineer.

Project: Librarian 
 
High-Level Vision:
Librarian is a structured cognitive layer for AI systems. 
Instead of chat conversations remaining unstructured logs, Librarian converts live conversations into a transparent, queryable, relational knowledge system.

Stage: Phase 2 — Intelligent Structuring + Entity Resolution + Schema Evolution  

Phase 1 proved:
Conversations → Entities/Facts/Relations → Transparent storage.

Phase 2 must prove:
Conversations → Adaptive Structured Knowledge System that improves over time.

This is no longer a demo.
This is the beginning of a defensible product.

------------------------------------------------------------
PHASE 2 OBJECTIVES
------------------------------------------------------------

1) Replace rule-based extraction with structured LLM extraction.
2) Implement entity resolution + deduplication.
3) Implement schema stabilization (controlled type system).
4) Introduce conversation-level knowledge graph reasoning.
5) Improve explainability + traceability.
6) Prepare architecture for multi-conversation aggregation.
7) Introduce search + embeddings layer.

Do NOT:
- Build enterprise multi-tenancy yet.
- Over-engineer graph visualization.
- Add premature distributed systems.
- Build full ontology automation.

------------------------------------------------------------
CORE ARCHITECTURAL EVOLUTION
------------------------------------------------------------

Phase 2 adds intelligence layers:

Layer 1: Structured Extraction Engine
Layer 2: Entity Resolution Engine
Layer 3: Schema Governance Layer
Layer 4: Knowledge Query Layer
Layer 5: Search + Embeddings Layer

Each layer must be modular.

------------------------------------------------------------
1) STRUCTURED LLM EXTRACTION (MANDATORY)
------------------------------------------------------------

Replace simple regex or naive LLM output with:

- Strict JSON schema enforced extraction.
- Use Pydantic or JSON Schema validation.
- Extraction must occur in two passes:

Pass A: Raw structured extraction
Pass B: Validation + normalization pass

Extraction must produce:
{
  entities: [...],
  facts: [...],
  relations: [...]
}

Constraints:
- Entities must include canonical_name and type.
- Facts must reference entity names (resolved later).
- Relations must include directional semantics.

Extraction must be deterministic:
- Same input → same structured output (within reason).
- Avoid hallucinated entities not present in text.

------------------------------------------------------------
2) ENTITY RESOLUTION ENGINE
------------------------------------------------------------

This is critical.

Goal:
Avoid duplicate entities like:
- "Apple"
- "Apple Inc."
- "AAPL"

Add:
entity_resolution/
    resolver.py

Resolution steps:
1) Exact name match
2) Alias match
3) Embedding similarity threshold
4) Optional LLM-assisted disambiguation

Store:
- canonical_name
- known_aliases
- first_seen_timestamp
- confidence score

All entity merges must log:
- merged_entity_ids
- reason_for_merge
- timestamp

Transparency is mandatory.

------------------------------------------------------------
3) SCHEMA GOVERNANCE LAYER
------------------------------------------------------------

Phase 1 allowed arbitrary types.

Phase 2 introduces controlled type system.

Entity Types (v1 fixed list):
- Company
- Person
- Event
- Concept
- Metric
- Location
- Other

Fact Predicate Guidelines:
- Must be normalized (snake_case)
- Avoid natural language sentences
- Examples:
    reported_revenue
    experienced_stock_change
    impacted_by
    has_market_cap

Implement:
schema/
    entity_types.py
    predicate_registry.py

Predicate registry should:
- Store known predicates
- Track frequency
- Prevent explosion of near-duplicate predicates

------------------------------------------------------------
4) MULTI-CONVERSATION KNOWLEDGE ACCUMULATION
------------------------------------------------------------

Phase 2 enables:
- Multiple conversations contributing to same entity graph.

Add:
- Global entity table (not per conversation only)
- Conversation-entity linking table

Implement:
conversation_entities
conversation_facts
conversation_relations

Allow:
- Query by conversation
- Query global graph

This is the first step toward persistent AI memory.

------------------------------------------------------------
5) SEARCH + EMBEDDINGS LAYER
------------------------------------------------------------

Add embeddings for:
- Entities
- Facts

Use:
- text-embedding model
- Store vectors in Postgres (pgvector)

Capabilities:
- Semantic search
- Find related entities
- Suggest potential relation candidates

Add endpoint:
GET /search?q=...

Must return:
- Matched entities
- Matched facts
- Similarity score

------------------------------------------------------------
6) KNOWLEDGE QUERY ENDPOINTS
------------------------------------------------------------

Add:

GET /entities/{id}/graph
Returns:
{
  entity,
  related_entities,
  outgoing_relations,
  incoming_relations,
  supporting_facts
}

GET /entities/{id}/timeline
Returns:
- Facts ordered by timestamp
- Related events

This proves structured reasoning over stored knowledge.

------------------------------------------------------------
7) EXPLAINABILITY IMPROVEMENTS
------------------------------------------------------------

Every fact and relation must support:

GET /facts/{id}/explain
Returns:
{
  structured_record,
  source_messages,
  extraction_prompt_version,
  resolution_steps
}

Track:
- extractor_version
- resolver_version

This is critical for future investor demos.

------------------------------------------------------------
DIRECTORY STRUCTURE (UPDATED)
------------------------------------------------------------

backend/app/

    extraction/
        extractor_interface.py
        llm_extractor.py
        validation.py

    entity_resolution/
        resolver.py
        similarity.py

    schema/
        entity_types.py
        predicate_registry.py

    search/
        embedding_service.py
        search_service.py

    graph/
        graph_service.py

------------------------------------------------------------
TECH REQUIREMENTS
------------------------------------------------------------

Backend:
- FastAPI
- SQLAlchemy
- Alembic
- pgvector extension

Extraction:
- OpenAI structured output API
- JSON schema enforcement
- Retry + validation logic

All services:
- Type hints required
- Logging required
- Errors must be explicit
- No silent failures

------------------------------------------------------------
DATA INTEGRITY RULES
------------------------------------------------------------

- Never delete entities during merge.
- Instead mark merged_into_id.
- Keep full audit trail.
- Never allow orphaned foreign keys.
- All merges must be reversible.

------------------------------------------------------------
PERFORMANCE CONSTRAINTS
------------------------------------------------------------

- Extraction async
- Resolution batched
- Search indexed
- Use proper DB indexing on:
    conversation_id
    entity_id
    relation_type
    predicate

------------------------------------------------------------
DEFINITION OF DONE (PHASE 2)
------------------------------------------------------------

We can:

1) Input multiple stock research conversations.
2) System merges AAPL/Apple automatically.
3) Search “AI supply chain impact”.
4) See connected companies + events.
5) View entity graph.
6) Click any fact → see explanation trail.
7) System maintains clean predicate vocabulary.

Phase 2 success metric:
The database looks intelligent, not just extracted.

------------------------------------------------------------
PROJECT PHILOSOPHY (PHASE 2)
------------------------------------------------------------

Librarian is evolving from:
"Structured logging"

to:
"Structured cognition."

The system must:
- Improve coherence over time.
- Reduce duplication.
- Maintain semantic integrity.
- Remain transparent.

Every architectural decision must reinforce:

AI should not just answer.
It should accumulate structured, evolving knowledge.

Now begin implementing Phase 2.