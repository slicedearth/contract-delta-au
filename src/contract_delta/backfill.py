"""Resumable, bounded historical amendment collection."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from contract_delta.client import AusTenderClient
from contract_delta.models import BackfillCheckpoint
from contract_delta.pipeline import process_releases


class BackfillError(RuntimeError):
    """Raised when checkpoint settings or a requested range are unsafe."""


def checkpoint_path(data_root: Path, start_date: date, end_date: date) -> Path:
    """Return the stable checkpoint path for one inclusive historical range."""

    return data_root / "data/manifests" / f"backfill-{start_date}-to-{end_date}.json"


def _write_checkpoint(path: Path, checkpoint: BackfillCheckpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        checkpoint.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_checkpoint(
    path: Path,
    *,
    start_date: date,
    end_date: date,
    window_days: int,
    max_amended_contracts: int,
) -> BackfillCheckpoint:
    if not path.exists():
        return BackfillCheckpoint(
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
            max_amended_contracts=max_amended_contracts,
            next_window_start=start_date,
            updated_at=datetime.now(UTC),
        )
    try:
        checkpoint = BackfillCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BackfillError(f"cannot read backfill checkpoint: {exc}") from exc
    expected = (start_date, end_date, window_days, max_amended_contracts)
    actual = (
        checkpoint.start_date,
        checkpoint.end_date,
        checkpoint.window_days,
        checkpoint.max_amended_contracts,
    )
    if actual != expected:
        raise BackfillError(
            "existing checkpoint settings do not match; use the original window and limit"
        )
    return checkpoint


def run_backfill(
    client: AusTenderClient,
    *,
    root: Path,
    data_root: Path | None = None,
    start_date: date,
    end_date: date,
    window_days: int = 7,
    max_windows: int = 1,
    max_amended_contracts: int = 20,
) -> tuple[BackfillCheckpoint, Path]:
    """Process a limited number of windows and persist progress after each one."""

    if end_date < start_date:
        raise BackfillError("end date must be on or after start date")
    if (end_date - start_date).days > 365:
        raise BackfillError("backfill range cannot exceed 366 inclusive days")
    if not 1 <= window_days <= 31:
        raise BackfillError("window days must be between 1 and 31")
    if not 1 <= max_windows <= 53:
        raise BackfillError("max windows must be between 1 and 53")
    if not 1 <= max_amended_contracts <= 500:
        raise BackfillError("maximum amended contracts must be between 1 and 500")

    data_root = data_root or root
    path = checkpoint_path(data_root, start_date, end_date)
    checkpoint = _load_checkpoint(
        path,
        start_date=start_date,
        end_date=end_date,
        window_days=window_days,
        max_amended_contracts=max_amended_contracts,
    )
    if checkpoint.status == "complete":
        return checkpoint, path

    for _ in range(max_windows):
        if checkpoint.next_window_start > end_date:
            checkpoint.status = "complete"
            break
        window_start = checkpoint.next_window_start
        window_end = min(
            window_start + timedelta(days=window_days - 1),
            end_date,
        )
        fetched = client.fetch_modified(
            datetime.combine(window_start, time.min, tzinfo=UTC),
            datetime.combine(window_end, time.max, tzinfo=UTC),
            hydrate_amendments=True,
            amendments_only=True,
            max_amended_contracts=max_amended_contracts,
        )
        pipeline_result = process_releases(
            fetched.releases,
            root=root,
            data_root=data_root,
            source_urls=fetched.source_urls,
            source_license=fetched.license_url,
            source_publisher=fetched.publisher,
            pages_fetched=fetched.pages_fetched,
            coverage=fetched.coverage(),
        )
        checkpoint.completed_windows += 1
        checkpoint.completed_through = window_end
        checkpoint.next_window_start = window_end + timedelta(days=1)
        checkpoint.amended_contracts_discovered += fetched.amended_contracts_discovered
        checkpoint.amended_contracts_selected += fetched.amended_contracts_selected
        checkpoint.amended_contracts_skipped += fetched.amended_contracts_skipped
        checkpoint.change_events_added += pipeline_result.events_added
        checkpoint.updated_at = datetime.now(UTC)
        if checkpoint.next_window_start > end_date:
            checkpoint.status = "complete"
        _write_checkpoint(path, checkpoint)
        if checkpoint.status == "complete":
            break

    return checkpoint, path
