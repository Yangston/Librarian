# Librarian (Phase 1 MVP)

Librarian is a structured cognitive layer for AI systems. Phase 1 proves one core flow:

`Conversation -> Structured Entities/Facts/Relations -> Transparent Database`

This repository contains:

- `backend/`: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- `frontend/`: Minimal Next.js scaffold for `/conversation`, `/database`, `/explain`
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

- insert a deterministic 5-message stock conversation
- run extraction
- print record counts and suggested inspection endpoints

### 3) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at `http://127.0.0.1:3000`.

## API Endpoints (Phase 1)

- `POST /conversations/{conversation_id}/messages`
- `GET /conversations/{conversation_id}/messages`
- `POST /conversations/{conversation_id}/extract`
- `GET /conversations/{conversation_id}/entities`
- `GET /conversations/{conversation_id}/facts`
- `GET /conversations/{conversation_id}/relations`

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

3. Query entities, facts, relations:

```powershell
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/entities"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/facts"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/relations"
```

4. Explain a fact/relation (replace IDs with real values from the previous responses):

```powershell
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/facts/1/explain"
Invoke-RestMethod -Method Get -Uri "$base/conversations/$conversationId/relations/1/explain"
```

## Notes

- Extraction is deterministic and rule-based for the MVP.
- The extractor is modular and can be replaced later with an LLM-backed implementation.
- Facts and relations include `source_message_ids_json` for traceability.
