"""Bounded client for the public AusTender OCDS API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from contract_delta.normalize import AUSTENDER_API


class SourceAPIError(RuntimeError):
    """Raised when the source cannot be fetched or safely interpreted."""


@dataclass(slots=True)
class FetchResult:
    """Raw releases and retrieval metadata returned by the client."""

    releases: list[dict[str, Any]] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    publisher: str = "Department of Finance"
    license_url: str = "https://creativecommons.org/licenses/by/3.0/au/"


class AusTenderClient:
    """Fetch date ranges, follow opaque cursors, and hydrate amendment histories."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_pages: int = 250,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.max_pages = max_pages
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=AUSTENDER_API,
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "ContractDelta-AU/0.1"},
            transport=transport,
        )

    def __enter__(self) -> AusTenderClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _validate_next_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.tenders.gov.au":
            raise SourceAPIError("source returned an unsafe pagination URL")
        if not parsed.path.startswith("/ocds/findByDates/"):
            raise SourceAPIError("source returned an unexpected pagination path")

    def _get_json(self, url: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(url)
                if response.status_code == 400:
                    body = response.json()
                    if str(body.get("errorCode")) == "100":
                        return {"releases": [], "uri": str(response.url)}
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == self.max_retries:
                        response.raise_for_status()
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else 2**attempt
                    )
                    time.sleep(min(delay, 8))
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise SourceAPIError("source response is not a JSON object")
                return payload
            except (httpx.HTTPError, ValueError, SourceAPIError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(min(2**attempt, 8))
        raise SourceAPIError(f"failed to retrieve AusTender data: {last_error}") from last_error

    def find_by_id(self, contract_id: str) -> dict[str, Any]:
        if not contract_id.startswith("CN") or not contract_id[2:].isdigit():
            raise ValueError("contract_id must look like CN123456")
        return self._get_json(f"/ocds/findById/{contract_id}")

    def fetch_modified(
        self,
        start: datetime,
        end: datetime,
        *,
        hydrate_amendments: bool = True,
    ) -> FetchResult:
        """Fetch releases modified in a bounded interval and follow all cursor pages."""

        if end <= start:
            raise ValueError("end must be after start")
        if (end - start).days > 31:
            raise ValueError("date range cannot exceed 31 days")

        start_text = self._iso(start)
        end_text = self._iso(end)
        next_url = (
            f"{AUSTENDER_API}/ocds/findByDates/contractLastModified/{start_text}/{end_text}"
        )
        result = FetchResult()

        for _ in range(self.max_pages):
            self._validate_next_url(next_url)
            package = self._get_json(next_url)
            result.pages_fetched += 1
            result.source_urls.append(str(package.get("uri") or next_url))
            result.publisher = str((package.get("publisher") or {}).get("name") or result.publisher)
            result.license_url = str(package.get("license") or result.license_url)
            releases = package.get("releases") or []
            if not isinstance(releases, list):
                raise SourceAPIError("source releases field is not a list")
            result.releases.extend(release for release in releases if isinstance(release, dict))

            candidate = (package.get("links") or {}).get("next")
            if not candidate:
                break
            next_url = str(candidate)
        else:
            raise SourceAPIError(f"pagination exceeded the safety limit of {self.max_pages} pages")

        if hydrate_amendments:
            result = self._hydrate_amendment_histories(result)
        return result

    def _hydrate_amendment_histories(self, result: FetchResult) -> FetchResult:
        contract_ids: set[str] = set()
        for release in result.releases:
            if "contractAmendment" not in (release.get("tag") or []):
                continue
            contracts = release.get("contracts") or []
            if contracts and isinstance(contracts[0], dict):
                contract_id = contracts[0].get("id")
                if isinstance(contract_id, str):
                    contract_ids.add(contract_id)

        for contract_id in sorted(contract_ids):
            package = self.find_by_id(contract_id)
            result.pages_fetched += 1
            source_url = package.get("uri") or f"{AUSTENDER_API}/ocds/findById/{contract_id}"
            result.source_urls.append(str(source_url))
            releases = package.get("releases") or []
            result.releases.extend(release for release in releases if isinstance(release, dict))
        return result
