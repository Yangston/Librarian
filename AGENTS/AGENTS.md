# Librarian — AGENTS.md

## Project Overview

Librarian is a structured cognitive layer for AI systems — built for the human user.

Modern AI assistants generate answers, but they do not accumulate structured, inspectable knowledge over time. Conversations become long logs of text with no explicit schema, no relational structure, and no transparency into how information is organized or reused.

Librarian transforms AI conversations into dynamic, evolving knowledge systems.

Instead of chat history remaining unstructured text, Librarian continuously extracts entities, attributes, relationships, and claims — connects them across messages and conversations — and stores them in a transparent, queryable system.

Librarian is not a chatbot.

It is infrastructure that sits alongside AI systems and converts conversation into structured, visible cognition.

---

# Core Philosophy

## 1. Structured Accumulation

AI should not just answer questions.
It should accumulate structured knowledge that can be queried, refined, and reused.

Conversation becomes structured state.

---

## 2. Human-Centered Transparency

Most AI memory systems optimize for the model:
- Hidden vector stores
- Invisible context injection
- Black-box persistence

Librarian optimizes for the human.

All stored knowledge must be:
- Visible
- Queryable
- Navigable
- Explainable

The system must surface:
- Structured tables
- Linked records
- Graph views
- Timelines
- Schema evolution
- Provenance trails

Nothing is hidden.

---

## 3. Dynamic Ontology (No Hardcoded Schema)

Librarian does NOT use:

- Hardcoded entity type enums
- Fixed predicate lists
- Rigid schema governance layers

Instead:

- Entity types emerge from usage.
- Attributes emerge from conversation.
- Relation labels emerge organically.
- The schema stabilizes over time using semantic similarity and statistical signals.

The schema is stored as data, not code.

---

## 4. Conversational + Global Persistence

Knowledge must persist:

- Within a conversation (connect ideas across messages)
- Across conversations (build global memory)

Entities are global.
Conversations link to entities.
Facts and relations may be scoped.

---

## 5. Explainability by Default

Every fact and relation must be traceable to:

- Source messages
- Extraction run
- Resolution decisions
- Schema stabilization steps

All automated decisions must be logged and reversible.

Transparency is non-negotiable.

---

# Architecture Principles

## Backend
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic migrations
- pgvector for embeddings

## Design Constraints
- No microservices
- No graph database (use Postgres relational model)
- No destructive merges
- No fixed schema enums
- No hidden memory injection

## Schema-as-Data
Ontology is stored in database tables:
- schema_nodes (learned types)
- schema_fields (learned attributes)
- schema_relations (learned relation labels)
- schema_proposals (canonicalization/merge suggestions)

---

# System Layers

1. Extraction Layer  
   Converts messages into structured entities, facts, and relations using LLMs.

2. Entity Resolution Layer  
   Deduplicates entities and manages aliases.

3. Schema Learning Layer  
   Learns types, attributes, and relations dynamically.

4. Schema Stabilization Layer  
   Identifies similar labels and proposes canonicalization without hardcoding.

5. Persistence Layer  
   Stores conversational and global knowledge.

6. Search + Embeddings Layer  
   Enables semantic search over structured data.

7. Knowledge Query Layer  
   Graph endpoints, timelines, conversation summaries.

8. Human-Facing Workspace Layer  
   Tables, entity pages, schema explorer, explain pages.

---

# MVP Roadmap

The MVP consists of four phases only. Phase one has been completed

Advanced reasoning, human-in-the-loop governance, and deep ontology refinement are explicitly NOT part of the MVP.

---
## Phase 1 — Structured Extraction Prototype (Completed)

Goal:
Prove that conversations can be transformed into structured data.

Phase 1 established the foundational pipeline:

- Message ingestion
- Basic LLM-based structured extraction
- Entities / facts / relations storage
- Simple relational database structure
- Basic testing UI
- Initial explainability endpoints

Characteristics of Phase 1:

- Extraction focused on correctness, not sophistication.
- Schema was simple and partially static.
- Entity resolution was limited.
- Cross-conversation persistence was minimal.
- UI was primarily for testing and inspection.

