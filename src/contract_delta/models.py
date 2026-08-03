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
    source_release_id: str = Field(min_length=1, max_length=256)
    source_modified_at: datetime
    source_url: str = Field(
        max_length=2048,
        pattern=r"^https://api\.tenders\.gov\.au/ocds/findById/CN\d+$",
    )
    official_record_url: str | None = Field(
        default=None,
        max_length=2048,
        pattern=(
            r"^https://www\.tenders\.gov\.au/(?:Cn/Show/[0-9a-f]{8}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|Search/CnAdvancedSearch\?"
            r"SearchFrom=CnSearch&Type=Cn&AgencyStatus=-1&KeywordTypeSearch=AllWord&"
            r"CnId=CN\d+&DateType=Publish%20Date)$"
        ),
    )
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    agency_name: str = Field(min_length=1, max_length=500)
    supplier_name: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=1000)
    description: str = Field(min_length=1, max_length=20_000)
    category_code: str | None = Field(default=None, max_length=100)
    procurement_method: str | None = Field(default=None, max_length=500)
    reported_value: Decimal | None = None
    currency: str = Field(default="AUD", pattern=r"^[A-Za-z]{3}$")
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


class CollectionCoverage(BaseModel):
    """Selection boundaries and counts for one source collection interval."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["all_releases", "bounded_amendments", "fixture"] = "all_releases"
    selection_method: str = Field(
        default="All supplied releases were processed.",
        min_length=1,
        max_length=500,
    )
    query_start: datetime | None = None
    query_end: datetime | None = None
    max_amended_contracts: int | None = Field(default=None, ge=1, le=500)
    amended_contracts_discovered: int = Field(default=0, ge=0)
    amended_contracts_selected: int = Field(default=0, ge=0)
    amended_contracts_skipped: int = Field(default=0, ge=0)


class SourceManifest(BaseModel):
    """Reproducibility and quality metadata for one pipeline run."""

    model_config = ConfigDict(extra="forbid")

    parser_version: str
    retrieved_at: datetime
    source_urls: list[str]
    source_license: str
    source_publisher: str
    coverage: CollectionCoverage = Field(default_factory=CollectionCoverage)
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
    supplier_names_redacted: int = Field(default=0, ge=0)
    descriptions_redacted: int = Field(default=0, ge=0)


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
    supplier_names_redacted: int = Field(default=0, ge=0)
    descriptions_redacted: int = Field(default=0, ge=0)


class BackfillCheckpoint(BaseModel):
    """Resumable progress and cumulative coverage for a historical collection."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    start_date: date
    end_date: date
    window_days: int = Field(ge=1, le=31)
    max_amended_contracts: int = Field(ge=1, le=500)
    next_window_start: date
    completed_through: date | None = None
    completed_windows: int = Field(default=0, ge=0)
    status: Literal["in_progress", "complete"] = "in_progress"
    amended_contracts_discovered: int = Field(default=0, ge=0)
    amended_contracts_selected: int = Field(default=0, ge=0)
    amended_contracts_skipped: int = Field(default=0, ge=0)
    change_events_added: int = Field(default=0, ge=0)
    updated_at: datetime
