"""Unit tests for partner ingestion HTTP client resilience behavior."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
import requests

from app.ingestion.client import PartnerIngestionClient
from app.ingestion.client import PartnerIngestionRequestError
from app.ingestion.client import PartnerIngestionResponseError


@dataclass
class _FakeResponse:
    status_code: int
    body: Any
    headers: dict[str, str] | None = None

    def json(self) -> Any:
        return self.body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)


class _SessionStub:
    def __init__(self, request_fn: Callable[..., _FakeResponse]) -> None:
        self._request_fn = request_fn
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, headers: dict[str, str], params: dict[str, Any] | None, timeout: float):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
        )
        return self._request_fn(url=url, headers=headers, params=params, timeout=timeout)


def test_fetch_runs_retries_retryable_statuses_and_succeeds() -> None:
    responses = [
        _FakeResponse(429, {"runs": []}, headers={"Retry-After": "2"}),
        _FakeResponse(500, {"runs": []}),
        _FakeResponse(200, {"runs": [{"id": "run-1"}], "next_cursor": "cursor-2"}),
    ]

    def request_fn(**_: Any) -> _FakeResponse:
        return responses.pop(0)

    session = _SessionStub(request_fn)
    sleep_delays: list[float] = []
    client = PartnerIngestionClient(
        base_url="https://partner.example.com",
        api_token="top-secret-token",
        timeout_seconds=4.0,
        max_retries=3,
        backoff_seconds=1.0,
        session=session,  # type: ignore[arg-type]
        sleep_fn=sleep_delays.append,
        jitter_fn=lambda: 0.0,
    )

    page = client.fetch_runs("vendor-pipeline-01")

    assert page == {"runs": [{"id": "run-1"}], "next_cursor": "cursor-2"}
    assert len(session.calls) == 3
    assert session.calls[0]["timeout"] == 4.0
    assert session.calls[0]["headers"]["Authorization"] == "Bearer top-secret-token"
    assert sleep_delays == [2.0, 2.0]


def test_fetch_runs_retries_connection_errors_until_budget_exhausted() -> None:
    attempts = {"count": 0}

    def request_fn(**_: Any) -> _FakeResponse:
        attempts["count"] += 1
        raise requests.ConnectionError("temporary network issue")

    session = _SessionStub(request_fn)
    sleep_delays: list[float] = []
    client = PartnerIngestionClient(
        base_url="https://partner.example.com",
        api_token="token",
        timeout_seconds=2.0,
        max_retries=2,
        backoff_seconds=1.0,
        session=session,  # type: ignore[arg-type]
        sleep_fn=sleep_delays.append,
        jitter_fn=lambda: 0.0,
    )

    with pytest.raises(PartnerIngestionRequestError):
        client.fetch_runs("vendor-pipeline-01")

    assert attempts["count"] == 3
    assert sleep_delays == [1.0, 2.0]


def test_fetch_runs_does_not_retry_non_retryable_http_errors() -> None:
    responses = [_FakeResponse(400, {"error": "bad request"})]

    def request_fn(**_: Any) -> _FakeResponse:
        return responses.pop(0)

    session = _SessionStub(request_fn)
    sleep_delays: list[float] = []
    client = PartnerIngestionClient(
        base_url="https://partner.example.com",
        api_token="token",
        max_retries=3,
        backoff_seconds=1.0,
        session=session,  # type: ignore[arg-type]
        sleep_fn=sleep_delays.append,
        jitter_fn=lambda: 0.0,
    )

    with pytest.raises(PartnerIngestionRequestError):
        client.fetch_runs("vendor-pipeline-01")

    assert len(session.calls) == 1
    assert sleep_delays == []


def test_fetch_runs_rejects_malformed_payload() -> None:
    responses = [_FakeResponse(200, {"runs": "not-a-list"})]

    def request_fn(**_: Any) -> _FakeResponse:
        return responses.pop(0)

    session = _SessionStub(request_fn)
    client = PartnerIngestionClient(
        base_url="https://partner.example.com",
        api_token="token",
        session=session,  # type: ignore[arg-type]
        sleep_fn=lambda _: None,
        jitter_fn=lambda: 0.0,
    )

    with pytest.raises(PartnerIngestionResponseError):
        client.fetch_runs("vendor-pipeline-01")

