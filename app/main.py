"""FastAPI application entrypoint for CHM."""

from fastapi import FastAPI

from app.core.errors import register_error_handlers

app = FastAPI(title="CHM")
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check stub endpoint for service readiness."""
    return {"status": "ok"}
