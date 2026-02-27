You are acting as a senior full-stack engineer and systems architect.

Project Name: Librarian

High-Level Vision:
Librarian is a structured cognitive layer for AI systems. 
Instead of chat conversations remaining unstructured logs, Librarian converts live conversations into a transparent, queryable, relational knowledge system.

The goal of Phase 1 (MVP) is NOT to build a full knowledge graph platform.
The goal is to prove one core capability:

    Conversations → Structured Entities + Facts + Relations → Transparent Database

This MVP must prioritize:
- Clarity
- Simplicity
- Clean architecture
- Deterministic data structure
- Explainability (trace each extracted record back to source messages)

Do NOT build advanced AI orchestration.
Do NOT build general ontology engines.
Do NOT build unnecessary UI complexity.
Do NOT over-engineer.

------------------------------------
PHASE 1 MVP REQUIREMENTS
------------------------------------

Core Functionality:

1) Message Ingestion
- Accept a conversation (array of messages).
- Store messages in database.
- Each message has:
    id
    conversation_id
    role (user / assistant)
    content
    timestamp

2) Extraction Pipeline (initially rule-based or stub)
- Convert messages into:
    - Entities
    - Facts
    - Relations
- Every extracted record must store:
    source_message_ids (array of message IDs)
- Extraction must be modular so we can swap in an LLM later.

3) Transparent Database View
- Ability to query:
    - Entities by conversation
    - Facts by conversation
    - Relations by conversation
- Ability to click a fact/relation and see:
    - The source message(s)
    - The exact text snippet (if available)

------------------------------------
DATABASE SCHEMA (PHASE 1)
------------------------------------

Messages:
- id (UUID or serial)
- conversation_id (string)
- role (string)
- content (text)
- timestamp (ISO 8601)

Entities:
- id (UUID or serial)
- conversation_id
- name (string)
- type (string: Company / Person / Event / Concept / Metric / Other)
- aliases_json (JSON array)
- tags_json (JSON array)
- created_at

Facts:
- id
- conversation_id
- subject_entity_id
- predicate (string)
- object_value (string)
- confidence (float, default 1.0)
- source_message_ids_json (JSON array)
- created_at

Relations:
- id
- conversation_id
- from_entity_id
- relation_type (string)
- to_entity_id
- qualifiers_json (JSON object)
- source_message_ids_json (JSON array)
- created_at

------------------------------------
TECH STACK
------------------------------------

Backend:
- Python 3.11+
- FastAPI
- SQLAlchemy ORM
- Alembic migrations
- PostgreSQL
- Pydantic models for validation

Frontend:
- Next.js (TypeScript)
- Basic pages only:
    /conversation
    /database
    /explain

Dev Environment:
- Docker Compose for Postgres
- Backend + frontend run locally
- Clear README setup instructions

------------------------------------
ARCHITECTURE REQUIREMENTS
------------------------------------

- Use clean folder structure:
    backend/
        app/
            models/
            schemas/
            routers/
            services/
            extraction/
            db/
    frontend/

- Extraction must be separated into:
    extraction/
        extractor_interface.py
        rule_based_extractor.py

- Create an Extractor interface so we can later replace it with an LLM-based extractor.

- All API endpoints must:
    - Validate inputs
    - Return consistent JSON responses
    - Use proper status codes

------------------------------------
PHASE 1 ENDPOINTS
------------------------------------

POST   /conversations/{conversation_id}/messages
GET    /conversations/{conversation_id}/messages

POST   /conversations/{conversation_id}/extract

GET    /conversations/{conversation_id}/entities
GET    /conversations/{conversation_id}/facts
GET    /conversations/{conversation_id}/relations

------------------------------------
EXTRACTION BEHAVIOR (MVP SIMPLIFIED)
------------------------------------

For Phase 1, implement simple deterministic extraction:
- Detect stock tickers via regex (e.g. AAPL, TSLA)
- Detect percentage changes
- Detect simple patterns like:
    "[Company] reported [metric]"
    "[Event] impacted [Company]"

This is just to prove architecture.
Design the system so LLM-based extraction can be dropped in later.

------------------------------------
IMPORTANT CONSTRAINTS
------------------------------------

- No microservices.
- No GraphQL.
- No unnecessary abstractions.
- No premature optimization.
- Keep code readable and production-quality.
- Add docstrings and type hints.

------------------------------------
DEFINITION OF DONE
------------------------------------

When complete, we must be able to:

1) Paste a conversation about 3–5 stocks.
2) Store the messages.
3) Run extraction.
4) See:
    - Entities populated
    - Facts populated
    - Relations populated
5) Click any fact/relation and see which messages produced it.

------------------------------------
OUTPUT REQUIREMENTS
------------------------------------

When generating code:
- Specify which files are created or modified.
- Provide full file contents.
- Ensure imports are correct.
- Ensure migrations are included.
- Ensure docker-compose runs without errors.
- Ensure backend starts with:
    uvicorn app.main:app --reload

------------------------------------
PROJECT PHILOSOPHY
------------------------------------

Librarian is about:
- Structured accumulation of AI knowledge
- Transparent state
- Inspectable memory

Everything built in Phase 1 must reinforce:
    "AI should not just answer. It should accumulate structured knowledge."

Now begin implementing Phase 1 of Librarian MVP.