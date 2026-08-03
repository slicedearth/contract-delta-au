"""Normalisation of AusTender OCDS releases into a conservative local schema."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo

from contract_delta.models import ContractVersion
from contract_delta.privacy import sanitise_description, sanitise_supplier_name

AUSTENDER_API = "https://api.tenders.gov.au"
AUSTENDER_WEB = "https://www.tenders.gov.au"
CANBERRA_TIME = ZoneInfo("Australia/Sydney")


class NormalisationError(ValueError):
    """Raised when an OCDS release lacks a field required for attribution."""


def clean_text(value: Any, *, required: bool = False) -> str | None:
    """Collapse whitespace and decode entities without changing letter case."""

    if value is None:
        if required:
            raise NormalisationError("required text value is missing")
        return None
    cleaned = re.sub(r"\s+", " ", unescape(str(value))).strip()
    if not cleaned:
        if required:
            raise NormalisationError("required text value is empty")
        return None
    return cleaned


def parse_amount(value: Any) -> Decimal | None:
    """Parse an AUD amount while treating formatting-only differences as equal."""

    if value is None or value == "":
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise NormalisationError(f"invalid contract value: {value!r}") from exc


def parse_source_datetime(value: Any) -> datetime:
    """Parse an ISO 8601 release timestamp and return a UTC-aware datetime."""

    text = clean_text(value, required=True)
    assert text is not None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NormalisationError(f"invalid source timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_contract_date(value: Any) -> date | None:
    """Convert midnight-like UTC timestamps to the corresponding Canberra date."""

    if value is None or value == "":
        return None
    return parse_source_datetime(value).astimezone(CANBERRA_TIME).date()


def _party_name(release: dict[str, Any], role: str) -> str:
    for party in release.get("parties") or []:
        if role in (party.get("roles") or []):
            name = clean_text(party.get("name"), required=True)
            assert name is not None
            return name
    raise NormalisationError(f"release has no {role} party")


def _normalised_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def amendment_number(notice_id: str) -> int:
    """Return zero for a parent notice or the numeric suffix for an amendment."""

    match = re.search(r"-A(\d+)$", notice_id)
    return int(match.group(1)) if match else 0


def official_record_url(
    contract_id: str,
    notice_id: str,
    item_identifier: Any = None,
    award_identifier: Any = None,
) -> str:
    """Return an exact AusTender record URL, or a safe CN search fallback."""

    candidates = [item_identifier]
    if amendment_number(notice_id) == 0:
        candidates.append(award_identifier)
    for candidate in candidates:
        text = clean_text(candidate)
        match = re.search(r"(?:^|-)([0-9a-fA-F]{32})$", text or "")
        if match:
            compact = match.group(1).lower()
            record_uuid = "-".join(
                (compact[:8], compact[8:12], compact[12:16], compact[16:20], compact[20:])
            )
            return f"{AUSTENDER_WEB}/Cn/Show/{record_uuid}"
    return (
        f"{AUSTENDER_WEB}/Search/CnAdvancedSearch?SearchFrom=CnSearch&Type=Cn"
        f"&AgencyStatus=-1&KeywordTypeSearch=AllWord&CnId={contract_id}"
        "&DateType=Publish%20Date"
    )


def normalise_release(release: dict[str, Any]) -> ContractVersion:
    """Extract the fields ContractDelta needs while excluding contact details and addresses."""

    contracts = release.get("contracts") or []
    if not contracts:
        raise NormalisationError("release has no contract")
    contract = contracts[0]
    contract_id = clean_text(contract.get("id"), required=True)
    release_id = clean_text(release.get("id"), required=True)
    if contract_id is None or release_id is None:
        raise NormalisationError("contract or release identifier is missing")
    if not re.fullmatch(r"CN\d+", contract_id):
        raise NormalisationError(f"unexpected contract identifier: {contract_id!r}")

    amendments = contract.get("amendments") or []
    notice_id = clean_text(amendments[0].get("id")) if amendments else contract_id
    if notice_id is None or not re.fullmatch(r"CN\d+(?:-A\d+)?", notice_id):
        raise NormalisationError(f"unexpected notice identifier: {notice_id!r}")

    period = contract.get("period") or {}
    value = contract.get("value") or {}
    items = contract.get("items") or []
    classification = (items[0].get("classification") or {}) if items else {}
    awards = release.get("awards") or []
    tender = release.get("tender") or {}
    description = clean_text(contract.get("description"), required=True)
    assert description is not None

    fields: dict[str, Any] = {
        "contract_id": contract_id,
        "notice_id": notice_id,
        "source_release_id": release_id,
        "source_modified_at": parse_source_datetime(release.get("date")),
        "source_url": f"{AUSTENDER_API}/ocds/findById/{contract_id}",
        "official_record_url": official_record_url(
            contract_id,
            notice_id,
            items[0].get("id") if items else None,
            awards[0].get("id") if awards else None,
        ),
        "agency_name": _party_name(release, "procuringEntity"),
        "supplier_name": sanitise_supplier_name(_party_name(release, "supplier")),
        "title": clean_text(contract.get("title")),
        "description": sanitise_description(description),
        "category_code": clean_text(classification.get("id")),
        "procurement_method": clean_text(tender.get("procurementMethodDetails"))
        or clean_text(tender.get("procurementMethod")),
        "reported_value": parse_amount(value.get("amount")),
        "currency": clean_text(value.get("currency")) or "AUD",
        "contract_start_date": parse_contract_date(period.get("startDate")),
        "contract_end_date": parse_contract_date(period.get("endDate")),
    }
    hash_payload = {
        key: value
        for key, value in fields.items()
        if not key.startswith("source_") and key != "official_record_url"
    }
    fields["source_hash"] = _normalised_hash(hash_payload)
    return ContractVersion.model_validate(fields)


def version_sort_key(version: ContractVersion) -> tuple[int, datetime, str]:
    """Order parent and amendment releases deterministically."""

    return (
        amendment_number(version.notice_id),
        version.source_modified_at,
        version.source_release_id,
    )
