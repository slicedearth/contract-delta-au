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
    ],
)
def test_live_update_rejects_unbounded_inputs(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)
