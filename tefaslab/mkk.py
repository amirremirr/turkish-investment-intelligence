"""Small, rate-limited client for MKK's official KAP data-publication API.

The API is a *discovery and provenance* source.  Holdings themselves can
still be delivered as PDF attachments, so callers must not assume that every
``disclosureDetail`` response has a ``flatData`` table.

Credentials are deliberately read only from environment variables:
``MKK_USERNAME`` and ``MKK_PASSWORD``.  Do not put them in source, a checked-in
configuration file, issue, or workflow log.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth


BASE_URL = "https://apigwdev.mkk.com.tr/api/vyk"
# The supplied product quota is six calls per minute.  Leave a little room
# rather than running exactly on the boundary and receiving intermittent 429s.
MIN_REQUEST_INTERVAL_SECONDS = 10.5
# A 429 is a normal signal from a quota-limited upstream, not a reason to
# discard a month's scan checkpoint.  Retry a small, bounded number of times
# and honour a server-provided delay when available.
MAX_RATE_LIMIT_RETRIES = 4
RETRYABLE_SERVER_STATUSES = {500, 502, 503, 504}


class MKKConfigurationError(RuntimeError):
    """Raised before any network call when the MKK credentials are absent."""


class MKKTransientError(requests.HTTPError):
    """A bounded retryable upstream failure; callers may defer one page."""


class MKKClient:
    """Authenticated, deliberately slow MKK API client.

    ``session``, ``clock`` and ``sleep`` are injectable so the contract can be
    tested without network traffic or a real wait.
    """

    def __init__(self, username: str | None = None, password: str | None = None,
                 session: requests.Session | None = None,
                 min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.username = username if username is not None else os.getenv("MKK_USERNAME")
        self.password = password if password is not None else os.getenv("MKK_PASSWORD")
        if not self.username or not self.password:
            raise MKKConfigurationError(
                "MKK_USERNAME and MKK_PASSWORD must be set for the MKK API")
        self.session = session or requests.Session()
        self.min_interval = min_interval
        self.clock = clock
        self.sleep = sleep
        self._last_request_at: float | None = None

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float:
        """Return a conservative delay for an upstream 429 response."""
        raw = response.headers.get("Retry-After")
        try:
            return max(MIN_REQUEST_INTERVAL_SECONDS, float(raw)) if raw else 30.0
        except (TypeError, ValueError):
            return 30.0

    def _request(self, path: str, *, params: dict[str, str] | None = None,
                 timeout: int = 30, binary: bool = False) -> Any:
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            if self._last_request_at is not None:
                wait = self.min_interval - (self.clock() - self._last_request_at)
                if wait > 0:
                    self.sleep(wait)
            response = self.session.get(
                f"{BASE_URL}{path}",
                auth=HTTPBasicAuth(self.username, self.password),
                headers={"Accept": "application/json"} if not binary else {},
                params=params,
                timeout=timeout,
            )
            self._last_request_at = self.clock()
            retryable = response.status_code == 429 or response.status_code in RETRYABLE_SERVER_STATUSES
            if not retryable:
                response.raise_for_status()
                return response.content if binary else response.json()

            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise MKKTransientError(
                    f"MKK transient HTTP {response.status_code} after {attempt + 1} attempts",
                    response=response,
                )

            # Start the next attempt after the provider's cooldown. Clearing
            # the per-client timestamp avoids assuming an injected test clock
            # advanced while the injected sleeper ran.
            delay = (self._retry_after_seconds(response) if response.status_code == 429
                     else min(60.0, self.min_interval * (2 ** attempt)))
            self.sleep(delay)
            self._last_request_at = None

        raise AssertionError("unreachable")

    def funds(self) -> list[dict[str, Any]]:
        data = self._request("/funds", timeout=60)
        if not isinstance(data, list):
            raise ValueError("MKK /funds returned a non-list payload")
        return data

    def last_disclosure_index(self) -> int:
        data = self._request("/lastDisclosureIndex")
        try:
            return int(data["lastDisclosureIndex"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("MKK /lastDisclosureIndex payload is invalid") from exc

    def disclosures(self, disclosure_index: int) -> list[dict[str, Any]]:
        data = self._request("/disclosures", params={
            "disclosureIndex": str(int(disclosure_index)),
        })
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data", "content", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise ValueError("MKK /disclosures returned no list payload")

    def disclosure_detail(self, disclosure_index: int,
                          file_type: str = "data") -> dict[str, Any]:
        data = self._request(f"/disclosureDetail/{int(disclosure_index)}",
                             params={"fileType": file_type}, timeout=60)
        if not isinstance(data, dict):
            raise ValueError("MKK /disclosureDetail returned a non-object payload")
        return data

    def download_attachment(self, attachment_url_or_id: str) -> bytes:
        """Fetch an attachment using the id carried in ``attachmentUrls``."""
        path = urlparse(attachment_url_or_id).path.rstrip("/")
        attachment_id = path.rsplit("/", 1)[-1]
        if not attachment_id:
            raise ValueError("MKK attachment URL has no attachment id")
        return self._request(f"/downloadAttachment/{attachment_id}",
                             timeout=120, binary=True)


def subject_text(detail: dict[str, Any]) -> str:
    """Return all localised subject fields as a single searchable string."""
    subject = detail.get("subject")
    if isinstance(subject, dict):
        return " ".join(str(value) for value in subject.values() if value)
    return str(subject or "")
