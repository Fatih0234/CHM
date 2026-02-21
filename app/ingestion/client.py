"""HTTP client for partner run ingestion with bounded resilience controls."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import random
import time

import requests

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class PartnerIngestionClientError(RuntimeError):
    """Base error raised by partner ingestion client operations."""


class PartnerIngestionRequestError(PartnerIngestionClientError):
    """Raised when partner requests fail after retry budget is exhausted."""


class PartnerIngestionResponseError(PartnerIngestionClientError):
    """Raised when partner responses are malformed."""


class PartnerIngestionClient:
    """Fetch paginated run pages from a partner API with retry/backoff behavior."""

    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        jitter_fn: Callable[[], float] = random.random,
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized:
            raise ValueError("base_url is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if backoff_seconds <= 0:
            raise ValueError("backoff_seconds must be positive")

        self._base_url = normalized
        self._api_token = api_token
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._session = session or requests.Session()
        self._sleep_fn = sleep_fn
        self._jitter_fn = jitter_fn

    def fetch_runs(
        self,
        pipeline_external_id: str,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of run events for a pipeline external identifier."""
        return self._request_page(pipeline_external_id=pipeline_external_id, cursor=cursor)

    def list_runs(
        self,
        pipeline_external_id: str,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Alias for compatibility with ingestion orchestration call sites."""
        return self.fetch_runs(pipeline_external_id=pipeline_external_id, cursor=cursor)

    def fetch_pipeline_runs(
        self,
        pipeline_external_id: str,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Alias for compatibility with ingestion orchestration call sites."""
        return self.fetch_runs(pipeline_external_id=pipeline_external_id, cursor=cursor)

    def _request_page(
        self,
        *,
        pipeline_external_id: str,
        cursor: str | None,
    ) -> dict[str, Any]:
        if not pipeline_external_id:
            raise ValueError("pipeline_external_id is required")

        endpoint = quote(pipeline_external_id, safe="")
        url = f"{self._base_url}/pipelines/{endpoint}/runs"
        params = {"cursor": cursor} if cursor else None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self._timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= self._max_retries:
                    raise PartnerIngestionRequestError(
                        "Partner request failed after retry budget was exhausted",
                    ) from exc
                self._sleep_fn(self._retry_delay(attempt))
                continue
            except requests.RequestException as exc:
                raise PartnerIngestionRequestError("Partner request failed") from exc

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt >= self._max_retries:
                    raise PartnerIngestionRequestError(
                        f"Partner request failed with retryable status {response.status_code}",
                    )
                self._sleep_fn(self._retry_delay(attempt, response.headers))
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise PartnerIngestionRequestError(
                    f"Partner request failed with status {response.status_code}",
                ) from exc

            return self._normalize_page(response.json())

        raise PartnerIngestionRequestError("Partner request failed")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
            "User-Agent": "chm-ingestion/0.1",
        }

    def _retry_delay(
        self,
        attempt: int,
        headers: Mapping[str, Any] | None = None,
    ) -> float:
        base = self._backoff_seconds * (2**attempt)
        jitter = self._jitter_fn() * self._backoff_seconds
        delay = base + jitter

        if headers:
            retry_after = headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass
        return delay

    @staticmethod
    def _normalize_page(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise PartnerIngestionResponseError("Partner payload must be a JSON object")

        runs = raw.get("runs", [])
        if runs is None:
            runs = []
        if not isinstance(runs, list):
            raise PartnerIngestionResponseError("Partner payload field `runs` must be a list")

        next_cursor = raw.get("next_cursor")
        return {
            "runs": runs,
            "next_cursor": None if next_cursor is None else str(next_cursor),
        }