Phase 1 validated the core thesis:

Conversation → Structured Entities → Stored in Database.

However, Phase 1 did NOT include:

- Dynamic ontology learning
- Schema stabilization
- Cross-conversation entity merging
- Semantic search
- Human-centered structured workspace
- Production hardening

Phase 1 should not be expanded further.
It exists as a stable baseline that Phase 2 builds upon.

Outcome:
The system can reliably convert chat logs into structured database records.

## Phase 2 — Dynamic Knowledge Engine
File: PHASE_2.md

Goal:
Build an intelligent, persistent backend that learns schema dynamically and connects knowledge across conversations.

Includes:

- LLM structured extraction
- Extractor run logging
- Dynamic schema formation (schema-on-write)
- Ontology learning
- Soft schema stabilization (no hardcoded lists)
- Entity resolution with reversible merges
- Global entity persistence
- Embeddings + semantic search
- Knowledge query endpoints
- Explain endpoints with full provenance

Outcome:
A self-evolving, persistent structured backend.

---

## Phase 3 — Human-Centered Workspace
File: PHASE_3.md

Goal:
Turn structured storage into a visible, intuitive, user-friendly system.

Includes:

- Workspace dashboard
- Entity detail pages
- Facts + relations tables
- Timeline views
- Graph visualization
- Dynamic table views
- Schema explorer (read-only)
- Conversation summary view
- Explain buttons on all records

Outcome:
The system feels like an automated Notion-style database built from conversation.

This is the core product differentiation.

---

## Phase 4 — MVP Completion & Hardening
File: PHASE_4.md

Goal:
Make the product stable and demo-ready.

Includes:

- Background jobs for extraction and stabilization
- Async processing
- Index optimization
- Pagination
- Performance improvements
- Real-time ingestion support (if feasible)
- Export (JSON / CSV)
- Logging hardening
- Error handling polish

Outcome:
A complete, usable MVP ready for early users and demos.

---

# Development Order

Agents must implement work incrementally:

1. Fully complete Phase 2 backend infrastructure.
2. Move to Phase 3 workspace UI.
3. Finalize Phase 4 hardening.

Do NOT:

- Skip phases.
- Add advanced reasoning systems.
- Introduce hardcoded type lists.
- Implement heavy UI before backend stability.

---

# Data Integrity Rules

- Never delete entities during merge.
- Use merged_into_id to represent merges.
- Log every resolution event.
- Log every schema proposal.
- Store extractor version on every run.
- Never allow orphaned foreign keys.

All automated decisions must be auditable.

---

# Testing Guidelines

Existing unit tests with mocks and fixtures are valid and should be maintained.

However, for features involving LLM-based extraction or schema learning, agents should also test behavior using real OpenAI API calls when necessary.

End-to-end extraction logic must be validated against live model responses to ensure:
- Correct structured JSON output
- Proper validation and retry handling
- Deterministic behavior at low temperature

Use mocks for isolated unit tests, but use real API calls to verify full extraction pipelines when appropriate.

---

## AGENTS_LOG Logging Rules

- Keep `AGENTS_LOG/` as the working progress mirror for planning + execution notes.
- After every meaningful code change, update `AGENTS_LOG/PHASE_XXX_PROGRESS_LOG.md` in the same turn. If the file doesnt exist, make it.
- Log entries must include: step number, short summary, files changed, migration/test status, and next step.
- Use checkbox status for Phase XXX steps (`[x]` complete, `[ ]` pending) and keep it current.
- Append updates; do not remove prior history unless correcting a factual error.
- If work is paused or blocked, add a short blocker note and explicitly mark current state.

---

# Definition of MVP Success

A user can:

1. Connect a chatbot.
2. Have multiple conversations.
3. See:
   - Entities table auto-built
   - Linked relations
   - Schema explorer
   - Graph view
   - Semantic search results
4. Click any fact and see:
   - Source messages
   - Extraction run metadata
   - Resolution decisions
   - Canonicalization history

The system must feel:

- Structured
- Persistent
- Transparent
- Human-understandable

Librarian converts AI conversations into visible, evolving structured cognition.