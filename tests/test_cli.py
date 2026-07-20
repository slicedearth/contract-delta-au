from __future__ import annotations

import pytest

from contract_delta.cli import build_parser


@pytest.mark.parametrize(
    "arguments",
    [
        ["update", "--lookback-days", "0"],
        ["update", "--lookback-days", "32"],
        ["update", "--max-pages", "0"],
        ["update", "--max-pages", "251"],
        ["update", "--max-amended-contracts", "0"],
        ["update", "--max-amended-contracts", "501"],
        ["backfill", "--from", "2026-01-01", "--to", "2026-02-01", "--window-days", "0"],
        ["backfill", "--from", "2026-01-01", "--to", "2026-02-01", "--max-windows", "54"],
    ],
)
def test_live_update_rejects_unbounded_inputs(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)
