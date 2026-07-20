"""Bounded client for the public AusTender OCDS API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import httpx

from contract_delta.models import CollectionCoverage
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
    query_start: datetime | None = None
    query_end: datetime | None = None
    selection_method: str = "All releases returned for the interval were processed."
    max_amended_contracts: int | None = None
    amended_contracts_discovered: int = 0
    amended_contracts_selected: int = 0
    amended_contracts_skipped: int = 0
    amendments_only: bool = False

    def coverage(self) -> CollectionCoverage:
        """Return validated coverage metadata for publication and checkpoints."""

        return CollectionCoverage(
            mode="bounded_amendments" if self.amendments_only else "all_releases",
            selection_method=self.selection_method,
            query_start=self.query_start,
            query_end=self.query_end,
            max_amended_contracts=self.max_amended_contracts,
            amended_contracts_discovered=self.amended_contracts_discovered,
            amended_contracts_selected=self.amended_contracts_selected,
            amended_contracts_skipped=self.amended_contracts_skipped,
        )


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
        amendments_only: bool = False,
        max_amended_contracts: int | None = None,
    ) -> FetchResult:
        """Fetch releases modified in a bounded interval and follow all cursor pages."""

        if end <= start:
            raise ValueError("end must be after start")
        if (end - start).days > 31:
            raise ValueError("date range cannot exceed 31 days")
        if max_amended_contracts is not None:
            if not amendments_only:
                raise ValueError("max_amended_contracts requires amendments_only")
            if not 1 <= max_amended_contracts <= 500:
                raise ValueError("max_amended_contracts must be between 1 and 500")

        start_text = self._iso(start)
        end_text = self._iso(end)
        next_url = (
            f"{AUSTENDER_API}/ocds/findByDates/contractLastModified/{start_text}/{end_text}"
        )
        result = FetchResult(
            query_start=start,
            query_end=end,
            amendments_only=amendments_only,
        )

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

        selected_releases, selected_ids = self._select_amendment_releases(
            result.releases,
            maximum=max_amended_contracts,
        )
        result.amended_contracts_discovered = len(
            self._amendment_contract_ids(result.releases)
        )
        result.amended_contracts_selected = len(selected_ids)
        result.amended_contracts_skipped = (
            result.amended_contracts_discovered - result.amended_contracts_selected
        )

        if amendments_only:
            result.releases = selected_releases
            result.max_amended_contracts = max_amended_contracts
            result.selection_method = (
                "Explicit amendment contracts were ranked by current reported value, then "
                "source modification time and contract ID. Only the highest-ranked bounded "
                "set was processed."
            )
        if hydrate_amendments:
            result = self._hydrate_amendment_histories(result, selected_ids)
        return result

    @staticmethod
    def _amendment_contract_ids(releases: list[dict[str, Any]]) -> set[str]:
        contract_ids: set[str] = set()
        for release in releases:
            if "contractAmendment" not in (release.get("tag") or []):
                continue
            contracts = release.get("contracts") or []
            if contracts and isinstance(contracts[0], dict):
                contract_id = contracts[0].get("id")
                if (
                    isinstance(contract_id, str)
                    and contract_id.startswith("CN")
                    and contract_id[2:].isdigit()
                ):
                    contract_ids.add(contract_id)
        return contract_ids

    @staticmethod
    def _candidate_reported_value(release: dict[str, Any]) -> Decimal:
        contracts = release.get("contracts") or []
        contract = contracts[0] if contracts and isinstance(contracts[0], dict) else {}
        amount = (contract.get("value") or {}).get("amount")
        try:
            return (
                Decimal(str(amount).replace("$", "").replace(",", "").strip())
                if amount is not None
                else Decimal("-1")
            )
        except InvalidOperation:
            return Decimal("-1")

    @staticmethod
    def _candidate_latest_rank(release: dict[str, Any]) -> tuple[Any, ...]:
        contracts = release.get("contracts") or []
        contract = contracts[0] if contracts and isinstance(contracts[0], dict) else {}
        amendments = contract.get("amendments") or []
        notice_id = str(amendments[0].get("id") or "") if amendments else ""
        suffix = notice_id.rpartition("-A")[2]
        amendment_number = int(suffix) if suffix.isdigit() else 0
        source_date = str(release.get("date") or "")
        release_id = str(release.get("id") or "")
        return amendment_number, source_date, release_id

    @classmethod
    def _candidate_selection_rank(
        cls,
        release: dict[str, Any],
        contract_id: str,
    ) -> tuple[Any, ...]:
        source_date = str(release.get("date") or "")
        release_id = str(release.get("id") or "")
        return cls._candidate_reported_value(release), source_date, contract_id, release_id

    def _select_amendment_releases(
        self,
        releases: list[dict[str, Any]],
        *,
        maximum: int | None,
    ) -> tuple[list[dict[str, Any]], set[str]]:
        latest_by_contract: dict[str, dict[str, Any]] = {}
        for release in releases:
            contract_ids = self._amendment_contract_ids([release])
            if not contract_ids:
                continue
            contract_id = next(iter(contract_ids))
            current = latest_by_contract.get(contract_id)
            if current is None or self._candidate_latest_rank(
                release
            ) > self._candidate_latest_rank(current):
                latest_by_contract[contract_id] = release

        ranked = sorted(
            latest_by_contract.items(),
            key=lambda item: self._candidate_selection_rank(item[1], item[0]),
            reverse=True,
        )
        if maximum is not None:
            ranked = ranked[:maximum]
        selected_ids = {contract_id for contract_id, _ in ranked}
        return [release for _, release in ranked], selected_ids

    def _hydrate_amendment_histories(
        self,
        result: FetchResult,
        contract_ids: set[str],
    ) -> FetchResult:

        for contract_id in sorted(contract_ids):
            package = self.find_by_id(contract_id)
            result.pages_fetched += 1
            source_url = package.get("uri") or f"{AUSTENDER_API}/ocds/findById/{contract_id}"
            result.source_urls.append(str(source_url))
            releases = package.get("releases") or []
            result.releases.extend(release for release in releases if isinstance(release, dict))
        return result
