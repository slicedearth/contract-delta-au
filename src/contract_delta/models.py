"""Validated, privacy-minimised models used throughout the pipeline."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractVersion(BaseModel):
    """One normalised version of an AusTender Contract Notice."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str = Field(pattern=r"^CN\d+$")
    notice_id: str = Field(pattern=r"^CN\d+(?:-A\d+)?$")
    source_release_id: str
    source_modified_at: datetime
    source_url: str
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    agency_name: str
    supplier_name: str
    title: str | None = None
    description: str
    category_code: str | None = None
    procurement_method: str | None = None
    reported_value: Decimal | None = None
    currency: str = "AUD"
    contract_start_date: date | None = None
    contract_end_date: date | None = None

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        return value.upper()


ChangeField = Literal[
    "reported_value",
    "contract_start_date",
    "contract_end_date",
    "agency_name",
    "supplier_name",
    "title",
    "description",
    "category_code",
    "procurement_method",
]


class ChangeEvent(BaseModel):
    """An immutable field-level difference between two contract versions."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_id: str
    notice_id: str
    detected_at: datetime
    field_name: ChangeField
    old_value: str | None
    new_value: str | None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    duration_change_days: int | None = None
    before_release_id: str
    after_release_id: str
    before_source_hash: str
    after_source_hash: str
    source_url: str


class ContractState(BaseModel):
    """All known, substantive versions for one contract plus deduplication state."""

    model_config = ConfigDict(extra="forbid")

    versions: list[ContractVersion] = Field(min_length=1)
    seen_release_ids: list[str] = Field(default_factory=list)

    @property
    def latest(self) -> ContractVersion:
        return self.versions[-1]


class SourceManifest(BaseModel):
    """Reproducibility and quality metadata for one pipeline run."""

    model_config = ConfigDict(extra="forbid")

    parser_version: str
    retrieved_at: datetime
    source_urls: list[str]
    source_license: str
    source_publisher: str
    pages_fetched: int = 0
    releases_received: int
    releases_normalised: int
    duplicate_releases: int
    ignored_out_of_order_releases: int
    validation_failures: list[dict[str, Any]] = Field(default_factory=list)
    contracts_in_state: int
    change_events_total: int
    change_events_added: int
    latest_source_modified_at: datetime | None = None
    state_sha256: str
    events_sha256: str


class PipelineResult(BaseModel):
    """Small summary returned to the CLI and tests."""

    model_config = ConfigDict(extra="forbid")

    releases_received: int
    releases_normalised: int
    contracts_in_state: int
    events_added: int
    events_total: int
    validation_failures: int
    manifest_path: str
