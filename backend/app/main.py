"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.session import SessionLocal
from app.routers import (
    database,
    explain,
    extraction,
    knowledge,
    live_chat,
    messages,
    mutations,
    schema,
    search,
    workspace,
)
from app.services.workspace import (
    get_schema_overview,
    list_conversations,
    list_entities_catalog,
    list_recent_entities,
)

logger = logging.getLogger(__name__)


def _warm_backend_state() -> None:
    """Prime DB connection and commonly-hit workspace queries at process start."""

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            list_conversations(db, limit=1, offset=0)
            list_recent_entities(db, limit=1)
            list_entities_catalog(
                db,
                limit=1,
                offset=0,
                sort="last_seen",
                order="desc",
                selected_fields=[],
            )
            get_schema_overview(db, per_section_limit=1, proposal_limit=1)
    except Exception:
        logger.exception("Backend warm-up failed; continuing without startup pre-warm.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _warm_backend_state()
    yield


app = FastAPI(title="Librarian API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router, tags=["messages"])
app.include_router(live_chat.router, tags=["live-chat"])
app.include_router(extraction.router, tags=["extraction"])
app.include_router(database.router, tags=["database"])
app.include_router(schema.router, tags=["schema"])
app.include_router(explain.router, tags=["explain"])
app.include_router(explain.global_router, tags=["explain"])
app.include_router(search.router, tags=["search"])
app.include_router(workspace.router, tags=["workspace"])
app.include_router(knowledge.router, tags=["knowledge"])
app.include_router(mutations.router, tags=["mutations"])


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""

    return {"status": "ok"}
