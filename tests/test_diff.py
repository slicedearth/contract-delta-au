from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from contract_delta.diff import compare_versions
from contract_delta.normalize import normalise_release


def test_value_increase_is_calculated_from_normalised_amounts(
    fixture_releases: list[dict],
) -> None:
    previous = normalise_release(fixture_releases[0])
    current = normalise_release(fixture_releases[1])

    events = compare_versions(previous, current)

    assert len(events) == 1
    assert events[0].field_name == "reported_value"
    assert events[0].absolute_change == Decimal("31745.88")
    assert events[0].percentage_change == Decimal("10.00")


def test_formatting_only_change_produces_no_event(fixture_releases: list[dict]) -> None:
    source = deepcopy(fixture_releases[0])
    reformatted = deepcopy(source)
    reformatted["id"] += "-format"
    reformatted["contracts"][0]["description"] = " Software as a service\nplus CiA Live fee "
    reformatted["contracts"][0]["value"]["amount"] = "$317,458.84"

    assert compare_versions(normalise_release(source), normalise_release(reformatted)) == []


def test_date_extension_and_null_transition_are_explicit(fixture_releases: list[dict]) -> None:
    before_release = deepcopy(fixture_releases[0])
    after_release = deepcopy(fixture_releases[1])
    before_release["contracts"][0]["title"] = None
    after_release["contracts"][0]["title"] = "New reference"
    after_release["contracts"][0]["period"]["endDate"] = "2030-06-13T14:00:00Z"

    events = compare_versions(normalise_release(before_release), normalise_release(after_release))
    by_field = {event.field_name: event for event in events}

    assert by_field["contract_end_date"].duration_change_days == 365
    assert by_field["title"].old_value is None
    assert by_field["title"].new_value == "New reference"


def test_versions_from_different_contracts_are_rejected(fixture_releases: list[dict]) -> None:
    with pytest.raises(ValueError, match="different contracts"):
        compare_versions(
            normalise_release(fixture_releases[0]),
            normalise_release(fixture_releases[2]),
        )
