"""FastAPI application entrypoint for CHM."""

from fastapi import FastAPI

from app.api.clients import router as clients_router
from app.core.errors import register_error_handlers
from app.db import models as _models  # noqa: F401

app = FastAPI(title="CHM")
register_error_handlers(app)
app.include_router(clients_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check stub endpoint for service readiness."""
    return {"status": "ok"}
