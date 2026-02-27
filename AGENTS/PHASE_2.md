# PHASE_2.md — Dynamic Knowledge Engine

## Phase Objective

Phase 2 builds the intelligent backend for Librarian.

The goal is to transform Phase 1’s basic extraction system into a:

- Dynamic schema engine
- Persistent cross-conversation knowledge graph
- Self-stabilizing ontology system
- Fully explainable structured memory layer

This phase focuses on backend infrastructure only.
UI work is handled in Phase 3.

---

# Core Goals

Phase 2 must implement:

1. LLM-based structured extraction
2. Extraction run logging
3. Dynamic schema formation (schema-on-write + schema-on-read)
4. Ontology learning (no hardcoded lists)
5. Soft schema stabilization (data-driven canonicalization)
6. Entity resolution with reversible merges
7. Global persistence across conversations
8. Embeddings + semantic search
9. Knowledge query endpoints
10. Full explainability trail

---

# Architectural Overview

The Phase 2 backend is composed of the following layers:

1. Extraction Layer
2. Entity Resolution Layer
3. Schema Learning Layer
4. Schema Stabilization Layer
5. Persistence Layer
6. Search Layer
7. Knowledge Query Layer

Each layer must be modular and independently testable.

---

# 1. Extraction Layer (LLM Structured Extraction)

## Requirements

Replace simple or rule-based extraction with:

- LLM structured output
- Strict JSON schema validation
- Deterministic structure (low temperature)
- Versioned prompt files

## Extraction Output Format

Extractor must return:

{
  entities: [
    {
      name: string,
      aliases: string[],
      type_label: string | null,
      confidence: float
    }
  ],
  facts: [
    {
      entity_name: string,
      field_label: string,
      value_text: string,
      confidence: float,
      source_message_ids: []
    }
  ],
  relations: [
    {
      from_entity: string,
      relation_label: string,
      to_entity: string,
      qualifiers: {},
      confidence: float,
      source_message_ids: []
    }
  ]
}

No hardcoded type list.
Type labels are free-form strings.

## Extraction Logging

Create table: extractor_runs

- id
- conversation_id
- model_name
- prompt_version
- input_message_ids_json
- raw_output_json
- validated_output_json
- created_at

Every extraction run must be stored.

---

# 2. Entity Resolution Layer

## Purpose

Prevent duplicate entities across and within conversations.

Examples:
- "Apple"
- "Apple Inc."
- "AAPL"

## Resolution Strategy

1. Exact canonical_name match
2. Alias match
3. Embedding similarity (pgvector)
4. Optional LLM disambiguation if similarity borderline

## Entity Table (Updated)

entities:

- id
- canonical_name
- display_name
- aliases_json
- type_label (string)
- embedding (vector)
- merged_into_id (nullable)
- created_at
- updated_at

Never delete entities.
Use merged_into_id to represent merges.

## Resolution Logging

Create table: resolution_events

- id
- event_type (match | merge | alias_add)
- entity_ids_json
- similarity_score
- rationale
- source_message_ids_json
- created_at

All resolution actions must be logged.

---

# 3. Dynamic Schema Formation (Schema-as-Data)

No fixed enums.

## Schema Registry Tables

### schema_nodes
Represents learned types.

- id
- label
- description
- examples_json
- embedding
- stats_json
- created_at

### schema_fields
Represents learned attributes.

- id
- label
- canonical_of_id (nullable)
- description
- examples_json
- embedding
- stats_json
- created_at

### schema_relations
Represents learned relation labels.

- id
- label
- canonical_of_id (nullable)
- description
- examples_json
- embedding
- stats_json
- created_at

### schema_proposals
Tracks canonicalization or merge suggestions.

- id
- proposal_type
- payload_json
- confidence
- evidence_json
- status (proposed | auto_accepted | rejected)
- created_at

## Schema-On-Write

When new facts or relations are created:

If field_label does not exist:
→ Create schema_fields entry.

If relation_label does not exist:
→ Create schema_relations entry.

If type_label does not exist:
→ Create schema_nodes entry.

Everything is data-driven.

---

# 4. Schema Stabilization (Soft Governance)

Purpose:
Prevent schema explosion without hardcoding lists.

## Stabilization Job

Runs after extraction.

Steps:

1. Compute embedding similarity across:
   - schema_fields
   - schema_relations
   - schema_nodes

2. Identify high similarity clusters.

3. Create schema_proposals:
   - merge_fields
   - canonicalize_labels
   - merge_relations
   - merge_nodes

4. Auto-accept proposals if confidence very high.

No destructive changes.
Canonicalization uses canonical_of_id.

---

# 5. Persistence Model

## Conversational Persistence

Knowledge connects across messages in same conversation.

Facts and relations store source_message_ids.

## Global Persistence

Entities are global.

Create conversation_entity_links:

- conversation_id
- entity_id
- first_seen_message_id
- last_seen_message_id
- created_at

Facts and relations may have scope:

- conversation
- global

---

# 6. Embeddings + Search Layer

Use pgvector.

Embed:

- entities (name + aliases + optional summary)
- facts ("entity field value")

## Search Endpoint

GET /search?q=...

Return:

- entities
- facts
- similarity score

Support:

- scoped search (conversation_id)
- global search

---

# 7. Knowledge Query Endpoints

## GET /entities/{id}

Return canonical entity record.

## GET /entities/{id}/graph

Return:

- outgoing relations
- incoming relations
- related entities
- supporting facts

## GET /entities/{id}/timeline

Return facts ordered by message timestamp.

## GET /conversations/{conversation_id}/summary

Return:

- key entities
- key facts
- schema changes triggered
- relation clusters

---

# 8. Explainability Endpoints

## GET /facts/{id}/explain

Return:

- fact record
- source messages
- extractor_run_id
- resolution events
- schema canonicalization info

## GET /relations/{id}/explain

Same pattern.

Nothing is opaque.

---

# Implementation Order

Agents must implement Phase 2 in this order:

1. extractor_runs table + logging
2. LLM structured extraction with validation
3. Entity resolution + resolution logging
4. Schema registry tables
5. Schema-on-write logic
6. Schema stabilization job
7. Embeddings integration
8. Search endpoint
9. Knowledge query endpoints
10. Explain endpoints

Do NOT attempt everything at once.

---

# Performance Constraints

- Use DB indexes on:
  - canonical_name
  - conversation_id
  - entity_id
  - relation_label
  - field_label

- Use background jobs for:
  - stabilization
  - embedding generation

---

# Phase 2 Completion Criteria

Phase 2 is complete when:

1. Multiple conversations can be ingested.
2. Entities are merged automatically.
3. Schema registry grows dynamically.
4. Similar labels are clustered and canonicalized.
5. Semantic search works.
6. Graph endpoint returns meaningful structure.
7. Every fact/relation has a full explain trail.

At completion, Librarian has:

- Dynamic ontology
- Cross-conversation memory
- Semantic search
- Explainable structured cognition

UI is not the priority in this phase.