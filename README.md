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

## Notes

- Extraction is deterministic and rule-based for the MVP.
- The extractor is modular and can be replaced later with an LLM-backed implementation.
- Facts and relations include `source_message_ids_json` for traceability.

