from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from contract_delta.backfill import run_backfill
from contract_delta.client import FetchResult
from contract_delta.models import PipelineResult


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def fetch_modified(self, start: datetime, end: datetime, **_: object) -> FetchResult:
        self.calls.append((start, end))
        return FetchResult(
            releases=[],
            query_start=start,
            query_end=end,
            amendments_only=True,
            max_amended_contracts=10,
            amended_contracts_discovered=12,
            amended_contracts_selected=10,
            amended_contracts_skipped=2,
        )


def test_backfill_checkpoints_and_resumes_windows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def process_stub(*_: object, **__: object) -> PipelineResult:
        return PipelineResult(
            releases_received=0,
            releases_normalised=0,
            contracts_in_state=0,
            events_added=3,
            events_total=3,
            validation_failures=0,
            manifest_path="manifest.json",
        )

    monkeypatch.setattr("contract_delta.backfill.process_releases", process_stub)
    client = FakeClient()
    settings = {
        "root": tmp_path,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 10),
        "window_days": 3,
        "max_amended_contracts": 10,
    }

    first, path = run_backfill(client, max_windows=2, **settings)

    assert first.status == "in_progress"
    assert first.completed_through == date(2026, 1, 6)
    assert first.next_window_start == date(2026, 1, 7)
    assert first.completed_windows == 2
    assert path.exists()

    second, _ = run_backfill(client, max_windows=53, **settings)

    assert second.status == "complete"
    assert second.completed_through == date(2026, 1, 10)
    assert second.completed_windows == 4
    assert second.amended_contracts_discovered == 48
    assert second.amended_contracts_selected == 40
    assert second.amended_contracts_skipped == 8
    assert second.change_events_added == 12
    assert client.calls[0][0] == datetime(2026, 1, 1, tzinfo=UTC)
    assert client.calls[-1][1].date() == date(2026, 1, 10)
