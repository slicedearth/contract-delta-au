from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contract_delta.models import ContractVersion
from contract_delta.normalize import (
    NormalisationError,
    clean_text,
    normalise_release,
    official_record_url,
    parse_amount,
)
from contract_delta.privacy import REDACTED_DESCRIPTION


def test_normalise_release_uses_canberra_contract_dates(fixture_releases: list[dict]) -> None:
    version = normalise_release(fixture_releases[0])

    assert version.contract_id == "CN4260041"
    assert version.notice_id == "CN4260041"
    assert version.contract_start_date.isoformat() == "2026-06-15"
    assert version.contract_end_date.isoformat() == "2029-06-14"
    assert version.reported_value == Decimal("317458.84")
    assert version.agency_name == "Department of the Senate"
    assert version.source_url.endswith("/CN4260041")
    assert version.official_record_url == (
        "https://www.tenders.gov.au/Cn/Show/81b45321-0ee0-4eec-b4b7-d75d436750d1"
    )


def test_normalise_release_reads_explicit_amendment_id(fixture_releases: list[dict]) -> None:
    version = normalise_release(fixture_releases[1])
    assert version.notice_id == "CN4260041-A1"
    assert version.official_record_url == (
        "https://www.tenders.gov.au/Cn/Show/d895668d-bbac-4391-8a56-df40c6558d75"
    )


def test_official_record_url_falls_back_to_cn_search() -> None:
    url = official_record_url("CN4260041", "CN4260041-A1", "unexpected-item-id")
    assert url.startswith("https://www.tenders.gov.au/Search/CnAdvancedSearch?")
    assert "CnId=CN4260041" in url


def test_official_record_url_must_remain_on_valid_austender_path(
    fixture_releases: list[dict],
) -> None:
    payload = normalise_release(fixture_releases[0]).model_dump()
    payload["official_record_url"] = "https://www.tenders.gov.au/Cn/Show/not-a-record-id"

    with pytest.raises(ValidationError, match="official_record_url"):
        ContractVersion.model_validate(payload)


def test_formatting_helpers_collapse_non_substantive_differences() -> None:
    assert clean_text("  Legal\n\tServices  ") == "Legal Services"
    assert parse_amount("$1,000,000") == Decimal("1000000.00")
    assert parse_amount(1_000_000) == Decimal("1000000.00")


def test_missing_attribution_is_rejected(fixture_releases: list[dict]) -> None:
    release = fixture_releases[0] | {"parties": []}
    with pytest.raises(NormalisationError, match="party"):
        normalise_release(release)


def test_oversized_source_text_is_rejected(fixture_releases: list[dict]) -> None:
    release = deepcopy(fixture_releases[0])
    release["contracts"][0]["description"] = "x" * 20_001

    with pytest.raises(ValidationError, match="description"):
        normalise_release(release)


def test_description_is_redacted_before_hashing(fixture_releases: list[dict]) -> None:
    release = deepcopy(fixture_releases[0])
    source_description = "Delivery to 42 Example Street, Canberra."
    release["contracts"][0]["description"] = source_description

    version = normalise_release(release)

    assert version.description == REDACTED_DESCRIPTION
    assert source_description not in version.model_dump_json()
