from __future__ import annotations

from decimal import Decimal

import pytest

from contract_delta.normalize import NormalisationError, clean_text, normalise_release, parse_amount


def test_normalise_release_uses_canberra_contract_dates(fixture_releases: list[dict]) -> None:
    version = normalise_release(fixture_releases[0])

    assert version.contract_id == "CN4260041"
    assert version.notice_id == "CN4260041"
    assert version.contract_start_date.isoformat() == "2026-06-15"
    assert version.contract_end_date.isoformat() == "2029-06-14"
    assert version.reported_value == Decimal("317458.84")
    assert version.agency_name == "Department of the Senate"
    assert version.source_url.endswith("/CN4260041")


def test_normalise_release_reads_explicit_amendment_id(fixture_releases: list[dict]) -> None:
    version = normalise_release(fixture_releases[1])
    assert version.notice_id == "CN4260041-A1"


def test_formatting_helpers_collapse_non_substantive_differences() -> None:
    assert clean_text("  Legal\n\tServices  ") == "Legal Services"
    assert parse_amount("$1,000,000") == Decimal("1000000.00")
    assert parse_amount(1_000_000) == Decimal("1000000.00")


def test_missing_attribution_is_rejected(fixture_releases: list[dict]) -> None:
    release = fixture_releases[0] | {"parties": []}
    with pytest.raises(NormalisationError, match="party"):
        normalise_release(release)
