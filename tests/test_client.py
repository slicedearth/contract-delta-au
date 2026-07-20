from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from contract_delta.client import AusTenderClient, SourceAPIError


def test_client_follows_opaque_pagination_links() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.query:
            return httpx.Response(200, json={"releases": [{"id": "release-2"}]})
        return httpx.Response(
            200,
            json={
                "uri": str(request.url),
                "releases": [{"id": "release-1"}],
                "links": {"next": f"{request.url}?cursor=opaque"},
            },
        )

    with AusTenderClient(transport=httpx.MockTransport(handler)) as client:
        result = client.fetch_modified(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
            hydrate_amendments=False,
        )

    assert [release["id"] for release in result.releases] == ["release-1", "release-2"]
    assert result.pages_fetched == 2
    assert len(calls) == 2


def test_client_rejects_cross_origin_next_link() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"releases": [], "links": {"next": "https://example.com/steal-cursor"}},
        )

    with (
        AusTenderClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SourceAPIError, match="unsafe pagination"),
    ):
        client.fetch_modified(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
            hydrate_amendments=False,
        )


def test_client_bounds_date_ranges() -> None:
    with (
        AusTenderClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client,
        pytest.raises(ValueError, match="31 days"),
    ):
        client.fetch_modified(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 3, 1, tzinfo=UTC),
        )


def test_client_selects_a_deterministic_bounded_amendment_set(
    fixture_releases: list[dict],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "uri": str(request.url),
                "releases": fixture_releases,
            },
        )

    with AusTenderClient(transport=httpx.MockTransport(handler)) as client:
        result = client.fetch_modified(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
            hydrate_amendments=False,
            amendments_only=True,
            max_amended_contracts=2,
        )

    selected_ids = {release["contracts"][0]["id"] for release in result.releases}
    assert selected_ids == {"CN4255613", "CN4260041"}
    assert result.amended_contracts_discovered == 4
    assert result.amended_contracts_selected == 2
    assert result.amended_contracts_skipped == 2
    assert result.coverage().mode == "bounded_amendments"


def test_client_requires_amendment_mode_for_a_selection_limit() -> None:
    with (
        AusTenderClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client,
        pytest.raises(ValueError, match="requires amendments_only"),
    ):
        client.fetch_modified(
            datetime(2026, 7, 1, tzinfo=UTC),
            datetime(2026, 7, 2, tzinfo=UTC),
            max_amended_contracts=10,
        )
