from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from contract_delta.source_links import (
    SourceLinkError,
    check_source_links,
    dashboard_source_links,
)

OFFICIAL_OK = "https://www.tenders.gov.au/Cn/Show/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OFFICIAL_MISSING = (
    "https://www.tenders.gov.au/Cn/Show/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
)
OCDS_BLOCKED = "https://api.tenders.gov.au/ocds/findById/CN123456"
OCDS_OFFLINE = "https://api.tenders.gov.au/ocds/findById/CN654321"
OCDS_REDIRECTED = "https://api.tenders.gov.au/ocds/findById/CN111111"


def test_dashboard_source_links_are_deduplicated_and_sorted(tmp_path: Path) -> None:
    path = tmp_path / "dashboard.json"
    path.write_text(
        json.dumps(
            {
                "contracts": [
                    {"official_record_url": OFFICIAL_OK, "source_url": OCDS_BLOCKED},
                    {"official_record_url": OFFICIAL_OK, "source_url": OCDS_BLOCKED},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert dashboard_source_links(path) == sorted([OFFICIAL_OK, OCDS_BLOCKED])


def test_dashboard_source_links_reject_an_excessive_set(tmp_path: Path) -> None:
    path = tmp_path / "dashboard.json"
    path.write_text(
        json.dumps({"official_record_url": OFFICIAL_OK, "source_url": OCDS_BLOCKED}),
        encoding="utf-8",
    )

    with pytest.raises(SourceLinkError, match="safety limit"):
        dashboard_source_links(path, maximum=1)


def test_source_link_outcomes_distinguish_missing_from_temporary_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == OFFICIAL_OK:
            return httpx.Response(200)
        if url == OFFICIAL_MISSING:
            return httpx.Response(404)
        if url == OCDS_BLOCKED:
            return httpx.Response(403)
        if url == OCDS_REDIRECTED:
            return httpx.Response(302, headers={"Location": "https://example.com/redirect"})
        raise httpx.ConnectError("temporary network failure", request=request)

    report = check_source_links(
        [OFFICIAL_OK, OFFICIAL_MISSING, OCDS_BLOCKED, OCDS_OFFLINE, OCDS_REDIRECTED],
        max_workers=2,
        transport=httpx.MockTransport(handler),
    )
    outcomes = {result.url: result.outcome for result in report.results}

    assert outcomes == {
        OCDS_BLOCKED: "indeterminate",
        OCDS_OFFLINE: "indeterminate",
        OCDS_REDIRECTED: "indeterminate",
        OFFICIAL_MISSING: "broken",
        OFFICIAL_OK: "reachable",
    }
    assert report.reachable == 1
    assert report.broken == 1
    assert report.indeterminate == 3


def test_source_link_check_rejects_unapproved_destinations_without_requesting_them() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    report = check_source_links(
        ["https://example.com/redirected-record"],
        transport=httpx.MockTransport(handler),
    )

    assert report.broken == 1
    assert report.results[0].detail == "URL is outside the approved source paths"
    assert requests == []
