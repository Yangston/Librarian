# AGENTS.md
# Librarian – Pod-Based Knowledge & Organization Architecture
# Example Implementation: AI Tech Stock Research

---

## OVERVIEW

Librarian is a structured memory layer that operates alongside AI systems.

It separates two fundamental concerns:

1) KNOWLEDGE LAYER  
   Canonical entities + semantic relationships (graph-based).

2) ORGANIZATION LAYER  
   Pods, collections, tables, hierarchy (Notion-like UX).

The graph remains the source of truth.  
Pods and hierarchy organize it for humans.

Core Principle:

    Organization must never replace knowledge.
    The graph remains canonical. Pods organize it.

---

# ARCHITECTURE SUMMARY

There are two layers that coexist:

--------------------------------------------------------
| KNOWLEDGE LAYER (Graph, Canonical, Global)          |
| - entities                                           |
| - knowledge_edges                                    |
| - sources                                            |
| - evidence                                           |
--------------------------------------------------------
| ORGANIZATION LAYER (Workspace, Scoped, Notion-like)|
| - pods                                               |
| - collections                                        |
| - collection_items                                   |
| - workspace containment edges                        |
--------------------------------------------------------

The knowledge layer is global.
The organization layer scopes and structures it.

---

# EXAMPLE POD
# AI Tech Stock Research

--------------------------------------------------------
POD
--------------------------------------------------------

pod:
  id: pod_ai_tech_stocks
  name: "AI Tech Stock Research"
  description: "Research and track AI-related public equities, macro drivers, supply chains, and valuation models"
  created_at: <timestamp>

This pod is logically isolated (recommended), not physically isolated.

---

# ORGANIZATION LAYER

The organization layer creates a Notion-style experience.

--------------------------------------------------------
COLLECTIONS (Workspace Hierarchy)
--------------------------------------------------------

Each collection belongs to a pod.

collection:
  id
  pod_id
  type: PAGE | TABLE | FOLDER
  name
  parent_id
  schema_json (if TABLE)
  view_config_json (optional)

---

## Root Home Page

collection:
  id: col_home
  pod_id: pod_ai_tech_stocks
  type: PAGE
  name: "AI Tech Stock Research – Home"
  parent_id: null

---

## BIG IDEA: STOCKS (Table)

collection:
  id: col_stocks
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Stocks"
  parent_id: col_home
  schema:
    columns:
      - name (title)
      - ticker (text)
      - exchange (select: NASDAQ | NYSE | TSX | Other)
      - sector (select: Semis | Cloud | Software | Hardware | Services | Other)
      - market_cap_usd (number)
      - thesis (rich_text)
      - status (select: Watch | Researching | Owned | Avoid)
      - conviction (select: Low | Medium | High)
      - tags (multi_select)
      - last_updated (datetime)

This table contains Company entities.

---

## BIG IDEA: MACRO (Table)

collection:
  id: col_macro
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Macro"
  parent_id: col_home
  schema:
    columns:
      - event (title)
      - category (select: Rates | Inflation | Liquidity | Trade | FX | Geopolitics)
      - date (date)
      - summary (rich_text)
      - impacted_entities (relation_multi → Entity)
      - status (select: Monitor | Active | Resolved)
      - sources (relation_multi → Source)

This table contains MacroEvent entities.

---

## BIG IDEA: EARNINGS & GUIDANCE

collection:
  id: col_earnings
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Earnings & Guidance"
  parent_id: col_home
  schema:
    columns:
      - company (relation → Company)
      - quarter (select: Q1 | Q2 | Q3 | Q4)
      - fiscal_year (number)
      - report_date (date)
      - beat_miss (select: Beat | Meet | Miss | Mixed)
      - guidance_change (select: Raised | Maintained | Lowered | N/A)
      - key_highlights (rich_text)
      - transcript (relation → Source)

This table contains EarningsReport entities.

---

## BIG IDEA: NEWS

collection:
  id: col_news
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "News"
  parent_id: col_home
  schema:
    columns:
      - headline (title)
      - datetime (datetime)
      - related_entities (relation_multi → Entity)
      - topic (select: Earnings | Product | Regulation | Supply Chain | M&A | Security)
      - sentiment (select: Positive | Neutral | Negative | Mixed)
      - source (relation → Source)
      - summary (rich_text)

This table contains NewsItem entities.

---

## BIG IDEA: SUPPLY CHAIN

collection:
  id: col_supply_chain
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Supply Chain"
  parent_id: col_home
  schema:
    columns:
      - from_entity (relation → Entity)
      - relationship (select: SUPPLIER_OF | CUSTOMER_OF | DEPENDS_ON | PARTNER_OF)
      - to_entity (relation → Entity)
      - criticality (select: Low | Medium | High)
      - notes (rich_text)
      - evidence (relation_multi → Evidence)

This table may represent SupplyChainLink entities OR simply visualize knowledge edges.

---

