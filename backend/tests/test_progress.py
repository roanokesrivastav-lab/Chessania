"""Session 22 — progress tracking.

Progress is pure DB/JSON math; these tests run offline and never touch
Stockfish.
"""

from __future__ import annotations

import pytest

from app.coach import build_report
from app.features import load_features
from app.models import Report as ReportModel
from app.progress import _delta, build_progress
from tests.fixtures.features.builders import build_sequential_player


# ---------------------------------------------------------------------------
# _delta unit tests
# ---------------------------------------------------------------------------


def test_delta_conversion_up_is_better():
    delta = _delta("Endgame conversion", 0.3, 0.5, higher_is_better=True)
    assert delta is not None
    assert delta.metric == "Endgame conversion"
    assert delta.direction == "better"


def test_delta_acpl_down_is_better():
    delta = _delta("Overall ACPL", 50.0, 40.0, higher_is_better=False)
    assert delta is not None
    assert delta.direction == "better"


def test_delta_blunders_up_is_worse():
    delta = _delta("Blunders/game", 1.0, 2.0, higher_is_better=False)
    assert delta is not None
    assert delta.direction == "worse"


def test_delta_within_epsilon_is_flat():
    # prev=100, curr=101 -> change of 1, which is <= 0.02*100 = 2.
    delta = _delta("Overall ACPL", 100.0, 101.0, higher_is_better=False)
    assert delta is not None
    assert delta.direction == "flat"


def test_delta_null_side_is_dropped():
    assert _delta("Endgame conversion", None, 0.5, higher_is_better=True) is None
    assert _delta("Endgame conversion", 0.5, None, higher_is_better=True) is None
    assert _delta("Endgame conversion", None, None, higher_is_better=True) is None


# ---------------------------------------------------------------------------
# build_progress integration tests
# ---------------------------------------------------------------------------


def test_build_progress_no_prior_report_returns_none(db_session):
    player, _ = build_sequential_player(db_session, batch2_size=5)
    # Remove the seeded prior report so there is nothing to compare against.
    for row in db_session.query(ReportModel).all():
        db_session.delete(row)
    db_session.commit()

    features = load_features(db_session, "chesscom", player.username)
    progress = build_progress(db_session, player, features, [])
    assert progress is None


def test_build_progress_sign_flip(db_session):
    """Conversion improves from the previous report -> direction is 'better'."""
    player, _ = build_sequential_player(db_session, batch2_size=5)
    features = load_features(db_session, "chesscom", player.username)
    report = build_report(features, db_session, player)

    assert report.progress is not None
    conversion_deltas = [
        d for d in report.progress.vs_previous if d.metric == "Endgame conversion"
    ]
    assert len(conversion_deltas) == 1
    conversion = conversion_deltas[0]
    assert conversion.previous == 0.0
    assert conversion.current > conversion.previous
    assert conversion.direction == "better"

    # Worst-phase ACPL delta should be present because worst_phase is non-null.
    metric_names = [d.metric for d in report.progress.vs_previous]
    assert any("ACPL" in name for name in metric_names)


def test_build_progress_low_signal_note(db_session):
    """Fewer than 5 new games since the last report -> note is set."""
    player, _ = build_sequential_player(db_session, batch2_size=3)
    features = load_features(db_session, "chesscom", player.username)
    report = build_report(features, db_session, player)

    assert report.progress is not None
    assert report.progress.note is not None
    assert "few more" in report.progress.note


@pytest.mark.parametrize("batch2_size", [5, 6, 10])
def test_build_progress_no_note_when_enough_new_games(db_session, batch2_size):
    player, _ = build_sequential_player(db_session, batch2_size=batch2_size)
    features = load_features(db_session, "chesscom", player.username)
    report = build_report(features, db_session, player)

    assert report.progress is not None
    assert report.progress.note is None
