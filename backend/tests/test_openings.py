"""Session 16 offline tests for app/openings.py.

No engine, no network — these are pure deterministic lookups over the
committed openings.json table.
"""

import re

import pytest

from app.features import PlayerFeatures, PhaseACPL, WLD
from app.openings import _eco_in_family, build_opening_recs
from app.playstyle import Playstyle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_features(bucket: str, top_eco_by_color: dict[str, str | None] | None = None) -> PlayerFeatures:
    """Build a minimal PlayerFeatures for the requested playstyle bucket."""
    return PlayerFeatures(
        games_analyzed=10,
        results=WLD(win=5, loss=5),
        rating_snapshot=1500,
        time_class_mix={"blitz": 10},
        blunders_per_game=0.5,
        mistakes_per_game=1.0,
        inaccuracies_per_game=1.0,
        acpl_overall=80.0,
        acpl_by_phase=PhaseACPL(opening=10.0, middlegame=30.0, endgame=50.0),
        worst_phase="middlegame",
        worst_phase_margin=10.0,
        worst_phase_evidence=[],
        accuracy_trend="flat",
        per_game_acpl=[80.0] * 10,
        opening_leak_rate=0.0,
        opening_leak_evidence=[],
        endgame_conversion=None,
        endgame_conversion_evidence=[],
        meaningful_blunders_per_game=0.5,
        by_color={},
        detectors={},
        playstyle=Playstyle(
            label=bucket,
            score=0.0,
            explanation="",
            components={
                "capture_density": 0.48,
                "eval_volatility": 0.62,
                "game_length": 0.10,
                "opposite_castling": -0.20,
                "queen_keep": 0.05,
            },
        ),
        top_eco_by_color=top_eco_by_color or {},
    )


def _has_digit(text: str) -> bool:
    return bool(re.search(r"\d", text))


# ---------------------------------------------------------------------------
# Bucket selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bucket, expected_white, expected_black",
    [
        ("tactical", "Italian Game (incl. Evans Gambit)", "Scandinavian Defense"),
        ("positional", "London System", "Caro-Kann Defense"),
        ("balanced", "Italian Game (quiet lines)", "Classical 1...e5"),
    ],
)
def test_build_opening_recs_selects_primary_per_bucket_and_color(bucket, expected_white, expected_black):
    recs = build_opening_recs(_make_features(bucket))
    assert len(recs) == 2

    white_rec = next(r for r in recs if r.color == "white")
    black_rec = next(r for r in recs if r.color == "black")

    assert white_rec.name == expected_white
    assert black_rec.name == expected_black
    assert white_rec.study_link.url.startswith("https://lichess.org/opening/")
    assert black_rec.study_link.url.startswith("https://lichess.org/opening/")


# ---------------------------------------------------------------------------
# Digit rule: every why must contain a number
# ---------------------------------------------------------------------------


def test_every_why_contains_a_digit():
    for bucket in ("tactical", "positional", "balanced"):
        recs = build_opening_recs(_make_features(bucket))
        for rec in recs:
            assert _has_digit(rec.why), f"{bucket} {rec.color}: {rec.why}"


# ---------------------------------------------------------------------------
# Already-plays path (deepen-don't-switch)
# ---------------------------------------------------------------------------


def test_already_plays_triggers_deepen_copy():
    # "C52" falls inside the tactical-white primary family "C50–C54".
    features = _make_features("tactical", top_eco_by_color={"white": "C52", "black": "B12"})
    recs = build_opening_recs(features)
    white_rec = next(r for r in recs if r.color == "white")

    assert white_rec.already_plays is True
    assert "already play" in white_rec.why.lower()
    assert "deeper" in white_rec.why.lower()
    # The alt line is mentioned as a second weapon.
    assert "second weapon" in white_rec.why.lower()


def test_not_already_plays_uses_bucket_template_with_components():
    features = _make_features("tactical", top_eco_by_color={"white": "D00", "black": "E00"})
    recs = build_opening_recs(features)
    white_rec = next(r for r in recs if r.color == "white")

    assert white_rec.already_plays is False
    assert "capture_density" in white_rec.why or "capture density" in white_rec.why
    assert "eval_volatility" in white_rec.why or "eval volatility" in white_rec.why


# ---------------------------------------------------------------------------
# _eco_in_family edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, family, expected",
    [
        # single
        ("D02", "D02", True),
        ("d02", "D02", True),  # case insensitive
        ("C50", "C50", True),
        ("C50", "D02", False),  # wrong letter
        # range with ASCII hyphen
        ("C52", "C50-C54", True),
        ("C49", "C50-C54", False),
        ("C55", "C50-C54", False),
        # range with en-dash
        ("B12", "B10–B19", True),
        ("B09", "B10–B19", False),
        ("B20", "B10–B19", False),
        # open-ended
        ("E60", "E60+", True),
        ("E75", "E60+", True),
        ("D06", "D06+", True),
        ("D05", "D06+", False),
        # missing / malformed
        (None, "C50", False),
        ("", "C50", False),
        ("C50", "", False),
        ("XYZ", "C50", False),
    ],
)
def test_eco_in_family(code, family, expected):
    assert _eco_in_family(code, family) is expected
