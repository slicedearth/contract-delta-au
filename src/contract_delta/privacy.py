"""High-confidence privacy checks for normalised public contract fields."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contract_delta.models import ContractVersion

TEXT_FIELDS = (
    "agency_name",
    "supplier_name",
    "title",
    "description",
    "procurement_method",
)

PATTERNS = {
    "email address": re.compile(
        r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])"
    ),
    "labelled business identifier": re.compile(
        r"(?i)\b(?:ABN|ACN|Australian Business Number)\s*[:#-]?\s*"
        r"(?:\d[ -]?){8,11}\b"
    ),
    "Australian phone number": re.compile(
        r"(?<!\d)(?:\+?61[ -]?[2-478]|0[2-478])(?:[ -]?\d){8}(?!\d)"
    ),
    "street address": re.compile(
        r"(?i)\b\d{1,5}\s+[A-Z][A-Z0-9'. -]{1,60}\s+"
        r"(?:STREET|ST|ROAD|RD|AVENUE|AVE|DRIVE|DR|COURT|CT|LANE|LN|PLACE|PL)\b"
    ),
}


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """Field and marker type without retaining the matched source value."""

    field_name: str
    marker: str


def privacy_findings(version: ContractVersion) -> tuple[PrivacyFinding, ...]:
    """Return high-confidence contact or address markers in retained text fields."""

    findings: list[PrivacyFinding] = []
    for field_name in TEXT_FIELDS:
        value = getattr(version, field_name)
        if not value:
            continue
        for marker, pattern in PATTERNS.items():
            if pattern.search(value):
                findings.append(PrivacyFinding(field_name=field_name, marker=marker))
    return tuple(findings)
