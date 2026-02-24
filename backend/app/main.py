"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.routers import database, extraction, explain, messages


app = FastAPI(title="Librarian API", version="0.1.0")

app.include_router(messages.router, tags=["messages"])
app.include_router(extraction.router, tags=["extraction"])
app.include_router(database.router, tags=["database"])
app.include_router(explain.router, tags=["explain"])


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""

    return {"status": "ok"}

