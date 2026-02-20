"""FastAPI application entrypoint for CHM."""

from fastapi import FastAPI

app = FastAPI(title="CHM")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check stub endpoint for service readiness."""
    return {"status": "ok"}
