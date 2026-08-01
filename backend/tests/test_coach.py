"""Session 15 offline tests for app/coach.py.

Every test runs against a seeded in-memory database so evidence refs can be
resolved into real Game/MoveEval rows. No engine, no network.
"""

import datetime as dt
import uuid

import pytest

from app.coach import build_report
from app.features import OpeningLineStat, PlayerFeatures, PhaseACPL, WLD
from app.models import Game, MoveEval, Player
from app.playstyle import Playstyle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_player_and_game(db_session, *, player_color: str = "white", result: str = "win"):
    """Insert a throwaway player + game, returning both."""
    player = Player(platform="chesscom", username="coachtester")
    db_session.add(player)
    db_session.commit()

    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class="blitz",
        player_color=player_color,
        result=result,
        played_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    db_session.add(game)
    db_session.commit()
    return player, game


def _insert_row(
    db_session,
    game: Game,
    *,
    ply: int,
    classification: str = "ok",
    phase: str = "middlegame",
    eval_cp_before: int = 0,
    eval_cp_after: int = 0,
    cp_loss: int = 0,
    seconds_spent: int | None = None,
    move_san: str = "e4",
) -> MoveEval:
    row = MoveEval(
        game_id=game.id,
        ply=ply,
        move_san=move_san,
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        eval_cp_before=eval_cp_before,
        eval_cp_after=eval_cp_after,
        cp_loss=cp_loss,
        best_move_san=move_san,
        classification=classification,
        phase=phase,
        seconds_spent=seconds_spent,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _base_features(**overrides) -> PlayerFeatures:
    """A PlayerFeatures with sensible defaults so tests only override what
    they care about."""
    defaults = {
        "games_analyzed": 10,
        "results": WLD(win=5, loss=5),
        "rating_snapshot": 1500,
        "time_class_mix": {"blitz": 10},
        "blunders_per_game": 0.5,
        "mistakes_per_game": 1.0,
        "inaccuracies_per_game": 1.0,
        "acpl_overall": 80.0,
        "acpl_by_phase": PhaseACPL(opening=10.0, middlegame=30.0, endgame=200.0),
        "worst_phase": "endgame",
        "worst_phase_margin": 120.0,
        "worst_phase_evidence": [],
        "accuracy_trend": "flat",
        "per_game_acpl": [80.0] * 10,
        "opening_leak_rate": 0.0,
        "opening_leak_evidence": [],
        "endgame_conversion": None,
        "endgame_conversion_evidence": [],
        "advantage_capitalization": None,
        "advantage_reached": 0,
        "advantage_converted": 0,
        "advantage_capitalization_evidence": [],
        "resourcefulness": None,
        "resource_trouble_games": 0,
        "resource_comebacks": 0,
        "missed_save_evidence": [],
        "meaningful_blunders_per_game": 0.5,
        "by_color": {},
        "detectors": {
            "hung_pieces": {"fired": False, "stats": {}, "evidence": []},
            "late_collapse": {"fired": False, "stats": {}, "evidence": []},
            "opening_leak": {"fired": False, "stats": {}, "evidence": []},
            "overextension": {"fired": False, "stats": {}, "evidence": []},
            "time_class_split": {"fired": False, "stats": {}, "evidence": []},
            "turning_point": {"fired": False, "stats": {"ponr_by_game": {}}, "evidence": []},
            "rushed_blunders": {"fired": False, "stats": {}, "evidence": []},
            "time_trouble_collapse": {"fired": False, "stats": {}, "evidence": []},
            "dawdling": {"fired": False, "stats": {}, "evidence": []},
        },
        "playstyle": Playstyle(label="balanced", score=0.0, explanation="", components={}),
    }
    defaults.update(overrides)
    return PlayerFeatures(**defaults)


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _sentences_contain_digits(text: str) -> bool:
    for sentence in text.split("."):
        if sentence.strip() and not _has_digit(sentence):
            return False
    return True


# ---------------------------------------------------------------------------
# 1. Each of the 11 rules fires and renders a valid, digit-rich Issue
# ---------------------------------------------------------------------------


def test_each_individual_rule_renders_a_valid_issue(db_session):
    """For every Appendix 3 rule, build a PlayerFeatures that triggers only
    that rule and verify the resulting Issue validates, has evidence, and
    contains a digit in diagnosis/prescription/success_metric."""
    player, game = _insert_player_and_game(db_session)
    gid = str(game.id)

    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)
    endgame_row = _insert_row(
        db_session,
        game,
        ply=5,
        classification="ok",
        phase="endgame",
        eval_cp_before=200,
    )
    opening_row = _insert_row(db_session, game, ply=20, classification="ok")

    rule_configs = [
        (
            "blunder_rate",
            _base_features(
                meaningful_blunders_per_game=2.0,
                detectors={
                    **_base_features().detectors,
                    "turning_point": {
                        "fired": True,
                        "stats": {"ponr_by_game": {gid: 10}, "qualifying_games": 1},
                        "evidence": [(gid, 1)],
                    },
                },
            ),
        ),
        (
            "hung_pieces",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "hung_pieces": {
                        "fired": True,
                        "stats": {"hang_pct": 50.0, "hung_count": 2},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "opening_leak",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "opening_leak": {
                        "fired": True,
                        "stats": {"family": "B0", "avg_cp": -80.0, "game_count": 5},
                        "evidence": [(gid, opening_row.ply)],
                    },
                }
            ),
        ),
        (
            "endgame_conversion",
            _base_features(
                endgame_conversion=0.50,
                endgame_conversion_evidence=[(gid, endgame_row.ply)],
            ),
        ),
        (
            "opening_variation",
            _base_features(
                opening_variation_stats=[
                    OpeningLineStat(
                        color="white",
                        eco="B07",
                        name="Pirc Defense",
                        games=3,
                        results=WLD(win=1, loss=2, draw=0),
                        avg_opening_eval=50.0,
                        low_signal=True,
                        evidence=[(gid, 20)],
                    )
                ],
            ),
        ),
        (
            "advantage_capitalization",
            _base_features(
                advantage_capitalization=0.50,
                advantage_reached=4,
                advantage_converted=2,
                advantage_capitalization_evidence=[(gid, blunder_row.ply)],
            ),
        ),
        (
            "late_collapse",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "late_collapse": {
                        "fired": True,
                        "stats": {"late_ratio": 5.0, "late_blunders": 5},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "blitz_gap",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "time_class_split": {
                        "fired": True,
                        "stats": {"blitz_bpg": 1.0, "rapid_bpg": 0.2},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "opening_general",
            _base_features(
                opening_leak_rate=0.40,
                opening_leak_evidence=[(gid, opening_row.ply)],
            ),
        ),
        (
            "overextension",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "overextension": {
                        "fired": True,
                        "stats": {"occurrences": 4},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "rushed_blunders",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "rushed_blunders": {
                        "fired": True,
                        "stats": {"share": 0.5, "rush_seconds": 15},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "time_trouble_collapse",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "time_trouble_collapse": {
                        "fired": True,
                        "stats": {"rate_low": 1.0, "rate_normal": 0.1, "low_clock": 30},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
        (
            "dawdling",
            _base_features(
                detectors={
                    **_base_features().detectors,
                    "dawdling": {
                        "fired": True,
                        "stats": {"avg_dawdle_seconds": 25, "game_count": 5},
                        "evidence": [(gid, blunder_row.ply)],
                    },
                }
            ),
        ),
    ]

    for expected_key, features in rule_configs:
        report = build_report(features, db_session, player)
        keys = [issue.key for issue in report.issues]
        assert keys == [expected_key], f"Rule {expected_key}: got {keys}"
        issue = report.issues[0]
        assert issue.evidence, f"Rule {expected_key} produced empty evidence"
        assert _sentences_contain_digits(issue.diagnosis), f"{expected_key} diagnosis: {issue.diagnosis}"
        assert _sentences_contain_digits(issue.prescription), f"{expected_key} prescription: {issue.prescription}"
        assert _sentences_contain_digits(issue.success_metric), f"{expected_key} metric: {issue.success_metric}"


# ---------------------------------------------------------------------------
# 2. Issue ordering: rating_impact bucket first, then priority
# ---------------------------------------------------------------------------


def test_issues_ordered_by_rating_impact_then_priority(db_session):
    player, game = _insert_player_and_game(db_session)
    gid = str(game.id)
    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)

    features = _base_features(
        meaningful_blunders_per_game=2.0,
        endgame_conversion=0.50,
        endgame_conversion_evidence=[(gid, 1)],
        opening_leak_rate=0.0,
        detectors={
            "hung_pieces": {"fired": True, "stats": {"hang_pct": 50.0, "hung_count": 2}, "evidence": [(gid, blunder_row.ply)]},
            "late_collapse": {"fired": False, "stats": {}, "evidence": []},
            "opening_leak": {"fired": False, "stats": {}, "evidence": []},
            "overextension": {"fired": True, "stats": {"occurrences": 4}, "evidence": [(gid, blunder_row.ply)]},
            "time_class_split": {"fired": False, "stats": {}, "evidence": []},
            "turning_point": {"fired": False, "stats": {"ponr_by_game": {}}, "evidence": []},
            "rushed_blunders": {"fired": False, "stats": {}, "evidence": []},
            "time_trouble_collapse": {"fired": False, "stats": {}, "evidence": []},
            "dawdling": {"fired": False, "stats": {}, "evidence": []},
        },
    )

    report = build_report(features, db_session, player)
    # Fired rules: blunder_rate (pri 1, high), hung_pieces (pri 2, high),
    # endgame_conversion (pri 4, medium), overextension (pri 8, low).
    # Top 3 should drop overextension.
    keys = [issue.key for issue in report.issues]
    assert keys == ["blunder_rate", "hung_pieces", "endgame_conversion"]
    assert all(issue.rating_impact == "high" for issue in report.issues[:2])
    assert report.issues[2].rating_impact == "medium"


# ---------------------------------------------------------------------------
# 3. Top-3 cap — never padded
# ---------------------------------------------------------------------------


def test_report_never_returns_more_than_three_issues(db_session):
    player, game = _insert_player_and_game(db_session)
    gid = str(game.id)
    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)

    features = _base_features(
        meaningful_blunders_per_game=2.0,
        endgame_conversion=0.50,
        endgame_conversion_evidence=[(gid, 1)],
        detectors={
            "hung_pieces": {"fired": True, "stats": {"hang_pct": 50.0, "hung_count": 2}, "evidence": [(gid, blunder_row.ply)]},
            "late_collapse": {"fired": True, "stats": {"late_ratio": 5.0, "late_blunders": 5}, "evidence": [(gid, blunder_row.ply)]},
            "opening_leak": {"fired": False, "stats": {}, "evidence": []},
            "overextension": {"fired": True, "stats": {"occurrences": 4}, "evidence": [(gid, blunder_row.ply)]},
            "time_class_split": {"fired": True, "stats": {"blitz_bpg": 1.0, "rapid_bpg": 0.2}, "evidence": [(gid, blunder_row.ply)]},
            "turning_point": {"fired": False, "stats": {"ponr_by_game": {}}, "evidence": []},
            "rushed_blunders": {"fired": False, "stats": {}, "evidence": []},
            "time_trouble_collapse": {"fired": False, "stats": {}, "evidence": []},
            "dawdling": {"fired": False, "stats": {}, "evidence": []},
        },
    )

    report = build_report(features, db_session, player)
    assert len(report.issues) == 3


# ---------------------------------------------------------------------------
# 4. Clean player → valid strength, no padding, no crash
# ---------------------------------------------------------------------------


def test_clean_player_produces_valid_strength_and_empty_issues(db_session):
    player, _game = _insert_player_and_game(db_session)
    features = _base_features(
        blunders_per_game=0.1,
        meaningful_blunders_per_game=0.0,
        acpl_overall=20.0,
        acpl_by_phase=PhaseACPL(opening=10.0, middlegame=20.0, endgame=30.0),
    )

    report = build_report(features, db_session, player)
    assert len(report.issues) == 0
    assert len(report.strengths) == 1
    strength = report.strengths[0]
    assert _sentences_contain_digits(strength.detail)
    assert len(report.opening_recs) == 2
    assert report.progress is None


# ---------------------------------------------------------------------------
# 5. Pydantic round-trip
# ---------------------------------------------------------------------------


def test_report_serializes_and_validates(db_session):
    player, game = _insert_player_and_game(db_session)
    gid = str(game.id)
    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)

    features = _base_features(
        meaningful_blunders_per_game=2.0,
        detectors={
            "hung_pieces": {"fired": True, "stats": {"hang_pct": 50.0, "hung_count": 2}, "evidence": [(gid, blunder_row.ply)]},
            "late_collapse": {"fired": False, "stats": {}, "evidence": []},
            "opening_leak": {"fired": False, "stats": {}, "evidence": []},
            "overextension": {"fired": False, "stats": {}, "evidence": []},
            "time_class_split": {"fired": False, "stats": {}, "evidence": []},
            "turning_point": {"fired": False, "stats": {"ponr_by_game": {}}, "evidence": []},
            "rushed_blunders": {"fired": False, "stats": {}, "evidence": []},
            "time_trouble_collapse": {"fired": False, "stats": {}, "evidence": []},
            "dawdling": {"fired": False, "stats": {}, "evidence": []},
        },
    )

    report = build_report(features, db_session, player)
    raw = report.model_dump(mode="json")
    assert raw["schema_version"] == 1
    assert raw["player_summary"]["games_analyzed"] == 10
    assert raw["stats_block"]["blunders_per_game"] == 0.5


# ---------------------------------------------------------------------------
# 6. opening_general rule fires when opening_leak does not
# ---------------------------------------------------------------------------


def test_advantage_capitalization_does_not_fire_below_min_games(db_session):
    player, game = _insert_player_and_game(db_session)
    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)

    features = _base_features(
        advantage_capitalization=0.50,
        advantage_reached=3,  # below FEATURE_ADVANTAGE_MIN_GAMES (4)
        advantage_converted=1,
        advantage_capitalization_evidence=[(str(game.id), blunder_row.ply)],
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "advantage_capitalization" not in keys


# ---------------------------------------------------------------------------
# Opening performance by variation (S31)
# ---------------------------------------------------------------------------

def test_opening_variation_fires_on_fine_but_losing_line(db_session):
    player, game = _insert_player_and_game(db_session)
    opening_row = _insert_row(db_session, game, ply=20, classification="ok")

    features = _base_features(
        opening_variation_stats=[
            OpeningLineStat(
                color="white",
                eco="B07",
                name="Pirc Defense",
                games=3,
                results=WLD(win=0, loss=3, draw=0),
                avg_opening_eval=50.0,  # fine out of the opening
                low_signal=True,
                evidence=[(str(game.id), opening_row.ply)],
            )
        ],
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "opening_variation" in keys
    issue = next(i for i in report.issues if i.key == "opening_variation")
    assert "Pirc Defense" in issue.diagnosis
    assert "100.0%" in issue.diagnosis  # 3 losses / 3 games
    assert issue.counter_evidence
    assert len(issue.evidence) == 1
    assert issue.rating_impact == "medium"
    assert _has_digit(issue.diagnosis)
    assert _has_digit(issue.prescription)
    assert _has_digit(issue.success_metric)


def test_opening_variation_does_not_fire_when_line_comes_out_worse(db_session):
    """A line with avg eval below -FEATURE_OPENING_FINE_CP is opening_leak's
    seat, never opening_variation's — the two are provably exclusive."""
    player, _game = _insert_player_and_game(db_session)
    features = _base_features(
        opening_variation_stats=[
            OpeningLineStat(
                color="white",
                eco="B07",
                name="Pirc Defense",
                games=3,
                results=WLD(win=0, loss=3, draw=0),
                avg_opening_eval=-150.0,  # clearly worse out of the book
                low_signal=True,
                evidence=[],
            )
        ],
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "opening_variation" not in keys


def test_opening_variation_does_not_fire_when_loss_share_below_threshold(db_session):
    """Fine line but losing under COACH_OPENING_VARIATION_LOSS -> no fire."""
    player, _game = _insert_player_and_game(db_session)
    features = _base_features(
        opening_variation_stats=[
            OpeningLineStat(
                color="white",
                eco="B07",
                name="Pirc Defense",
                games=3,
                results=WLD(win=2, loss=1, draw=0),
                avg_opening_eval=50.0,
                low_signal=True,
                evidence=[],
            )
        ],
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "opening_variation" not in keys


# ---------------------------------------------------------------------------
# Resourcefulness / missed saves (S29)
# ---------------------------------------------------------------------------

def test_missed_saves_rule_fires_and_renders(db_session):
    player, game = _insert_player_and_game(db_session)
    blunder_row = _insert_row(db_session, game, ply=1, classification="blunder", cp_loss=300)

    features = _base_features(
        resourcefulness=0.25,
        resource_trouble_games=4,
        resource_comebacks=1,
        missed_save_evidence=[(str(game.id), blunder_row.ply)],
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "missed_saves" in keys
    missed = next(i for i in report.issues if i.key == "missed_saves")
    assert _has_digit(missed.diagnosis)
    assert _has_digit(missed.success_metric)
    assert missed.counter_evidence
    assert len(missed.evidence) == 1


def test_comeback_strength_surfaces_when_resourceful(db_session):
    player, _game = _insert_player_and_game(db_session)
    features = _base_features(
        resourcefulness=0.50,
        resource_trouble_games=4,
        resource_comebacks=2,
    )

    report = build_report(features, db_session, player)
    assert len(report.strengths) == 1
    assert "fought back" in report.strengths[0].detail.lower()
    assert "missed_saves" not in [issue.key for issue in report.issues]


def test_missed_saves_does_not_fire_below_min_games(db_session):
    player, _game = _insert_player_and_game(db_session)
    features = _base_features(
        resourcefulness=0.25,
        resource_trouble_games=3,  # below FEATURE_RESOURCE_MIN_GAMES (4)
        resource_comebacks=0,
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "missed_saves" not in keys


def test_opening_general_fires_when_no_single_family_leak_but_general_leak(db_session):
    player, game = _insert_player_and_game(db_session)
    opening_row = _insert_row(db_session, game, ply=20, classification="ok")

    features = _base_features(
        opening_leak_rate=0.40,
        opening_leak_evidence=[(str(game.id), opening_row.ply)],
        detectors={
            "hung_pieces": {"fired": False, "stats": {}, "evidence": []},
            "late_collapse": {"fired": False, "stats": {}, "evidence": []},
            "opening_leak": {"fired": False, "stats": {}, "evidence": []},
            "overextension": {"fired": False, "stats": {}, "evidence": []},
            "time_class_split": {"fired": False, "stats": {}, "evidence": []},
            "turning_point": {"fired": False, "stats": {"ponr_by_game": {}}, "evidence": []},
            "rushed_blunders": {"fired": False, "stats": {}, "evidence": []},
            "time_trouble_collapse": {"fired": False, "stats": {}, "evidence": []},
            "dawdling": {"fired": False, "stats": {}, "evidence": []},
        },
    )

    report = build_report(features, db_session, player)
    keys = [issue.key for issue in report.issues]
    assert "opening_general" in keys
