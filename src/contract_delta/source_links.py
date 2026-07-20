"""Bounded availability checks for published source destinations."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

LinkOutcome = Literal["reachable", "broken", "indeterminate"]

OFFICIAL_RECORD_PATTERN = re.compile(
    r"^https://www\.tenders\.gov\.au/(?:Cn/Show/[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|Search/CnAdvancedSearch\?"
    r"SearchFrom=CnSearch&Type=Cn&AgencyStatus=-1&KeywordTypeSearch=AllWord&"
    r"CnId=CN\d+&DateType=Publish%20Date)$"
)
OCDS_RECORD_PATTERN = re.compile(
    r"^https://api\.tenders\.gov\.au/ocds/findById/CN\d+$"
)
SOURCE_URL_KEYS = frozenset({"official_record_url", "source_url"})
MAX_SOURCE_LINKS = 500


class SourceLinkError(RuntimeError):
    """Raised when generated link data cannot be checked safely."""


@dataclass(frozen=True, slots=True)
class SourceLinkResult:
    """The availability outcome for one validated destination."""

    url: str
    outcome: LinkOutcome
    status_code: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SourceLinkReport:
    """A deterministic summary of a bounded source-link check."""

    results: tuple[SourceLinkResult, ...]

    @property
    def reachable(self) -> int:
        return sum(result.outcome == "reachable" for result in self.results)

    @property
    def broken(self) -> int:
        return sum(result.outcome == "broken" for result in self.results)

    @property
    def indeterminate(self) -> int:
        return sum(result.outcome == "indeterminate" for result in self.results)


def _collect_source_links(value: Any, links: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in SOURCE_URL_KEYS:
                if not isinstance(nested, str):
                    raise SourceLinkError(f"{key} must be a string")
                links.add(nested)
            else:
                _collect_source_links(nested, links)
    elif isinstance(value, list):
        for nested in value:
            _collect_source_links(nested, links)


def dashboard_source_links(path: Path, *, maximum: int = MAX_SOURCE_LINKS) -> list[str]:
    """Read, deduplicate, and bound source URLs from generated dashboard data."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceLinkError(f"cannot read generated dashboard: {exc}") from exc
    links: set[str] = set()
    _collect_source_links(payload, links)
    if not links:
        raise SourceLinkError("generated dashboard contains no source links")
    if len(links) > maximum:
        raise SourceLinkError(
            f"generated dashboard contains {len(links)} source links; safety limit is {maximum}"
        )
    return sorted(links)


def _is_valid_source_url(url: str) -> bool:
    return bool(OFFICIAL_RECORD_PATTERN.fullmatch(url) or OCDS_RECORD_PATTERN.fullmatch(url))


def _check_one(client: httpx.Client, url: str) -> SourceLinkResult:
    if not _is_valid_source_url(url):
        return SourceLinkResult(url, "broken", detail="URL is outside the approved source paths")
    try:
        with client.stream("GET", url) as response:
            status_code = response.status_code
    except httpx.HTTPError as exc:
        return SourceLinkResult(url, "indeterminate", detail=type(exc).__name__)

    if 200 <= status_code < 300:
        return SourceLinkResult(url, "reachable", status_code=status_code)
    if status_code in {404, 410}:
        return SourceLinkResult(url, "broken", status_code=status_code)
    return SourceLinkResult(url, "indeterminate", status_code=status_code)


def check_source_links(
    urls: list[str],
    *,
    timeout: float = 10.0,
    max_workers: int = 4,
    transport: httpx.BaseTransport | None = None,
) -> SourceLinkReport:
    """Check source URLs without following redirects or downloading response bodies."""

    if not urls:
        raise SourceLinkError("no source links were supplied")
    if len(urls) > MAX_SOURCE_LINKS:
        raise SourceLinkError(f"source-link safety limit is {MAX_SOURCE_LINKS}")
    if not 1 <= max_workers <= 8:
        raise ValueError("max_workers must be between 1 and 8")

    with (
        httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            headers={
                "Accept": "text/html, application/json;q=0.9, */*;q=0.1",
                "User-Agent": "ContractDelta-AU-LinkCheck/0.1",
            },
            limits=httpx.Limits(
                max_connections=max_workers,
                max_keepalive_connections=max_workers,
            ),
            transport=transport,
        ) as client,
        ThreadPoolExecutor(max_workers=max_workers) as executor,
    ):
        results = tuple(executor.map(lambda url: _check_one(client, url), urls))
    return SourceLinkReport(tuple(sorted(results, key=lambda result: result.url)))


def check_dashboard_source_links(path: Path) -> SourceLinkReport:
    """Check every distinct source destination in a generated dashboard."""

    return check_source_links(dashboard_source_links(path))
