from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from contract_delta.models import CollectionCoverage
from contract_delta.pipeline import (
    DataQualityError,
    _csv_safe,
    process_releases,
    write_public_status,
)
from contract_delta.privacy import REDACTED_SUPPLIER_NAME


def test_pipeline_builds_idempotent_evidence_assets(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    coverage = CollectionCoverage(
        mode="bounded_amendments",
        selection_method="Test selection.",
        max_amended_contracts=4,
        amended_contracts_discovered=10,
        amended_contracts_selected=4,
        amended_contracts_skipped=6,
    )
    first = process_releases(
        fixture_releases,
        root=tmp_path,
        source_urls=["fixture"],
        coverage=coverage,
    )

    state_path = tmp_path / "data/state/current-contracts.json"
    legacy_state = json.loads(state_path.read_text(encoding="utf-8"))
    for record in legacy_state.values():
        for version in record["versions"]:
            version.pop("official_record_url")
    state_path.write_text(json.dumps(legacy_state), encoding="utf-8")

    second = process_releases(
        fixture_releases,
        root=tmp_path,
        source_urls=["fixture"],
        coverage=coverage,
    )

    assert first.contracts_in_state == 4
    assert first.events_added == 5
    assert first.events_total == 5
    assert second.events_added == 0
    assert second.events_total == 5

    dashboard = json.loads(
        (tmp_path / "site/src/data/dashboard.json").read_text(encoding="utf-8")
    )
    assert dashboard["stats"] == {
        "amendments_tracked": 5,
        "change_events": 5,
        "changed_contracts": 4,
        "current_reported_value": "2967417.36",
    }
    assert dashboard["source"]["coverage"]["mode"] == "bounded_amendments"
    assert dashboard["source"]["coverage"]["amended_contracts_skipped"] == 6
    assert (tmp_path / "site/public/evidence/CN4175467.json").exists()
    csv_text = (tmp_path / "site/public/data/change-events.csv").read_text(encoding="utf-8")
    assert "source_publisher,source_license,adaptation_notice" in csv_text.splitlines()[0]

    public_events = json.loads(
        (tmp_path / "site/public/data/change-events.json").read_text(encoding="utf-8")
    )
    assert len(public_events) == dashboard["stats"]["change_events"]
    assert public_events[0]["source_publisher"] == "Australian Government Department of Finance"
    assert public_events[0]["source_license"].endswith("/by/3.0/au/")
    assert public_events[0]["adaptation_notice"].startswith("Adapted and normalised")
    assert public_events[0]["official_record_url"].startswith(
        "https://www.tenders.gov.au/Cn/Show/"
    )

    migrated_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(
        version["official_record_url"].startswith("https://www.tenders.gov.au/Cn/Show/")
        for record in migrated_state.values()
        for version in record["versions"]
    )


def test_out_of_order_versions_do_not_roll_back_state(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    process_releases(fixture_releases, root=tmp_path)
    old_release = deepcopy(fixture_releases[0])
    old_release["id"] += "-late-copy"

    result = process_releases([old_release], root=tmp_path)
    state = json.loads(
        (tmp_path / "data/state/current-contracts.json").read_text(encoding="utf-8")
    )

    assert result.events_added == 0
    assert state["CN4260041"]["versions"][-1]["notice_id"] == "CN4260041-A1"


def test_pipeline_separates_private_state_from_public_build_outputs(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"

    process_releases(
        fixture_releases,
        root=public_root,
        data_root=private_root,
    )
    status = write_public_status(
        public_root,
        data_root=private_root,
        data_revision="abc123",
    )

    assert (private_root / "data/state/current-contracts.json").exists()
    assert (private_root / "data/events/change-events.json").exists()
    assert (private_root / "data/manifests/source-manifest.json").exists()
    assert not (public_root / "data/state/current-contracts.json").exists()
    assert (public_root / "site/src/data/dashboard.json").exists()
    assert (public_root / "site/src/data/update-status.json").exists()
    assert status["data_revision"] == "abc123"
    assert status["contracts_in_private_state"] == 4


def test_quality_threshold_stops_publication(tmp_path: Path) -> None:
    bad_release = {"id": "broken", "date": "not-a-date"}
    with pytest.raises(DataQualityError, match="publication stopped"):
        process_releases([bad_release], root=tmp_path)
    assert not (tmp_path / "data/state/current-contracts.json").exists()


def test_source_licence_change_stops_publication(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    with pytest.raises(DataQualityError, match="source licence changed"):
        process_releases(
            fixture_releases,
            root=tmp_path,
            source_license="https://example.com/unknown-licence",
        )
    assert not (tmp_path / "data/state/current-contracts.json").exists()


def test_source_publisher_change_stops_publication(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    with pytest.raises(DataQualityError, match="source publisher changed"):
        process_releases(
            fixture_releases,
            root=tmp_path,
            source_publisher="Unknown publisher",
        )


@pytest.mark.parametrize(
    "value",
    [
        "Contact records@example.net for the service.",
        "Delivery to 42 Example Street, Canberra.",
        "Call 02 1234 5678 for details.",
    ],
)
def test_non_supplier_privacy_markers_stop_publication(
    tmp_path: Path,
    fixture_releases: list[dict],
    value: str,
) -> None:
    release = deepcopy(fixture_releases[0])
    release["contracts"][0]["description"] = value

    with pytest.raises(DataQualityError, match="privacy scan"):
        process_releases([release], root=tmp_path)

    assert not (tmp_path / "data/state/current-contracts.json").exists()


@pytest.mark.parametrize(
    "value",
    [
        "Contact records@example.net",
        "Example Supplier ABN 12 345 678 901",
        "Call 02 1234 5678",
        "42 Example Street",
    ],
)
def test_supplier_privacy_markers_are_redacted(
    tmp_path: Path,
    fixture_releases: list[dict],
    value: str,
) -> None:
    release = deepcopy(fixture_releases[0])
    supplier = next(
        party for party in release["parties"] if "supplier" in party.get("roles", [])
    )
    supplier["name"] = value

    result = process_releases([release], root=tmp_path)
    contract_id = release["contracts"][0]["id"]
    state = json.loads(
        (tmp_path / "data/state/current-contracts.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (tmp_path / "data/manifests/source-manifest.json").read_text(encoding="utf-8")
    )

    assert state[contract_id]["versions"][0]["supplier_name"] == REDACTED_SUPPLIER_NAME
    assert value not in json.dumps(state)
    assert result.supplier_names_redacted == 1
    assert manifest["supplier_names_redacted"] == 1


def test_redacted_suppliers_are_excluded_from_supplier_summaries(
    tmp_path: Path,
    fixture_releases: list[dict],
) -> None:
    releases = deepcopy(fixture_releases[:2])
    for release in releases:
        supplier = next(
            party for party in release["parties"] if "supplier" in party.get("roles", [])
        )
        supplier["name"] = "42 Example Street"

    process_releases(releases, root=tmp_path)
    dashboard = json.loads(
        (tmp_path / "site/src/data/dashboard.json").read_text(encoding="utf-8")
    )

    assert dashboard["contracts"][0]["supplier_name"] == REDACTED_SUPPLIER_NAME
    assert dashboard["suppliers"] == []


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(A1:A2)", "\tvalue"])
def test_csv_cells_cannot_become_spreadsheet_formulas(value: str) -> None:
    assert _csv_safe(value) == f"'{value}"
