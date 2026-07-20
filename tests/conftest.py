from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def fixture_packages() -> list[dict[str, Any]]:
    path = Path(__file__).parent / "fixtures/amended_releases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def fixture_releases(fixture_packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [release for package in fixture_packages for release in package["releases"]]
