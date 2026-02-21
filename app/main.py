"""FastAPI application entrypoint for CHM."""

from fastapi import FastAPI

from app.api.alert_rules import router as alert_rules_router
from app.api.clients import router as clients_router
from app.api.ingestion import router as ingestion_router
from app.api.pipelines import router as pipelines_router
from app.api.runs import router as runs_router
from app.core.errors import register_error_handlers
from app.db import models as _models  # noqa: F401

app = FastAPI(title="CHM")
register_error_handlers(app)
app.include_router(alert_rules_router)
app.include_router(clients_router)
app.include_router(pipelines_router)
app.include_router(runs_router)
app.include_router(ingestion_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check stub endpoint for service readiness."""
    return {"status": "ok"}
