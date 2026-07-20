"""Pure, deterministic comparison of normalised contract versions."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from contract_delta.models import ChangeEvent, ContractVersion

TRACKED_FIELDS = (
    "reported_value",
    "contract_start_date",
    "contract_end_date",
    "agency_name",
    "supplier_name",
    "title",
    "description",
    "category_code",
    "procurement_method",
)


def _serialise(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _event_id(current: ContractVersion, field_name: str) -> str:
    seed = f"{current.contract_id}|{current.source_release_id}|{field_name}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def compare_versions(
    previous: ContractVersion,
    current: ContractVersion,
) -> list[ChangeEvent]:
    """Return one evidence-linked event for each substantive field change."""

    if previous.contract_id != current.contract_id:
        raise ValueError("cannot compare versions from different contracts")

    events: list[ChangeEvent] = []
    for field_name in TRACKED_FIELDS:
        old = getattr(previous, field_name)
        new = getattr(current, field_name)
        if old == new:
            continue

        absolute_change = None
        percentage_change = None
        duration_change_days = None
        if field_name == "reported_value" and isinstance(old, Decimal) and isinstance(new, Decimal):
            absolute_change = (new - old).quantize(Decimal("0.01"))
            if old != 0:
                percentage_change = ((new - old) / old * 100).quantize(Decimal("0.01"))
        if (
            field_name in {"contract_start_date", "contract_end_date"}
            and isinstance(old, date)
            and isinstance(new, date)
        ):
            duration_change_days = (new - old).days

        events.append(
            ChangeEvent(
                event_id=_event_id(current, field_name),
                contract_id=current.contract_id,
                notice_id=current.notice_id,
                detected_at=current.source_modified_at,
                field_name=field_name,
                old_value=_serialise(old),
                new_value=_serialise(new),
                absolute_change=absolute_change,
                percentage_change=percentage_change,
                duration_change_days=duration_change_days,
                before_release_id=previous.source_release_id,
                after_release_id=current.source_release_id,
                before_source_hash=previous.source_hash,
                after_source_hash=current.source_hash,
                source_url=current.source_url,
            )
        )
    return events
