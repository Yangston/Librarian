"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import database, explain, extraction, knowledge, live_chat, messages, schema, search


app = FastAPI(title="Librarian API", version="0.1.0")

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
app.include_router(knowledge.router, tags=["knowledge"])


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""

    return {"status": "ok"}
