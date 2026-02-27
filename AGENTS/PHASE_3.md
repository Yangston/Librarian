# PHASE_3.md — Human-Centered Workspace (Visible Product Layer)

## Phase Objective

Phase 3 turns the Phase 2 Dynamic Knowledge Engine into a **usable, human-friendly product**.

Phase 2 proves the system can learn structure.
Phase 3 proves the user can **see, understand, navigate, and trust** that structure.

The UI should feel like:
- an automated Notion-style workspace that builds itself as conversations evolve
- with transparent provenance and explainability

This phase is primarily **frontend + product UX**, with a few backend additions for UX support.

---

# Core Outcomes

Phase 3 must deliver:

1) A **Workspace Dashboard** where users orient themselves quickly  
2) **Dynamic table views** generated from learned schema (no fixed templates)  
3) **Entity pages** that feel like “records” in a Notion database  
4) **Graph neighborhood view** (lightweight, navigable)  
5) A **Schema Explorer** that makes ontology learning visible (read-only in MVP)  
6) **Explainability UI** everywhere (one click to see “why”)  
7) Fast **search-first navigation** (semantic + structured filters)

---

# UX Principles (Non-negotiable)

## 1) Human-first representations
The core wedge: knowledge is not hidden in vectors.
Users should be able to see:
- what the system knows
- how it’s organized
- how it connects
- where it came from

## 2) “Notion-like” interaction patterns
- tables with sorting/filtering
- linked record navigation
- drilldown detail pages
- “properties” (facts) on a record
- relational edges as linked items

## 3) No hardcoded entity types or views
All views derive from Phase 2’s learned schema:
- types are discovered labels
- attributes are discovered fields
- relations are discovered relation labels

The UI must adapt.

## 4) Explainability is a first-class UI element
Every fact/relation displayed must have:
- an “Explain” affordance
- a clear provenance view showing the source messages + extraction metadata

---

# Frontend Requirements

Preferred stack:
- Next.js (TypeScript)
- A table/grid library (simple, performant)
- A graph library for neighborhood visualization
- A clean component structure; avoid heavy UI frameworks if it slows iteration

Pages (minimum):

- `/` or `/workspace`
- `/conversations`
- `/conversations/[conversation_id]`
- `/entities`
- `/entities/[entity_id]`
- `/schema`
- `/search`
- `/explain/[kind]/[id]` (kind ∈ facts|relations|entities optional)

You may merge some routes if needed, but preserve the conceptual separation.

---

# Required Product Views

## 1) Workspace Dashboard

Purpose:
A user lands here and immediately understands what’s in the system.

Must include:
- Search bar (global)
- Recent conversations list
- “Recently updated entities”
- “Recent schema changes” (optional but high leverage)
- Quick links: Entities, Schema Explorer, Conversations

Data sources:
- conversations list endpoint (may need to add)
- recent entities endpoint (may need to add)
- schema proposals / canonicalizations endpoint (read-only)

---

## 2) Conversations Views

### A) Conversations List (`/conversations`)
- list conversations with:
  - conversation_id
  - timestamps
  - top entities (optional)
  - extraction status (optional)

### B) Conversation Detail (`/conversations/[id]`)
Must include 2 panels/tabs:

1) **Chat Log View**
- show messages
- highlight entity mentions (nice-to-have)

2) **Conversation Summary View**
- key entities
- key facts (top N)
- key relations (top N)
- “Schema learned in this conversation” (fields/relations/types discovered)

Also include:
- “Re-run extraction” button (if safe)
- “Recompute embeddings” button (optional)

---

## 3) Entities Table (`/entities`)

This is your “Notion database” feel.

Must support:
- global entities table with:
  - canonical_name
  - type_label (if present)
  - alias count
  - last_seen
  - conversation count
- sorting
- filtering
- pagination

Crucially:
- enable **dynamic columns** based on learned schema fields:
  - user can pick fields to show as columns
  - system can suggest common fields based on frequency

Example:
If many entities have fields like `market_cap`, `sector`, `sentiment`, these can be added as optional columns.

No hardcoded field list.

---

## 4) Entity Detail Page (`/entities/[entity_id]`)

This page must feel like a Notion “record.”

Minimum sections:

### Header
- canonical name
- aliases (editable later; for MVP read-only is fine)
- type label (free-form)
- quick metadata (first_seen, last_seen, conversation count)

