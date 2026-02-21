"""Application configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

DEFAULT_PARTNER_API_BASE_URL = "https://partner.example.com"
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0
DEFAULT_HTTP_MAX_RETRIES = 3
DEFAULT_HTTP_BACKOFF_SECONDS = 1.0


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def redact_secret(secret: str) -> str:
    """Return a non-recoverable placeholder for sensitive values."""
    if not secret:
        return "<empty>"
    return "<redacted>"


@dataclass(frozen=True)
class IngestionSettings:
    """Runtime settings for partner ingestion calls."""

    partner_api_base_url: str
    partner_api_token: str
    http_timeout_seconds: float
    http_max_retries: int
    http_backoff_seconds: float

    def safe_for_logging(self) -> dict[str, str | int | float]:
        """Return ingestion settings safe for logs."""
        return {
            "partner_api_base_url": self.partner_api_base_url,
            "partner_api_token": redact_secret(self.partner_api_token),
            "http_timeout_seconds": self.http_timeout_seconds,
            "http_max_retries": self.http_max_retries,
            "http_backoff_seconds": self.http_backoff_seconds,
        }


@lru_cache(maxsize=1)
def get_ingestion_settings() -> IngestionSettings:
    """Load ingestion settings from the environment."""
    return IngestionSettings(
        partner_api_base_url=os.getenv("CHM_PARTNER_API_BASE_URL", DEFAULT_PARTNER_API_BASE_URL),
        partner_api_token=os.getenv("CHM_PARTNER_API_TOKEN", ""),
        http_timeout_seconds=_get_float_env("CHM_HTTP_TIMEOUT_SECONDS", DEFAULT_HTTP_TIMEOUT_SECONDS),
        http_max_retries=_get_int_env("CHM_HTTP_MAX_RETRIES", DEFAULT_HTTP_MAX_RETRIES),
        http_backoff_seconds=_get_float_env("CHM_HTTP_BACKOFF_SECONDS", DEFAULT_HTTP_BACKOFF_SECONDS),
    )

