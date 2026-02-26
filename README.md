# Librarian (Phase 2 In Progress)

Librarian is a structured cognitive layer for AI systems. Phase 2 builds on the Phase 1 core flow:

`Conversation -> Structured Entities/Facts/Relations -> Transparent Database`

Testing is now supported in two browser-first modes:

- `JSON Batch Test`: paste a message payload and run extraction manually
- `Live GPT Chat Test`: send live prompts, persist both sides, and auto-run extraction per turn

This repository contains:

- `backend/`: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- `frontend/`: Next.js test harness for `/conversation`, `/database`, `/explain`
- `docker-compose.yml`: Local PostgreSQL

## Quick Start

### 1) Start PostgreSQL

```bash
docker compose up -d
```

### 2) Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit backend/.env and set OPENAI_API_KEY (LLM extraction is required, model defaults to gpt-5.2)
alembic upgrade head
uvicorn app.main:app --reload
```

Backend will run at `http://127.0.0.1:8000`.

### 2b) Seed a demo 3-5 stock conversation (optional)

From the repository root:

```bash
python backend/scripts/seed_demo.py
```

Or from `backend/`:

```bash
python scripts/seed_demo.py
# or
python -m scripts.seed_demo
```

This will:

- insert a deterministic 5-message stock conversation (including alias variants like `AAPL` / `Apple Inc.` / `Apple`)
- run LLM extraction + Phase 2 entity resolution
- print record counts and suggested inspection endpoints

### 3) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at `http://127.0.0.1:3000`.

## API Endpoints (Phase 2 current slice)

- `POST /conversations/{conversation_id}/messages`
- `GET /conversations/{conversation_id}/messages`
- `POST /conversations/{conversation_id}/chat/turn`
- `POST /conversations/{conversation_id}/extract`
- `GET /conversations/{conversation_id}/entities`
- `GET /conversations/{conversation_id}/entity-merges`
- `GET /conversations/{conversation_id}/facts`
- `GET /conversations/{conversation_id}/relations`
- `GET /schema/predicates`

Additional explainability endpoints:

- `GET /conversations/{conversation_id}/facts/{fact_id}/explain`
- `GET /conversations/{conversation_id}/relations/{relation_id}/explain`

## Example API Requests (3-5 Stock Demo)

Request collection file:

- `examples/stock-demo-requests.http`

### PowerShell examples

Set a conversation ID and base URL:

```powershell
$base = "http://127.0.0.1:8000"
$conversationId = "stocks-demo-001"
```

1. Ingest demo conversation:

```powershell
$body = @{
  messages = @(
    @{
      role = "user"
      content = "AAPL reported iPhone revenue strength and the stock rose 3.2% after the call."
      timestamp = "2026-02-24T14:00:00Z"
    },
    @{
      role = "assistant"
      content = "TSLA reported vehicle deliveries and shares moved -1.4% in late trading."
      timestamp = "2026-02-24T14:01:00Z"
    },
    @{
      role = "user"
      content = "Fed rate decision impacted NVDA as traders reassessed AI valuations."
      timestamp = "2026-02-24T14:02:00Z"
    },
    @{
      role = "assistant"
      content = "Supply chain disruption impacted AAPL and management flagged margin pressure."
      timestamp = "2026-02-24T14:03:00Z"
    },
    @{
      role = "user"
      content = "MSFT reported cloud revenue acceleration while AMZN gained 2.1%."
      timestamp = "2026-02-24T14:04:00Z"
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "$base/conversations/$conversationId/messages" `
  -ContentType "application/json" `
  -Body $body
```

2. Run extraction:

```powershell
Invoke-RestMethod -Method Post -Uri "$base/conversations/$conversationId/extract"
```

2b. Live chat turn (persists user + assistant messages, and optionally runs extraction):

```powershell
$liveBody = @{
  content = "Compare AAPL and NVDA exposure to AI supply chain disruption."
  auto_extract = $true
  system_prompt = "You are a concise stock research assistant."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$base/conversations/$conversationId/chat/turn" `
  -ContentType "application/json" `
  -Body $liveBody
```

3. Query entities, merge audits, facts, relations:

```powershell
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/entities"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/entity-merges"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/facts"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/relations"
Invoke-RestMethod -Method Get -Uri "$base/schema/predicates"
```

4. Explain a fact/relation (replace IDs with real values from the previous responses):

```powershell
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/facts/1/explain"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/relations/1/explain"
```

## Testing (Phase 2)

### Automated backend tests

From `backend/`:

```bash
.venv\Scripts\python.exe -m unittest tests.test_entity_resolver -v
.venv\Scripts\python.exe -m unittest tests.test_phase2_resolution_integration -v
```

These cover:

- deterministic entity resolution (`AAPL` / `Apple` / `Apple Inc.` style merges)
- merge audit persistence
- canonical fact/relation linking after deduplication
- rerun behavior replacing prior merge audits for a conversation
- predicate registry normalization/frequency tracking and schema service listing

### Manual website smoke test (Phase 2 entity resolution)

1. Start backend and frontend.
2. Open `http://127.0.0.1:3000/conversation` for the unified test console.
3. Test Mode A (`JSON Batch Test`): click `Run Demo Flow`.
4. Confirm the structured tables populate and merge audits appear.
5. Test Mode B (`Live Chat Test`): switch to `Live Chat Test` or open `http://127.0.0.1:3000/live`.
6. Send a prompt with `Auto-run extraction` enabled.
7. Confirm new messages appear and the database panels refresh automatically.
8. In `/database`, confirm `Entities` shows `canonical_name`, `merged_into_id`, and resolution metadata.
9. Confirm `Entity Merge Audits` shows merge reason + confidence.
10. Confirm `Predicate Registry` table shows canonical predicates/relation types with frequency counts.

### Manual API smoke test (Phase 2 entity resolution)

After running extraction for a conversation:

```powershell
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/entities"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/entity-merges"
Invoke-RestMethod -Method Get -Uri "$base/schema/predicates"
```

Verify:

- merged duplicates are preserved with `merged_into_id`
- canonical rows have `merged_into_id = null`
- merge audit rows include `reason_for_merge`, `confidence`, `resolver_version`
- schema predicate registry accumulates normalized `fact_predicate` and `relation_type` entries
- `POST /chat/turn` returns `user_message`, `assistant_message`, and optional `extraction`

## Notes

- Extraction is AI-powered and normalized into the same deterministic database schema.
- `OPENAI_API_KEY` must be set in `backend/.env` before running extraction.
- Facts and relations include `source_message_ids_json` for traceability.
- Phase 2 entity resolution stores merge transparency in `/entity-merges` and preserves duplicate rows via `merged_into_id`.
