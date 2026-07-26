"""Session 14 offline tests for app/playstyle.py — pure computation over
hand-built Game + MoveEval rows in the in-memory test database (no engine,
no network).

The playstyle index is a weighted combination of five normalized components
(Appendix 5). Tests here cover the normalization helper (including the
inverted game_length bounds), each component function, and end-to-end
compute_playstyle over synthetic game sets that are deliberately tactical,
positional, or balanced.
"""

import datetime as dt
import math
import uuid

import chess
import pytest
from sqlalchemy.orm import Session

from app.models import Game, MoveEval, Player
from app.playstyle import (
    Playstyle,
    _capture_density,
    _eval_volatility,
    _game_length,
    _normalize,
    _opposite_castling,
    _queen_keep,
    compute_playstyle,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _base_time() -> dt.datetime:
    return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def _insert_player(db_session: Session, username: str = "tester") -> Player:
    player = Player(platform="chesscom", username=username)
    db_session.add(player)
    db_session.commit()
    return player


def _insert_game(
    db_session: Session,
    player: Player,
    *,
    color: str = "white",
    played_at: dt.datetime | None = None,
) -> Game:
    game = Game(
        player_id=player.id,
        platform_game_id=str(uuid.uuid4()),
        game_url="https://example.com/g",
        pgn="1. e4 e5",
        time_class="blitz",
        player_color=color,
        result="win",
        played_at=played_at,
        analyzed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(game)
    db_session.commit()
    return game


def _make_rows(game: Game, specs: list[dict]) -> list[MoveEval]:
    """Build MoveEval rows directly so every field (move_san, fen_before,
    eval_cp_after) is under test control."""
    rows = []
    for spec in specs:
        rows.append(
            MoveEval(
                game_id=game.id,
                ply=spec["ply"],
                move_san=spec.get("move_san", "e4"),
                fen_before=spec.get("fen_before", chess.STARTING_FEN),
                eval_cp_before=spec.get("eval_cp_before", 0),
                eval_cp_after=spec.get("eval_cp_after", 0),
                cp_loss=spec.get("cp_loss", 0),
                best_move_san=spec.get("best_move_san", "e4"),
                classification=spec.get("classification", "ok"),
                phase=spec.get("phase", "middlegame"),
            )
        )
    return rows


def _evals_for(db_session: Session, *games: Game) -> dict[str, list[MoveEval]]:
    return {str(g.id): db_session.query(MoveEval).filter_by(game_id=g.id).all() for g in games}


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_maps_standard_bounds():
    # capture_density bounds: 0.15 -> -1, 0.40 -> +1, midpoint 0.275 -> 0
    assert _normalize(0.15, 0.15, 0.40) == pytest.approx(-1.0)
    assert _normalize(0.40, 0.15, 0.40) == pytest.approx(1.0)
    assert _normalize(0.275, 0.15, 0.40) == pytest.approx(0.0, abs=1e-9)


def test_normalize_clamps_outside_bounds():
    assert _normalize(0.0, 0.15, 0.40) == pytest.approx(-1.0)
    assert _normalize(1.0, 0.15, 0.40) == pytest.approx(1.0)


def test_normalize_handles_inverted_game_length_bounds():
    # 90 plies (lo) -> -1 (positional), 40 plies (hi) -> +1 (tactical),
    # 65 plies -> ~0.
    assert _normalize(90, 90, 40) == pytest.approx(-1.0)
    assert _normalize(40, 90, 40) == pytest.approx(1.0)
    assert _normalize(65, 90, 40) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Component: capture_density
# ---------------------------------------------------------------------------


def test_capture_density_counts_only_player_moves(db_session):
    player = _insert_player(db_session, "capture")
    game = _insert_game(db_session, player)
    # White player on odd plies: 1, 3, 5. Only ply 3 is a capture.
    rows = _make_rows(
        game,
        [
            {"ply": 1, "move_san": "e4"},
            {"ply": 2, "move_san": "e5"},
            {"ply": 3, "move_san": "Nxc3"},
            {"ply": 4, "move_san": "Bb4"},
            {"ply": 5, "move_san": "d4"},
        ],
    )
    db_session.add_all(rows)
    db_session.commit()
    density = _capture_density([game], _evals_for(db_session, game))
    assert density == pytest.approx(1 / 3, abs=1e-9)


def test_capture_density_returns_zero_when_no_player_moves(db_session):
    player = _insert_player(db_session, "empty")
    game = _insert_game(db_session, player)
    assert _capture_density([game], _evals_for(db_session, game)) == 0.0


# ---------------------------------------------------------------------------
# Component: game_length
# ---------------------------------------------------------------------------


def test_game_length_mean_plies_per_game(db_session):
    player = _insert_player(db_session, "glen")
    g1 = _insert_game(db_session, player, played_at=_base_time())
    g2 = _insert_game(db_session, player, played_at=_base_time() + dt.timedelta(minutes=1))
    db_session.add_all(_make_rows(g1, [{"ply": i} for i in range(1, 11)]))
    db_session.add_all(_make_rows(g2, [{"ply": i} for i in range(1, 31)]))
    db_session.commit()
    assert _game_length([g1, g2], _evals_for(db_session, g1, g2)) == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Component: eval_volatility
# ---------------------------------------------------------------------------


def test_eval_volatility_is_population_stddev_of_player_pov_eval(db_session):
    """White-POV eval after each move; for a black player the POV is flipped."""
    player = _insert_player(db_session, "vol")
    wg = _insert_game(db_session, player, color="white", played_at=_base_time())
    bg = _insert_game(db_session, player, color="black", played_at=_base_time() + dt.timedelta(minutes=1))

    db_session.add_all(
        _make_rows(
            wg,
            [
                {"ply": 1, "eval_cp_after": 60},
                {"ply": 2, "eval_cp_after": 50},
                {"ply": 3, "eval_cp_after": 40},
            ],
        )
    )
    # Black POV flips sign: 60 -> -60, -50 -> 50, -40 -> 40.
    db_session.add_all(
        _make_rows(
            bg,
            [
                {"ply": 1, "eval_cp_after": 60},
                {"ply": 2, "eval_cp_after": -50},
                {"ply": 3, "eval_cp_after": -40},
            ],
        )
    )
    db_session.commit()

    vol = _eval_volatility([wg, bg], _evals_for(db_session, wg, bg))
    # combined values: [60, 50, 40, -60, 50, 40]
    values = [60, 50, 40, -60, 50, 40]
    mean = sum(values) / len(values)
    expected = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    assert vol == pytest.approx(expected, abs=1e-6)


def test_eval_volatility_returns_zero_below_two_points(db_session):
    player = _insert_player(db_session, "vol_lo")
    game = _insert_game(db_session, player)
    db_session.add_all(_make_rows(game, [{"ply": 1, "eval_cp_after": 100}]))
    db_session.commit()
    assert _eval_volatility([game], _evals_for(db_session, game)) == 0.0


# ---------------------------------------------------------------------------
# Component: opposite_castling
# ---------------------------------------------------------------------------


def test_opposite_castling_only_counts_both_sides_castled_opposite_wings(db_session):
    player = _insert_player(db_session, "castle_pos")
    game = _insert_game(db_session, player)
    db_session.add_all(
        _make_rows(
            game,
            [
                {"ply": 5, "move_san": "O-O"},
                {"ply": 6, "move_san": "O-O-O"},
            ],
        )
    )
    db_session.commit()
    assert _opposite_castling([game], _evals_for(db_session, game)) == pytest.approx(1.0)


def test_opposite_castling_does_not_count_same_wing(db_session):
    player = _insert_player(db_session, "castle_neg")
    game = _insert_game(db_session, player)
    db_session.add_all(
        _make_rows(
            game,
            [
                {"ply": 5, "move_san": "O-O"},
                {"ply": 6, "move_san": "O-O"},
            ],
        )
    )
    db_session.commit()
    assert _opposite_castling([game], _evals_for(db_session, game)) == pytest.approx(0.0)


def test_opposite_castling_does_not_count_when_one_side_did_not_castle(db_session):
    player = _insert_player(db_session, "castle_none")
    game = _insert_game(db_session, player)
    db_session.add_all(
        _make_rows(
            game,
            [
                {"ply": 5, "move_san": "O-O"},
                {"ply": 6, "move_san": "e5"},
            ],
        )
    )
    db_session.commit()
    assert _opposite_castling([game], _evals_for(db_session, game)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Component: queen_keep
# ---------------------------------------------------------------------------


def test_queen_keep_counts_games_with_queen_past_ply_30(db_session):
    player = _insert_player(db_session, "queen_pos")
    game = _insert_game(db_session, player)
    db_session.add_all(
        _make_rows(
            game,
            [
                {"ply": 31, "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"},
            ],
        )
    )
    db_session.commit()
    assert _queen_keep([game], _evals_for(db_session, game)) == pytest.approx(1.0)


def test_queen_keep_zero_when_game_ended_by_ply_30(db_session):
    player = _insert_player(db_session, "queen_neg")
    game = _insert_game(db_session, player)
    db_session.add_all(_make_rows(game, [{"ply": 30}]))
    db_session.commit()
    assert _queen_keep([game], _evals_for(db_session, game)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# End-to-end: compute_playstyle bands
# ---------------------------------------------------------------------------


def test_compute_playstyle_is_tactical_for_capture_heavy_short_swingy_games(db_session):
    games = []
    for i in range(5):
        g = _make_tactical_game(db_session, i)
        games.append(g)
    result = compute_playstyle(games, _evals_for(db_session, *games))
    assert result.label == "tactical"
    assert result.score >= 0.25


def test_compute_playstyle_is_positional_for_long_quiet_queenless_games(db_session):
    games = []
    for i in range(5):
        g = _make_positional_game(db_session, i)
        games.append(g)
    result = compute_playstyle(games, _evals_for(db_session, *games))
    assert result.label == "positional"
    assert result.score <= -0.25


def test_compute_playstyle_is_balanced_for_mixed_profile(db_session):
    # Five balanced games with raw metrics deliberately near each mid-point.
    games = [_make_balanced_game(db_session, i) for i in range(5)]
    result = compute_playstyle(games, _evals_for(db_session, *games))
    assert result.label == "balanced"
    assert -0.25 < result.score < 0.25


def test_compute_playstyle_empty_input_returns_balanced():
    result = compute_playstyle([], {})
    assert isinstance(result, Playstyle)
    assert result.label == "balanced"
    assert result.score == 0.0
    assert all(v == 0.0 for v in result.components.values())


def test_compute_playstyle_explanation_cites_top_two_components(db_session):
    g = _make_tactical_game(db_session, 0)
    result = compute_playstyle([g], _evals_for(db_session, g))

    # The tactical game should be driven by opposite-side castling plus one
    # other highly tactical component. The explanation uses the human-readable
    # component sentences, not the raw component names.
    assert "you castle opposite sides" in result.explanation
    assert (
        "evals swing" in result.explanation
        or "queens stay" in result.explanation
        or "pieces on" in result.explanation
    )


def test_build_explanation_selects_top_two_components():
    """Direct unit test of the explanation builder: it picks the two components
    with the largest |normalized| values and uses their raw numbers."""
    from app.playstyle import _build_explanation

    raw = {
        "capture_density": 0.39,
        "game_length": 45.0,
        "eval_volatility": 250.0,
        "opposite_castling": 1.0,
        "queen_keep": 1.0,
    }
    normalized = {
        "capture_density": 0.9,
        "game_length": 0.8,
        "eval_volatility": 1.0,
        "opposite_castling": 1.0,
        "queen_keep": 1.0,
    }
    explanation = _build_explanation(raw, normalized)
    # opposite_castling and eval_volatility have the largest |normalized|.
    assert "you castle opposite sides in 100% of games" in explanation
    assert "your evals swing by about 250 centipawns" in explanation


# ---------------------------------------------------------------------------
# Synthetic game builders
# ---------------------------------------------------------------------------


def _make_tactical_game(db_session: Session, i: int) -> Game:
    """Short, capture-heavy, swingy, opposite-wing castling, queen kept —
    designed to push every component toward the tactical end."""
    player = _insert_player(db_session, f"tactical_{i}")
    game = _insert_game(db_session, player, played_at=_base_time() + dt.timedelta(minutes=i))
    rows = []
    # 45 plies, player moves are odd plies -> 23 player moves.
    capture_plies = {3, 7, 11, 15, 19, 23, 27, 31, 35}
    for ply in range(1, 46):
        if ply in capture_plies:
            move = "Bxc7"
        elif ply == 5:
            move = "O-O"
        elif ply == 6:
            move = "O-O-O"
        else:
            move = "Qh4"
        # High volatility: 250/-250 alternating.
        rows.append(
            {
                "ply": ply,
                "move_san": move,
                "eval_cp_after": 250 if ply % 2 == 1 else -250,
            }
        )
    # Ensure queen is on the board at the ply-30 boundary.
    rows[30] = {
        "ply": 31,
        "move_san": rows[30]["move_san"],
        "eval_cp_after": rows[30]["eval_cp_after"],
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    }
    db_session.add_all(_make_rows(game, rows))
    db_session.commit()
    return game


def _make_positional_game(db_session: Session, i: int) -> Game:
    """Long, quiet, no captures, same-side castling, queen gone past ply 30 —
    designed to push every component toward the positional end."""
    player = _insert_player(db_session, f"positional_{i}")
    game = _insert_game(db_session, player, played_at=_base_time() + dt.timedelta(minutes=i))
    rows = []
    # 95 plies: long games -> positional.
    for ply in range(1, 96):
        if ply == 5 or ply == 6:
            move = "O-O"
        else:
            move = "e4" if ply % 2 == 1 else "e5"
        # Low volatility: small eval values.
        rows.append(
            {
                "ply": ply,
                "move_san": move,
                "eval_cp_after": 5 if ply % 2 == 1 else 2,
            }
        )
    # No queen past ply 30.
    rows[30] = {
        "ply": 31,
        "move_san": rows[30]["move_san"],
        "eval_cp_after": rows[30]["eval_cp_after"],
        "fen_before": "rnbk1bnr/pppppppp/8/8/8/8/PPPPPPPP/RNBK1BNR w - - 0 1",
    }
    db_session.add_all(_make_rows(game, rows))
    db_session.commit()
    return game


def _make_balanced_game(db_session: Session, i: int) -> Game:
    """Raw metrics deliberately near the center of each component range:
    65 plies (midpoint), ~27% captures, ~155 cp volatility, same-side castling,
    queens kept on — balanced overall because opposite_castling and queen_keep
    pull in opposite directions.
    """
    player = _insert_player(db_session, f"balanced_{i}")
    game = _insert_game(db_session, player, played_at=_base_time() + dt.timedelta(minutes=i))
    rows = []
    # 65 plies -> game_length midpoint.
    # 9 capture plies among the 33 odd plies -> density ~0.273.
    capture_plies = {7, 13, 19, 25, 31, 37, 43, 49, 55}
    for ply in range(1, 66):
        if ply == 5 or ply == 6:
            move = "O-O"
        elif ply in capture_plies:
            move = "Bxc7"
        else:
            move = "e4" if ply % 2 == 1 else "e5"
        # Volatility near 155: values around +155 and -155.
        rows.append(
            {
                "ply": ply,
                "move_san": move,
                "eval_cp_after": 155 if ply % 2 == 1 else -155,
            }
        )
    # Queen on board at ply-30 boundary for all balanced games.
    rows[30] = {
        "ply": 31,
        "move_san": rows[30]["move_san"],
        "eval_cp_after": rows[30]["eval_cp_after"],
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    }
    db_session.add_all(_make_rows(game, rows))
    db_session.commit()
    return game
