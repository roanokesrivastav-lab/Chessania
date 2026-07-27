"""Session 17 — golden report fixtures and determinism gate.

Each profile in `tests.fixtures.features.builders` seeds a synthetic player,
games, and move_evals rows; `build_report` turns the resulting
`PlayerFeatures` into a `Report`.  This test treats those reports as golden
fixtures: once generated and reviewed, the JSON is committed, and future
runs assert byte-for-bit equality (minus the non-deterministic
`generated_at` field).

Regenerate the golden files with::

    REGEN_GOLDENS=1 pytest backend/tests/test_golden_reports.py -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.coach import build_report
from tests.fixtures.features.builders import (
    build_endgame_loser,
    build_positional_leaker,
    build_tactical_blunderer,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "features"

_BUILDERS = [
    ("tactical_blunderer", build_tactical_blunderer),
    ("positional_leaker", build_positional_leaker),
    ("endgame_loser", build_endgame_loser),
]


def _build_report_dict(builder, session) -> dict:
    """Return the report as a deterministic dict (``generated_at`` removed)."""
    features, player = builder(session)
    report = build_report(features, session, player)
    data = report.model_dump(mode="json")
    data.pop("generated_at", None)
    return data


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_golden_report(name: str, builder, db_session):
    """The report for each profile matches the committed golden fixture."""
    actual = _build_report_dict(builder, db_session)
    golden_path = FIXTURES_DIR / f"{name}.json"

    if os.environ.get("REGEN_GOLDENS") == "1":
        golden_path.write_text(json.dumps(actual, indent=2) + "\n")
        return

    expected = json.loads(golden_path.read_text())
    assert actual == expected


def test_build_report_is_deterministic(db_session):
    """Building the same profile twice yields identical reports (minus timestamp)."""
    for _name, builder in _BUILDERS:
        features, player = builder(db_session)

        first = build_report(features, db_session, player).model_dump(mode="json")
        first.pop("generated_at", None)
        second = build_report(features, db_session, player).model_dump(mode="json")
        second.pop("generated_at", None)

        assert first == second, f"{builder.__name__} report was not deterministic"
