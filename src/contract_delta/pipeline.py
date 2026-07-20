"""Stateful ingestion, immutable event generation, and static-site publication."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contract_delta import __version__
from contract_delta.diff import compare_versions
from contract_delta.models import (
    ChangeEvent,
    ContractState,
    ContractVersion,
    PipelineResult,
    SourceManifest,
)
from contract_delta.normalize import (
    NormalisationError,
    amendment_number,
    normalise_release,
    version_sort_key,
)

SOURCE_LICENSE = "https://creativecommons.org/licenses/by/3.0/au/"
SOURCE_PUBLISHER = "Australian Government Department of Finance"
DISCLAIMER = (
    "ContractDelta identifies changes in publicly reported procurement records. "
    "A change is not evidence of misconduct. Contract amendments can result from "
    "legitimate changes in scope, timing, pricing, reporting, or data correction."
)


class DataQualityError(RuntimeError):
    """Raised before publication when source validation crosses a safety threshold."""


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default)
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> bytes:
    content = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return content


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_state(path: Path) -> dict[str, ContractState]:
    raw = _load_json(path, {})
    return {key: ContractState.model_validate(value) for key, value in raw.items()}


def _load_events(path: Path) -> list[ChangeEvent]:
    return [ChangeEvent.model_validate(value) for value in _load_json(path, [])]


def _direction(event: ChangeEvent) -> str:
    if event.absolute_change is not None:
        if event.absolute_change > 0:
            return "increase"
        if event.absolute_change < 0:
            return "decrease"
    if event.duration_change_days is not None:
        if event.duration_change_days > 0:
            return "extension"
        if event.duration_change_days < 0:
            return "reduction"
    return "changed"


def _money(value: str | Decimal | None, currency: str = "AUD") -> str:
    if value is None:
        return "not reported"
    amount = Decimal(str(value))
    prefix = "$" if currency == "AUD" else f"{currency} "
    return f"{prefix}{amount:,.2f}"


def _plain_language(event: ChangeEvent, currency: str = "AUD") -> str:
    field = event.field_name
    if field == "reported_value" and event.absolute_change is not None:
        verb = "increased" if event.absolute_change > 0 else "decreased"
        percentage = (
            f" ({event.percentage_change:+.2f}%)" if event.percentage_change is not None else ""
        )
        return (
            f"Reported contract value {verb} by "
            f"{_money(abs(event.absolute_change), currency)}{percentage}."
        )
    if field == "contract_end_date" and event.duration_change_days is not None:
        verb = "extended" if event.duration_change_days > 0 else "shortened"
        return f"Contract end date {verb} by {abs(event.duration_change_days):,} days."
    if field == "contract_start_date" and event.duration_change_days is not None:
        return f"Contract start date moved by {event.duration_change_days:+,} days."
    labels = {
        "agency_name": "Agency",
        "supplier_name": "Supplier",
        "title": "Reference",
        "description": "Description",
        "category_code": "Category code",
        "procurement_method": "Procurement method",
    }
    return f"{labels.get(field, field.replace('_', ' ').title())} changed."


def _event_for_site(event: ChangeEvent, currency: str = "AUD") -> dict[str, Any]:
    payload = event.model_dump(mode="json")
    payload["direction"] = _direction(event)
    payload["summary"] = _plain_language(event, currency)
    payload["field_label"] = event.field_name.replace("_", " ").title()
    return payload


def _contract_for_site(state: ContractState, events: list[ChangeEvent]) -> dict[str, Any]:
    latest = state.latest
    first = state.versions[0]
    initial_value = first.reported_value
    current_value = latest.reported_value
    value_change = None
    value_change_percentage = None
    if initial_value is not None and current_value is not None:
        value_change = current_value - initial_value
        if initial_value != 0:
            value_change_percentage = (value_change / initial_value * 100).quantize(
                Decimal("0.01")
            )
    return {
        "contract_id": latest.contract_id,
        "notice_id": latest.notice_id,
        "agency_name": latest.agency_name,
        "supplier_name": latest.supplier_name,
        "title": latest.title,
        "description": latest.description,
        "category_code": latest.category_code,
        "procurement_method": latest.procurement_method,
        "currency": latest.currency,
        "original_reported_value": initial_value,
        "current_reported_value": current_value,
        "value_change": value_change,
        "value_change_percentage": value_change_percentage,
        "contract_start_date": latest.contract_start_date,
        "contract_end_date": latest.contract_end_date,
        "latest_modified_at": latest.source_modified_at,
        "amendment_count": max(amendment_number(version.notice_id) for version in state.versions),
        "source_url": latest.source_url,
        "evidence_path": f"evidence/{latest.contract_id}.json",
        "versions": [version.model_dump(mode="json") for version in state.versions],
        "events": [_event_for_site(event, latest.currency) for event in events],
    }


def build_site_data(
    state: dict[str, ContractState],
    events: list[ChangeEvent],
    *,
    root: Path,
) -> dict[str, Any]:
    """Generate the compact dashboard, evidence JSON, and CSV exports."""

    events_by_contract: dict[str, list[ChangeEvent]] = defaultdict(list)
    for event in events:
        events_by_contract[event.contract_id].append(event)
    for grouped in events_by_contract.values():
        grouped.sort(
            key=lambda event: (
                amendment_number(event.notice_id),
                event.detected_at,
                event.event_id,
            )
        )

    contracts = [
        _contract_for_site(state[contract_id], events_by_contract[contract_id])
        for contract_id in sorted(events_by_contract)
        if contract_id in state
    ]
    contracts.sort(key=lambda contract: contract["latest_modified_at"], reverse=True)

    site_events: list[dict[str, Any]] = []
    contract_lookup = {contract["contract_id"]: contract for contract in contracts}
    for event in sorted(events, key=lambda item: (item.detected_at, item.event_id), reverse=True):
        contract = contract_lookup.get(event.contract_id)
        if contract is None:
            continue
        item = _event_for_site(event, contract["currency"])
        item.update(
            {
                "agency_name": contract["agency_name"],
                "supplier_name": contract["supplier_name"],
                "description": contract["description"],
            }
        )
        site_events.append(item)

    agencies: dict[str, dict[str, Any]] = {}
    suppliers: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        value = contract["current_reported_value"] or Decimal("0")
        agency = agencies.setdefault(
            contract["agency_name"],
            {
                "name": contract["agency_name"],
                "contracts": 0,
                "events": 0,
                "reported_value": Decimal("0"),
            },
        )
        supplier = suppliers.setdefault(
            contract["supplier_name"],
            {
                "name": contract["supplier_name"],
                "contracts": 0,
                "events": 0,
                "reported_value": Decimal("0"),
            },
        )
        for summary in (agency, supplier):
            summary["contracts"] += 1
            summary["events"] += len(contract["events"])
            summary["reported_value"] += value

    latest_modified = max(
        (record.latest.source_modified_at for record in state.values()), default=None
    )
    generated_at = latest_modified or datetime.now(UTC)
    dashboard = {
        "generated_at": generated_at,
        "latest_source_modified_at": latest_modified,
        "source": {
            "name": "AusTender OCDS API",
            "publisher": SOURCE_PUBLISHER,
            "license": SOURCE_LICENSE,
        },
        "disclaimer": DISCLAIMER,
        "stats": {
            "changed_contracts": len(contracts),
            "change_events": len(events),
            "amendments_tracked": sum(contract["amendment_count"] for contract in contracts),
            "current_reported_value": sum(
                (contract["current_reported_value"] or Decimal("0") for contract in contracts),
                Decimal("0"),
            ),
        },
        "events": site_events,
        "contracts": contracts,
        "agencies": sorted(agencies.values(), key=lambda item: (-item["events"], item["name"])),
        "suppliers": sorted(suppliers.values(), key=lambda item: (-item["events"], item["name"])),
    }

    _write_json(root / "site/src/data/dashboard.json", dashboard)
    _write_json(root / "site/public/data/change-events.json", site_events)

    evidence_dir = root / "site/public/evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for contract in contracts:
        evidence = {
            "schema_version": "1.0",
            "generated_at": dashboard["generated_at"],
            "source": dashboard["source"],
            "disclaimer": DISCLAIMER,
            "contract": contract,
        }
        _write_json(evidence_dir / f"{contract['contract_id']}.json", evidence)

    csv_path = root / "site/public/data/change-events.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "event_id",
            "contract_id",
            "notice_id",
            "detected_at",
            "agency_name",
            "supplier_name",
            "field_name",
            "old_value",
            "new_value",
            "absolute_change",
            "percentage_change",
            "duration_change_days",
            "source_url",
        ]
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(site_events)
    return dashboard


def process_releases(
    releases: list[dict[str, Any]],
    *,
    root: Path,
    source_urls: list[str] | None = None,
    pages_fetched: int = 0,
    source_license: str = SOURCE_LICENSE,
    source_publisher: str = SOURCE_PUBLISHER,
    retrieved_at: datetime | None = None,
) -> PipelineResult:
    """Normalise releases, update history, append events, and rebuild site assets."""

    retrieved_at = retrieved_at or datetime.now(UTC)
    state_path = root / "data/state/current-contracts.json"
    events_path = root / "data/events/change-events.json"
    manifest_path = root / "data/manifests/source-manifest.json"
    state = _load_state(state_path)
    events = _load_events(events_path)
    existing_event_ids = {event.event_id for event in events}

    unique_releases: dict[str, dict[str, Any]] = {}
    anonymous_releases: list[dict[str, Any]] = []
    duplicate_releases = 0
    for release in releases:
        release_id = release.get("id")
        if not isinstance(release_id, str):
            anonymous_releases.append(release)
        elif release_id in unique_releases:
            duplicate_releases += 1
        else:
            unique_releases[release_id] = release

    versions: list[ContractVersion] = []
    failures: list[dict[str, Any]] = []
    for release in [*unique_releases.values(), *anonymous_releases]:
        try:
            versions.append(normalise_release(release))
        except (NormalisationError, ValidationError, TypeError, KeyError) as exc:
            failures.append(
                {
                    "release_id": str(release.get("id") or "unknown"),
                    "error": str(exc),
                }
            )

    received_count = len(releases)
    failure_rate = len(failures) / max(len(unique_releases) + len(anonymous_releases), 1)
    if failures and (failure_rate > 0.02 or len(versions) == 0):
        raise DataQualityError(
            f"validation failed for {len(failures)} releases "
            f"({failure_rate:.1%}); publication stopped"
        )

    grouped: dict[str, list[ContractVersion]] = defaultdict(list)
    for version in versions:
        grouped[version.contract_id].append(version)

    events_added = 0
    ignored_out_of_order = 0
    for contract_id, incoming_versions in grouped.items():
        incoming_versions.sort(key=version_sort_key)
        record = state.get(contract_id)
        if record is None:
            first = incoming_versions.pop(0)
            record = ContractState(versions=[first], seen_release_ids=[first.source_release_id])
            state[contract_id] = record

        seen = set(record.seen_release_ids)
        for version in incoming_versions:
            if version.source_release_id in seen:
                duplicate_releases += 1
                continue
            latest = record.latest
            latest_order = (amendment_number(latest.notice_id), latest.source_modified_at)
            incoming_order = (amendment_number(version.notice_id), version.source_modified_at)
            seen.add(version.source_release_id)
            record.seen_release_ids.append(version.source_release_id)
            if incoming_order < latest_order:
                ignored_out_of_order += 1
                continue
            if version.source_hash == latest.source_hash:
                continue
            for event in compare_versions(latest, version):
                if event.event_id not in existing_event_ids:
                    events.append(event)
                    existing_event_ids.add(event.event_id)
                    events_added += 1
            record.versions.append(version)

    state_payload = {
        contract_id: record.model_dump(mode="json")
        for contract_id, record in sorted(state.items())
    }
    events.sort(key=lambda event: (event.detected_at, event.event_id))
    events_payload = [event.model_dump(mode="json") for event in events]
    state_bytes = _write_json(state_path, state_payload)
    events_bytes = _write_json(events_path, events_payload)
    build_site_data(state, events, root=root)

    latest_modified = max((version.source_modified_at for version in versions), default=None)
    manifest = SourceManifest(
        parser_version=__version__,
        retrieved_at=retrieved_at,
        source_urls=sorted(set(source_urls or [])),
        source_license=source_license or SOURCE_LICENSE,
        source_publisher=source_publisher or SOURCE_PUBLISHER,
        pages_fetched=pages_fetched,
        releases_received=received_count,
        releases_normalised=len(versions),
        duplicate_releases=duplicate_releases,
        ignored_out_of_order_releases=ignored_out_of_order,
        validation_failures=failures,
        contracts_in_state=len(state),
        change_events_total=len(events),
        change_events_added=events_added,
        latest_source_modified_at=latest_modified,
        state_sha256=hashlib.sha256(state_bytes).hexdigest(),
        events_sha256=hashlib.sha256(events_bytes).hexdigest(),
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    return PipelineResult(
        releases_received=received_count,
        releases_normalised=len(versions),
        contracts_in_state=len(state),
        events_added=events_added,
        events_total=len(events),
        validation_failures=len(failures),
        manifest_path=str(manifest_path),
    )


def rebuild_site(root: Path) -> dict[str, Any]:
    """Recreate static assets from already-validated state and events."""

    return build_site_data(
        _load_state(root / "data/state/current-contracts.json"),
        _load_events(root / "data/events/change-events.json"),
        root=root,
    )