## BIG IDEA: VALUATION & MODELS

collection:
  id: col_valuation
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Valuation & Models"
  parent_id: col_home
  schema:
    columns:
      - company (relation → Company)
      - method (select: DCF | Comps | SOTP | PEG | Rule-of-40)
      - base_case_fmv (currency USD)
      - bull_case_fmv (currency USD)
      - bear_case_fmv (currency USD)
      - key_assumptions (rich_text)
      - model_link (url)
      - last_reviewed (date)

---

## BIG IDEA: RESEARCH TASKS

collection:
  id: col_tasks
  pod_id: pod_ai_tech_stocks
  type: TABLE
  name: "Research Tasks"
  parent_id: col_home
  schema:
    columns:
      - task (title)
      - due (date)
      - priority (select: Low | Medium | High)
      - related_entities (relation_multi → Entity)
      - status (select: Not started | In progress | Done)

---

# COLLECTION MEMBERSHIP

collection_items:
  collection_id
  entity_id
  sort_key
  added_at

Example:

collection_items:
  - col_stocks → comp_nvda
  - col_stocks → comp_msft
  - col_macro → macro_fomc_mar_2026
  - col_earnings → earn_nvda_fy2026_q4

An entity may exist in multiple collections.

No duplication of entity records.

---

# KNOWLEDGE LAYER (Canonical Graph)

--------------------------------------------------------
ENTITIES
--------------------------------------------------------

Entity schema:

entity:
  id
  type
  props_json
  created_at
  updated_at

Example entities:

comp_nvda:
  type: Company
  props:
    name: "NVIDIA"
    ticker: "NVDA"
    exchange: "NASDAQ"
    sector: "Semis"

comp_tsmc:
  type: Company
  props:
    name: "TSMC"
    ticker: "TSM"
    exchange: "NYSE"

macro_fomc_mar_2026:
  type: MacroEvent
  props:
    name: "FOMC Rate Decision"
    date: 2026-03-18
    category: "Rates"

earn_nvda_fy2026_q4:
  type: EarningsReport
  props:
    fiscal_year: 2026
    quarter: "Q4"
    beat_miss: "Beat"
    guidance_change: "Raised"

news_nvda_guidance:
  type: NewsItem
  props:
    headline: "NVIDIA raises guidance on data center demand"
    sentiment: "Positive"

---

--------------------------------------------------------
KNOWLEDGE EDGES (Semantic)
--------------------------------------------------------

edge:
  id
  src_entity_id
  dst_entity_id
  type
  namespace: "knowledge"
  props_json
  evidence_id
  created_at

Examples:

comp_nvda --DEPENDS_ON--> comp_tsmc
comp_tsmc --SUPPLIER_OF--> comp_nvda

macro_fomc_mar_2026 --IMPACTS--> comp_nvda
macro_fomc_mar_2026 --IMPACTS--> comp_msft

earn_nvda_fy2026_q4 --REPORTED_BY--> comp_nvda
news_nvda_guidance --MENTIONS--> comp_nvda

These edges power:
- Graph view
- Reasoning
- AI retrieval

---

# WORKSPACE CONTAINMENT (Non-Semantic)

Containment is NOT meaning.

edge:
  src
  dst
  type: CONTAINS
  namespace: "workspace"

Example:

pod_ai_tech_stocks --CONTAINS--> col_stocks
col_stocks --CONTAINS--> comp_nvda

Used for navigation only.

---

# GRAPH SCOPING RULES

Graph engine is global.

UI scope modes:

1) Pod Scope
   - Include entities that belong to collections under this pod
   - Show knowledge edges among them
   - Optionally show external nodes faded

2) Collection Scope
   - Include entities inside selected collection
   - Show internal knowledge edges
   - Optional 1-hop expansion

3) Global Scope
   - Show entire graph

---

# REQUIRED TABLES (MINIMUM)

Relational tables:

pods
collections
collection_items
entities
edges
sources
evidence

entities + edges = knowledge layer  
pods + collections + collection_items = organization layer  

---

# MIGRATION STRATEGY

1) Create default pod: "Legacy"
2) Create Big Idea tables (Stocks, Macro, News, Earnings, Supply Chain, Valuation)
3) Assign existing entities into appropriate collections by type
4) Preserve all knowledge edges unchanged
5) Replace single Entities page with Pod → Big Idea → Table navigation

---

# SYSTEM REQUIREMENTS

The system must:

- Feel like a clean Notion workspace
- Preserve existing graph relationships
- Allow entity to exist in multiple collections
- Support evidence-backed claims
- Allow pod-scoped graph visualization
- Avoid duplicating entities across pods
- Keep graph canonical and global

---

# FINAL SUMMARY

Knowledge Layer:
  What things are and how they relate.

Organization Layer:
  How humans group and browse them.

Graph remains canonical.
Pods create clarity.
Collections create hierarchy.
Edges preserve meaning.

End of AGENTS.md