### Properties (Facts)
- table of facts:
  - field_label (canonical + raw display if different)
  - value
  - confidence
  - scope (conversation/global)
  - timestamp
  - explain button

Support:
- filter by field
- show only canonical fields by default

### Relations
Two tables:
- outgoing relations
- incoming relations

Each row:
- relation label
- connected entity (clickable)
- qualifiers
- confidence
- explain button

### Timeline
Show a chronological list of:
- facts added
- relations added
- key messages (optional)

### Graph Neighborhood (lightweight)
Inline graph showing:
- entity at center
- neighbors as nodes
- edges labeled by relation_label

Graph should support:
- click a node to navigate
- hover to preview
- limit to N neighbors with “load more”

---

## 5) Search (`/search`)

Search is the primary navigation mechanism in Librarian.

Must support:
- semantic search input
- show results grouped by:
  - Entities
  - Facts
  - Relations (optional)
- filters:
  - conversation scope
  - type label (if available)
  - time range (optional)

Each result must:
- show snippet or preview
- link to the entity page or explain page

---

## 6) Schema Explorer (`/schema`)

This is your transparency wedge.

Schema is dynamic and learned.
Users must be able to see what is being learned.

Read-only in MVP.

Must show:

### Types (schema_nodes)
- discovered type labels
- descriptions (if available)
- examples
- frequency / last seen

### Fields (schema_fields)
- label
- canonical label (if canonical_of_id exists)
- examples
- frequency
- “cluster” or “similar to” hints (optional)

### Relations (schema_relations)
- label
- canonical label
- examples
- frequency

### Proposals (schema_proposals)
- proposed merges/canonicalizations
- status (proposed/auto-accepted/rejected)
- rationale and evidence (click to expand)
- link to affected schema items

Goal:
The user can *see* schema stabilization happening and trust it.

---

## 7) Explainability UI

Provide a unified explain page:

`/explain/facts/[id]`  
`/explain/relations/[id]`  
(optionally `/explain/entities/[id]`)

Explain page must display:

- The record (fact/relation)
- Canonicalization status:
  - raw label
  - canonical label
  - which proposal caused canonicalization (if any)
- Provenance:
  - source messages (full content)
  - highlight relevant spans if available (optional)
- Extraction metadata:
  - extractor_run_id
  - model_name
  - prompt_version
  - confidence
- Resolution metadata:
  - which entities were merged (if applicable)
  - resolution events chain

This page is key for demos.
It turns “AI magic” into “auditable system.”

---

# Backend Additions for Phase 3 (UX support)

Phase 2 provides most endpoints, but Phase 3 may require:

1) `GET /conversations`
- list conversations, last updated, counts

2) `GET /entities?sort=&filter=&fields=`
- allow selecting fields as columns
- return per-entity field values (canonicalized)

3) `GET /schema/overview`
- combined schema_nodes, schema_fields, schema_relations, proposals summary

4) `GET /recent/entities`
- recent activity feed for dashboard

5) `GET /activity`
- optional unified feed (facts/relations created over time)

These endpoints should remain simple wrappers over existing tables.

---

# MVP UI “Polish” Requirements

Even in MVP, these matter:

- pagination everywhere
- loading states
- error states with actionable messages
- no blank screens
- consistent navigation
- responsive layout (desktop-first is fine)
- fast table rendering (avoid huge DOM lists)

---

# Implementation Order (Phase 3)

Implement Phase 3 in this order:

1) Workspace Dashboard + navigation shell
2) Conversations list + conversation detail (chat log + summary)
3) Entities table (with pagination/filtering)
4) Entity detail page (facts + relations + timeline)
5) Search page (semantic search)
6) Explain pages (facts + relations)
7) Schema explorer (read-only)
8) Graph neighborhood view (entity page)

Do not start with graph visuals.
Start with tables and drilldowns; they deliver value faster.

---

# Phase 3 Completion Criteria

Phase 3 is complete when:

1) A user can browse:
   - conversations
   - entities
   - schema
2) An entity page feels like a Notion record:
   - facts table
   - relations tables
   - timeline
3) Search works and is the default navigation tool.
4) Every fact/relation can be explained with provenance and metadata.
5) Schema Explorer makes dynamic ontology visible and understandable.

At completion, Librarian should feel like:

**A self-building, transparent, relational workspace created from conversation.**